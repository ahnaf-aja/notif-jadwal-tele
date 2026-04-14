import requests
import pandas as pd
import time
import schedule
import json
import os

# =========================
# CONFIG
# =========================
URL = "https://jkt48.com/api/v1/schedules?month=4&year=2026"

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

CACHE_FILE = "cache.json"


# =========================
# LOAD CACHE (ANTI SPAM)
# =========================
def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(list(data), f)


previous_ids = load_cache()


# =========================
# SEND TELEGRAM
# =========================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg
    }
    requests.post(url, json=payload)


# =========================
# MAIN CHECK FUNCTION
# =========================
def check_schedule():
    global previous_ids

    try:
        res = requests.get(URL, timeout=10)
        data = res.json()['data']
        df = pd.DataFrame(data)

        if df.empty:
            print("⚠️ Data kosong")
            return

        df['date'] = pd.to_datetime(df['date'])

        # mapping title
        title_col = 'title' if 'title' in df.columns else df.columns[0]

        # =========================
        # ⏰ FORMAT WAKTU (FIX TBA)
        # =========================
        def format_time(row):
            start = row.get('start_time')
            end = row.get('end_time')

            if pd.notna(start) and pd.notna(end):
                return f"{str(start)[:5]} - {str(end)[:5]}"
            elif pd.notna(start):
                return str(start)[:5]
            else:
                return "TBA"

        df['time_fmt'] = df.apply(format_time, axis=1)

        # =========================
        # 🆔 UNIQUE ID (ANTI DUPLICATE)
        # =========================
        df['uid'] = df.apply(
            lambda x: f"{x['date']}_{x[title_col]}_{x['time_fmt']}",
            axis=1
        )

        current_ids = set(df['uid'])

        print(f"🔍 Cek jadwal... total {len(current_ids)} event")

        # =========================
        # 🚨 DETEKSI EVENT BARU
        # =========================
        new_ids = current_ids - previous_ids

        if new_ids:
            new_events = df[df['uid'].isin(new_ids)]

            for _, row in new_events.iterrows():
                today = pd.Timestamp.today().date()
                event_date = row['date'].date()

                if event_date == today:
                    label = "HARI INI"
                elif event_date == today + pd.Timedelta(days=1):
                    label = "BESOK"
                else:
                    label = "UPCOMING"

                msg = f"""
🚨 JADWAL BARU JKT48!

🎭 {row[title_col]}
📅 {row['date'].strftime('%d %B %Y')} ({label})
⏰ {row['time_fmt']} WIB
"""

                send_telegram(msg)

            print(f"✅ {len(new_events)} notif terkirim!")

        else:
            print("✔️ Tidak ada jadwal baru")

        previous_ids = current_ids
        save_cache(previous_ids)

    except Exception as e:
        print("❌ Error:", e)
        # =========================
        # 💾 UPDATE CACHE
        # =========================
        previous_ids = current_ids
        save_cache(previous_ids)

    except Exception as e:
        print("❌ Error:", e)
# =========================
# SCHEDULER
# =========================
schedule.every(10).seconds.do(check_schedule)

print("🟢 Monitoring aktif (cek tiap 10 detik)...")

while True:
    schedule.run_pending()
    time.sleep(2)
