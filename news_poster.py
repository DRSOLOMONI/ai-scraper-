import feedparser
import requests
import hashlib
import os
import time
from datetime import datetime

# ========================= CONFIG =========================
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Enhanced list of RSS feeds (AI + Crypto)
RSS_FEEDS = [
    # AI Feeds
    "https://openai.com/news/rss.xml",
    "https://huggingface.co/blog/feed.xml",
    "https://www.marktechpost.com/feed/",
    "https://techcrunch.com/tag/artificial-intelligence/feed/",
    "https://www.bensbites.com/feed",
    "https://www.technologyreview.com/topic/artificial-intelligence/feed/",
    "https://research.google/blog/rss/",
    "https://www.wired.com/feed/tag/ai/latest/rss",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://simonwillison.net/atom/everything/",
    # Crypto Feeds
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://cryptopotato.com/feed/",
    "https://cryptoslate.com/feed/",
    "https://cryptobriefing.com/feed/",
]

MAX_PER_FEED = 5
SEEN_FILE = "seen.txt"
MAX_MESSAGE_LENGTH = 4000
KEYWORDS = ["AI", "artificial intelligence", "crypto", "bitcoin", "ethereum", "LLM", "gpt", "blockchain", "solana"]

# ========================================================

def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return {line.strip() for line in f if line.strip()}
    return set()

def save_seen(seen: set):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for item in seen:
            f.write(item + "\n")

def clean_text(text: str, max_len: int = 250) -> str:
    if not text:
        return ""
    text = text.replace("<p>", "").replace("</p>", "\n").strip()
    if len(text) > max_len:
        return text[:max_len].strip() + "..."
    return text

def send_telegram(message: str, retries: int = 3) -> bool:
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ Telegram credentials missing!")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    
    for attempt in range(retries):
        try:
            response = requests.post(url, json=payload, timeout=15)
            if response.status_code == 200:
                return True
            elif response.status_code == 429:
                wait = int(response.headers.get("Retry-After", 5))
                print(f"Rate limited. Waiting {wait}s...")
                time.sleep(wait)
                continue
            else:
                print(f"Telegram API error {response.status_code}: {response.text}")
        except Exception as e:
            print(f"Request failed: {e}")
        time.sleep(2 ** attempt)
    return False

def main():
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("❌ Error: TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set in environment!")
        return

    seen = load_seen()
    new_seen = seen.copy()
    posted_count = 0

    print(f"[{datetime.now()}] Starting AI + Crypto news scan...")

    for feed_url in RSS_FEEDS:
        try:
            print(f"📡 Parsing: {feed_url}")
            feed = feedparser.parse(feed_url)
            
            if not feed.entries:
                print(f"  ⚠️ No entries or failed to parse {feed_url}")
                continue

            for entry in feed.entries[:MAX_PER_FEED]:
                title = getattr(entry, 'title', '').strip()
                link = getattr(entry, 'link', '')
                
                if not title or not link:
                    continue

                item_id = hashlib.md5((title + link).encode('utf-8')).hexdigest()
                
                if item_id in seen:
                    continue

                # Optional keyword filter
                content = (title + " " + 
                          getattr(entry, 'summary', '') + " " + 
                          getattr(entry, 'description', ''))
                
                if not any(kw.lower() in content.lower() for kw in KEYWORDS):
                    continue

                summary = clean_text(getattr(entry, 'summary', '') or getattr(entry, 'description', ''), 250)
                
                message = f"<b>{title}</b>\n\n"
                if summary:
                    message += f"{summary}\n\n"
                message += f"<a href='{link}'>Read full article →</a>"

                # Truncate safely
                if len(message) > MAX_MESSAGE_LENGTH:
                    message = message[:MAX_MESSAGE_LENGTH-3] + "..."

                if send_telegram(message):
                    posted_count += 1
                    new_seen.add(item_id)
                    print(f"✅ Posted: {title[:60]}...")
                    time.sleep(1.5)  # Be gentle with Telegram
                else:
                    print(f"❌ Failed to post: {title[:60]}...")

        except Exception as e:
            print(f"❌ Error parsing {feed_url}: {e}")

    # Save updated seen items
    save_seen(new_seen)
    print(f"🏁 Scan complete. Posted {posted_count} new items.")

if __name__ == "__main__":
    main()
