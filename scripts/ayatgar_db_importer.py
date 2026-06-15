"""
Ayatgar DB Importer
====================
این فایل را روی سیستم خودت اجرا کن — بعد از اینکه Colab کارش تمام شد.
فایل‌های JSONL خروجی Colab را به PostgreSQL وارد می‌کند.

پیش‌نیاز:
  pip install psycopg2-binary tqdm

اجرا:
  python ayatgar_db_importer.py
"""

import json
import os
import sys
import psycopg2
from psycopg2.extras import execute_values
from tqdm import tqdm

# ── تنظیمات ────────────────────────────────────────────────────────
DB_CONFIG = {
    "dbname":   "ayatgar_db",
    "user":     "postgres",
    "password": "ayatgar2024",
    "host":     "localhost",
    "port":     5432
}

EMBED_DIM   = 1024

# مسیر فایل‌های خروجی Colab — بعد از دانلود از Drive اینجا بگذار
POEMS_FILE  = r"C:\AI\ganjoor\ayatgar_output\poems_embedded.jsonl"
VERSES_FILE = r"C:\AI\ganjoor\ayatgar_output\verses_embedded.jsonl"

DB_BATCH = 500


# ── راه‌اندازی دیتابیس ──────────────────────────────────────────────
def setup_db(conn):
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS poems (
            id          SERIAL PRIMARY KEY,
            ganjoor_id  INT UNIQUE,
            title       TEXT,
            full_title  TEXT,
            poet        VARCHAR(150),
            cat_path    TEXT,
            url         TEXT,
            full_text   TEXT,
            verse_count INT,
            embedding   vector({EMBED_DIM}),
            created_at  TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS verses (
            id          SERIAL PRIMARY KEY,
            ganjoor_id  INT,
            poem_id     INT REFERENCES poems(id) ON DELETE CASCADE,
            verse_order INT,
            position    INT,
            text        TEXT NOT NULL,
            poet        VARCHAR(150),
            cat_path    TEXT,
            embedding   vector({EMBED_DIM})
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS poems_fts_idx ON poems USING gin(to_tsvector('simple', full_text));")
    cur.execute("CREATE INDEX IF NOT EXISTS verses_fts_idx ON verses USING gin(to_tsvector('simple', text));")
    cur.execute("CREATE INDEX IF NOT EXISTS poems_poet_idx ON poems (poet);")
    cur.execute("CREATE INDEX IF NOT EXISTS verses_poet_idx ON verses (poet);")
    conn.commit()
    cur.close()
    print("✓ ساختار دیتابیس آماده شد")


def build_hnsw(conn):
    print("\nساخت ایندکس HNSW...")
    cur = conn.cursor()
    cur.execute("SET maintenance_work_mem = '512MB';")
    cur.execute(f"""
        CREATE INDEX IF NOT EXISTS poems_hnsw_idx
        ON poems USING hnsw (embedding vector_cosine_ops)
        WITH (m=16, ef_construction=64);
    """)
    conn.commit()
    cur.execute(f"""
        CREATE INDEX IF NOT EXISTS verses_hnsw_idx
        ON verses USING hnsw (embedding vector_cosine_ops)
        WITH (m=16, ef_construction=64);
    """)
    conn.commit()
    cur.close()
    print("✓ ایندکس HNSW ساخته شد")


# ── import اشعار ────────────────────────────────────────────────────
def import_poems(conn):
    if not os.path.exists(POEMS_FILE):
        print(f"❌ فایل یافت نشد: {POEMS_FILE}")
        return {}

    with open(POEMS_FILE, "r", encoding="utf-8") as f:
        total = sum(1 for _ in f)

    print(f"\nimport اشعار ({total:,})...")
    cur  = conn.cursor()
    buf  = []
    done = 0
    # نگاشت ganjoor_id به db id برای verses
    id_map = {}

    with open(POEMS_FILE, "r", encoding="utf-8") as f:
        for line in tqdm(f, total=total, unit="شعر"):
            try:
                d = json.loads(line.strip())
            except:
                continue

            emb = d.get("embedding")
            if not emb:
                continue

            buf.append((
                d.get("ganjoor_id"), d.get("title",""), d.get("full_title",""),
                d.get("poet","نامشخص"), d.get("cat_path",""), d.get("url",""),
                d.get("full_text",""), d.get("verse_count", 0), emb
            ))

            if len(buf) >= DB_BATCH:
                execute_values(cur, """
                    INSERT INTO poems
                        (ganjoor_id,title,full_title,poet,cat_path,url,full_text,verse_count,embedding)
                    VALUES %s
                    ON CONFLICT (ganjoor_id) DO UPDATE SET embedding=EXCLUDED.embedding
                    RETURNING id, ganjoor_id;
                """, buf)
                for row in cur.fetchall():
                    id_map[row[1]] = row[0]
                conn.commit()
                done += len(buf)
                buf.clear()

    if buf:
        execute_values(cur, """
            INSERT INTO poems
                (ganjoor_id,title,full_title,poet,cat_path,url,full_text,verse_count,embedding)
            VALUES %s
            ON CONFLICT (ganjoor_id) DO UPDATE SET embedding=EXCLUDED.embedding
            RETURNING id, ganjoor_id;
        """, buf)
        for row in cur.fetchall():
            id_map[row[1]] = row[0]
        conn.commit()
        done += len(buf)

    cur.close()
    print(f"✓ {done:,} شعر import شد")
    return id_map


# ── import بیت‌ها ────────────────────────────────────────────────────
def import_verses(conn, id_map: dict):
    if not os.path.exists(VERSES_FILE):
        print(f"❌ فایل یافت نشد: {VERSES_FILE}")
        return

    with open(VERSES_FILE, "r", encoding="utf-8") as f:
        total = sum(1 for _ in f)

    print(f"\nimport بیت‌ها ({total:,})...")
    cur  = conn.cursor()
    buf  = []
    done = 0
    miss = 0

    with open(VERSES_FILE, "r", encoding="utf-8") as f:
        for line in tqdm(f, total=total, unit="بیت"):
            try:
                d = json.loads(line.strip())
            except:
                continue

            emb        = d.get("embedding")
            ganjoor_id = d.get("ganjoor_id")
            poem_id    = id_map.get(ganjoor_id)

            if not emb or not poem_id:
                miss += 1
                continue

            buf.append((
                ganjoor_id, poem_id,
                d.get("verse_order", 0), d.get("position", 0),
                d.get("text",""), d.get("poet","نامشخص"),
                d.get("cat_path",""), emb
            ))

            if len(buf) >= DB_BATCH:
                execute_values(cur, """
                    INSERT INTO verses
                        (ganjoor_id,poem_id,verse_order,position,text,poet,cat_path,embedding)
                    VALUES %s;
                """, buf)
                conn.commit()
                done += len(buf)
                buf.clear()

    if buf:
        execute_values(cur, """
            INSERT INTO verses
                (ganjoor_id,poem_id,verse_order,position,text,poet,cat_path,embedding)
            VALUES %s;
        """, buf)
        conn.commit()
        done += len(buf)

    cur.close()
    print(f"✓ {done:,} بیت import شد | رد شده: {miss:,}")


def main():
    print("═" * 60)
    print("  ایاتگار — DB Importer")
    print("═" * 60)

    print("\nاتصال به PostgreSQL...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur  = conn.cursor()
        cur.execute("SET synchronous_commit = OFF;")
        cur.close()
    except Exception as e:
        print(f"❌ خطا: {e}")
        print("  docker start ayatgar-db")
        sys.exit(1)

    setup_db(conn)
    id_map = import_poems(conn)
    import_verses(conn, id_map)
    build_hnsw(conn)
    conn.close()

    print("\n" + "═" * 60)
    print("  ✓ همه چیز آماده است!")
    print("  حالا backend را اجرا کن:")
    print("  uvicorn ayatgar_backend:app --reload --port 8000")
    print("═" * 60)


if __name__ == "__main__":
    main()
