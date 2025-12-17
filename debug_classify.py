
from transformers import AutoModel, AutoProcessor
from PIL import Image
import torch
import os

# Hardcoded paths from previous step
samples = {
    "IMG_7220 (Food/Paper)": r"E:\本地照片\赵挺的手机照片\位置测试\IMG_7220.JPEG",
    "IMG_6710 (Kid)": r"E:\本地照片\赵挺的手机照片\位置测试\IMG_6710.JPG"
}

def load_model():
    print("Loading SigLIP...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = AutoModel.from_pretrained('google/siglip-so400m-patch14-384').to(device)
    processor = AutoProcessor.from_pretrained('google/siglip-so400m-patch14-384')
    return model, processor, device

def test_prompts(model, processor, device):
    # Prompt Sets to Test
    prompt_sets = {
        "Set B (Explicit)": [
             "a photo of a person, animal, food, object, or scene",
             "a digital screen capture or interface",
             "a document consisting primarily of text, like a letter, receipt, or book page"
        ],
        "Set E (Dense Text)": [
            "a photo of a person, child, animal, food, object, or scene",
            "a digital screenshot",
            "a close-up document or page containing a large amount of dense text"
        ]
    }
    
    for name, path in samples.items():
        if not os.path.exists(path):
            continue
            
        print(f"\nAnalyzing: {name}")
        image = Image.open(path).convert("RGB")
        
        for p_name, prompts in prompt_sets.items():
            inputs = processor(
                text=prompts, 
                images=image, 
                return_tensors="pt", 
                padding=True
            ).to(device)
            
            with torch.no_grad():
                outputs = model(**inputs)
                logits_per_image = outputs.logits_per_image
                probs = logits_per_image.softmax(dim=1).cpu().tolist()[0]
                
            print(f"  [{p_name}]")
            labels = ["Photo", "Screenshot", "Document"]
            
            # Find winner
            max_p = max(probs)
            winner_idx = probs.index(max_p)
            print(f"    WINNER: {labels[winner_idx]} ({max_p:.4f})")
            print(f"    - Photo: {probs[0]:.4f}")
            print(f"    - Screen: {probs[1]:.4f}")
            print(f"    - Doc: {probs[2]:.4f}")

if __name__ == "__main__":
    m, p, d = load_model()
    test_prompts(m, p, d)
