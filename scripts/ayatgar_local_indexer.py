import json
import os
import sys
import time
import torch
import psycopg2
from tqdm import tqdm
from sentence_transformers import SentenceTransformer

# ── ۱. تنظیمات مسیرها و دیتابیس ──────────────────────────────────────
DATASET_PATH = r"C:\AI\ganjoor\ganjoor_dataset\poems.jsonl"  # مسیر فایل خام و اصلی گنجور

DB_CONFIG = {
    "dbname":   "ayatgar_db",
    "user":     "postgres",
    "password": "ayatgar2024",
    "host":     "localhost",
    "port":     5432
}

MODEL_NAME     = "intfloat/multilingual-e5-large-instruct"
EMBED_DIM      = 1024
BATCH_SIZE     = 32   # کاملاً ایمن و بهینه برای VRAM هشت گیگابایتی 4060
MAX_VERSE_LEN  = 300
MIN_VERSE_LEN  = 5
MAX_POEM_CHARS = 2000 

# ── ۲. پیشوندهای رسمی مدل E5 ────────────────────────────────────────
POEM_INSTRUCTION  = "Represent this Persian poem for semantic retrieval"
VERSE_INSTRUCTION = "Represent this Persian verse for semantic retrieval"

def format_e5_instruct(instruction: str, text: str) -> str:
    return f"Instruct: {instruction}\nQuery: {text}"

# ── ۳. استخراج اشعار موجود در داکر برای جلوگیری از تکرار ──────────────────
def get_existing_poem_ids(conn) -> set:
    print("\n[نگهبان ضد تکرار] در حال بررسی دیتابیس برای استخراج اشعارِ موجود...")
    cur = conn.cursor()
    # اشعاری که فیلد embedding آن‌ها پر است را پیدا می‌کند
    cur.execute("SELECT ganjoor_id FROM poems WHERE embedding IS NOT NULL;")
    rows = cur.fetchall()
    cur.close()
    existing_ids = {row[0] for row in rows if row[0] is not None}
    print(f"✓ تعداد {len(existing_ids):,} شعر از قبل در دیتابیس وجود دارد. از روی آن‌ها می‌پریم.")
    return existing_ids

# ── ۴. تابع اصلی پردازش ──────────────────────────────────────────────
def main():
    print("═" * 65)
    print("  ایاتگار — Local Indexer (نسخه کارت گرافیک)")
    print(f"  مدل: {MODEL_NAME}")
    print("═" * 65)

    # اتصال به دیتابیس داکر
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SET synchronous_commit = OFF;")  # سرعت تزریق را مگا‌سریع می‌کند
        cur.close()
    except Exception as e:
        print(f"❌ خطا در اتصال به دیتابیس داکر: {e}")
        print("مطمئن شو Docker Desktop باز است و کانتینر ayatgar-db اجرا می‌شود.")
        sys.exit(1)

    # بررسی سخت‌افزار
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\n سخت‌افزار: {device.upper()}")
    if device == "cuda":
        print(f" GPU: {torch.cuda.get_device_name(0)}")
    else:
        print(" ⚠ GPU یافت نشد — پردازش روی CPU خیلی کند خواهد بود!")
        sys.exit(1)

    # بارگذاری مدل با دقت fp16 برای بهره‌وری کامل از سری 4060
    print(f"\n بارگذاری مدل روی کارت گرافیک...")
    model = SentenceTransformer(
        MODEL_NAME, 
        device=device, 
        model_kwargs={"torch_dtype": torch.float16}
    )
    print(f" ✓ مدل آماده شد (ابعاد: {EMBED_DIM})")

    # بررسی وجود فایل خام
    if not os.path.exists(DATASET_PATH):
        print(f"\n❌ فایل دیتاست خام یافت نشد در مسیر: {DATASET_PATH}")
        sys.exit(1)

    # شمارش خطوط کل فایل خام
    print(" در حال شمارش خطوط فایل خام...")
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        total_lines = sum(1 for _ in f)
    print(f" اشعار کل دیتاست: {total_lines:,}")

    # فعال‌سازی سیستم ضد تکرار
    done_ids = get_existing_poem_ids(conn)

    # بافرهای محلی
    poem_buf = []
    verse_buf = []
    
    skipped = 0
    total_poems = len(done_ids)
    t_start = time.time()

    # تابع فلاش کردن اشعار مستقیم به داکر
    def flush_poems_to_db():
        if not poem_buf:
            return
        texts = [p["text"] for p in poem_buf]
        with torch.no_grad():
            embs = model.encode(texts, batch_size=BATCH_SIZE, show_progress_bar=False, normalize_embeddings=True).tolist()
        
        db_cur = conn.cursor()
        for p, emb in zip(poem_buf, embs):
            m = p["meta"]
            db_cur.execute("""
                INSERT INTO poems (ganjoor_id, title, full_title, poet, cat_path, url, full_text, verse_count, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ganjoor_id) DO UPDATE SET embedding = EXCLUDED.embedding;
            """, (m["ganjoor_id"], m["title"], m["full_title"], m["poet"], m["cat_path"], m["url"], m["full_text"], m["verse_count"], emb))
        conn.commit()
        db_cur.close()
        poem_buf.clear()

    # تابع فلاش کردن بیت‌ها مستقیم به داکر
    def flush_verses_to_db():
        if not verse_buf:
            return
        texts = [v["text"] for v in verse_buf]
        with torch.no_grad():
            embs = model.encode(texts, batch_size=BATCH_SIZE, show_progress_bar=False, normalize_embeddings=True).tolist()
        
        db_cur = conn.cursor()
        
        # پیدا کردن نگاشت آیدی دیتابیس برای حفظ Foreign Key ریلیشن‌ها
        db_cur.execute("SELECT id, ganjoor_id FROM poems WHERE ganjoor_id IN %s;", (tuple(set(v["meta"]["ganjoor_id"] for v in verse_buf)),))
        id_map = {row[1]: row[0] for row in db_cur.fetchall()}

        for v, emb in zip(verse_buf, embs):
            m = v["meta"]
            p_id = id_map.get(m["ganjoor_id"])
            if not p_id:
                continue
            db_cur.execute("""
                INSERT INTO verses (ganjoor_id, poem_id, verse_order, position, text, poet, cat_path, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """, (m["ganjoor_id"], p_id, m["verse_order"], m["position"], m["text"], m["poet"], m["cat_path"], emb))
        conn.commit()
        db_cur.close()
        verse_buf.clear()

    print(f"\n شروع پردازش نهایی روی سخت‌افزار لوکال...\n")
    pbar = tqdm(total=total_lines, desc="پیشرفت کل", unit="شعر", initial=len(done_ids), dynamic_ncols=True)

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line.strip())
            except json.JSONDecodeError:
                skipped += 1
                pbar.update(1)
                continue

            ganjoor_id = data.get("id")
            if ganjoor_id in done_ids:
                pbar.update(1)
                continue

            title      = data.get("title", "")
            full_title = data.get("full_title", title)
            poet       = data.get("poet", "نامشخص")
            cat_path   = data.get("cat_path", "")
            url        = data.get("url", "")
            full_text  = data.get("text", "").strip()
            verses_raw = data.get("verses", [])

            if not full_text or not verses_raw:
                skipped += 1
                pbar.update(1)
                continue

            # آماده‌سازی متن شعر
            embed_poem_text = format_e5_instruct(POEM_INSTRUCTION, full_text[:MAX_POEM_CHARS])
            poem_buf.append({
                "text": embed_poem_text,
                "meta": {
                    "ganjoor_id":  ganjoor_id,
                    "title":       title,
                    "full_title":  full_title,
                    "poet":        poet,
                    "cat_path":    cat_path,
                    "url":         url,
                    "full_text":   full_text,
                    "verse_count": len(verses_raw)
                }
            })

            # آماده‌سازی بیت‌ها
            for v in verses_raw:
                text = v.get("text", "").strip()
                if not text or len(text) < MIN_VERSE_LEN or len(text) > MAX_VERSE_LEN:
                    continue
                embed_verse_text = format_e5_instruct(VERSE_INSTRUCTION, text)
                verse_buf.append({
                    "text": embed_verse_text,
                    "meta": {
                        "ganjoor_id":  ganjoor_id,
                        "verse_order": v.get("order", 0),
                        "position":    v.get("position", 0),
                        "text":        text,
                        "poet":        poet,
                        "cat_path":    cat_path
                    }
                })

            total_poems += 1
            done_ids.add(ganjoor_id)

            # تخلیه بافرها به دیتابیس داکر در پارت‌های بهینه
            if len(poem_buf) >= BATCH_SIZE:
                flush_poems_to_db()
            if len(verse_buf) >= BATCH_SIZE * 4:
                flush_verses_to_db()

            # به روز رسانی نوارهای پیشرفت و نمایش وضعیت زنده
            if total_poems % 100 == 0:
                elapsed = time.time() - t_start
                pbar.set_postfix({"شعر/دقیقه": f"{total_poems / (elapsed / 60):.0f}"})

            pbar.update(1)

    # تخلیه نهایی بافرهای باقی‌مانده
    flush_poems_to_db()
    flush_verses_to_db()
    pbar.close()

    elapsed = time.time() - t_start
    print("\n" + "═" * 65)
    print(f"  ✓ پردازش لوکال با موفقیت ۱۰۰٪ پایان یافت!")
    print(f"  کل اشعار موجود در داکر: {total_poems:,}")
    print(f"  زمان صرف شده در این سشن: {elapsed/60:.1f} دقیقه")
    print("═" * 65)
    
    conn.close()

if __name__ == "__main__":
    main()