
from deep_translator import GoogleTranslator

def test():
    trans = GoogleTranslator(source='auto', target='zh-CN')
    
    # Test Cases
    inputs = [
        "Yanta",
        "Yanta, Shaanxi",
        "Yanta, Xi'an, Shaanxi, China",
        "Changyanbao",
        "Changyanbao, Shaanxi",
        "Changyanbao, Xi'an, Shaanxi"
    ]
    
    print("--- Google Translate Context Test ---")
    for i in inputs:
        try:
            res = trans.translate(i)
            print(f"'{i}' -> '{res}'")
        except Exception as e:
            print(f"Error '{i}': {e}")

if __name__ == "__main__":
    test()
