
from transformers import AutoModelForCausalLM, AutoTokenizer
from deep_translator import GoogleTranslator
import torch

def test():
    names = ["Yanta", "Changyanbao", "Ziyou"]
    
    # 1. Google Translate
    print("--- Google Translate ---")
    try:
        g = GoogleTranslator(source='auto', target='zh-CN')
        for n in names:
            print(f"'{n}' -> '{g.translate(n)}'")
    except Exception as e:
        print(f"Google Error: {e}")

    # 2. Qwen 0.5B
    print("\n--- Qwen 0.5B ---")
    try:
        model_name = "Qwen/Qwen2.5-0.5B-Instruct"
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading {model_name} on {device}...")
        
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(model_name, device_map=device, torch_dtype="auto")
        
        prompt_template = "Translate the following place name from Pinyin/English to Simplified Chinese. Name: {name}\nTranslation:"
        
        for n in names:
            # Try a few prompt variations if needed, but start simple
            messages = [
                {"role": "system", "content": "You are a helpful assistant. Translate the English/Pinyin place name to Simplified Chinese. output ONLY the Chinese name."},
                {"role": "user", "content": n}
            ]
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer([text], return_tensors="pt").to(device)
            
            outputs = model.generate(inputs.input_ids, max_new_tokens=50, do_sample=False)
            generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(inputs.input_ids, outputs)]
            response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            print(f"'{n}' -> '{response.strip()}'")
            
    except Exception as e:
        print(f"Qwen Error: {e}")

if __name__ == "__main__":
    test()
