from src.database.sqlite_store import SQLiteStore
store = SQLiteStore()
val = store.get_config("top_k", "Not Set")
print(f"Current DB top_k: {val}")
