from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import os

import logging
logger = logging.getLogger(__name__)

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
            cls._device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"[LocalTranslator] Initialized singleton. Device: {cls._device}. Module: {cls.__module__}, ID: {id(cls)}, PID: {os.getpid()}")
        return cls._instance

    def _ensure_small_model(self):
        if self._model_small is not None:
            return

        logger.info("[LocalTranslator] Lazy loading 0.5B model...")
        try:
            model_name_small = "Qwen/Qwen2.5-0.5B-Instruct"
            self._tokenizer_small = AutoTokenizer.from_pretrained(model_name_small)
            self._model_small = AutoModelForCausalLM.from_pretrained(
                model_name_small, 
                device_map=self._device, 
                torch_dtype="auto"
            )
            logger.info("[LocalTranslator] 0.5B Model loaded.")
        except Exception as e:
            logger.error(f"[LocalTranslator] Failed to load 0.5B model: {e}")

    def _ensure_large_model(self):
        if self._model_large is not None:
            return
            
        logger.info("[LocalTranslator] Lazy loading 7B model for high-quality translation...")
        try:
            model_name_large = "Qwen/Qwen2.5-7B-Instruct"
            self._tokenizer_large = AutoTokenizer.from_pretrained(model_name_large)
            self._model_large = AutoModelForCausalLM.from_pretrained(
                model_name_large,
                device_map=self._device,
                torch_dtype="auto"
            )
            logger.info("[LocalTranslator] 7B Model loaded.")
        except Exception as e:
            logger.error(f"[LocalTranslator] Failed to load 7B model: {e}")

    def _generate(self, model, tokenizer, prompt, target_lang="Simplified Chinese", max_tokens=512):
        try:
            messages = [
                {"role": "system", "content": f"You are a professional translator. Translate the following text to {target_lang}. Return ONLY the translation."},
                {"role": "user", "content": prompt}
            ]
            text_input = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer([text_input], return_tensors="pt").to(model.device)
            
            outputs = model.generate(inputs.input_ids, max_new_tokens=max_tokens, do_sample=False)
            generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(inputs.input_ids, outputs, strict=False)]
            return tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
        except Exception as e:
            logger.error(f"[LocalTranslator] Generation error: {e}")
            return prompt

    def translate(self, text: str, target_lang: str = "Simplified Chinese") -> str:
        """
        Default translation using 0.5B model.
        """
        self._ensure_small_model()
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
                {"role": "system", "content": "You are a geographic expert. Translate the place name from Pinyin/English to Simplified Chinese. \n"
                                             "RULES:\n"
                                             "1. Output ONLY the Chinese name.\n"
                                             "2. If it is a district or city, include the common Chinese name (e.g. 'Yanta' -> '雁塔区').\n"
                                             "3. If you are unsure about the location, just translate the name literally. DO NOT guess the province if not provided in input.\n"
                                             "4. Example: 'Baiyanggou' -> '白杨沟', 'Changyanbao' -> '长延堡'."},
                {"role": "user", "content": text}
            ]
            text_input = self._tokenizer_large.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = self._tokenizer_large([text_input], return_tensors="pt").to(self._model_large.device)
            
            outputs = self._model_large.generate(inputs.input_ids, max_new_tokens=50, do_sample=False)
            generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(inputs.input_ids, outputs, strict=False)]
            raw_output = self._tokenizer_large.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
            
            # --- Post-Processing / Cleaning ---
            import re
            cleaned = raw_output
            
            # 1. Remove parenthetical notes like （注：...） or (Note: ...)
            cleaned = re.sub(r'（.*?）', '', cleaned)
            cleaned = re.sub(r'\(.*?\)', '', cleaned)
            
            # 2. Remove "Translation:" prefixes
            cleaned = re.sub(r'^(Translation|Translate|Target|Chinese):?\s*', '', cleaned, flags=re.IGNORECASE)
            
            # 3. Remove artifacts like _tolerance_
            cleaned = cleaned.replace("_tolerance_", "").replace("_", "").strip()
            
            # --- NEW: Check for refusal ---
            refusal_keywords = [
                "I cannot", "I can't", "apologize", "I am sorry", "I'm sorry", 
                "provide the translation", "content policy", "violate",
                "对不起", "不能提供", "无法提供", "语言模型", "Policy",
                "AI language model", "unable to translate", "cannot translate",
                "generate content", "inappropriate", "harmful"
            ]
            
            # If refusal detected, fallback to original text or empty?
            # Usually strict location translation should return the input or attempt fallback.
            # Returning input is safer than a long refusal.
            for kw in refusal_keywords:
                if kw.lower() in cleaned.lower():
                    logger.info(f"[LocalTranslator] Refusal detected for '{text}': {cleaned}")
                    return text # Fallback to original
            
            # 4. If result still contains extensive non-Chinese characters, try to extract just the Chinese part
            # Matches continuous block of Chinese characters
            chinese_match = re.search(r'[\u4e00-\u9fa5]+', cleaned)
            if chinese_match:
                # If the extracted Chinese is a significant part (or the only part), use it.
                # But sometimes "City" suffix might be English. 
                # Let's simple take the first Chinese block if the string is messy.
                if len(cleaned) > len(chinese_match.group()) + 5: # If lots of other noise
                     cleaned = chinese_match.group()
            
            return cleaned.strip()

        except Exception as e:
            logger.error(f"[LocalTranslator] 7B Translation error: {e}")
            return text

# Global instance placeholder
_translator_instance = None

def get_translator():
    global _translator_instance
    if _translator_instance is None:
        _translator_instance = LocalTranslator()
    return _translator_instance
