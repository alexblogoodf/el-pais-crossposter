import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup

# ================== НАСТРОЙКИ ==================
BRIDGE_URL = "https://rss-bridge.org/bridge01/?action=display&username=elpaisru&bridge=TelegramBridge&format=Html"

HISTORY_FILE = "threads_posted_history.json"
BANNERS_DIR  = "banners"

MAX_TEXT_LENGTH = 500
TOPIC_TAG = "Испания"  # Изменили с "Новости" на "Испания"

# Threads Graph API
ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN")
USER_ID = os.environ.get("THREADS_USER_ID")
GRAPH_URL = "https://graph.threads.net/v1.0"
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
    """Извлекает номер поста из ссылки: https://t.me/elpaisru/107 -> 107 (как int)"""
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
    """Возвращает словарь {int_ID: {title_raw, full_text, link}} всех постов из RSS"""
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
    """Возвращает список int-номеров баннеров из папки banners/"""
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
    """Подсчёт длины текста с учётом эмодзи (как в Twitter)"""
    n = 0
    for ch in text:
        o = ord(ch)
        if o >= 0x1000 or 0x2600 <= o <= 0x27BF or 0x2B00 <= o <= 0x2BFF or 0xFE00 <= o <= 0xFE0F:
            n += 2
        else:
            n += 1
    return n


def build_threads_text(title_raw):
    """Формирует текст для Threads: только заголовок (без ссылки, без хештегов)"""
    available = MAX_TEXT_LENGTH
    title = title_raw.strip()
    
    if tweet_len(title) > available:
        while title and tweet_len(title) > available - 1:
            title = title[:-1]
        title = title.rstrip() + "…"
    
    return title


# ---------- Threads Graph API ----------
def create_threads_container(text, image_url, topic_tag=None):
    """Создаёт контейнер для основного поста"""
    url = f"{GRAPH_URL}/{USER_ID}/threads"
    payload = {
        "access_token": ACCESS_TOKEN,
        "text": text,
        "media_type": "IMAGE",
        "image_url": image_url
    }
    if topic_tag:
        payload["topic_tag"] = topic_tag
    
    res = requests.post(url, data=payload, timeout=30).json()
    if "id" not in res:
        raise Exception(f"Ошибка создания контейнера: {res}")
    return res["id"]


def create_reply_container(text, reply_to_id):
    """Создаёт контейнер для комментария (reply)"""
    url = f"{GRAPH_URL}/{USER_ID}/threads"
    payload = {
        "access_token": ACCESS_TOKEN,
        "text": text,
        "media_type": "TEXT",
        "reply_to_id": reply_to_id
    }
    
    res = requests.post(url, data=payload, timeout=30).json()
    if "id" not in res:
        raise Exception(f"Ошибка создания reply-контейнера: {res}")
    return res["id"]


def publish_container(creation_id):
    """Публикует подготовленный контейнер"""
    url = f"{GRAPH_URL}/{USER_ID}/threads_publish"
    payload = {
        "access_token": ACCESS_TOKEN,
        "creation_id": creation_id
    }
    
    res = requests.post(url, data=payload, timeout=30).json()
    if "id" not in res:
        raise Exception(f"Ошибка публикации: {res}")
    return res["id"]


def check_container_status(container_id):
    """Проверяет статус обработки контейнера"""
    url = f"{GRAPH_URL}/{container_id}"
    payload = {
        "access_token": ACCESS_TOKEN,
        "fields": "status,error_message"
    }
    
    # Ждём 15 секунд перед первой проверкой
    time.sleep(15)
    
    max_attempts = 8
    for attempt in range(max_attempts):
        res = requests.get(url, params=payload, timeout=15).json()
        status = res.get("status")
        
        if status == "FINISHED":
            return True
        elif status == "ERROR":
            raise Exception(f"Ошибка обработки: {res.get('error_message')}")
        
        # Если ещё в процессе, ждём ещё 10 секунд
        time.sleep(10)
    
    raise Exception("Таймаут: Threads не успел обработать картинку за 90 секунд")


# ---------- Главный сценарий ----------
def main():
    if not ACCESS_TOKEN or not USER_ID:
        print("⚠️ THREADS_ACCESS_TOKEN или THREADS_USER_ID не заданы в секретах — выходим.")
        return
    if not os.environ.get("GITHUB_REPOSITORY"):
        print("❌ Запуск вне GitHub Actions (нет GITHUB_REPOSITORY).")
        return

    history    = load_history()
    posted_ids = set(history.get("posted", []))

    # 1. Получаем все новости из RSS (ключи — INT)
    cache_counter = history.get("cache_counter", 1)
    rss_news = fetch_all_rss_news(cache_counter)
    history["cache_counter"] = cache_counter + 1

    if not rss_news:
        print("❌ Не удалось получить новости из RSS. Завершаемся.")
        save_history(history)
        return

    rss_ids = set(rss_news.keys())
    print(f"📋 Доступно в RSS (int): {sorted(rss_ids)}")

    # 2. Получаем все готовые баннеры (INT)
    banner_ids = set(get_available_banner_ids())
    print(f"🖼 Доступно баннеров (int): {sorted(banner_ids)}")

    # 3. Приводим posted_ids к INT для корректного сравнения
    posted_int_ids = set()
    for pid in posted_ids:
        try:
            posted_int_ids.add(int(pid))
        except ValueError:
            pass

    # 4. Находим пересечение: (есть в RSS) И (есть баннер) И (не запощено)
    candidates = sorted(list((rss_ids & banner_ids) - posted_int_ids))

    print(f"📊 Пересечение (RSS ∩ баннеры): {sorted(rss_ids & banner_ids)}")
    print(f"📊 Уже запощено: {sorted(posted_int_ids)}")
    print(f"🎯 Кандидаты к публикации: {candidates}")

    if not candidates:
        print("😴 Нет свободных баннеров с актуальным текстом в RSS. Ждём.")
        save_history(history)
        return

    # Берём самый ранний
    target_id = candidates[0]
    target_str = str(target_id)
    banner_path = f"{BANNERS_DIR}/{target_str}.jpg"
    news = rss_news[target_id]

    print(f"\n🎯 Публикуем баннер: {banner_path}")
    print(f"📝 Заголовок: {news['title_raw']}")

    # Основной пост: только заголовок
    main_text = build_threads_text(news['title_raw'])
    print(f"📝 Основной текст:\n{main_text}\n")
    print(f"🏷️ Топик: {TOPIC_TAG}\n")

    repo   = os.environ.get("GITHUB_REPOSITORY", "")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    image_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{banner_path}"
    print(f"🖼 Картинка: {image_url}")

    # Комментарий: ссылка на телеграм
    reply_text = f"Читать в телеграм 👉 {news['link']}"
    print(f"💬 Комментарий:\n{reply_text}\n")

    try:
        # 1. Создаём основной пост
        print("⏳ Создаём основной пост...")
        main_container_id = create_threads_container(main_text, image_url, TOPIC_TAG)
        print(f"✅ Основной контейнер создан: {main_container_id}")
        
        # 2. Ждём обработки картинки
        print("⏳ Ждём обработки картинки...")
        check_container_status(main_container_id)
        
        # 3. Публикуем основной пост
        print("⏳ Публикуем основной пост...")
        published_main_id = publish_container(main_container_id)
        print(f"✅ Основной пост опубликован! ID: {published_main_id}")
        
        # 4. Создаём комментарий
        time.sleep(3)  # Небольшая задержка перед созданием reply
        print("⏳ Создаём комментарий...")
        reply_container_id = create_reply_container(reply_text, published_main_id)
        print(f"✅ Контейнер комментария создан: {reply_container_id}")
        
        # 5. Публикуем комментарий
        time.sleep(2)
        print("⏳ Публикуем комментарий...")
        published_reply_id = publish_container(reply_container_id)
        print(f"✅ Комментарий опубликован! ID: {published_reply_id}")
        
        # Успех!
        posted_ids.add(target_str)
        history["posted"] = sorted(list(posted_ids))[-500:]
        save_history(history)
        print("💾 История обновлена.")
        
    except Exception as e:
        print(f"❌ Ошибка при публикации: {e}")
        save_history(history)


if __name__ == "__main__":
    main()
