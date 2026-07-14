"""System routes: indexing, system info, filesystem, explorer, logs."""
import os
import sys
import time
import gc
import subprocess
import traceback

from fastapi import APIRouter, HTTPException, BackgroundTasks

from api.state import get_db, get_store, get_model, get_sync_manager, state, invalidate_all_caches
from core.tasks import runner
from api.models import IndexRunRequest, IndexingProgress, FSListRequest, ExplorerRequest

import logging
logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])

# Initialize indexing progress on module load
state.progress = IndexingProgress()


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------
@router.get("/index/scan")
def scan_indexing_files(force: bool = False, background_tasks: BackgroundTasks = BackgroundTasks()):
    if state.progress.state in ["scanning", "indexing"]:
        raise HTTPException(status_code=400, detail="Indexing already in progress")

    def _do_scan():
        try:
            state.progress.state = "scanning"
            state.progress.phase = "正在扫描文件变动..."
            manager = get_sync_manager()
            if force:
                diff = manager.scan_files(force_simulation=True)
            else:
                diff = manager.scan_files()

            count = len(diff['to_add']) + len(diff['to_update']) + len(diff['to_delete'])
            video_exts = ('.mp4', '.mov', '.avi', '.mkv')

            def count_types(paths):
                videos = sum(1 for p in paths if p.lower().endswith(video_exts))
                return len(paths) - videos, videos

            added_photos, added_videos = count_types(diff['to_add'])
            updated_photos, updated_videos = count_types(diff['to_update'])

            state.progress.scan_result = {
                "added": len(diff['to_add']), "added_photos": added_photos, "added_videos": added_videos,
                "updated": len(diff['to_update']), "updated_photos": updated_photos, "updated_videos": updated_videos,
                "deleted": len(diff['to_delete']), "total_ops": count, "diff_obj": diff
            }
            state.progress.state = "scanned"
            state.progress.phase = f"扫描完成. 发现 {count} 个变动."
        except Exception as e:
            state.progress.state = "error"
            state.progress.phase = f"扫描失败: {str(e)}"
            traceback.print_exc()

    state.progress.state = "scanning"
    state.progress.phase = "正在启动扫描..."
    # Runs on the TaskRunner worker instead of the request thread pool.
    task = runner.submit("index_scan", lambda t: _do_scan())
    return {"status": "scan_started", "task_id": task.id}


@router.get("/tasks")
def list_tasks():
    """Unified view over background jobs (indexing today; clustering and
    location refinement will ride the same runner)."""
    return runner.list()


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str):
    if runner.cancel(task_id):
        return {"status": "cancelling", "task_id": task_id}
    raise HTTPException(status_code=404, detail="No such active task")


@router.post("/index/stop")
def stop_indexing():
    if state.progress.state not in ["indexing", "scanning"]:
        return {"status": "ignored", "message": "Not running"}
    state.progress.stop_requested = True
    state.progress.phase = "正在停止..."
    return {"status": "stopping"}


@router.post("/index/run")
def run_indexing(req: IndexRunRequest, background_tasks: BackgroundTasks):
    if state.progress.state == "indexing":
        raise HTTPException(status_code=400, detail="Indexing already in progress")

    def _progress_cb(curr, total, msg, is_video=False, task=None):
        state.progress.current = curr
        state.progress.total = total
        state.progress.current_file = msg
        state.progress.phase = f"正在处理 {curr}/{total}"
        if task is not None and total:
            task.report(curr / total, msg)
        if is_video:
            state.progress.processed_videos += 1
        elif "Deleting" not in msg:
            state.progress.processed_photos += 1

    def _do_run(task):
        try:
            state.progress.state = "indexing"
            state.progress.start_time = time.time()
            state.progress.processed_photos = 0
            state.progress.processed_videos = 0
            state.progress.phase = "正在加载 AI 模型..."

            manager = get_sync_manager()

            def _scan_status(msg):
                state.progress.phase = msg

            if req.force:
                state.progress.phase = "正在清空旧索引..."
                get_db().reset_collection()
                get_store().clear_faces()
                if state.progress.scan_result and state.progress.scan_result.get('diff_obj'):
                    diff = state.progress.scan_result['diff_obj']
                else:
                    diff = manager.scan_files(force_simulation=True, status_callback=_scan_status)
            elif state.progress.scan_result and state.progress.scan_result.get('diff_obj'):
                diff = state.progress.scan_result['diff_obj']
            else:
                diff = manager.scan_files(status_callback=_scan_status)

            video_exts = ('.mp4', '.mov', '.avi', '.mkv')
            all_paths = []
            if isinstance(diff, dict):
                all_paths.extend(diff.get('to_add', []))
                all_paths.extend(diff.get('to_update', []))
                all_paths.extend(diff.get('to_delete', []))
            t_videos = sum(1 for p in all_paths if p.lower().endswith(video_exts))
            state.progress.total_photos = len(all_paths) - t_videos
            state.progress.total_videos = t_videos

            state.progress.stop_requested = False

            def stop_check():
                # Either surface can cancel: the legacy /index/stop flag or
                # the task's own cancellation.
                return state.progress.stop_requested or task.cancelled

            manager.sync_changes(
                diff,
                progress_callback=lambda c, t, m, is_video=False: _progress_cb(
                    c, t, m, is_video=is_video, task=task),
                stop_check=stop_check)

            if state.progress.stop_requested:
                state.progress.state = "stopped"
                state.progress.phase = "索引已中止"
            else:
                state.progress.state = "completed"
                state.progress.phase = "索引更新完成，部分损坏文件已被跳过，请查看失败日志。"
                invalidate_all_caches()

                try:
                    all_files = get_db().get_all_files()
                    valid_paths = set(all_files.keys())
                    removed_count = get_store().prune_orphaned_faces(valid_paths)
                    if removed_count > 0:
                        logger.info(f"Cleaned up {removed_count} orphaned face records.")
                except Exception as e:
                    logger.warning(f"Cleanup warning: {e}")

            state.progress.scan_result = None
            store = get_store()
            state.progress.last_updated = store.get_config("last_indexed_time", "")

        except Exception as e:
            state.progress.state = "error"
            state.progress.phase = f"发生系统错误：{str(e)}"
            state.progress.scan_result = None
            logger.error(f"Index run error: {e}")

    state.progress.state = "indexing"
    state.progress.phase = "正在启动索引..."
    task = runner.submit("index_run", _do_run)
    return {"status": "indexing_started", "task_id": task.id}


@router.get("/index/status")
def get_index_status():
    store = get_store()
    try:
        stats = get_db().get_stats()
        db_count = stats.get("total", 0)
    except Exception as e:
        logger.error(f"stats collection failed: {e} ::: {traceback.format_exc()}")
        db_count = 0
        stats = {}

    last_updated = store.get_config("last_indexed_time", "")
    if not last_updated:
        last_updated = "Never"

    return {
        "status": state.progress.state, "phase": state.progress.phase,
        "current": state.progress.current, "total": state.progress.total,
        "total_photos": state.progress.total_photos, "total_videos": state.progress.total_videos,
        "current_file": state.progress.current_file, "scan_result": state.progress.scan_result,
        "db_count": db_count, "stats": stats, "last_updated": last_updated,
        "start_time": state.progress.start_time
    }


# ---------------------------------------------------------------------------
# System Info & Control
# ---------------------------------------------------------------------------
@router.get("/system/info")
def get_system_info():
    try:
        model = get_model()
        return {"device": model.device, "model_type": "VisionModel"}
    except Exception as e:
        return {"device": "unknown", "error": str(e)}


@router.post("/system/restart")
def restart_system():
    try:
        if state.progress.state in ["indexing", "scanning"]:
            state.progress.stop_requested = True
        state.model = None
        state.vector_db = None
        state.store = None
        invalidate_all_caches()
        gc.collect()
        return {"status": "restarted", "message": "Backend state reset. Components will reload on next request."}
    except Exception:
        raise


# ---------------------------------------------------------------------------
# Native Dialogs
# ---------------------------------------------------------------------------
@router.post("/system/dialog/folder")
def open_folder_dialog():
    path = ""
    try:
        cmd = [sys.executable, "-c",
               "import tkinter.filedialog; import tkinter; root=tkinter.Tk(); root.withdraw(); "
               "root.attributes('-topmost', True); print(tkinter.filedialog.askdirectory())"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            path = result.stdout.strip()
    except Exception:
        pass

    if not path:
        try:
            cmd = ["python", "-c",
                   "import tkinter.filedialog; import tkinter; root=tkinter.Tk(); root.withdraw(); "
                   "root.attributes('-topmost', True); print(tkinter.filedialog.askdirectory())"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                path = result.stdout.strip()
        except Exception:
            pass

    if not path and sys.platform == 'win32':
        try:
            ps_cmd = ["powershell", "-Command",
                      "Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.FolderBrowserDialog; "
                      "$f.ShowDialog() | Out-Null; $f.SelectedPath"]
            result = subprocess.run(ps_cmd, capture_output=True, text=True)
            path = result.stdout.strip()
        except Exception:
            pass

    return {"path": path or ""}


@router.post("/system/dialog/file")
def open_file_dialog():
    path = ""
    try:
        cmd = [sys.executable, "-c",
               "import tkinter.filedialog; import tkinter; root=tkinter.Tk(); root.withdraw(); "
               "root.attributes('-topmost', True); print(tkinter.filedialog.askopenfilename("
               "filetypes=[('SQLite DB', '*.db'), ('All Files', '*.*')]))"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            path = result.stdout.strip()
    except Exception:
        pass

    if not path:
        try:
            cmd = ["python", "-c",
                   "import tkinter.filedialog; import tkinter; root=tkinter.Tk(); root.withdraw(); "
                   "root.attributes('-topmost', True); print(tkinter.filedialog.askopenfilename("
                   "filetypes=[('SQLite DB', '*.db'), ('All Files', '*.*')]))"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                path = result.stdout.strip()
        except Exception:
            pass

    if not path and sys.platform == 'win32':
        try:
            ps_cmd = ["powershell", "-Command",
                      "Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.OpenFileDialog; "
                      "$f.Filter = 'SQLite DB (*.db)|*.db|All Files (*.*)|*.*'; $f.ShowDialog() | Out-Null; $f.FileName"]
            result = subprocess.run(ps_cmd, capture_output=True, text=True)
            path = result.stdout.strip()
        except Exception:
            pass

    return {"path": path or ""}


# ---------------------------------------------------------------------------
# Filesystem Browser
# ---------------------------------------------------------------------------
@router.get("/system/fs/drives")
def get_drives():
    try:
        drives = []
        if os.name == 'nt':
            try:
                import win32api
                drives_str = win32api.GetLogicalDriveStrings()
                drives = [d for d in drives_str.split('\000') if d]
            except ImportError:
                import string
                drives = [f"{letter}:\\" for letter in string.ascii_uppercase if os.path.exists(f"{letter}:\\")]
        else:
            drives = ["/"]
        return {"drives": drives}
    except Exception:
        return {"drives": []}


@router.post("/system/fs/list")
def list_directory(req: FSListRequest):
    try:
        path = req.path
        if not path or not os.path.exists(path):
            raise HTTPException(404, "Path not found")

        items = []
        with os.scandir(path) as it:
            for entry in it:
                try:
                    is_dir = entry.is_dir()
                    if req.only_dir and not is_dir:
                        continue
                    stat = entry.stat()
                    size = stat.st_size if not is_dir else 0
                    file_type = "文件夹" if is_dir else "文件"
                    if not is_dir:
                        _, ext = os.path.splitext(entry.name)
                        if ext:
                            file_type = f"{ext[1:].upper()} 文件"
                    items.append({
                        "name": entry.name, "is_dir": is_dir,
                        "path": entry.path.replace("\\", "/"),
                        "size": size, "mtime": stat.st_mtime, "type": file_type
                    })
                except (PermissionError, Exception):
                    continue

        items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        return items
    except Exception:
        raise


# ---------------------------------------------------------------------------
# Explorer
# ---------------------------------------------------------------------------
_explorer_locks = {}


@router.post("/system/explorer")
def open_in_explorer(req: ExplorerRequest):
    try:
        now = time.time()
        if req.path in _explorer_locks and now - _explorer_locks[req.path] < 1.0:
            return {"status": "ignored", "message": "Rate limited"}
        _explorer_locks[req.path] = now

        if os.name == 'nt':
            target_path = os.path.normpath(req.path.strip())
            if not os.path.exists(target_path):
                raise HTTPException(404, "File not found on disk")

            folder_path = os.path.dirname(target_path)
            file_name = os.path.basename(target_path)

            try:
                import win32com.client
                import win32gui
                import win32con
                import urllib.parse

                shell = win32com.client.Dispatch("Shell.Application")
                windows = shell.Windows()
                found = False

                for window in windows:
                    if 'explorer.exe' in window.FullName.lower():
                        try:
                            location_url = window.LocationURL
                            if location_url.startswith('file:///'):
                                window_path = urllib.parse.unquote(location_url[8:]).replace('/', '\\')
                                if window_path.lower() == folder_path.lower():
                                    found = True
                                    try:
                                        hwnd = window.HWND
                                        if win32gui.IsIconic(hwnd):
                                            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                                        win32gui.SetForegroundWindow(hwnd)
                                    except Exception:
                                        pass
                                    try:
                                        folder = window.Document.Folder
                                        item = folder.ParseName(file_name)
                                        if item:
                                            window.Document.SelectItem(item, 13)
                                    except Exception:
                                        pass
                                    break
                        except Exception:
                            pass

                if not found:
                    subprocess.Popen(f'explorer /select,"{target_path}"')
                return {"status": "success"}
            except ImportError:
                subprocess.Popen(f'explorer /select,"{target_path}"')
                return {"status": "success", "message": "Explorer opened (fallback)"}
        else:
            return {"status": "ignored", "message": "Not a Windows system"}
    except Exception:
        raise


# ---------------------------------------------------------------------------
# Error Logs
# ---------------------------------------------------------------------------
@router.delete("/system/logs/error")
def clear_error_logs():
    try:
        log_path = os.path.join(os.getcwd(), "error_media.log")
        if os.path.exists(log_path):
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("")
        return {"status": "success", "message": "Log file cleared"}
    except Exception:
        raise


@router.get("/system/logs/error")
def get_error_logs():
    try:
        log_path = os.path.join(os.getcwd(), "error_media.log")
        results = []
        if os.path.exists(log_path):
            valid_lines = []
            has_changes = False
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines:
                    if line.startswith('[') and '] REASON:' in line and '| FILE:' in line:
                        try:
                            time_part = line[1:20]
                            parts = line.split(' | FILE: ')
                            if len(parts) == 2:
                                reason_part = parts[0].split('] REASON: ')[1].strip()
                                file_path = parts[1].strip()
                                if os.path.exists(file_path):
                                    valid_lines.append(line)
                                    results.append({"time": time_part, "reason": reason_part, "path": file_path})
                                else:
                                    has_changes = True
                            else:
                                valid_lines.append(line)
                        except Exception:
                            valid_lines.append(line)
                    else:
                        valid_lines.append(line)
            if has_changes:
                try:
                    with open(log_path, "w", encoding="utf-8") as f:
                        f.writelines(valid_lines)
                except Exception:
                    pass
        results.reverse()
        return results
    except Exception:
        raise
