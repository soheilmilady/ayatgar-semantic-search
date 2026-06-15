import psycopg2
from psycopg2 import pool
from fastapi import HTTPException

# تنظیمات اتصال به دیتابیس داکر
DB_CONFIG = {
    "dbname":   "ayatgar_db",
    "user":     "postgres",
    "password": "ayatgar2024",
    "host":     "localhost",
    "port":     5432
}

db_pool = None

def initialize_db_pool():
    global db_pool
    try:
        db_pool = pool.SimpleConnectionPool(5, 20, **DB_CONFIG)
    except Exception as e:
        print(f"Error creating connection pool: {e}")
        raise e

def close_db_pool():
    global db_pool
    if db_pool:
        db_pool.closeall()

class get_db_connection:
    def __enter__(self):
        if not db_pool:
            raise HTTPException(status_code=500, detail="Database connection pool is not initialized")
        self.conn = db_pool.getconn()
        self.cur = self.conn.cursor()
        return self.cur
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, 'cur') and self.cur:
            self.cur.close()
        if hasattr(self, 'conn') and self.conn:
            db_pool.putconn(self.conn)