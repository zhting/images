import sys
import os
from deep_translator import GoogleTranslator

def verify():
    print("Testing En->Zh translation (Online/Google)...")
    
    samples = [
        "New York",
        "Paris",
        "Tokyo",
        "San Francisco"
    ]
    
    translator = GoogleTranslator(source='auto', target='zh-CN')

    for s in samples:
        print(f"Original: {s}")
        try:
            translated = translator.translate(s)
            print(f"Translated: {translated}")
        except Exception as e:
            print(f"Error: {e}")
        
    print("Test complete.")

if __name__ == "__main__":
    verify()
