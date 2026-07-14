import threading
import time
import urllib.request
import webview
import sys
import os
import json

# Ensure the correct path is added
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from api.server import app
import uvicorn

def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def start_server():
    # LAN mode (DEEPPHOTO_LAN=1) binds all interfaces so phones on the
    # same network can reach the app; default stays loopback-only.
    host = "0.0.0.0" if os.environ.get("DEEPPHOTO_LAN") == "1" else "127.0.0.1"
    uvicorn.run(app, host=host, port=8001, log_level="error")

def wait_for_server(url, timeout=30):
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            time.sleep(0.5)
            response = urllib.request.urlopen(url)
            if response.status == 200:
                print("Server is up and running.")
                return True
        except Exception:
            pass
    print("Server failed to start within timeout.")
    return False

def get_cache_config():
    config_path = os.path.join(get_app_dir(), 'webview_config.json')
    default_cache = os.path.join(get_app_dir(), 'cache')
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('cache_path', default_cache)
        except Exception as e:
            print(f"Error reading config: {e}")
            return default_cache
    else:
        # Create default config
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({"cache_path": default_cache, "_comment": "Modify cache_path to change the WebView cache directory"}, f, indent=4)
        except Exception:
            pass
        return default_cache

if __name__ == '__main__':
    # Determine cache path
    cache_dir = get_cache_config()
    os.makedirs(cache_dir, exist_ok=True)

    # Start the backend server in a daemon thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Wait until the backend API is ready
    if wait_for_server("http://127.0.0.1:8001/version_check"):
        # Create and start the pywebview window with local cache
        webview.create_window('Deep Photo', 'http://127.0.0.1:8001', width=1280, height=800)
        # Pass private_mode=False to allow caching, storage_path to specify path
        webview.start(private_mode=False, storage_path=cache_dir)
    else:
        sys.exit(1)
