import streamlit as st
import os
import sys
import time
from PIL import Image

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.append(src_dir)

from core.generator import MockGenerator, OpenAIGenerator, NanoBananaGenerator
from database.vector_db import VectorDB
from core.models import VisionModel
from database.sqlite_store import SQLiteStore
from core.sync import SyncManager
import uuid
import collections
import datetime

# Page Config
st.set_page_config(page_title="本地生成式视觉检索", layout="wide")

st.title("本地生成式视觉检索系统")

# ... (Imports remain above)

# Helper functions for caching
@st.cache_resource
def get_model():
    return VisionModel()

@st.cache_resource
def get_db(path):
    return VectorDB(db_path=path)

@st.cache_resource
def run_startup_sync_once():
    """
    Run sync check only once when the server/script starts (cached).
    """
    try:
        # We need fresh instances or cached ones? 
        # Using cached ones is fine.
        db = get_db("./search.db")
        model = get_model()
        store = SQLiteStore()
        
        syncer = SyncManager(db, model, store)
        stats = syncer.run_startup_sync(dry_run=True)
        return stats
    except Exception as e:
        print(f"Startup sync failed: {e}")
        return None

# Trigger Sync Check
sync_stats = run_startup_sync_once()
if sync_stats and (sync_stats['added'] > 0 or sync_stats['updated'] > 0 or sync_stats['deleted'] > 0):
    msg = f"检测到素材变动: 新增 {sync_stats['added']}, 更新 {sync_stats['updated']}, 删除 {sync_stats['deleted']}。请在左侧边栏重新构建索引。"
    st.toast(msg, icon="🔔")

import tkinter as tk
from tkinter import filedialog

# Sidebar - Configuration
st.sidebar.header("系统配置")
# DB Path hidden as requested, default to ./search.db, maybe allow advanced users to see via expander
# db_path = st.sidebar.text_input("向量库路径 (DB Path)", value="./search.db")
db_path = "./search.db" # Hardcoded for now

# Initialize Config Store
store = SQLiteStore()

# Asset Paths Management
st.sidebar.markdown("### 图片素材目录")
current_paths = store.get_asset_paths()

# Use container to manage paths state
if 'paths_refresh' not in st.session_state:
    st.session_state['paths_refresh'] = 0

# Display paths
if not current_paths:
    st.sidebar.warning("暂无素材目录")
else:
    for p in current_paths:
        c1, c2 = st.sidebar.columns([4, 1])
        c1.text(os.path.basename(p) if len(p)>20 else p, help=p)
        if c2.button("🗑️", key=f"del_{p}"):
            store.remove_asset_path(p)
            st.rerun()

# Add new path
if st.sidebar.button("➕ 添加目录", help="点击打开文件夹选择器"):
    try:
        root = tk.Tk()
        root.withdraw() 
        root.wm_attributes('-topmost', 1)
        selected_folder = filedialog.askdirectory()
        root.destroy()
        if selected_folder:
            store.add_asset_path(os.path.abspath(selected_folder))
            st.rerun()
    except Exception as e:
        st.sidebar.error(f"无法打开文件夹选择器: {e}")

# provider = st.sidebar.selectbox("生图服务提供商", ["mock", "openai", "nano-banana"])
# Unified Configuration
st.sidebar.markdown("### 生图模型配置")

# Retrieve persisted config
stored_api_key = store.get_config("api_key") or ""
stored_model_name = store.get_config("model_name") or "nano-banana"

api_key = st.sidebar.text_input("API Key", value=stored_api_key, type="password", help="留空则使用本地 Mock 生成器")
model_name = st.sidebar.text_input("模型名称 (Model)", value=stored_model_name, help="例如: nano-banana, dall-e-3")

# Save if changed
if api_key != stored_api_key:
    store.set_config("api_key", api_key)
if model_name != stored_model_name:
    store.set_config("model_name", model_name)

# Result Limit Config
stored_top_k = int(store.get_config("top_k") or 10)
top_k_limit = st.sidebar.slider("返回结果数量", min_value=1, max_value=100, value=stored_top_k)
if top_k_limit != stored_top_k:
    store.set_config("top_k", str(top_k_limit))

# Determine provider implicitly for UI logic if needed, mostly for generator instantiation
# Helper functions for caching

# Helper functions for caching
@st.cache_resource
def get_model():
    return VisionModel()

@st.cache_resource
def get_db(path):
    return VectorDB(db_path=path)

# Re-Index Section
st.sidebar.markdown("---")
# Display Device Info next to header or just below
try:
    model = get_model()
    device_label = "🚀 GPU 加速中" if model.device == "cuda" else "🐢 CPU 模式"
    st.sidebar.subheader(f"索引管理 ({device_label})")
except:
    st.sidebar.subheader("索引管理")

# Display Stats
try:
    db = get_db(db_path)
    total_images = db.count()
    last_indexed = store.get_config("last_indexed_time") or "从未"
    
    s1, s2 = st.sidebar.columns(2)
    s1.metric("已索引图片", total_images)
    s2.text(f"上次更新:\n{last_indexed}")
except Exception as e:
    st.sidebar.warning(f"无法获取统计信息: {e}")

if 'indexing_stage' not in st.session_state:
    st.session_state['indexing_stage'] = 'idle' # idle, confirming, indexing
if 'estimated_count' not in st.session_state:
    st.session_state['estimated_count'] = 0

def reset_indexing_state():
    st.session_state['indexing_stage'] = 'idle'

if 'indexing_plan' not in st.session_state:
    st.session_state['indexing_plan'] = None # {'add':[], 'update':[], 'delete':[], 'total_fs': 0}

if st.session_state['indexing_stage'] == 'idle':
    if st.sidebar.button("检查更新 / 重建索引"):
        paths = store.get_asset_paths()
        if not paths:
            st.sidebar.error("请先添加素材目录")
        else:
            with st.sidebar.status("正在扫描变动..."):
                try:
                    db = get_db(db_path)
                    db_files = db.get_all_files()
                    
                    to_add = []
                    to_update = []
                    to_delete = []
                    
                    fs_files_map = {}
                    
                    for p in paths:
                        if os.path.exists(p):
                            for root, _, files in os.walk(p):
                                for f in files:
                                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                                        full_path = os.path.abspath(os.path.join(root, f))
                                        mtime = int(os.path.getmtime(full_path))
                                        fs_files_map[full_path] = mtime
                                        
                                        if full_path not in db_files:
                                            to_add.append(full_path)
                                        elif mtime > db_files[full_path]:
                                            to_update.append(full_path)

                    # Check deletions
                    # Only check files that belong to managed paths
                    for db_p in db_files:
                        belongs = False
                        for p in paths:
                            if db_p.startswith(os.path.abspath(p)):
                                belongs = True
                                break
                        if belongs and db_p not in fs_files_map:
                            to_delete.append(db_p)

                    st.session_state['indexing_plan'] = {
                        'add': to_add,
                        'update': to_update,
                        'delete': to_delete,
                        'total_fs': len(fs_files_map)
                    }
                    st.session_state['indexing_stage'] = 'confirming'
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"扫描失败: {e}")

elif st.session_state['indexing_stage'] == 'confirming':
    plan = st.session_state['indexing_plan']
    if plan:
        count_add = len(plan['add'])
        count_update = len(plan['update'])
        count_delete = len(plan['delete'])
        total_change = count_add + count_update
        
        st.sidebar.info(f"扫描完成:\n新增: {count_add}, 更新: {count_update}, 删除: {count_delete}")
        
        force_rebuild = st.sidebar.checkbox("强制全量重建", value=False)
        
        # Estimate
        if force_rebuild:
            work_count = plan['total_fs']
        else:
            work_count = total_change
            
        import datetime
        # Dynamic estimation based on device
        try:
            device = get_model().device
            # with threading + gpu, we target ~0.1s - 0.2s per image
            per_image_sec = 0.15 if device == "cuda" else 1.0
        except:
            per_image_sec = 1.0

        est_sec = int(work_count * per_image_sec)
        est_sec = max(1, est_sec)
        est_str = str(datetime.timedelta(seconds=est_sec))
        st.sidebar.caption(f"预计处理: {work_count} 张 (耗时 ~{est_str})")
        
        c1, c2 = st.sidebar.columns(2)
        with c1:
            if st.sidebar.button("开始更新"):
                st.session_state['force_rebuild'] = force_rebuild
                st.session_state['work_count'] = work_count
                st.session_state['indexing_stage'] = 'indexing'
                st.rerun()
        with c2:
            if st.sidebar.button("取消"):
                reset_indexing_state()
                st.rerun()

elif st.session_state['indexing_stage'] == 'indexing':
    if st.sidebar.button("🛑 停止索引", key="stop_btn_top"):
        reset_indexing_state()
        st.rerun()

    plan = st.session_state['indexing_plan']
    force = st.session_state.get('force_rebuild', False)
    
    progress_bar = st.sidebar.progress(0)
    status_text = st.sidebar.empty()

    import threading
    import collections
    import concurrent.futures
    import datetime

    # Progress shared state
    # count: newly processed items (committed)
    # loaded: items loaded in memory but not processed (optional, for finer grain if needed)
    progress_state = {'count': 0, 'total': 0, 'done': False, 'error': None}
    stop_event = threading.Event()

    def index_worker(file_list, db_path_arg, model_ref, batch_sz, prog_state, stop_evt, force_rebuild=False):
        try:
            # Create a dedicated DB connection for this thread
            local_db = get_db(db_path_arg)
            
            if force_rebuild:
                local_db.reset_collection()
            
            def load_img(path):
                if stop_evt.is_set(): return None, None, None, path
                try:
                    with Image.open(path) as i:
                        img = i.convert('RGB')
                        img.load()
                        
                        # Extract EXIF time
                        captured_time = 0
                        try:
                            exif = i._getexif()
                            if exif:
                                # DateTimeOriginal = 36867, DateTime = 306
                                date_str = exif.get(36867) or exif.get(306)
                                if date_str:
                                    # Format: YYYY:MM:DD HH:MM:SS
                                    # Handle occasional weird formats or bytes
                                    if isinstance(date_str, bytes):
                                         date_str = date_str.decode()
                                    dt = datetime.datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                                    captured_time = int(dt.timestamp())
                        except:
                            pass
                        
                        mtime = int(os.path.getmtime(path))
                        if captured_time == 0:
                            captured_time = mtime
                            
                        return img, mtime, captured_time, path
                except:
                    return None, None, None, path

            total_files = len(file_list)
            
            for i in range(0, total_files, batch_sz):
                if stop_evt.is_set(): break
                
                batch_paths = file_list[i:i + batch_sz]
                batch_imgs = []
                batch_times = []
                batch_ctimes = []
                valid_p = []
                
                # Parallel Load
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    results = list(executor.map(load_img, batch_paths))
                
                for img, mtime, ctime, path in results:
                    if img is not None:
                        batch_imgs.append(img)
                        batch_times.append(mtime)
                        batch_ctimes.append(ctime)
                        valid_p.append(path)
                
                if not valid_p: continue
                
                # GPU Encode
                vecs = model_ref.encode_batch(batch_imgs)
                
                # DB Insert
                local_db.insert_batch(vecs, valid_p, batch_times, captured_times=batch_ctimes)
                
                # Update State
                prog_state['count'] += len(valid_p)
                
        except Exception as e:
            prog_state['error'] = str(e)
        finally:
            prog_state['done'] = True

    # Prepare Target Files
    target_files = []
    if force:
        paths = store.get_asset_paths()
        for p in paths:
             if os.path.exists(p):
                for root, _, files in os.walk(p):
                    for f in files:
                        if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                            target_files.append(os.path.join(root, f))
    else:
        target_files = plan['add'] + plan['update']
    
    total_work = len(target_files)
    st.session_state['work_count'] = total_work # Update session state for safety
    progress_state['total'] = total_work
    
    # Start Thread
    db_path_safe = db_path
    
    # 64 is good for throughput
    batch_size = 64
    
    worker_thread = threading.Thread(
        target=index_worker,
        args=(target_files, db_path_safe, get_model(), batch_size, progress_state, stop_event, force)
    )
    worker_thread.start()
    
    # UI Loop
    display_count = 0.0
    start_time = time.time()
    
    while worker_thread.is_alive():
        # Check stop

            
        # We need to handle the button outside or via unique key. 
        # But `st.sidebar.button` returns False unless clicked.
        # If we put it in the loop, we get many buttons.
        # Solution: The STOP button is best handled by check at top of `indexing` stage block (which we have).
        # IF we are in this loop, we are blocking the script. User cannot click button effectively unless script yields?
        # Streamlit scripts are blocking. The UI is responsive only if we complete the run.
        # WAIT. `time.sleep` blocks the event loop?
        # Streamlit handles interactions by re-running the script.
        # If we are in a `while` loop, the script effectively never finishes, user input cannot be processed EXCEPT
        # if we use `st.empty` and `rerun`? No.
        
        # CORRECT PATTERN for Long Running Jobs in Streamlit:
        # We need to break the loop to handle events?
        # No, "While loop with sleep" prevents Streamlit from processing new events (like Stop Click).
        # We must use `st.empty` to update, but we CANNOT respond to buttons inside a tight loop easily.
        # HOWEVER, the user asked for smooth updates.
        
        # Compromise:
        # We just animate. If user wants to stop, they might have to wait or we rely on Streamlit's "Stop" button in the browser?
        # Or we check a specialized Stop button?
        
        # Actually, if we want the "Stop Indexing" button to work, we can't block the main thread forever.
        # But we need to animate...
        
        # Let's simple interpolation:
        target = progress_state['count']
        
        # Move display_count towards target
        diff = target - display_count
        if diff > 0:
            # Catch up speed: faster content -> faster catchup
            step = max(0.1, diff * 0.1) 
            display_count += step
            
        if display_count > target: display_count = target # Clamp?
        
        # Update UI
        dct = int(display_count)
        if total_work > 0:
            prog = min(dct / total_work, 1.0)
            progress_bar.progress(prog)
            
            # Smooth ETA based on configured speed
            # Avoid calculating rate from live stats to prevent jumping
            try:
                dev = get_model().device
                rate = 0.15 if dev == "cuda" else 1.0
            except:
                rate = 1.0
            
            rem = total_work - dct
            eta_s = int(rem * rate)
            eta_str = str(datetime.timedelta(seconds=eta_s))
            
            status_text.text(f"处理中: {dct}/{total_work}\n剩余时间: ~{eta_str}")
        
        time.sleep(0.05)
        
        # Safety break if thread dies
        if not worker_thread.is_alive():
             break

    # Final Sync
    worker_thread.join()
    
    if progress_state['error']:
        st.sidebar.error(f"出错: {progress_state['error']}")
    else:
        st.sidebar.success("更新完成！")
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        store.set_config("last_indexed_time", now_str)
        time.sleep(1)
        reset_indexing_state()
        st.rerun()


# Main Area
tab1, tab2, tab3, tab4 = st.tabs(["📷 以图搜图", "🎨 文生图搜索", "📝 直接搜图", "⏳ 时间轴"])

# --- Tab 1: Image Search ---
with tab1:
    st.markdown("### 上传图片进行相似度检索")
    uploaded_file = st.file_uploader("选择一张参考图片...", type=['png', 'jpg', 'jpeg', 'webp'])
    
    if uploaded_file is not None:
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(uploaded_file, caption="上传的图片", use_container_width=True)
            search_btn = st.button("开始搜索", key="search_img")
        
        with col2:
            if search_btn:
                st.subheader("检索结果")
                with st.spinner("正在检索中..."):
                    try:
                        start_time = time.time()
                        
                        # Load and encode
                        img = Image.open(uploaded_file).convert('RGB')
                        model = get_model() # Cached
                        query_vec = model.encode(img)
                        
                        # Search
                        db = get_db(db_path) # Cached
                        results = db.search(query_vec, top_k=top_k_limit)
                        
                        end_time = time.time()
                        elapsed_time = end_time - start_time
                        st.success(f"检索完成，耗时: {elapsed_time:.4f} 秒")
                        
                        if results and results[0]:
                            hits = results[0]
                            # Grid display
                            cols = st.columns(3)
                            for i, hit in enumerate(hits):
                                file_path = hit['entity']['file_path']
                                dist = hit['distance']
                                # Chroma default cosine distance is (1 - similarity)
                                # So similarity = 1 - distance
                                similarity = (1 - dist) * 100
                                # Clamp to 0-100 just in case
                                similarity = max(0.0, min(100.0, similarity))
                                
                                with cols[i % 3]:
                                    if os.path.exists(file_path):
                                        st.image(file_path, caption=f"相似度: {similarity:.2f}%")
                                        st.caption(f"路径: {file_path}")
                                    else:
                                        st.warning(f"文件丢失: {file_path}")
                        else:
                            st.info("未找到相似图片。")
                    except Exception as e:
                        st.error(f"检索出错: {e}")

# --- Tab 2: Text Generated Search ---
with tab2:
    st.markdown("### 描述你想找的画面")
    
    col_input1, col_input2 = st.columns([3, 1])
    with col_input1:
        query = st.text_input("请输入提示词 (Prompt):", placeholder="例如：一只在雪地里奔跑的哈士奇")
    with col_input2:
        # Multi-file uploader for reference images
        ref_files = st.file_uploader("参考图 (可选, 支持多张)", type=['png', 'jpg', 'jpeg', 'webp'], accept_multiple_files=True)
    
    # State management for proxy image
    if 'proxy_image_path' not in st.session_state:
        st.session_state['proxy_image_path'] = None
    if 'proxy_provider' not in st.session_state:
        st.session_state['proxy_provider'] = None

    if st.button("Step 1: 生成基准图", key="gen_btn"):
        if not query:
             st.error("请输入提示词")
        else:
            with st.spinner("正在生成基准图..."):
                try:
                    # Logic to determine provider
                    if not api_key:
                        # Fallback to Mock if no key provided
                        gen = MockGenerator()
                        provider_label = "mock"
                    else:
                        # Heuristic selection
                        if model_name.startswith("dall-e"):
                             gen = OpenAIGenerator(api_key=api_key, model=model_name)
                             provider_label = "openai"
                        else:
                             # Default to Nano-Banana (Grsai) for others
                             gen = NanoBananaGenerator(api_key=api_key, model=model_name)
                             provider_label = "nano-banana"
                    
                    # Process reference images
                    ref_pil_images = []
                    if ref_files:
                        for rf in ref_files:
                            ref_pil_images.append(Image.open(rf).convert('RGB'))

                    proxy_img = gen.generate(query, reference_images=ref_pil_images)
                    
                    # Log to SQLite
                    store = SQLiteStore()
                    temp_path = f"temp_{uuid.uuid4().hex}.png"
                    # In real app, put temp in a better place
                    if not os.path.exists("temp_history"):
                         os.makedirs("temp_history")
                    full_temp_path = os.path.join("temp_history", temp_path)
                    proxy_img.save(full_temp_path)
                    store.add_record(uuid.uuid4().hex, query, full_temp_path, provider_label)
                    
                    # Update Session State
                    st.session_state['proxy_image_path'] = full_temp_path
                    st.session_state['proxy_provider'] = provider_label
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"生成失败: {e}")

    # Display Generated Image and Search Button
    if st.session_state.get('proxy_image_path') and os.path.exists(st.session_state['proxy_image_path']):
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st.subheader("生成的基准图")
            st.image(st.session_state['proxy_image_path'], 
                     caption=f"Source: {st.session_state['proxy_provider']}", 
                     use_container_width=True)
            
            if st.button("Step 2:以此图搜索", key="search_proxy_btn"):
                # Trigger search
                with col2:
                    st.subheader("检索结果")
                    with st.spinner("正在基于基准图检索..."):
                        try:
                            start_time = time.time()
                            proxy_img = Image.open(st.session_state['proxy_image_path']).convert('RGB')
                            model = get_model()
                            query_vec = model.encode(proxy_img)
                            
                            db = get_db(db_path)
                            results = db.search(query_vec, top_k=top_k_limit)
                            
                            end_time = time.time()
                            elapsed_time = end_time - start_time
                            st.success(f"检索完成，耗时: {elapsed_time:.4f} 秒")
                            
                            
                            if results and results[0]:
                                hits = results[0]
                                cols = st.columns(3)
                                for i, hit in enumerate(hits):
                                    file_path = hit['entity']['file_path']
                                    dist = hit['distance']
                                    similarity = (1 - dist) * 100
                                    similarity = max(0.0, min(100.0, similarity))
                                    
                                    with cols[i % 3]:
                                        if os.path.exists(file_path):
                                            st.image(file_path, caption=f"相似度: {similarity:.2f}%")
                                            st.caption(f"路径: {file_path}")
                                        else:
                                            st.warning(f"文件丢失: {file_path}")
                            else:
                                st.info("未找到相似图片。")
                        except Exception as e:
                             st.error(f"检索出错: {e}")

# --- Tab 3: Direct Text Search ---
with tab3:
    st.markdown("### 输入文本直接搜索图片 (不经过生成)")
    
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        text_query = st.text_input("请输入检索文本:", placeholder="例如：a cat sleeping on a sofa")
    with col_t2:
        text_search_btn = st.button("直接搜索", key="text_search_btn")


    if text_search_btn and text_query:
        st.subheader("检索结果")
        
        # Translation Step
        final_query = text_query
        try:
             # Basic check if query might contain non-ascii (Chinese)
             # Use isascii() or just always try translating 'auto' -> 'en'
             if not text_query.isascii():
                  from deep_translator import GoogleTranslator
                  translated = GoogleTranslator(source='auto', target='en').translate(text_query)
                  if translated and translated != text_query:
                       final_query = translated
                       st.info(f"已自动翻译: {text_query} -> {final_query}")
        except Exception as e:
             st.warning(f"翻译服务暂不可用，使用原始文本搜索: {e}")

        with st.spinner("正在检索中..."):
            try:
                start_time = time.time()
                
                # Get text embedding
                model = get_model()
                query_vec = model.encode_text(final_query)
                
                # Search
                db = get_db(db_path)
                results = db.search(query_vec, top_k=top_k_limit)
                
                end_time = time.time()
                elapsed = end_time - start_time
                st.success(f"检索完成，耗时: {elapsed:.4f} 秒")
                
                if results and results[0]:
                    hits = results[0]
                    # Grid display
                    cols = st.columns(3)
                    for i, hit in enumerate(hits):
                        file_path = hit['entity']['file_path']
                        dist = hit['distance']
                        # Chroma default cosine distance is (1 - similarity)
                        # So similarity = 1 - distance
                        similarity = (1 - dist) * 100
                        similarity = max(0.0, min(100.0, similarity))
                        
                        with cols[i % 3]:
                            if os.path.exists(file_path):
                                st.image(file_path, caption=f"相似度: {similarity:.2f}%")
                                st.caption(f"路径: {file_path}")
                            else:
                                st.warning(f"文件丢失: {file_path}")
                else:
                    st.info("未找到相似图片。")
            except Exception as e:
                st.error(f"检索出错: {e}")


@st.dialog("图片预览", width="large")
def render_gallery_modal():
    current_items = st.session_state.get('gallery_items', [])
    idx = st.session_state.get('gallery_index', 0)
    
    if not current_items or idx >= len(current_items):
         st.warning("暂无图片信息")
         return

    item = current_items[idx]
    path = item['file_path']
    
    # Navigation & Main Image
    col_prev, col_img, col_next = st.columns([1, 10, 1])
    
    with col_prev:
        st.write("") 
        st.write("")
        st.write("")
        st.write("")
        if idx > 0:
            if st.button("⬅️", key="modal_prev_btn", help="上一张"):
                st.session_state['gallery_index'] = idx - 1
                st.rerun()
    
    with col_img:
         if os.path.exists(path):
             st.image(path, caption=os.path.basename(path), use_container_width=True)
         else:
             st.warning(f"文件丢失: {path}")
             
    with col_next:
        st.write("") 
        st.write("")
        st.write("")
        st.write("")
        if idx < len(current_items) - 1:
            if st.button("➡️", key="modal_next_btn", help="下一张"):
                st.session_state['gallery_index'] = idx + 1
                st.rerun()
                
    st.markdown("---")
    # Thumbnails Strip
    st.caption("本月预览")
    
    # Calculate window
    window = 7
    half = window // 2
    start = max(0, idx - half)
    end = min(len(current_items), start + window)
    if end - start < window:
        start = max(0, end - window)
        
    thumb_cols = st.columns(window)
    
    for i in range(window):
        actual_idx = start + i
        if actual_idx < len(current_items):
            t_item = current_items[actual_idx]
            t_path = t_item['file_path']
            
            with thumb_cols[i]:
                if os.path.exists(t_path):
                    if actual_idx == idx:
                        st.image(t_path, use_container_width=True)
                        st.markdown(f"<div style='text-align:center; color:red; font-weight:bold'>▲</div>", unsafe_allow_html=True)
                    else:
                        st.image(t_path, use_container_width=True)
                        if st.button("👁️", key=f"modal_thumb_{actual_idx}"):
                            st.session_state['gallery_index'] = actual_idx
                            st.rerun()

# --- Tab 4: Timeline ---
with tab4:
    # Custom CSS for Timeline
    st.markdown("""
    <style>
    .timeline-container {
        padding-left: 20px;
        border-left: 2px solid #e0e0e0;
        margin-left: 10px;
        position: relative;
    }
    .timeline-dot {
        position: absolute;
        left: -26px; /* Adjust based on border + padding */
        top: 0px;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background-color: #FF4B4B; /* Streamlit Red */
        border: 2px solid white;
    }
    .month-header {
        font-size: 1.2em;
        font-weight: bold;
        margin-bottom: 10px;
        color: #333;
    }
    .gallery-thumb-selected {
        border: 2px solid #FF4B4B;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("### ⏳ 时光轴")
    
    if 'timeline_focus' not in st.session_state:
        st.session_state['timeline_focus'] = None 
    if 'show_gallery_modal' not in st.session_state:
        st.session_state['show_gallery_modal'] = False
    if 'gallery_items' not in st.session_state:
        st.session_state['gallery_items'] = []
    if 'gallery_index' not in st.session_state:
        st.session_state['gallery_index'] = 0

    # Fetch data (Shared across modes)
    try:
        db = get_db(db_path)
        all_files = db.get_all_files_with_time()
        
        # Sort by captured_time desc
        all_files.sort(key=lambda x: x['captured_time'], reverse=True)
        
        # Group by Month and extract Year
        groups = collections.defaultdict(list)
        years = set()
        
        for f in all_files:
            if f['captured_time'] > 0:
                dt = datetime.datetime.fromtimestamp(f['captured_time'])
                key = dt.strftime("%Y-%m")
                groups[key].append(f)
                years.add(dt.year)
            else:
                groups["Unknown"].append(f)
                
    except Exception as e:
        st.error(f"加载时间轴数据失败: {e}")
        all_files = []
        groups = {}

    # Handle Years for Selector
    sorted_years = sorted(list(years), reverse=True)
    # Add "All" option
    sorted_years = ["全部"] + sorted_years
    
    if groups.get("Unknown") and "Unknown" not in sorted_years:
         sorted_years.append("Unknown")
         
    # Year Selector
    if len(sorted_years) <= 1 and not all_files: # Only "全部" and no files
         st.info("暂无索引照片，请先构建索引。")
    else:
         # Use selectbox or radio for years
         selected_year = st.selectbox("📅 选择年份", sorted_years, index=0)
         
         # Filter Keys
         sorted_keys = sorted(groups.keys(), reverse=True)
         filtered_keys = []
         
         if selected_year == "全部":
             filtered_keys = sorted_keys
         elif selected_year == "Unknown":
             if "Unknown" in groups: filtered_keys.append("Unknown")
         else:
             prefix = str(selected_year)
             for k in sorted_keys:
                 if k.startswith(prefix):
                     filtered_keys.append(k)

         # Check focus (List vs Single Month Grid)
         focus_key = st.session_state['timeline_focus']
    
         if focus_key:
            # Focus Mode (Single Month Grid)
            st.button("⬅️ 返回完整时间轴", on_click=lambda: st.session_state.update({'timeline_focus': None}))
            st.subheader(f"{focus_key}")
            
            items = groups.get(focus_key, [])
            
            # Grid
            cols = st.columns(4)
            for i, item in enumerate(items):
                p = item['file_path']
                with cols[i % 4]:
                    if os.path.exists(p):
                        st.image(p, use_container_width=True)
                        # Filename as Button to trigger Gallery
                        if st.button(os.path.basename(p), key=f"focus_btn_{i}_{p}"):
                            st.session_state['gallery_items'] = items
                            st.session_state['gallery_index'] = i
                            st.session_state['show_gallery_modal'] = True
                            st.rerun()
        
         else:
            # Timeline List Mode
            if not filtered_keys:
                st.info(f"{selected_year} 年没有照片。")
            
            for key in filtered_keys:
                items = groups[key]
                count = len(items)
                
                # Split into date label and content
                c_date, c_content = st.columns([0.15, 0.85])
                
                with c_date:
                    # Month Label with Dot visual trick (pure markdown approach)
                    month_label = key.split("-")[1] if "-" in key else "NA"
                    st.markdown(f"<div style='text-align:right; padding-right:10px; font-weight:bold; font-size:1.5em'>{month_label}月</div>", unsafe_allow_html=True)
                    st.caption(f"{count} 张")
                
                with c_content:
                    # Content Container with Border
                    st.markdown(f"""
                    <div class="timeline-container">
                         <div class="timeline-dot"></div>
                         <div class="month-header">{key}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Show first 10
                    preview_count = 10
                    preview_items = items[:preview_count]
                    
                    # Dynamic columns
                    cols_count = min(len(preview_items), 5)
                    if cols_count > 0:
                         cols = st.columns(cols_count)
                         for i, item in enumerate(preview_items):
                             p = item['file_path']
                             with cols[i % cols_count]:
                                 if os.path.exists(p):
                                     st.image(p, use_container_width=True)
                                     # Filename as Button to trigger Gallery
                                     if st.button(os.path.basename(p), key=f"list_btn_{key}_{i}"):
                                         st.session_state['gallery_items'] = items # Pass FULL list for navigation
                                         st.session_state['gallery_index'] = i
                                         st.session_state['show_gallery_modal'] = True
                                         st.rerun()
                    
                    if count > preview_count:
                        if st.button(f"查看 {key} 全部照片 ({count})", key=f"view_{key}"):
                            st.session_state['timeline_focus'] = key
                            st.rerun()
                    
                    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # Check if we need to open modal
    if st.session_state.get('show_gallery_modal', False):
        render_gallery_modal()

