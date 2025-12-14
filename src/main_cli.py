import argparse
import os
import sys
from PIL import Image

# Ensure src is in python path if running from outside
# If running as `python src/main_cli.py`, sys.path[0] is src/
# If running `python -m src.main_cli`, we need careful handling
# But for now let's just ensure we rely on standard imports relative to src
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from core.models import VisionModel
from core.generator import MockGenerator, OpenAIGenerator
from database.vector_db import VectorDB
from database.sqlite_store import SQLiteStore
import uuid

def cmd_index(args):
    print(f"Initializing VectorDB at {args.db_path}...")
    db = VectorDB(db_path=args.db_path)
    db.create_collection_with_schema()
    
    print("Loading Vision Model...")
    model = VisionModel()
    
    # Simple recursive scan
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
    count = 0
    
    print(f"Scanning directory: {args.target_dir}...")
    for root, _, files in os.walk(args.target_dir):
        for file in files:
            if os.path.splitext(file)[1].lower() in image_extensions:
                file_path = os.path.join(root, file)
                try:
                    img = Image.open(file_path).convert('RGB')
                    vector = model.encode(img)
                    
                    # Dummy values for hash/modified
                    file_hash = "hash_placeholder" 
                    last_modified = int(os.path.getmtime(file_path))
                    
                    db.insert(vector, file_path, file_hash, last_modified)
                    print(f"Indexed: {file_path}")
                    count += 1
                except Exception as e:
                    print(f"Failed to index {file_path}: {e}")
    print(f"Indexing complete. Total images: {count}")


def cmd_search(args):
    # 0. Setup DB
    history_db = SQLiteStore()

    # 1. Generate Proxy Image
    if args.provider == 'openai':
        generator = OpenAIGenerator() # Expects env var
    else:
        generator = MockGenerator()
        
    print(f"Generating proxy image for prompt: '{args.query}'...")
    try:
        proxy_img = generator.generate(args.query)
    except Exception as e:
        print(f"Generation failed: {e}")
        return

    # Save to history
    gen_id = str(uuid.uuid4())
    # Save image to temp file for record? Or just path
    # For now, let's save the proxy image to a specific history folder
    history_dir = "./history_images"
    if not os.path.exists(history_dir):
        os.makedirs(history_dir)
    image_filename = f"{gen_id}.png"
    image_path = os.path.join(history_dir, image_filename)
    proxy_img.save(image_path)
    
    history_db.add_record(gen_id, args.query, image_path, api_provider=args.provider)
    print(f"Generation recorded: {gen_id}")
    
    # 2. Encode Proxy Image
    
    # Save proxy for debug
    # proxy_path = "proxy_debug.jpg"
    # proxy_img.save(proxy_path)
    # print(f"Proxy image saved to {proxy_path}")
    
    # 2. Encode Proxy Image
    print("Loading Vision Model...")
    model = VisionModel()
    query_vector = model.encode(proxy_img)
    
    # 3. Search in DB
    db = VectorDB(db_path=args.db_path)
    print("Searching in database...")
    results = db.search(query_vector, top_k=5)
    
    print("\n--- Search Results ---")
    if not results or len(results) == 0:
         print("No results found.")
    else:
        for hits in results:
            for hit in hits:
                # Milvus Lite search results structure might vary slightly by version, 
                # but usually hit is object with .entity or dict access
                # Let's try to access as dict if possible or attribute
                path = hit.get('entity', {}).get('file_path') if isinstance(hit, dict) else getattr(hit, 'entity', {}).get('file_path')
                score = hit.get('distance') if isinstance(hit, dict) else getattr(hit, 'distance', 0.0)
                
                # If pymilvus returns objects
                if path is None:
                     # Fallback for some return formats
                     path = hit.id 
                     # Wait, we requested output_fields=['file_path']
                     # In some versions, hit.file_path works or hit['file_path']
                     pass
                
                print(f"Result: {hit}") # Print full hit for debug if specific field extraction fails
                # Ideally:
                # print(f"Path: {path} (Score: {score:.4f})")

def main():
    parser = argparse.ArgumentParser(description="Local Generative Visual Retrieval System CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Index Command
    index_parser = subparsers.add_parser("index", help="Index images in a directory")
    index_parser.add_argument("target_dir", help="Directory to scan")
    index_parser.add_argument("--db-path", default="./search.db", help="Path to Milvus Lite DB")
    
    # Search Command
    search_parser = subparsers.add_parser("search", help="Search using text query")
    search_parser.add_argument("query", help="Text description of the image")
    search_parser.add_argument("--db-path", default="./search.db", help="Path to Milvus Lite DB")
    search_parser.add_argument("--provider", default="mock", choices=["mock", "openai"], help="Image generation provider")
    
    args = parser.parse_args()
    
    if args.command == "index":
        cmd_index(args)
    elif args.command == "search":
        cmd_search(args)

if __name__ == "__main__":
    main()
