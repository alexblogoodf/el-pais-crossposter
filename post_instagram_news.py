import os
import re
import json
import requests
from bs4 import BeautifulSoup

# ================== НАСТРОЙКИ ==================
BRIDGE_URL = "https://rss-bridge.org/bridge01/?action=display&username=elpaisru&bridge=TelegramBridge&format=Html"
BUFFER_API = "https://api.buffer.com"

HISTORY_FILE = "instagram_posted_history.json"
BANNERS_DIR  = "banners"

START_FROM_ID = 105          # 👈 начинаем с 105.jpg
MAX_CAPTION   = 2100
MAX_RETRIES   = 5            # сколько запусков пробовать, прежде чем пометить пост пропущенным

DEFAULT_TAGS = ["#новости", "#эльпаис", "#Испания", "#ElPais", "#España"]
# =================================================


# ---------- История ----------
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Не удалось прочитать историю: {e}")
    return {"posted": [], "cache_counter": 1, "retry_counts": {}}


def save_history(h):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)


# ---------- Поиск готовых баннеров ----------
def get_available_banner_ids():
    if not os.path.isdir(BANNERS_DIR):
        print(f"❌ Папка {BANNERS_DIR} не найдена.")
        return []
    ids = []
    for f in os.listdir(BANNERS_DIR):
        m = re.match(r'^(\d+)\.(jpg|jpeg|png)$', f, re.IGNORECASE)
        if m:
            ids.append(int(m.group(1)))
    return ids


# ---------- RSS: получаем текст новости по номеру ----------
def extract_post_id(link):
    """Извлекает номер поста из ссылки тем же способом, что и main-9.py"""
    return link.rstrip("/").split("/")[-1].split("?")[0].split("#")[0]


def fetch_news_by_id(target_id, cache_counter):
    bridge_url = f"{BRIDGE_URL}&_cache_timeout={cache_counter}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(bridge_url, headers=headers, timeout=15)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка доступа к RSS-Bridge: {e}")
        return None

    soup = BeautifulSoup(r.text, 'html.parser')
    items = soup.find_all('section', class_='feeditem')
    if not items:
        items = soup.find_all('div', class_='item') or soup.find_all('article')

    print(f"🔍 Постов в RSS-ленте: {len(items)}")

    # Отладка: выводим все номера, которые видим в ленте
    all_ids = []
    for item in items:
        link_tag = item.find('a', class_='itemtitle')
        link = link_tag.get('href') if link_tag else None
        if not link:
            continue
        all_ids.append(extract_post_id(link))
    print(f"🔍 Номера в ленте: {', '.join(all_ids[:40])}")
    print(f"🎯 Ищем номер: {target_id}")

    for item in items:
        link_tag = item.find('a', class_='itemtitle')
        link = link_tag.get('href') if link_tag else None
        if not link:
            continue
        pid = extract_post_id(link)
        try:
            if int(pid) == target_id:
                return parse_news_item(item, link)
        except ValueError:
            continue
    return None


def parse_news_item(item, link):
    text_div = item.find('div', class_='tgme_widget_message_text')
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


# ---------- Сборка подписи ----------
def build_caption(news):
    title    = news["title"]
    hashtags = news["hashtags"]
    body     = news["full_text"]

    for h in hashtags:
        body = body.replace(h, '')
    body = re.sub(r'https?://t\.me/\S+', '', body)
    body = re.sub(r'(?<!\w)t\.me/\S+', '', body)
    lines = []
    for line in body.split('\n'):
        s = line.strip()
        if 'читать в телеграм' in s.lower():
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


def buffer_create_instagram_post(token, channel_id, text, image_url):
    text_lit = json.dumps(text, ensure_ascii=False)
    ch_lit   = json.dumps(channel_id)
    url_lit  = json.dumps(image_url)
    query = f'''mutation {{
  createPost(input: {{
    text: {text_lit},
    channelId: {ch_lit},
    schedulingType: automatic,
    mode: shareNow,
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
    token = os.environ.get("BUFFER_API_KEY", "")
    if not token:
        print("⚠️ BUFFER_API_KEY не задан в секретах — выходим.")
        return
    if not os.environ.get("GITHUB_REPOSITORY"):
        print("❌ Запуск вне GitHub Actions (нет GITHUB_REPOSITORY).")
        return

    history    = load_history()
    posted_ids = set(history.get("posted", []))
    retries    = history.get("retry_counts", {})

    available  = get_available_banner_ids()
    candidates = sorted([b for b in available
                         if b >= START_FROM_ID and str(b) not in posted_ids])

    if not candidates:
        print("😴 Свободных готовых баннеров нет. Ждём следующую новость.")
        return

    target_id   = candidates[0]
    banner_path = f"{BANNERS_DIR}/{target_id}.jpg"
    print(f"🎯 Публикуем баннер: {banner_path}")

    cache_counter = history.get("cache_counter", 1)
    news = fetch_news_by_id(target_id, cache_counter)
    history["cache_counter"] = cache_counter + 1

    if not news:
        count = retries.get(str(target_id), 0) + 1
        retries[str(target_id)] = count
        history["retry_counts"] = retries

        if count >= MAX_RETRIES:
            print(f"⚠️ Новость ID {target_id} не найдена после {count} попыток. Помечаем пропущенной.")
            posted_ids.add(str(target_id))
            history["posted"] = sorted(posted_ids)[-500:]
            retries.pop(str(target_id), None)
            history["retry_counts"] = retries
        else:
            print(f"⚠️ Новость ID {target_id} не найдена в RSS (попытка {count}/{MAX_RETRIES}). Попробуем в следующем запуске.")
        save_history(history)
        return

    caption = build_caption(news)
    print(f"📝 Подпись:\n{caption}\n")

    repo   = os.environ.get("GITHUB_REPOSITORY", "")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    image_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{banner_path}"
    print(f"🖼 Картинка: {image_url}")

    try:
        channel_id = get_instagram_channel_id(token)
        ok, info = buffer_create_instagram_post(token, channel_id, caption, image_url)
    except Exception as e:
        ok, info = False, str(e)

    already = ("already got this one scheduled" in str(info)
               or "same thing twice" in str(info))
    if ok or already:
        if already:
            print("⚠️ Buffer сообщает, что пост уже запланирован. Помечаем как запощенный.")
        else:
            print(f"✅ Пост принят Buffer, id: {info}")
        posted_ids.add(str(target_id))
        history["posted"] = sorted(posted_ids)[-500:]
        retries.pop(str(target_id), None)
        history["retry_counts"] = retries
        save_history(history)
        print("💾 История обновлена.")
    else:
        print(f"❌ Buffer не опубликовал: {info}. Повторим в следующем запуске.")


if __name__ == "__main__":
    main()
