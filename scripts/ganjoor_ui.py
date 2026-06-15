"""
Ganjoor Downloader — رابط گرافیکی
اجرا: python ganjoor_ui.py
"""

import tkinter as tk
from tkinter import font as tkfont
import queue
import threading
import time
from datetime import datetime, timedelta
import sys

# ── رنگ‌ها و تنظیمات ظاهری ─────────────────────────────────────────
BG          = "#0d0f14"
BG2         = "#13161e"
BG3         = "#1a1e2a"
CARD        = "#1e2332"
BORDER      = "#2a3048"
ACCENT      = "#4f8ef7"
ACCENT2     = "#7c5cfc"
GREEN       = "#3dd68c"
YELLOW      = "#f5c842"
RED         = "#f75f5f"
TEXT        = "#e8eaf0"
TEXT_DIM    = "#5a6080"
TEXT_MID    = "#8892b0"
FONT_MONO   = ("Courier New", 10)
FONT_TITLE  = ("Segoe UI", 22, "bold")
FONT_LABEL  = ("Segoe UI", 10)
FONT_SMALL  = ("Segoe UI", 9)
FONT_NUM    = ("Courier New", 26, "bold")
FONT_NUM_SM = ("Courier New", 14, "bold")

class GanjoorUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("دانلودر دیتاست گنجور")
        self.root.configure(bg=BG)
        self.root.geometry("920x680")
        self.root.minsize(820, 600)
        self.root.resizable(True, True)

        # وضعیت
        self.poem_count   = tk.IntVar(value=0)
        self.poet_index   = tk.IntVar(value=0)
        self.poet_total   = tk.IntVar(value=0)
        self.speed_var    = tk.StringVar(value="۰.۰")
        self.poet_name    = tk.StringVar(value="در حال شروع...")
        self.cat_name     = tk.StringVar(value="—")
        self.status_var   = tk.StringVar(value="در حال اتصال...")
        self.elapsed_var  = tk.StringVar(value="۰:۰۰:۰۰")
        self.errors_var   = tk.IntVar(value=0)

        self.start_time   = None
        self.log_lines    = []
        self.recent_poems = []
        self.running      = False

        self._build_ui()
        self.queue = queue.Queue()
        self._poll_queue()

    # ── ساخت رابط ──────────────────────────────────────────────────
    def _build_ui(self):
        # هدر
        header = tk.Frame(self.root, bg=BG, pady=0)
        header.pack(fill="x", padx=24, pady=(20, 0))

        tk.Label(header, text="گنجور", font=("Segoe UI", 28, "bold"),
                 bg=BG, fg=ACCENT).pack(side="left")
        tk.Label(header, text=" | دانلودر دیتاست اشعار",
                 font=("Segoe UI", 14), bg=BG, fg=TEXT_MID).pack(side="left", pady=6)

        self.status_lbl = tk.Label(header, textvariable=self.status_var,
                                   font=FONT_SMALL, bg=BG, fg=YELLOW)
        self.status_lbl.pack(side="right", pady=6)

        # خط جداکننده
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x", padx=24, pady=12)

        # ردیف کارت‌های آمار
        cards_row = tk.Frame(self.root, bg=BG)
        cards_row.pack(fill="x", padx=24, pady=(0, 14))

        self._stat_card(cards_row, "اشعار دانلود‌شده", self.poem_count,
                        GREEN, large=True).pack(side="left", padx=(0, 10), fill="both", expand=True)
        self._stat_card(cards_row, "سرعت (شعر/دقیقه)", self.speed_var,
                        ACCENT).pack(side="left", padx=(0, 10), fill="both", expand=True)
        self._stat_card(cards_row, "زمان سپری‌شده", self.elapsed_var,
                        ACCENT2).pack(side="left", padx=(0, 10), fill="both", expand=True)
        self._stat_card(cards_row, "خطاها", self.errors_var,
                        RED).pack(side="left", fill="both", expand=True)

        # نوار پیشرفت شاعران
        prog_frame = tk.Frame(self.root, bg=CARD, bd=0, highlightthickness=1,
                              highlightbackground=BORDER)
        prog_frame.pack(fill="x", padx=24, pady=(0, 14))
        prog_inner = tk.Frame(prog_frame, bg=CARD, padx=16, pady=12)
        prog_inner.pack(fill="x")

        row1 = tk.Frame(prog_inner, bg=CARD)
        row1.pack(fill="x")
        tk.Label(row1, text="پیشرفت شاعران", font=FONT_SMALL,
                 bg=CARD, fg=TEXT_MID).pack(side="left")
        self.poet_pct_lbl = tk.Label(row1, text="۰ / ۰",
                                     font=FONT_SMALL, bg=CARD, fg=TEXT)
        self.poet_pct_lbl.pack(side="right")

        self.prog_canvas = tk.Canvas(prog_inner, height=8, bg=BG3,
                                     highlightthickness=0, bd=0)
        self.prog_canvas.pack(fill="x", pady=(6, 8))
        self.prog_fill = self.prog_canvas.create_rectangle(0, 0, 0, 8,
                                                           fill=ACCENT, outline="")

        row2 = tk.Frame(prog_inner, bg=CARD)
        row2.pack(fill="x")
        tk.Label(row2, text="شاعر:", font=FONT_SMALL, bg=CARD, fg=TEXT_DIM).pack(side="left")
        tk.Label(row2, textvariable=self.poet_name, font=("Segoe UI", 10, "bold"),
                 bg=CARD, fg=TEXT).pack(side="left", padx=6)
        tk.Label(row2, text="دسته:", font=FONT_SMALL, bg=CARD, fg=TEXT_DIM).pack(side="left", padx=(20, 0))
        tk.Label(row2, textvariable=self.cat_name, font=FONT_SMALL,
                 bg=CARD, fg=ACCENT).pack(side="left", padx=6)

        # پایین: لاگ + آخرین اشعار
        bottom = tk.Frame(self.root, bg=BG)
        bottom.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        # ستون چپ: آخرین اشعار
        left_col = tk.Frame(bottom, bg=BG)
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

        tk.Label(left_col, text="آخرین اشعار دانلود‌شده",
                 font=("Segoe UI", 10, "bold"), bg=BG, fg=TEXT_MID).pack(anchor="w", pady=(0, 6))

        self.poems_frame = tk.Frame(left_col, bg=BG)
        self.poems_frame.pack(fill="both", expand=True)
        self.poem_rows = []
        for _ in range(7):
            row = tk.Frame(self.poems_frame, bg=BG2, pady=6, padx=10,
                           highlightthickness=1, highlightbackground=BG3)
            row.pack(fill="x", pady=2)
            poet_lbl  = tk.Label(row, text="", font=FONT_SMALL, bg=BG2,
                                 fg=ACCENT, width=14, anchor="w")
            poet_lbl.pack(side="left")
            title_lbl = tk.Label(row, text="", font=FONT_SMALL, bg=BG2,
                                 fg=TEXT, anchor="w")
            title_lbl.pack(side="left", padx=8, fill="x", expand=True)
            self.poem_rows.append((poet_lbl, title_lbl))

        # ستون راست: لاگ
        right_col = tk.Frame(bottom, bg=BG, width=290)
        right_col.pack(side="right", fill="both")
        right_col.pack_propagate(False)

        tk.Label(right_col, text="رویدادهای اخیر",
                 font=("Segoe UI", 10, "bold"), bg=BG, fg=TEXT_MID).pack(anchor="w", pady=(0, 6))

        log_outer = tk.Frame(right_col, bg=BG2, highlightthickness=1,
                             highlightbackground=BORDER)
        log_outer.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_outer, bg=BG2, fg=TEXT_MID,
                                font=("Consolas", 9),
                                relief="flat", bd=0, padx=10, pady=8,
                                wrap="word", state="disabled",
                                spacing1=3, spacing3=3)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.tag_config("green",  foreground=GREEN)
        self.log_text.tag_config("yellow", foreground=YELLOW)
        self.log_text.tag_config("red",    foreground=RED)
        self.log_text.tag_config("accent", foreground=ACCENT)
        self.log_text.tag_config("dim",    foreground=TEXT_DIM)

    def _stat_card(self, parent, label, var, color, large=False):
        frame = tk.Frame(parent, bg=CARD, padx=16, pady=14,
                         highlightthickness=1, highlightbackground=BORDER)
        num_font = FONT_NUM if large else FONT_NUM_SM
        if isinstance(var, tk.IntVar):
            lbl = tk.Label(frame, textvariable=var, font=num_font, bg=CARD, fg=color)
        else:
            lbl = tk.Label(frame, textvariable=var, font=num_font, bg=CARD, fg=color)
        lbl.pack(anchor="w")
        tk.Label(frame, text=label, font=FONT_SMALL, bg=CARD, fg=TEXT_DIM).pack(anchor="w")
        return frame

    # ── مدیریت رویدادها ────────────────────────────────────────────
    def _poll_queue(self):
        try:
            while True:
                ev = self.queue.get_nowait()
                self._handle_event(ev)
        except queue.Empty:
            pass
        finally:
            self._update_elapsed()
            self.root.after(200, self._poll_queue)

    def _handle_event(self, ev):
        t = ev.get("event")

        if t == "start":
            self.start_time = datetime.now()
            self.running    = True
            self.poem_count.set(ev.get("poem_count", 0))
            self.status_var.set("● در حال دانلود")
            self.status_lbl.config(fg=GREEN)
            self._log("شروع دانلود...", "green")

        elif t == "poets_loaded":
            total = ev["total"]
            done  = ev["done"]
            self.poet_total.set(total)
            self.poet_index.set(done)
            self._log(f"تعداد شاعران: {total}  (انجام‌شده: {done})", "accent")

        elif t == "progress":
            self.poet_index.set(ev["index"])
            self.poet_total.set(ev["total"])
            self._update_progress_bar()

        elif t == "poet":
            self.poet_name.set(ev["name"])
            self._log(f"شاعر: {ev['name']}", "yellow")

        elif t == "poet_done":
            self._log(f"✓ {ev['name']}  ({ev['count']} شعر)", "green")

        elif t == "cat":
            self.cat_name.set(ev["name"])

        elif t == "poem":
            self.poem_count.set(ev["total"])
            self._add_poem(ev["poet"], ev["title"])
            self._update_speed()

        elif t in ("warning", "error"):
            self.errors_var.set(self.errors_var.get() + 1)
            self._log(ev.get("msg",""), "red")

        elif t == "fatal":
            self.status_var.set("✗ خطای بحرانی")
            self.status_lbl.config(fg=RED)
            self._log(ev.get("msg",""), "red")

        elif t == "done":
            self.running = False
            self.status_var.set(f"✓ دانلود کامل شد — {ev['total']:,} شعر")
            self.status_lbl.config(fg=GREEN)
            self._log(f"پایان — مجموع: {ev['total']:,} شعر", "green")

    def _add_poem(self, poet, title):
        self.recent_poems.append((poet, title))
        if len(self.recent_poems) > 7:
            self.recent_poems.pop(0)
        for i, (poet_lbl, title_lbl) in enumerate(self.poem_rows):
            if i < len(self.recent_poems):
                p, t = self.recent_poems[-(i+1)]
                poet_lbl.config(text=p[:16])
                title_lbl.config(text=t[:42])
            else:
                poet_lbl.config(text="")
                title_lbl.config(text="")

    def _update_progress_bar(self):
        total = self.poet_total.get()
        idx   = self.poet_index.get()
        if total > 0:
            self.poet_pct_lbl.config(text=f"{idx} / {total}")
            self.prog_canvas.update_idletasks()
            w   = self.prog_canvas.winfo_width()
            pct = idx / total
            self.prog_canvas.coords(self.prog_fill, 0, 0, int(w * pct), 8)

    def _update_speed(self):
        if self.start_time:
            mins = (datetime.now() - self.start_time).total_seconds() / 60 or 0.001
            spd  = self.poem_count.get() / mins
            self.speed_var.set(f"{spd:.1f}")

    def _update_elapsed(self):
        if self.start_time and self.running:
            delta = timedelta(seconds=int((datetime.now() - self.start_time).total_seconds()))
            self.elapsed_var.set(str(delta))

    def _log(self, msg: str, tag: str = ""):
        self.log_text.config(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"{ts}  ", "dim")
        self.log_text.insert("end", msg + "\n", tag or None)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    # ── شروع دانلود ────────────────────────────────────────────────
    def start(self):
        import ganjoor_downloader as dl
        t = threading.Thread(target=dl.run_download, args=(self.queue,), daemon=True)
        t.start()


def main():
    root = tk.Tk()
    app  = GanjoorUI(root)
    root.after(500, app.start)
    root.mainloop()

if __name__ == "__main__":
    main()