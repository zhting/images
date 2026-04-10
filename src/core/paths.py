import os
import sys

def get_app_dir():
    """
    Returns the base installation directory where persistent data should be kept.
    When frozen via PyInstaller, sys.executable points to the .exe file.
    When not frozen, it returns the project root.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        # Assuming this file is at src/core/paths.py, project root is 2 dirs up
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_internal_data_dir():
    """Returns the _MEIPASS dir (bundled internal files) or app dir (source)."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return get_app_dir()

def get_db_dir():
    if getattr(sys, 'frozen', False):
        db_dir = os.path.join(get_app_dir(), 'db')
    else:
        db_dir = get_app_dir()
    os.makedirs(db_dir, exist_ok=True)
    return db_dir

def get_models_dir():
    models_dir = os.path.join(get_app_dir(), 'models')
    os.makedirs(models_dir, exist_ok=True)
    return models_dir
