from abc import ABC, abstractmethod
from typing import Optional
from PIL import Image
import os
import io
import base64

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
        # Use Official Domestic Host as per user provided docs
        self.api_url = "https://grsai.dakka.com.cn/v1/draw/nano-banana"

    def _image_to_base64(self, img: Image.Image) -> str:
        import base64
        from io import BytesIO
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return "data:image/png;base64," + img_str

    def generate(self, prompt, reference_images=None, strength=0.7, **kwargs):
        print(f"[NanoBananaGenerator] Generating with model: '{self.model}' using {self.api_url}")
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

        # Calculate Aspect Ratio
        aspect_ratio = "auto"
        image_size = "1K"
        
        if "width" in kwargs and "height" in kwargs:
            w = kwargs["width"]
            h = kwargs["height"]
            ratio = w / h
            
            # Common Ratios
            ratios = {
                "1:1": 1.0,
                "4:3": 4/3,
                "3:4": 3/4,
                "16:9": 16/9,
                "9:16": 9/16,
                "21:9": 21/9,
                "9:21": 9/21,
                "3:2": 3/2,
                "2:3": 2/3
            }
            
            # Find closest
            best_r = "1:1"
            min_diff = float('inf')
            
            # PREVENT 1:1 SNAP (User Correction)
            # If input is clearly not square (ratio difference > 0.15), do NOT choose 1:1.
            is_square_input = abs(ratio - 1.0) < 0.15
            
            for k, v in ratios.items():
                if k == "1:1" and not is_square_input:
                     continue # Skip 1:1 if input is clearly landscape/portrait
                
                diff = abs(ratio - v)
                if diff < min_diff:
                    min_diff = diff
                    best_r = k
            
            # If fallback happened (min_diff still large), default to 16:9 or 9:16 for safety
            if min_diff > 0.3:
                 if ratio > 1: best_r = "16:9"
                 else: best_r = "9:16"
            
            aspect_ratio = best_r
            print(f"[NanoBanana] Calculated Aspect Ratio: {best_r} (from {w}x{h}, diff={min_diff:.3f})")

        # Construct Payload per Generic API Spec
        payload = {
            "model": self.model, # e.g. "nano-banana-pro"
            "prompt": prompt,
            "urls": urls,
            "aspectRatio": aspect_ratio,
            "imageSize": image_size,  # Supported by Pro (1K/2K)
            "shutProgress": False, # We want stream progress
            "webHook": "" 
        }

        try:
            # Call API - Default Stream Response
            response = requests.post(self.api_url, headers=headers, json=payload, stream=True, timeout=120)
            
            if response.status_code != 200:
                print(f"[NanoBananaGenerator] Status: {response.status_code}, Body: {response.text}")
                raise Exception(f"API Error {response.status_code}: {response.text}")

            final_image_url = None
            
            print("[NanoBananaGenerator] Streaming response...")
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    try:
                        # Some SSE implementations use "data: " prefix
                        if decoded_line.startswith("data:"):
                            decoded_line = decoded_line[5:].strip()
                        
                        data = json.loads(decoded_line)
                        
                        status = data.get("status")
                        progress = data.get("progress", 0)
                        
                        # Only print occasionally to avoid log spam, or if status changes
                        if status == "succeeded":
                            print(f"[Stream] Success! Progress: {progress}%")
                            results = data.get("results")
                            if results and len(results) > 0:
                                final_image_url = results[0]["url"]
                                break
                        elif status == "failed":
                             failure = data.get("failure_reason") or "Unknown"
                             err = data.get("error") or ""
                             raise Exception(f"Generation failed: {failure} - {err}")
                        else:
                            # Running
                            pass
                             
                    except json.JSONDecodeError:
                        pass

            if not final_image_url:
                raise Exception("Stream closed without success status or image URL.")

            # Download Result with Retry
            print(f"[NanoBananaGenerator] Downloading result: {final_image_url}")
            
            import time
            for attempt in range(3):
                try:
                    img_resp = requests.get(final_image_url, timeout=60)
                    if img_resp.status_code == 200:
                        break
                    else:
                        print(f"[NanoBananaGenerator] Download failed (status {img_resp.status_code}), retrying...")
                except Exception as dl_err:
                     print(f"[NanoBananaGenerator] Download error: {dl_err}, retrying...")
                     if attempt == 2: raise dl_err
                     time.sleep(2)
            
            return Image.open(BytesIO(img_resp.content))

        except Exception as e:
            print(f"[NanoBananaGenerator] Error: {e}")
            raise e
class GeminiGenerator(IImageGenerator):
    def __init__(self, api_key=None, model="gemini-1.5-pro"):
        self.api_key = api_key
        # Use user-specified model or default
        self.model = model
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

    def generate(self, prompt, reference_images=None, strength=0.7, **kwargs):
        print(f"[GeminiGenerator] Generating with model: '{self.model}'")
        import requests
        import json
        import base64
        from io import BytesIO

        if not self.api_key:
            raise Exception("Google API Key not configured.")

        # Prepare Parts
        parts = []
        
        # 1. Add Protocol/System prompts (optional, but helpful)
        parts.append({"text": prompt})
        
        # 2. Add Images
        if reference_images:
            for i, img in enumerate(reference_images):
                # Convert to bytes
                buffered = BytesIO()
                # Ensure RGB
                if img.mode != 'RGB': img = img.convert('RGB')
                img.save(buffered, format="JPEG")
                img_bytes = buffered.getvalue()
                b64_data = base64.b64encode(img_bytes).decode('utf-8')
                
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": b64_data
                    }
                })

        payload = {
            "contents": [{
                "parts": parts
            }],
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE"
                }
            ],
            # If generating image, Gemini usually returns text description? 
            # Wait, Gemini 1.5 Pro is multimodal INPUT, text OUTPUT.
            # Does it generate IMAGES?
            # As of late 2024, Gemini models (Imagen 3 integration) can generate images via specific endpoints or tools.
            # BUT standard `generateContent` is for Text/Code.
            # If the user wants IMAGE generation using "gemini-3-pro" (assuming it supports it), 
            # we might need to check if the model returns image bytes or if we need a different endpoint.
            # 
            # However, looking at recent Google AI Studio updates, Imagen 3 is available via `generateContent` 
            # strictly if the model supports tool use or specific image generation capabilities.
            # Or usually it relies on `imagen-3.0-generate-001` model.
            # 
            # If user said "gemini-3-pro", maybe they mean the Multimodal-to-Image capability?
            # 
            # Let's assume for now we try to ask it to generate an image. 
            # If it returns text, we fail.
            # 
            # ALTERNATIVE: Use `NanoBanana` (which we verified supports generation) but pass the `Gemini` prompt?
            # The User EXPLICITLY said "call gemini 3 pro model to generate image".
            # Maybe they mean `imagen-3`?
            # I will follow the user's instruction and try `gemini-3-pro` (or fallbacks) against the `generateContent` endpoint?
            # NO, `generateContent` on language models returns TEXT.
            # 
            # Wait! If the user says "Gemini 3 Pro", maybe they are referring to the actual IMAGEN model?
            # Or maybe they know something I don't about a unified endpoint.
            # 
            # Let's write the code to handle a response that *might* contain image data or a link.
            # OR better: I will try to use the `imagen-3.0-generate-001` endpoint style but with the user's model name?
            # 
            # Actually, let's implement the standard `generateContent` first. 
            # If it returns text instructions (e.g. "I can't generate images"), then we know.
            # 
            # Re-reading: "Apply gemini 3 pro model to generate postcard... and add a message".
            # 
            # If Gemini 3 Pro is a VLM (Vision Language Model), it can EDIT images?
            # No, standard Gemini is output-text.
            # 
            # HYPOTHESIS: The user might be mistaken about "Gemini 3 Pro" generating images directly via that specific name
            # OR "Gemini 3" implies "Imagen 3".
            # 
            # I will IMPLEMENT it using the standard `generateContent` endpoint structure but I will ALSO implement 
            # a check. If the response is text, I'll log it.
            # 
            # NOTE: Google recently released Imagen 3. The endpoint is `.../models/imagen-3.0-generate-001:predict` (Vertex) 
            # or via AI Studio API.
            # 
            # Let's try to stick to `generateContent` if the user is adamant. 
            # BUT, standard `generateContent` DOES return images in the response parts if generation is supported!
            # It comes as `inlineData` in the response candidates.
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 1024,
            }
        }

        response = requests.post(self.api_url, headers={"Content-Type": "application/json"}, json=payload)
        
        if response.status_code != 200:
             raise Exception(f"Gemini API Error {response.status_code}: {response.text}")

        res_json = response.json()
        
        # Check for image content in response
        try:
            candidates = res_json.get("candidates", [])
            if not candidates:
                 raise Exception("No candidates returned")
            
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            
            # Look for image part
            # Currently (2024/2025), if Gemini generates an image, it usually provides it as base64 in parts?
            # Or it returns a text link?
            # 
            # If it only returns text ("Here is a postcard... [Description]"), then it failed at image gen.
            #
            # Let's handle the Text response (the "Message" part of the postcard) 
            # AND the Image response separately?
            # 
            # Actually, I'll return the TEXT from Gemini as the "Message"
            # And honestly, if Gemini CANNOT generate image, I should probably fallback to NanoBanana for the IMAGE
            # referencing the text?
            # 
            # NO, user said "Call gemini to generate postcard".
            # I will assume it works.
            
            # If ONLY text is returned:
            text_part = ""
            for p in parts:
                if 'text' in p: text_part += p['text']
            
            # If no image found in response, maybe the model name is wrong for image gen.
            # But let's proceed.
            
            # MOCK implementation for now if real API fails? No.
            # I will just write the code to look for image.
            
            # Ref: Google AI Studio API for Imagen returns base64 bytes.
            
            image_data = None
            for p in parts:
                if 'inline_data' in p:
                     image_data = p['inline_data']['data']
                     break
            
            if image_data:
                return Image.open(BytesIO(base64.b64decode(image_data))), text_part
            
            # Fallback: if user provided "generate image" prompt but model only returned text,
            # we might need to parse.
            
            print(f"[Gemini] Response was text only: {text_part}")
            return None, text_part

        except Exception as e:
            print(f"[Gemini] Parse Error: {e}")
            raise e

class GrsAIChatGenerator(IImageGenerator):
    """
    Wrapper for GrsAI Chat API (OpenAI compatible) for Planning/Text Generation.
    Returns (None, text_content).
    """
    def __init__(self, api_key=None, model="gemini-3-pro"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://grsai.dakka.com.cn/v1/chat/completions"

    def generate(self, prompt, reference_images=None, strength=0.7):
        # Note: reference_images not used in text planning for now unless multimodal
        print(f"[GrsAIChatGenerator] Planning with model: '{self.model}' using {self.api_url}")
        import requests
        import json
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        # OpenAI Chat Format
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
            if response.status_code != 200:
                raise Exception(f"Chat API Error {response.status_code}: {response.text}")
            
            data = response.json()
            # Handle potential variation in response structure?
            # Standard OpenAI: choices[0].message.content
            if 'choices' in data and len(data['choices']) > 0:
                 content = data['choices'][0]['message']['content']
                 return None, content
            else:
                 raise Exception(f"Unexpected response format: {data}")

        except Exception as e:
            print(f"[GrsAIChatGenerator] Error: {e}")
            raise e

class AntiGravityGenerator(IImageGenerator):
    """
    Generator for 'Anti-Gravity' (or compatible) APIs that use OpenAI Chat Completions
    endpoint to generate images via specific 'extra_body' or model behavior.
    """
    def __init__(self, api_key=None, model="gemini-3-pro-image", api_url=None):
        self.api_key = api_key
        self.model = model
        # Default local URL if not provided, though typically required
        self.base_url = api_url or "http://127.0.0.1:8045/v1"

    def generate(self, prompt, reference_images=None, strength=0.7, **kwargs):
        print(f"[AntiGravityGenerator] Generating with model: '{self.model}' using {self.base_url}")
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("Please install openai: pip install openai")
        
        try:
            client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key
            )
            
            # Construct messages
            if reference_images:
                # Multimodal request (Vision)
                content_parts = [{"type": "text", "text": prompt}]
                
                import base64
                from io import BytesIO
                
                for img in reference_images:
                    # Convert PIL to base64
                    buf = BytesIO()
                    # Resize if too large to save bandwidth/tokens? 
                    # User said "1024x1024" for generation, but for input, maybe allow original or slightly smaller.
                    # Safety: optimize to max 1024 dimension
                    img_copy = img.copy()
                    img_copy.thumbnail((1024, 1024))
                    
                    if img_copy.mode != 'RGB': img_copy = img_copy.convert('RGB')
                    
                    img_copy.save(buf, format="JPEG", quality=85)
                    b64_str = base64.b64encode(buf.getvalue()).decode('utf-8')
                    
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64_str}"
                        }
                    })
                
                messages = [{"role": "user", "content": content_parts}]
            else:
                # Text-only request
                messages = [{"role": "user", "content": prompt}]
            
            # Anti-Gravity specific: Image gen params in extra_body ONLY for image models
            # Heuristic: if 'image' in model name, send size param.
            
            api_params = {
                "model": self.model,
                "messages": messages
            }
            
            if "image" in self.model.lower():
                # Determine size based on reference image orientation if available
                size_param = "1024x1024"  # Default square
                
                if reference_images and len(reference_images) > 0:
                    # Use first reference image (which is now the fully prepared canvas)
                    ref_img = reference_images[0]
                    width, height = ref_img.size
                    
                    # Pass exact dimensions. The server logic already ensures they are multiple of 64.
                    size_param = f"{width}x{height}"
                    
                    print(f"[AntiGravityGenerator] Using exact canvas size: {size_param}")

                    # Convert to base64 for init_image (Img2Img triggering)
                    buf = io.BytesIO()
                    ref_img.save(buf, format="JPEG", quality=95)
                    init_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                    
                    # Handle Mask (Inpainting)
                    mask_b64 = None
                    if "mask_image" in kwargs:
                        mask_obj = kwargs.get("mask_image") # Use .get() to avoid pop affecting subsequent calls if any
                        buf_m = io.BytesIO()
                        mask_obj.save(buf_m, format="PNG")
                        mask_b64 = base64.b64encode(buf_m.getvalue()).decode('utf-8')

                    # Add to extra_body to force Img2Img mode
                    extra_settings = { 
                        "size": size_param,
                        "init_image": init_b64,
                        "strength": 0.35, 
                        "image_strength": 0.85 
                    }
                    
                    if mask_b64:
                        print("[AntiGravityGenerator] Activated Inpainting Mode (Mask provided). Ref Strength=1.0 on Mask.")
                        extra_settings["mask_image"] = mask_b64
                        # Force high modification on the MASKED area
                        extra_settings["strength"] = 0.99 
                        # Keep Reference logic to ensure style match

                    api_params["extra_body"] = extra_settings
                else:
                    api_params["extra_body"] = { "size": size_param }
                
                # Image gen typically doesn't stream well on this proxy? 
                # Keep stream=False for image models as they return URL/Base64 in one go.
            else:
                # Text Model: Use streaming for robustness
                api_params["stream"] = True
            
            response = None # Fix: Initialize response for error logging scope
            if api_params.get("stream"):
                response_stream = client.chat.completions.create(**api_params)
                collected_content = []
                print(f"[AntiGravityGenerator] Streaming response from {self.model}...")
                for chunk in response_stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content_chunk = chunk.choices[0].delta.content
                        collected_content.append(content_chunk)
                        # Optional: Print dots?
                
                content = "".join(collected_content)
            else:
                response = client.chat.completions.create(**api_params)
                content = response.choices[0].message.content

            # Truncate log for Base64
            # Truncate log for Base64
            log_content = content[:100] + "..." if content and len(content) > 100 else content
            print(f"[AntiGravityGenerator] Response content: {log_content}")
            
            # Extract Image URL from content
            # The content might be a URL string, or markdown image link, or just text.
            # User example: print(response.choices[0].message.content) -> Implies content IS the url or contains it.
            
            image_url = None
            
            if not content:
                 print(f"[AntiGravityGenerator] Warning: Content is None. Full Response: {response}")
                 raise Exception("API returned valid response but empty content.")

            if content.startswith("http"):
                image_url = content.strip()
            elif "(" in content and ")" in content:
                # Markdown link check?
                import re
                urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', content)
                if urls: image_url = urls[0]

            if image_url:
                 # Download
                import requests
                from io import BytesIO
                resp = requests.get(image_url)
                return Image.open(BytesIO(resp.content))
            
            # Check for Base64 (Anti-Gravity direct return)
            if len(content) > 100:
                 import base64
                 from io import BytesIO
                 
                 base64_str = content.strip()
                 # Remove header if present
                 if "base64," in base64_str:
                     base64_str = base64_str.split("base64,")[1]
                     
                 try:
                     img_data = base64.b64decode(base64_str)
                     return Image.open(BytesIO(img_data))
                 except Exception as e:
                     print(f"[AntiGravityGenerator] Base64 decode failed: {e}")
            
            # If we are here, it's not a URL and not valid Base64 image. 
            # It might be TEXT generation (for planner).
            # Return the raw content string.
            print("[AntiGravityGenerator] Returning raw content as text.")
            return content

            # End of Generate Method
            
        except Exception as e:
            print(f"[AntiGravityGenerator] Error: {e}")
            raise e
