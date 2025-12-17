
import os

path = r"d:\project\find\src\api\server.py"
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
    
found = False
for i, line in enumerate(lines):
    if "/files/organize/places" in line or "def get_places" in line:
        print(f"Found at line {i+1}: {line.strip()}")
        found = True

if not found:
    print("Not found!")
