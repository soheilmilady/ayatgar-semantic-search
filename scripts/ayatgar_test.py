"""
Ayatgar Semantic Search Test — اسکریپت تست دیتابیس برداری (نسخه عیب‌یابی)
اجرا: python ayatgar_test.py
"""

import sys
import torch
import psycopg2
from sentence_transformers import SentenceTransformer

# ── ۱. تنظیمات اتصال به دیتابیس داکر ──────────────────────────────
DB_CONFIG = {
    "dbname": "ayatgar_db",
    "user": "postgres",
    "password": "mysecretpassword",
    "host": "localhost",
    "port": 5432,
    "connect_timeout": 5  # حداکثر ۵ ثانیه منتظر دیتابیس بماند و اگر وصل نشد خطا بدهد
}

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

print("[۱] شروع اسکریپت... در حال بررسی سخت‌افزار گرافیک...")
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"    دستگاه شناسایی شده: {device}")

print("[۲] در حال فراخوانی کلاس SentenceTransformer...")
try:
    # اضافه کردن حالت local_files_only برای اینکه اصلاً سراغ چک کردن اینترنت نرود
    model = SentenceTransformer(MODEL_NAME, model_kwargs={"local_files_only": True})
    print("    کلاس با موفقیت ساخته شد.")
except Exception as e:
    print(f"    ❌ خطا در ساخت کلاس مدل: {str(e)}")
    sys.exit(1)

print(f"[۳] در حال انتقال لایه‌های مدل روی حافظه {device} (اینجا ممکن است قفل کند)...")
try:
    model.to(device)
    print("    مدل با موفقیت روی سخت‌افزار لود شد.")
except Exception as e:
    print(f"    ❌ خطا در انتقال مدل به سخت‌افزار: {str(e)}")
    sys.exit(1)

# ── ۲. تابع اصلی جستجوی معنایی ─────────────────────────────────────
def semantic_search(query_text, top_k=5):
    print(f"\n[۴] شروع فرآیند تبدیل متن به بردار برای: '{query_text}'...")
    query_embedding = model.encode(query_text).tolist()
    print("    متن با موفقیت به بردار ۷۶۸ رقمی تبدیل شد.")
    
    print("[۵] در حال تلاش برای اتصال به پایگاه داده داکر (پورت ۵۴۳۲)...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        print("    اتصال به دیتابیس برقرار شد.")
    except Exception as e:
        print(f"    ❌ خطا در اتصال به دیتابیس داکر: {str(e)}")
        print("    نکته: مطمئن شوید کانتینر داکر حتماً روشن (Up) باشد.")
        return
    
    print("[۶] در حال اجرای کوری محاسبات کسینوسی روی دیتابیس برداری...")
    search_query = """
        SELECT poet_name, cat_path, verse_text, 1 - (embedding <=> %s::vector) AS similarity
        FROM poem_verses
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
    """
    
    cur.execute(search_query, (query_embedding, query_embedding, top_k))
    results = cur.fetchall()
    
    print(f"\n🔍 نتایج جستجوی معنایی برای مفهوم: '{query_text}'")
    print("=" * 70)
    
    for i, row in enumerate(results, 1):
        poet, path, text, score = row
        print(f"{i}. [{poet}] - شباهت: {score*100:.2f}%")
        print(f"   📖 بیت: {text}")
        print(f"   📂 مسیر: {path}")
        print("-" * 70)
        
    cur.close()
    conn.close()

if __name__ == "__main__":
    print("\n--- هسته سرچ معنایی آماده کار است ---")
    while True:
        user_query = input("\nیک مفهوم، احساس یا موضوع ادبی وارد کنید (یا 'exit' برای خروج): ").strip()
        if user_query.lower() == 'exit' or not user_query:
            break
        try:
            semantic_search(user_query, top_k=5)
        except Exception as e:
            print(f"❌ خطایی در حین سرچ رخ داد: {str(e)}")