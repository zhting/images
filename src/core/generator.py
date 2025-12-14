from abc import ABC, abstractmethod
from typing import Optional
from PIL import Image
import os

class IImageGenerator(ABC):
    """
    生成服务抽象基类
    """
    @abstractmethod
    def generate(self, 
                 prompt: str, 
                 reference_images: Optional[list[Image.Image]] = None, 
                 strength: float = 0.7) -> Image.Image:
        """
        Args:
            prompt: 用户输入的自然语言描述
            reference_images: (可选) 用户上传的参考图片列表
            strength: (可选) 图生图的重绘幅度，0.0-1.0
        Returns:
            生成的 PIL Image 对象
        """
        pass

class MockGenerator(IImageGenerator):
    def __init__(self, assets_dir="./assets"):
        # We no longer need to create a file on disk
        pass

    def generate(self, prompt, reference_images=None, strength=0.7):
        print(f"[MockGenerator] Generating image for prompt: '{prompt}'")
        # Return an in-memory image
        img = Image.new('RGB', (512, 512), color = (73, 109, 137))
        return img

class OpenAIGenerator(IImageGenerator):
    def __init__(self, api_key=None, model="dall-e-3"):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("Please install openai: pip install openai")
        
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate(self, prompt, reference_images=None, strength=0.7):
        print(f"[OpenAIGenerator] Generating with prompt: '{prompt}'")
        try:
            response = self.client.images.generate(
                model=self.model,
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            image_url = response.data[0].url
            
            # Download image
            import requests
            from io import BytesIO
            resp = requests.get(image_url)
            return Image.open(BytesIO(resp.content))
        except Exception as e:
            print(f"[OpenAIGenerator] Error: {e}")
            raise e

class NanoBananaGenerator(IImageGenerator):
    def __init__(self, api_key=None, model="nano-banana"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.grsai.com/v1/draw/nano-banana" 

    def _image_to_base64(self, img: Image.Image) -> str:
        import base64
        from io import BytesIO
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return "data:image/png;base64," + img_str

    def generate(self, prompt, reference_images=None, strength=0.7):
        print(f"[NanoBananaGenerator] Generating with model: '{self.model}'")
        import requests
        from io import BytesIO
        import json

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # Prepare reference images
        urls = []
        if reference_images:
            for img in reference_images:
                try:
                    urls.append(self._image_to_base64(img))
                except Exception as e:
                    print(f"Failed to convert image to base64: {e}")

        payload = {
            "model": self.model,
            "prompt": prompt,
            "urls": urls,
            "aspectRatio": "auto",
            "imageSize": "1K",  # Default, only for pro but harmless for others?
            "shutProgress": False,
            "webHook": "" # Empty for stream
        }

        try:
            # Stream request
            response = requests.post(self.api_url, headers=headers, json=payload, stream=True, timeout=120)
            
            if response.status_code != 200:
                raise Exception(f"API Error {response.status_code}: {response.text}")

            final_image_url = None
            
            print("[NanoBananaGenerator] Streaming response...")
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    # Stream format: sometimes "data: {...}" or just raw json lines? 
                    # Docs don't specify SSE format explicitly but usually it's line by line JSON
                    # Let's try to parse each line as JSON
                    try:
                        # Some APIs send "data: " prefix
                        if decoded_line.startswith("data:"):
                            decoded_line = decoded_line[5:].strip()
                        
                        data = json.loads(decoded_line)
                        print(f"[Stream] {data.get('status')} - Progress: {data.get('progress')}%")
                        
                        if data.get("status") == "succeeded":
                            results = data.get("results")
                            if results and len(results) > 0:
                                final_image_url = results[0]["url"]
                                break
                        elif data.get("status") == "failed":
                             raise Exception(f"Generation failed: {data.get('failure_reason')} - {data.get('error')}")
                             
                    except json.JSONDecodeError:
                        print(f"Skipping non-json line: {decoded_line}")
                        pass

            if not final_image_url:
                raise Exception("Stream closed without success status or image URL.")

            # Download Result
            print(f"[NanoBananaGenerator] Downloading result: {final_image_url}")
            img_resp = requests.get(final_image_url)
            return Image.open(BytesIO(img_resp.content))

        except Exception as e:
            print(f"[NanoBananaGenerator] Error: {e}")
            raise e
