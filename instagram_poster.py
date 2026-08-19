import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup

# --- Конфигурация ---
BRIDGE_URL = "https://rss-bridge.org/bridge01/?action=display&username=elpaisru&bridge=TelegramBridge&format=Html"
HISTORY_FILE = "ig_history.json"
BANNERS_DIR = "banners"

IG_USER_ID = os.environ.get("IG_USER_ID")
IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN")


def upload_to_catbox(image_path):
    """Загружает локальный файл на публичный хостинг, чтобы Instagram API смог его скачать"""
    with open(image_path, "rb") as f:
        files = {"fileToUpload": f, "reqtype": (None, "fileupload")}
        r = requests.post("https://catbox.moe/user/api.php", files=files, timeout=60)
    if r.status_code == 200 and r.text.startswith("http"):
        return r.text.strip()
    raise Exception(f"Ошибка загрузки на catbox: {r.status_code} {r.text}")


def get_all_posts_from_rss_bridge(cache_counter):
    """Получает словарь постов из RSS, где ключ — это ID поста (например, '100')"""
    bridge_url = f"{BRIDGE_URL}&_cache_timeout={cache_counter}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(bridge_url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка доступа к RSS-Bridge: {e}")
        return {}

    soup = BeautifulSoup(response.text, 'html.parser')
    items = soup.find_all('section', class_='feeditem')
    if not items:
        items = soup.find_all('div', class_='item') or soup.find_all('article')

    posts = {}
    for item in items:
        link_tag = item.find('a', class_='itemtitle')
        link = link_tag.get('href') if link_tag else None
        if not link:
            continue
            
        post_id = link.rstrip("/").split("/")[-1]

        full_text = ""
        text_div = item.find('div', class_='tgme_widget_message_text')
        if text_div:
            for br in text_div.find_all('br'):
                br.replace_with('\n')
            raw = text_div.get_text()
            lines = [ln.strip() for ln in raw.split('\n')]
            full_text = re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()
            
        posts[post_id] = {
            "link": link,
            "full_text": full_text
        }
    return posts


def build_caption(post_data, post_id):
    """Формирует описание для Инстаграма"""
    if post_data:
        caption = post_data["full_text"] or "Новость ЭльПаис"
        link = post_data["link"]
    else:
        # Фолбек, если пост слишком старый и уже выпал из RSS-ленты
        caption = "Новость ЭльПаис"
        link = f"https://t.me/elpaisru/{post_id}"
        
    mandatory_tags = ["#новости", "#эльпаис"]
    for tag in mandatory_tags:
        if tag.lower() not in caption.lower():
            caption += "\n" + tag
            
    caption += f"\n\nЧитать в телеграм 👉 {link}"
    
    # Жесткий лимит Instagram
    if len(caption) > 2200:  
        caption = caption[:2196].rstrip() + " …"
    return caption


def post_to_instagram(local_image_path, caption):
    """Создает контейнер и публикует пост"""
    print("   ⬆️ Загружаем картинку на публичный хостинг (catbox)...")
    image_url = upload_to_catbox(local_image_path)
    
    r = requests.post(
        f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media",
        data={"image_url": image_url, "caption": caption, "access_token": IG_ACCESS_TOKEN},
        timeout=30)
    data = r.json()

    if "id" not in data:
        raise Exception(f"Ошибка создания контейнера IG: {data}")

    container_id = data["id"]
    
    # Ждем, пока сервера Meta обработают картинку
    for _ in range(24):
        st = requests.get(f"https://graph.facebook.com/v19.0/{container_id}",
                          params={"fields": "status_code", "access_token": IG_ACCESS_TOKEN},
                          timeout=15).json()
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise Exception(f"Ошибка обработки контейнера: {st}")
        time.sleep(5)

    # Финальная публикация
    pub = requests.post(f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish",
                        data={"creation_id": container_id, "access_token": IG_ACCESS_TOKEN},
                        timeout=30).json()
    if "id" not in pub:
        raise Exception(f"Ошибка публикации: {pub}")
    return pub["id"]


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Не удалось прочитать историю: {e}")
    return {"processed": [], "cache_counter": 1}


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def main():
    if not IG_USER_ID or not IG_ACCESS_TOKEN:
        print("❌ Не заданы секреты IG_USER_ID / IG_ACCESS_TOKEN.")
        return

    # --- ШАГ 1. Проверка папки с баннерами ---
    if not os.path.isdir(BANNERS_DIR):
        print(f"❌ Папка {BANNERS_DIR} не найдена.")
        return

    banner_files = [f for f in os.listdir(BANNERS_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    if not banner_files:
        print("😴 В папке banners нет файлов.")
        return

    history = load_history()
    processed = set(history.get("processed", []))
    
    # Ищем новые баннеры, которых еще нет в истории
    new_banners = []
    for f in banner_files:
        # Извлекаем только цифры из имени файла (например, '100.jpg' -> '100')
        post_id = re.sub(r'\D', '', f) 
        if post_id and post_id not in processed:
            new_banners.append((int(post_id), f))
            
    # --- ШАГ 2. Если новых нет — выходим ---
    if not new_banners:
        print("😴 Новых баннеров нет. Завершаем работу.")
        return
        
    # Сортируем по ID (от меньшего к большему), чтобы постить по порядку
    new_banners.sort(key=lambda x: x[0])
    print(f"🎯 Найдено новых баннеров для публикации: {len(new_banners)}")
    
    # --- ШАГ 3. Тянем тексты из RSS ---
    cache_counter = history.get("cache_counter", 1)
    rss_posts = get_all_posts_from_rss_bridge(cache_counter)
    history["cache_counter"] = cache_counter + 1

    # --- ШАГ 4. Публикация ---
    for post_id, filename in new_banners:
        print(f"➡️ Обрабатываем баннер: {filename} (ID: {post_id})")
        
        post_data = rss_posts.get(str(post_id))
        caption = build_caption(post_data, post_id)
        local_path = os.path.join(BANNERS_DIR, filename)
        
        try:
            ig_id = post_to_instagram(local_path, caption)
            print(f"✅ Опубликовано в Instagram (id={ig_id})")
            processed.add(str(post_id))
            
            # Храним только последние 500 ID, чтобы файл не раздувался
            history["processed"] = sorted(list(processed))[-500:]
            save_history(history)
            
        except Exception as e:
            print(f"❌ Ошибка при публикации {filename}: {e}")
            save_history(history)
            break # Прерываем цикл, чтобы не спамить, если API лег
            
    print("💾 Работа завершена.")


if __name__ == "__main__":
    main()
