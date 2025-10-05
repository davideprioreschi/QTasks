import os

def get_db_path():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(BASE_DIR, "app", "db", "qtasks.db")
    return DB_PATH
