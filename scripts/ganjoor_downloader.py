"""
Ganjoor Downloader — منطق اصلی
اجرا: python ganjoor_downloader.py
"""

import requests
import json
import time
import logging
import queue
import threading
from pathlib import Path
from datetime import datetime

BASE_URL   = "https://api.ganjoor.net/api/ganjoor"
OUTPUT_DIR = Path("ganjoor_dataset")
PROGRESS_F = OUTPUT_DIR / "progress.json"
OUTPUT_F   = OUTPUT_DIR / "poems.jsonl"
LOG_F      = OUTPUT_DIR / "downloader.log"

REQUEST_DELAY = 0.25
MAX_RETRIES   = 5
RETRY_DELAY   = 15

OUTPUT_DIR.mkdir(exist_ok=True)

file_handler = logging.FileHandler(LOG_F, encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log = logging.getLogger("ganjoor")
log.setLevel(logging.INFO)
log.addHandler(file_handler)

session = requests.Session()
session.headers.update({"Accept": "application/json", "User-Agent": "GanjoorDataset/2.0"})

# ── queue برای ارسال رویداد به UI ──────────────────────────────────
ui_queue: queue.Queue = None

def emit(event: str, **data):
    if ui_queue:
        ui_queue.put({"event": event, **data})

# ── توابع پایه ──────────────────────────────────────────────────────
def api_get(path: str):
    url = f"{BASE_URL}/{path}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 200:
                time.sleep(REQUEST_DELAY)
                return r.json()
            elif r.status_code == 404:
                return None
            elif r.status_code == 429:
                wait = RETRY_DELAY * attempt
                emit("warning", msg=f"Rate limit — انتظار {wait}s")
                time.sleep(wait)
            else:
                emit("warning", msg=f"HTTP {r.status_code} — تلاش {attempt}")
                time.sleep(RETRY_DELAY)
        except requests.RequestException as e:
            emit("error", msg=str(e))
            time.sleep(RETRY_DELAY * attempt)
    return None

def load_progress():
    if PROGRESS_F.exists():
        return json.loads(PROGRESS_F.read_text(encoding="utf-8"))
    return {"done_cats": [], "done_poem_ids": [], "done_poets": [], "poem_count": 0}

def save_progress(p):
    PROGRESS_F.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")

def fetch_poem(poem_meta, poet_name, cat_path):
    pid  = poem_meta["id"]
    data = api_get(f"poem/{pid}")
    if not data:
        return None
    plain = data.get("plainText", "").strip()
    verses = data.get("verses", [])
    if not plain and verses:
        plain = "\n".join(v.get("text","").strip() for v in verses if v.get("text","").strip())
    if not plain:
        return None
    return {
        "id":       pid,
        "title":    data.get("title",""),
        "poet":     poet_name,
        "cat_path": cat_path,
        "url":      data.get("fullUrl",""),
        "text":     plain,
        "verses":   [{"order": v.get("vOrder"), "text": v.get("text","").strip()}
                     for v in verses if v.get("text","").strip()]
    }

def process_cat(cat_id, cat_path, poet_name, progress, out_file):
    if cat_id in progress["done_cats"]:
        return 0
    data = api_get(f"cat/{cat_id}")
    if not data:
        return 0
    cat      = data.get("cat", {})
    children = cat.get("children") or []
    poems    = cat.get("poems")    or []
    count    = 0
    for child in children:
        count += process_cat(child["id"], f"{cat_path} / {child['title']}", poet_name, progress, out_file)
    emit("cat", name=cat_path.split("/")[-1].strip(), total=len(poems))
    for poem_meta in poems:
        pid = poem_meta["id"]
        if pid in progress["done_poem_ids"]:
            continue
        poem_data = fetch_poem(poem_meta, poet_name, cat_path)
        if poem_data:
            out_file.write(json.dumps(poem_data, ensure_ascii=False) + "\n")
            count += 1
            progress["poem_count"]    += 1
            progress["done_poem_ids"].append(pid)
            emit("poem",
                 title=poem_data["title"],
                 poet=poet_name,
                 cat=cat_path.split("/")[-1].strip(),
                 total=progress["poem_count"])
    progress["done_cats"].append(cat_id)
    save_progress(progress)
    return count

def process_poet(poet, progress, out_file):
    pid, name = poet["id"], poet["name"]
    if pid in progress.get("done_poets", []):
        return 0
    emit("poet", name=name)
    pdata = api_get(f"poet/{pid}")
    if not pdata:
        return 0
    root = (pdata.get("poet",{}).get("rootCatId")
            or pdata.get("cat",{}).get("id")
            or poet.get("rootCatId"))
    if not root:
        return 0
    count = process_cat(root, name, name, progress, out_file)
    if "done_poets" not in progress:
        progress["done_poets"] = []
    progress["done_poets"].append(pid)
    save_progress(progress)
    emit("poet_done", name=name, count=count)
    return count

def run_download(q: queue.Queue):
    global ui_queue
    ui_queue = q
    progress = load_progress()
    emit("start", poem_count=progress["poem_count"])
    poets = api_get("poets")
    if not poets:
        emit("fatal", msg="لیست شاعران دریافت نشد")
        return
    emit("poets_loaded", total=len(poets), done=len(progress.get("done_poets",[])))
    with open(OUTPUT_F, "a", encoding="utf-8") as f:
        for i, poet in enumerate(poets, 1):
            emit("progress", index=i, total=len(poets))
            process_poet(poet, progress, f)
            f.flush()
    emit("done", total=progress["poem_count"])

if __name__ == "__main__":
    # اجرای مستقل بدون UI (fallback)
    import sys
    logging.getLogger("ganjoor").addHandler(logging.StreamHandler(sys.stdout))
    run_download(queue.Queue())