import os
import re
import json
import requests
from bs4 import BeautifulSoup

# ================== НАСТРОЙКИ ==================
BRIDGE_URL = "https://rss-bridge.org/bridge01/?action=display&username=elpaisru&bridge=TelegramBridge&format=Html"
BUFFER_API = "https://api.buffer.com"

HISTORY_FILE = "threads_posted_history.json"
BANNERS_DIR  = "banners"

MAX_TEXT_LENGTH = 500
# Убираем топик или делаем нейтральным — иногда это триггерит модерацию
TOPIC_TAG = None  # Можно попробовать "news" или None
# =================================================


# ---------- История ----------
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Не удалось прочитать историю: {e}")
    return {"posted": [], "cache_counter": 1}


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
    title_raw, full_text = "", ""
    if text_div:
        # Заголовок = первый <b>
        for b in text_div.find_all('b'):
            raw = b.get_text().strip()
            if raw:
                title_raw = raw
                break
        # Полный текст с переносами
        for br in text_div.find_all('br'):
            br.replace_with('\n')
        full_text = text_div.get_text()

    if not link.startswith('http'):
        link = 'https://' + link

    return {
        "link": link,
        "title_raw": title_raw or "Новость ЭльПаис",
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


# ---------- Форматирование текста для Threads ----------
def tweet_len(text):
    n = 0
    for ch in text:
        o = ord(ch)
        if o >= 0x1000 or 0x2600 <= o <= 0x27BF or 0x2B00 <= o <= 0x2BFF or 0xFE00 <= o <= 0xFE0F:
            n += 2
        else:
            n += 1
    return n


def build_threads_text(title_raw, full_text):
    """Берём заголовок + первые 2-3 предложения из текста"""
    # Убираем хештеги и ссылки из текста
    clean_text = full_text
    clean_text = re.sub(r'#[^\s#]+', '', clean_text)  # убираем хештеги
    clean_text = re.sub(r'https?://\S+', '', clean_text)  # убираем ссылки
    clean_text = re.sub(r'(?<!\w)t\.me/\S+', '', clean_text)
    
    # Разбиваем на предложения
    sentences = re.split(r'(?<=[.!?])\s+', clean_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    
    # Берём первые 2-3 предложения (но не более 300 символов)
    body = ""
    for sent in sentences[:3]:
        if tweet_len(body + " " + sent) < 300:
            body += (" " if body else "") + sent
    
    # Собираем финальный текст: заголовок + тело
    title = title_raw.strip()
    if tweet_len(title) > 150:
        title = title[:147] + "…"
    
    available = MAX_TEXT_LENGTH - tweet_len(title) - 10
    if tweet_len(body) > available:
        body = body[:max(available - 3, 0)] + "…"
    
    if body:
        return f"{title}\n\n{body}"
    return title


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


def get_threads_channel_id(token):
    data = buffer_graphql(token, "query { account { organizations { id name } } }")
    orgs = data["account"]["organizations"]
    if not orgs:
        raise Exception("В аккаунте Buffer нет организаций")
    org_id = orgs[0]["id"]
    data = buffer_graphql(token,
        'query { channels(input: { organizationId: "%s" }) { id name service } }' % org_id)
    channels = data.get("channels", [])
    for ch in channels:
        if ch.get("service") == "threads":
            print(f"🧵 Найден Threads-канал: {ch['name']}")
            return ch["id"]
    raise Exception("К Buffer не подключен Threads-канал")


def buffer_create_threads_post_with_reply(token, channel_id, main_text, reply_text, image_url, topic_tag=None):
    """Создаёт тред в Threads: основной пост + первый комментарий (reply)"""
    text_lit = json.dumps(main_text, ensure_ascii=False)
    reply_lit = json.dumps(reply_text, ensure_ascii=False)
    ch_lit   = json.dumps(channel_id)
    url_lit  = json.dumps(image_url)
    
    # Формируем metadata с топиком (если есть)
    if topic_tag:
        topic_lit = json.dumps(topic_tag, ensure_ascii=False)
        threads_metadata = f'''threads: {{
        topic: {topic_lit},
        thread: [
          {{
            text: {text_lit},
            assets: [{{ image: {{ url: {url_lit} }} }}]
          }},
          {{
            text: {reply_lit}
          }}
        ]
      }}'''
    else:
        threads_metadata = f'''threads: {{
        thread: [
          {{
            text: {text_lit},
            assets: [{{ image: {{ url: {url_lit} }} }}]
          }},
          {{
            text: {reply_lit}
          }}
        ]
      }}'''
    
    query = f'''mutation {{
  createPost(input: {{
    text: {text_lit},
    channelId: {ch_lit},
    schedulingType: automatic,
    mode: shareNow,
    metadata: {{
      {threads_metadata}
    }}
  }}) {{
    ... on PostActionSuccess {{ post {{ id text status dueAt }} }}
    ... on MutationError {{ message }}
  }}
}}'''
    data = buffer_graphql(token, query)
    res = data.get("createPost", {})
    if res.get("post"):
        post = res["post"]
        status = post.get("status")
        due_at = post.get("dueAt")
        print(f"📊 Статус поста в Buffer: {status}")
        if due_at:
            print(f"📅 Запланирован на: {due_at}")
        if status in ["sent", "published"]:
            return True, post.get("id")
        elif status in ["pending", "scheduled"]:
            print(f"⏳ Пост запланирован, но еще не опубликован (статус: {status})")
            return True, post.get("id")
        else:
            print(f"⚠️ Неожиданный статус: {status}")
            return True, post.get("id")
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

    cache_counter = history.get("cache_counter", 1)
    rss_news = fetch_all_rss_news(cache_counter)
    history["cache_counter"] = cache_counter + 1

    if not rss_news:
        print("❌ Не удалось получить новости из RSS. Завершаемся.")
        save_history(history)
        return

    rss_ids = set(rss_news.keys())
    print(f"📋 Доступно в RSS (int): {sorted(rss_ids)}")

    banner_ids = set(get_available_banner_ids())
    print(f"🖼 Доступно баннеров (int): {sorted(banner_ids)}")

    posted_int_ids = set()
    for pid in posted_ids:
        try:
            posted_int_ids.add(int(pid))
        except ValueError:
            pass

    candidates = sorted(list((rss_ids & banner_ids) - posted_int_ids))

    print(f"📊 Пересечение (RSS ∩ баннеры): {sorted(rss_ids & banner_ids)}")
    print(f"📊 Уже запощено: {sorted(posted_int_ids)}")
    print(f"🎯 Кандидаты к публикации: {candidates}")

    if not candidates:
        print("😴 Нет свободных баннеров с актуальным текстом в RSS. Ждём.")
        save_history(history)
        return

    target_id = candidates[0]
    target_str = str(target_id)
    banner_path = f"{BANNERS_DIR}/{target_str}.jpg"
    news = rss_news[target_id]

    print(f"\n🎯 Публикуем баннер: {banner_path}")
    print(f"📝 Заголовок: {news['title_raw']}")

    # Теперь берём заголовок + часть текста новости
    main_text = build_threads_text(news['title_raw'], news['full_text'])
    reply_text = f"Читать в телеграм 👉 {news['link']}"
    
    print(f"📝 Основной текст:\n{main_text}\n")
    print(f"💬 Комментарий (reply):\n{reply_text}\n")
    print(f"🏷️ Топик: {TOPIC_TAG or 'не указан'}\n")

    repo   = os.environ.get("GITHUB_REPOSITORY", "")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    image_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{banner_path}"
    print(f"🖼 Картинка: {image_url}")

    try:
        channel_id = get_threads_channel_id(token)
        ok, info = buffer_create_threads_post_with_reply(token, channel_id, main_text, reply_text, image_url, TOPIC_TAG)
    except Exception as e:
        ok, info = False, str(e)

    already = ("already got this one scheduled" in str(info)
               or "same thing twice" in str(info))

    if ok or already:
        if already:
            print("⚠️ Buffer сообщает, что пост уже запланирован. Помечаем как запощенный.")
        else:
            print(f"✅ Пост принят Buffer, id: {info}")
        posted_ids.add(target_str)
        history["posted"] = sorted(list(posted_ids))[-500:]
        save_history(history)
        print("💾 История обновлена.")
    else:
        print(f"❌ Buffer не опубликовал: {info}. Повторим в следующем запуске.")


if __name__ == "__main__":
    main()
