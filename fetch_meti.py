import os
import re
import json
import smtplib
import requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

METI_URL = "https://www.meti.go.jp/shingikai/"
BASE_URL = "https://www.meti.go.jp"
RECIPIENT = "ryohei.shima@shizenenergy.net"
SENDER = os.environ["GMAIL_ADDRESS"]
APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
PREV_FILE = "prev_links.json"

def fetch_page():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ja,en;q=0.9",
    }
    r = requests.get(METI_URL, headers=headers, timeout=30)
    r.raise_for_status()
    r.encoding = "utf-8"
    return r.text

def parse_links(html):
    items = []
    seen = set()
    pattern = re.compile(
        r'(\d{4})年(\d{1,2})月(\d{1,2})日[\s\S]*?<a\s+href="([^"]+)"[^>]*>([^<]+)</a>'
    )
    for m in pattern.finditer(html):
        href = m.group(4)
        if not href.startswith("http"):
            href = BASE_URL + href
        if href in seen:
            continue
        seen.add(href)
        date_obj = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        items.append({
            "href": href,
            "text": m.group(5).strip(),
            "date": f"{m.group(1)}年{m.group(2)}月{m.group(3)}日",
            "date_obj": date_obj.isoformat(),
        })
    return items

def load_prev():
    if os.path.exists(PREV_FILE):
        with open(PREV_FILE) as f:
            return json.load(f)
    return None

def save_prev(items):
    with open(PREV_FILE, "w") as f:
        json.dump([{"href": i["href"]} for i in items], f)

def send_email(subject, body):
    msg = MIMEMultipart()
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER, APP_PASSWORD)
        server.send_message(msg)
    print(f"送信完了: {subject}")

def main():
    html = fetch_page()
    items = parse_links(html)
    print(f"取得リンク数: {len(items)}")

    prev = load_prev()
    is_first_run = prev is None
    prev_hrefs = set(i["href"] for i in prev) if prev else set()
    save_prev(items)

    today = datetime.now().strftime("%Y年%m月%d日")

    if is_first_run:
        three_days_ago = datetime.now() - timedelta(days=3)
        targets = [i for i in items if datetime.fromisoformat(i["date_obj"]) >= three_days_ago]
        subject = f"【経産省審議会】初回配信・直近3日間 {today}"
    else:
        targets = [i for i in items if i["href"] not in prev_hrefs]
        subject = f"【経産省審議会】新着 {len(targets)}件 {today}" if targets else f"【経産省審議会】新着なし {today}"

    if targets:
        body = subject + "\n" + "=" * 50 + "\n\n"
        for idx, item in enumerate(targets, 1):
            body += f"{idx}. [{item['date']}]\n{item['text']}\n{item['href']}\n\n"
        body += f"\nMETI審議会: {METI_URL}"
    else:
        body = f"本日（{today}）の新着はありませんでした。\n\nMETI審議会: {METI_URL}"

    send_email(subject, body)

if __name__ == "__main__":
    main()
