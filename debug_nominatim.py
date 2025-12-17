
from geopy.geocoders import Nominatim
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

def test():
    # Coords for Yanta/Changyanbao area (approx from previous logs)
    lat, lon = 34.204333, 108.956008
    
    print("--- Nominatim (Online) ---")
    try:
        geolocator = Nominatim(user_agent="my_vision_app")
        location = geolocator.reverse((lat, lon), language='zh-CN')
        print(f"Address: {location.address}")
        print(f"Raw: {location.raw}")
    except Exception as e:
        print(f"Nominatim Error: {e}")

    print("\n--- Qwen 0.5B with Context ---")
    try:
        model_name = "Qwen/Qwen2.5-0.5B-Instruct"
        device = "cuda" if torch.cuda.is_available() else "cpu"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(model_name, device_map=device, torch_dtype="auto")
        
        # Test Case: Yanta, Shaanxi
        name = "Yanta"
        province = "Shaanxi"
        
        prompt = f"Translate the place name '{name}' (located in {province}) to Simplified Chinese. Output ONLY the Chinese name."
        
        messages = [
            {"role": "system", "content": "You are a professional translator."},
            {"role": "user", "content": prompt}
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer([text], return_tensors="pt").to(device)
        
        outputs = model.generate(inputs.input_ids, max_new_tokens=50, do_sample=False)
        response = tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
        # Cleanup
        response = response.split("assistant")[-1].strip()
        print(f"'{name}' (in {province}) -> '{response}'")

    except Exception as e:
        print(f"Qwen Error: {e}")

if __name__ == "__main__":
    test()
