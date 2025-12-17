
import os
import time

def list_files():
    target_dir = r"E:\本地照片\赵挺的手机照片\12-17"
    if not os.path.exists(target_dir):
        print(f"Directory not found: {target_dir}")
        return

    print(f"Listing files in {target_dir}...")
    count = 0
    for root, dirs, files in os.walk(target_dir):
        for f in files:
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                count += 1
                full = os.path.join(root, f)
                mtime = os.path.getmtime(full)
                # Print first 5 only
                if count <= 5:
                    print(f"- {f} (mtime: {mtime})")
    
    print(f"Total images found: {count}")

if __name__ == "__main__":
    list_files()
