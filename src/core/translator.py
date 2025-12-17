from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

class LocalTranslator:
    _instance = None
    
    # Small Model (0.5B) - Always loaded
    _model_small = None
    _tokenizer_small = None
    
    # Large Model (7B) - Lazy loaded
    _model_large = None
    _tokenizer_large = None
    
    _device = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LocalTranslator, cls).__new__(cls)
            print("[LocalTranslator] Initializing...")
            try:
                cls._device = "cuda" if torch.cuda.is_available() else "cpu"
                print(f"[LocalTranslator] Device: {cls._device}")
                
                # Load Small Model (0.5B)
                print("[LocalTranslator] Loading 0.5B model...")
                model_name_small = "Qwen/Qwen2.5-0.5B-Instruct"
                cls._tokenizer_small = AutoTokenizer.from_pretrained(model_name_small)
                cls._model_small = AutoModelForCausalLM.from_pretrained(
                    model_name_small, 
                    device_map=cls._device, 
                    torch_dtype="auto"
                )
                print("[LocalTranslator] 0.5B Model loaded.")
                
            except Exception as e:
                print(f"[LocalTranslator] Failed to load 0.5B model: {e}")
                
        return cls._instance

    def _ensure_large_model(self):
        if self._model_large is not None:
            return
            
        print("[LocalTranslator] Lazy loading 7B model for high-quality translation...")
        try:
            model_name_large = "Qwen/Qwen2.5-7B-Instruct"
            self._tokenizer_large = AutoTokenizer.from_pretrained(model_name_large)
            self._model_large = AutoModelForCausalLM.from_pretrained(
                model_name_large,
                device_map=self._device,
                torch_dtype="auto"
            )
            print("[LocalTranslator] 7B Model loaded.")
        except Exception as e:
            print(f"[LocalTranslator] Failed to load 7B model: {e}")

    def _generate(self, model, tokenizer, prompt, target_lang="Simplified Chinese", max_tokens=512):
        try:
            messages = [
                {"role": "system", "content": f"You are a professional translator. Translate the following text to {target_lang}. Return ONLY the translation."},
                {"role": "user", "content": prompt}
            ]
            text_input = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer([text_input], return_tensors="pt").to(model.device)
            
            outputs = model.generate(inputs.input_ids, max_new_tokens=max_tokens, do_sample=False)
            generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(inputs.input_ids, outputs)]
            return tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
        except Exception as e:
            print(f"[LocalTranslator] Generation error: {e}")
            return prompt

    def translate(self, text: str, target_lang: str = "Simplified Chinese") -> str:
        """
        Default translation using 0.5B model.
        """
        if not self._model_small: return text
        return self._generate(self._model_small, self._tokenizer_small, text, target_lang=target_lang)

    def translate_location(self, text: str) -> str:
        """
        High-quality translation using 7B model (lazy load).
        Targeted for Location Names.
        """
        self._ensure_large_model()
        if not self._model_large: 
            # Fallback to small
            return self.translate(text)
            
        # Specific prompt for location
        try:
            messages = [
                {"role": "system", "content": "You are a geographic expert. Translate the place name from Pinyin/English to Simplified Chinese. IMPORTANT: Output ONLY the Chinese name. Example: 'Yanta' -> '雁塔', 'Changyanbao' -> '长延堡'."},
                {"role": "user", "content": text}
            ]
            text_input = self._tokenizer_large.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = self._tokenizer_large([text_input], return_tensors="pt").to(self._model_large.device)
            
            outputs = self._model_large.generate(inputs.input_ids, max_new_tokens=50, do_sample=False)
            generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(inputs.input_ids, outputs)]
            return self._tokenizer_large.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
        except Exception as e:
            print(f"[LocalTranslator] 7B Translation error: {e}")
            return text

# Global instance
translator = LocalTranslator()
