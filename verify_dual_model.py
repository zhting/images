
import sys
import os
import time

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from src.core.translator import translator

def verify():
    print("--- Verifying Dual Model Setup ---")
    
    # 1. Test Small Model (0.5B) - Should be fast/loaded
    start = time.time()
    text_small = "Hello World"
    print(f"\n1. Testing 0.5B Model with '{text_small}'...")
    res_small = translator.translate(text_small)
    print(f"Result (0.5B): {res_small}")
    print(f"Time: {time.time() - start:.2f}s")
    
    # 2. Test Large Model (7B) - Should trigger lazy load
    start = time.time()
    text_large = "Yanta"
    print(f"\n2. Testing 7B Model (Location) with '{text_large}'...")
    print("(This may take time to download/load first time...)")
    res_large = translator.translate_location(text_large)
    print(f"Result (7B): {res_large}")
    print(f"Time: {time.time() - start:.2f}s")
    
    # 3. Test Mixed Use
    print(f"\n3. Testing Mixed Use...")
    print(f"Small: {translator.translate('Apple')}")
    print(f"Large: {translator.translate_location('Changyanbao')}")

if __name__ == "__main__":
    verify()
