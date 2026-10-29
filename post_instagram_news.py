import os
import re
import json
import random
import time
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

# ================== НАСТРОЙКИ ==================
BRIDGE_URL = "https://rss-bridge.org/bridge01/?action=display&username=elpaisru&bridge=TelegramBridge&format=Html"
BUFFER_API = "https://api.buffer.com"

HISTORY_FILE = "instagram_posted_history.json"
BANNERS_DIR  = "banners"

MAX_CAPTION   = 2100
DEFAULT_TAGS = ["#новости", "#эльпаис", "#Испания", "#ElPais", "#España"]

# 👇 Случайный интервал между постами: от 5 до 10 минут
# (Instagram строже к большим объёмам, чем Threads)
MIN_INTERVAL_MINUTES = 5
MAX_INTERVAL_MINUTES = 10
# =================================================


# ---------- История ----------
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Не удалось прочитать историю: {e}")
    return {"posted": [], "cache_counter": 1, "last_scheduled_at": None}


def save_history(h):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)


# ---------- Парсинг RSS ----------
def extract_post_id(link):
    raw = link.rstrip("/").split("/")[-1].split("?")[0].split("#")[0]
    try:
        return int(raw)
    except ValueError:
        return None


def parse_text_div(text_div, link):
    title, hashtags, full_text = "", [], ""
    if text_div:
        for b in text_div.find_all('b'):
            t = b.get_text().strip()
            if t:
                title = t
                break
        for a in text_div.find_all('a'):
            t = a.get_text().strip()
            if t.startswith('#') and t not in hashtags:
                hashtags.append(t)
        for br in text_div.find_all('br'):
            br.replace_with('\n')
        full_text = text_div.get_text()

    if not link.startswith('http'):
        link = 'https://' + link

    return {
        "link": link,
        "title": title or "Новость ЭльПаис",
        "hashtags": hashtags,
        "full_text": full_text,
    }


def fetch_all_rss_news(cache_counter):
    bridge_url = f"{BRIDGE_URL}&_cache_timeout={cache_counter}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(bridge_url, headers=headers, timeout=15)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка доступа к RSS-Bridge: {e}")
        return {}

    soup = BeautifulSoup(r.text, 'html.parser')
    items = soup.find_all('section', class_='feeditem')
    if not items:
        items = soup.find_all('div', class_='item') or soup.find_all('article')

    news_dict = {}
    for item in items:
        link_tag = item.find('a', class_='itemtitle')
        link = link_tag.get('href') if link_tag else None
        if not link:
            continue
        pid = extract_post_id(link)
        if pid is None:
            continue
        text_div = item.find('div', class_='tgme_widget_message_text')
        news_dict[pid] = parse_text_div(text_div, link)

    print(f"🔍 Постов в RSS-ленте: {len(news_dict)}")
    if news_dict:
        ids = sorted(news_dict.keys())
        print(f"🔍 Номера в ленте (int): {ids[:40]}")
    return news_dict


def get_available_banner_ids():
    if not os.path.isdir(BANNERS_DIR):
        print(f"❌ Папка {BANNERS_DIR} не найдена.")
        return []
    ids = []
    for f in os.listdir(BANNERS_DIR):
        m = re.match(r'^(\d+)\.(jpg|jpeg|png)$', f, re.IGNORECASE)
        if m:
            ids.append(int(m.group(1)))
    return sorted(ids)


# ---------- Сборка подписи ----------
def build_caption(news):
    title    = news["title"]
    hashtags = news["hashtags"]
    body     = news["full_text"]

    for h in hashtags:
        body = body.replace(h, '')
    
    body = re.sub(r'https?://t\.me/\S+', '', body)
    body = re.sub(r'https?://elpais\.com/\S+', '', body)
    body = re.sub(r'(?<!\w)t\.me/\S+', '', body)
    
    lines = []
    for line in body.split('\n'):
        s = line.strip()
        s_lower = s.lower()
        if 'читать в телеграм' in s_lower or 'читать оригинал' in s_lower:
            continue
        if not s or re.match(r'^[\U0001F000-\U0001FFFF\U00002600-\U000027BF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002702-\U000027B0\U000024C2-\U0001F251\U0001F300-\U0001F5FF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+$', s):
            continue
        lines.append(s)
    body = '\n'.join(lines)

    if title and body.strip().startswith(title):
        body = body.strip()[len(title):].strip()
    body = re.sub(r'\n{3,}', '\n\n', body).strip()

    tags = []
    for h in hashtags:
        if len(tags) >= 5:
            break
        if h.lower() not in [x.lower() for x in tags]:
            tags.append(h)
    for d in DEFAULT_TAGS:
        if len(tags) >= 5:
            break
        if d.lower() not in [x.lower() for x in tags]:
            tags.append(d)
    tags_line = ' '.join(tags[:5])

    link_line = f"Читать в телеграм 👉 {news['link']}"

    fixed = len(title) + len(tags_line) + len(link_line) + 6
    avail = MAX_CAPTION - fixed
    if len(body) > avail:
        body = body[:max(avail, 0)].rstrip() + '…'

    parts = [title]
    if body:
        parts.append(body)
    parts.append(tags_line)
    parts.append(link_line)
    return '\n\n'.join(parts)


# ---------- Buffer API ----------
def buffer_graphql(token, query):
    r = requests.post(BUFFER_API,
                      headers={"Content-Type": "application/json",
                               "Authorization": f"Bearer {token}"},
                      json={"query": query}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("errors"):
        raise Exception(f"GraphQL error: {data['errors']}")
    return data["data"]


def get_instagram_channel_id(token):
    data = buffer_graphql(token, "query { account { organizations { id name } } }")
    orgs = data["account"]["organizations"]
    if not orgs:
        raise Exception("В аккаунте Buffer нет организаций")
    org_id = orgs[0]["id"]
    data = buffer_graphql(token,
        'query { channels(input: { organizationId: "%s" }) { id name service } }' % org_id)
    channels = data.get("channels", [])
    for ch in channels:
        if ch.get("service") == "instagram":
            print(f"📸 Найден Instagram-канал: {ch['name']}")
            return ch["id"]
    raise Exception("К Buffer не подключен Instagram-канал")


def buffer_schedule_instagram_post(token, channel_id, text, image_url, scheduled_at):
    """Планирует Instagram-пост на конкретное время через customScheduled + dueAt"""
    text_lit = json.dumps(text, ensure_ascii=False)
    ch_lit   = json.dumps(channel_id)
    url_lit  = json.dumps(image_url)
    # 👇 Формат ISO 8601 с миллисекундами, как в документации Buffer
    due_lit = json.dumps(scheduled_at.strftime("%Y-%m-%dT%H:%M:%S.000Z"))

    query = f'''mutation {{
  createPost(input: {{
    text: {text_lit},
    channelId: {ch_lit},
    schedulingType: automatic,
    mode: customScheduled,
    dueAt: {due_lit},
    assets: [{{ image: {{ url: {url_lit} }} }}],
    metadata: {{
      instagram: {{
        type: post,
        shouldShareToFeed: true
      }}
    }}
  }}) {{
    ... on PostActionSuccess {{ post {{ id text status dueAt }} }}
    ... on MutationError {{ message }}
  }}
}}'''
    data = buffer_graphql(token, query)
    res = data.get("createPost", {})
    if res.get("post"):
        return True, res["post"].get("id")
    return False, res.get("message", "неизвестная ошибка Buffer")


# ---------- Главный сценарий ----------
def main():
    print("=" * 60)
    print("🚀 Запуск генерации очереди Instagram-постов")
    print("=" * 60)

    token = os.environ.get("BUFFER_API_KEY", "")
    if not token:
        print("⚠️ BUFFER_API_KEY не задан в секретах — выходим.")
        return
    if not os.environ.get("GITHUB_REPOSITORY"):
        print("❌ Запуск вне GitHub Actions (нет GITHUB_REPOSITORY).")
        return

    history    = load_history()
    posted_ids = set(history.get("posted", []))
    last_scheduled_str = history.get("last_scheduled_at")

    # Парсим время последнего запланированного поста
    now = datetime.now(timezone.utc)
    if last_scheduled_str:
        try:
            last_scheduled = datetime.fromisoformat(last_scheduled_str.replace("Z", "+00:00"))
        except Exception:
            last_scheduled = now
    else:
        last_scheduled = now

    print(f"🕐 Текущее время (UTC): {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📅 Последний запланированный Instagram-пост: {last_scheduled.strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. Получаем все новости из RSS
    cache_counter = history.get("cache_counter", 1)
    rss_news = fetch_all_rss_news(cache_counter)
    history["cache_counter"] = cache_counter + 1

    if not rss_news:
        print("❌ Не удалось получить новости из RSS. Завершаемся.")
        save_history(history)
        return

    rss_ids = set(rss_news.keys())
    print(f"📋 Доступно в RSS (int): {sorted(rss_ids)}")

    # 2. Получаем готовые баннеры
    banner_ids = set(get_available_banner_ids())
    print(f"🖼 Доступно баннеров (int): {sorted(banner_ids)}")

    # 3. Приводим posted_ids к INT
    posted_int_ids = set()
    for pid in posted_ids:
        try:
            posted_int_ids.add(int(pid))
        except ValueError:
            pass

    # 4. Находим кандидатов
    candidates = sorted(list((rss_ids & banner_ids) - posted_int_ids))

    print(f"📊 Пересечение (RSS ∩ баннеры): {sorted(rss_ids & banner_ids)}")
    print(f"📊 Уже запощено: {sorted(posted_int_ids)}")
    print(f"🎯 Кандидаты к публикации: {candidates}")

    if not candidates:
        print("😴 Нет свободных баннеров с актуальным текстом в RSS. Ждём.")
        save_history(history)
        return

    # Получаем ID канала Buffer
    try:
        channel_id = get_instagram_channel_id(token)
    except Exception as e:
        print(f"❌ Ошибка получения канала: {e}")
        save_history(history)
        return

    repo   = os.environ.get("GITHUB_REPOSITORY", "")
    branch = os.environ.get("GITHUB_REF_NAME", "main")

    # Стартовый слот: max(сейчас, last_scheduled + мин. интервал)
    current_slot = max(now, last_scheduled + timedelta(minutes=MIN_INTERVAL_MINUTES))

    scheduled_posts = []
    new_last_scheduled = last_scheduled

    # Планируем каждого кандидата со случайным интервалом 5-10 минут
    for target_id in candidates:
        interval_seconds = random.randint(MIN_INTERVAL_MINUTES * 60, MAX_INTERVAL_MINUTES * 60)
        current_slot = current_slot + timedelta(seconds=interval_seconds)

        target_str = str(target_id)
        banner_path = f"{BANNERS_DIR}/{target_str}.jpg"
        news = rss_news[target_id]

        print(f"\n🎯 Готовим баннер: {banner_path}")
        print(f"📝 Заголовок: {news['title']}")

        caption = build_caption(news)
        image_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{banner_path}"

        print(f"🕐 Планируем на: {current_slot.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        try:
            ok, info = buffer_schedule_instagram_post(token, channel_id, caption, image_url, current_slot)
            if ok:
                print(f"✅ Запланировано (Buffer id: {info})")
                scheduled_posts.append(target_str)
                new_last_scheduled = current_slot
            else:
                print(f"❌ Ошибка планирования: {info}")
        except Exception as e:
            print(f"❌ Исключение: {e}")
            continue

        # Небольшая задержка между запросами к Buffer
        time.sleep(1)

    # Обновляем историю
    if scheduled_posts:
        for pid in scheduled_posts:
            posted_ids.add(pid)
        history["posted"] = sorted(list(posted_ids))[-500:]
        history["last_scheduled_at"] = new_last_scheduled.strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"\n📦 Запланировано {len(scheduled_posts)} Instagram-постов в очередь Buffer")
        print(f"🕐 Последний пост в очереди: {new_last_scheduled.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    else:
        print("\n⚠️ Ни один пост не был запланирован")

    save_history(history)
    print("💾 История обновлена.")
    print("=" * 60)


if __name__ == "__main__":
    main()
