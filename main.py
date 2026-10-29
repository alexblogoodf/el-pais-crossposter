import os
import re
import sys
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import cairosvg

BRIDGE_URL = "https://rss-bridge.org/bridge01/?action=display&username=elpaisru&bridge=TelegramBridge&format=Html"
HISTORY_FILE = "posted_history.json"
BUFFER_API = "https://api.buffer.com"

# Интервал между постами в очереди Buffer
POST_INTERVAL_MINUTES = 2

FALLBACK_IMAGES = {
    'people_with_flags.jpg': ['протест', 'митинг', 'демонстрация', 'акция', 'манифестация', 'pp', 'vox'],
    'government_building.jpg': ['правительство', 'парламент', 'закон', 'министр', 'санчес', 'конгресс', 'сенат', 'амнистия', 'депутат'],
    'police_officers.jpg': ['полиция', 'задержание', 'арест', 'миграция', 'мигрант', 'граница', 'сеута', 'мелилья', 'нелегал'],
    'city_life.jpg': ['мадрид', 'барселона', 'город', 'улица', 'район', 'валенси', 'севилья', 'малага'],
    'old_castle.jpg': ['история', 'культура', 'туризм', 'музей', 'собор', 'достопримечательность', 'архитектур'],
    'Flag_of_Spain.jpg': []
}


def remove_emojis(text):
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"
        "\u3030"
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text).strip()


def get_all_posts_from_rss_bridge(cache_counter):
    bridge_url = f"{BRIDGE_URL}&_cache_timeout={cache_counter}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(bridge_url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка доступа к RSS-Bridge: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    items = soup.find_all('section', class_='feeditem')
    if not items:
        items = soup.find_all('div', class_='item') or soup.find_all('article')

    posts = []
    for item in items:
        link_tag = item.find('a', class_='itemtitle')
        link = link_tag.get('href') if link_tag else None
        if not link:
            continue

        title_raw = ""
        hashtags = []
        text_div = item.find('div', class_='tgme_widget_message_text')
        if text_div:
            for b in text_div.find_all('b'):
                raw = b.get_text().strip()
                if remove_emojis(raw):
                    title_raw = raw
                    break
            for a in text_div.find_all('a'):
                t = a.get_text().strip()
                if t.startswith('#') and t not in hashtags:
                    hashtags.append(t)

        image_url = None
        blockquote = item.find('blockquote')
        if blockquote:
            img_tag = blockquote.find('img')
            if img_tag and img_tag.get('src'):
                image_url = img_tag.get('src')

        if not image_url:
            content_div = item.find('div', class_='item-content')
            if content_div:
                text_div = content_div.find('div', class_='tgme_widget_message_text')
                for img in content_div.find_all('img'):
                    if text_div and img.find_parent('div', class_='tgme_widget_message_text'):
                        continue
                    if img.get('src'):
                        image_url = img.get('src')
                        break

        posts.append({
            "link": link,
            "title_raw": title_raw or "Новость ЭльПаис",
            "title_clean": remove_emojis(title_raw) or "Новость ЭльПаис",
            "image_url": image_url,
            "hashtags": hashtags,
        })

    return posts


def tweet_len(text):
    n = 0
    for ch in text:
        o = ord(ch)
        if o >= 0x1000 or 0x2600 <= o <= 0x27BF or 0x2B00 <= o <= 0x2BFF or 0xFE00 <= o <= 0xFE0F:
            n += 2
        else:
            n += 1
    return n


def build_tweet_text(title_raw, link, hashtags=None):
    mandatory = ["#новости", "#эльпаис"]
    tags = []
    for t in (hashtags or []) + mandatory:
        t = t.strip()
        if t and t.lower() not in {x.lower() for x in tags}:
            tags.append(t)

    suffix = "\n\nЧитать в телеграм 👉 "

    while len(tags) > len(mandatory):
        tags_line = "\n\n" + " ".join(tags)
        if tweet_len(suffix) + 23 + tweet_len(tags_line) + 30 <= 280:
            break
        for i in range(len(tags) - 1, -1, -1):
            if tags[i].lower() not in {m.lower() for m in mandatory}:
                tags.pop(i)
                break
        else:
            break

    tags_line = "\n\n" + " ".join(tags)
    available = 280 - tweet_len(suffix) - 23 - tweet_len(tags_line)

    title = title_raw.strip()
    if tweet_len(title) > available:
        while title and tweet_len(title) > available - 1:
            title = title[:-1]
        title = title.rstrip() + "…"

    return f"{title}{suffix}{link}{tags_line}"


def select_fallback_image(title, text='', hashtags=None):
    combined_text = f"{title} {text} {' '.join(hashtags or [])}".lower()
    for img_name, keywords in FALLBACK_IMAGES.items():
        if not keywords:
            continue
        for keyword in keywords:
            if keyword in combined_text:
                img_path = f"images/{img_name}"
                if os.path.exists(img_path):
                    print(f"🖼️ Fallback выбран: {img_name} (совпадение: '{keyword}')")
                    return img_path

    default_img = "images/Flag_of_Spain.jpg"
    if os.path.exists(default_img):
        print(f"🖼️ Fallback по умолчанию: Flag_of_Spain.jpg")
        return default_img
    return None


def generate_card(image_url, title_text, fallback_context=None, output_path="banner.jpg"):
    img = None

    if image_url:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8"
        }
        for attempt in range(3):
            try:
                response = requests.get(image_url, headers=headers, timeout=15, stream=True)
                if response.status_code != 200:
                    print(f"⚠️ HTTP {response.status_code} (попытка {attempt+1}/3)")
                    if attempt < 2:
                        time.sleep(2 ** attempt)
                        continue
                    break
                content_type = response.headers.get('content-type', '')
                if not content_type.startswith('image/'):
                    print(f"⚠️ Не image, а {content_type}")
                    break
                with open("temp_src.jpg", "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                img = Image.open("temp_src.jpg").convert("RGBA")
                print(f"✅ Картинка загружена из Telegram CDN → {output_path}")
                break
            except (requests.exceptions.RequestException, IOError) as e:
                print(f"⚠️ Ошибка загрузки (попытка {attempt+1}/3): {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue

    if img is None and fallback_context:
        fallback_path = select_fallback_image(
            fallback_context.get('title', ''),
            fallback_context.get('text', ''),
            fallback_context.get('hashtags', [])
        )
        if fallback_path:
            try:
                img = Image.open(fallback_path).convert("RGBA")
            except Exception as e:
                print(f"⚠️ Fallback не открылся: {e}")

    if img is None:
        print("⚠️ Ни оригинала, ни fallback нет — используем чёрный фон")
        img = Image.new("RGBA", (1080, 1080), (30, 30, 30, 255))

    width, height = img.size
    min_side = min(width, height)
    img = img.crop(((width - min_side) / 2, (height - min_side) / 2,
                    (width + min_side) / 2, (height + min_side) / 2))
    img = img.resize((1080, 1080), Image.Resampling.LANCZOS)
    img = Image.alpha_composite(img, Image.new("RGBA", (1080, 1080), (0, 0, 0, 102)))

    txt_layer = Image.new("RGBA", (1080, 1080), (0, 0, 0, 0))
    draw = ImageDraw.Draw(txt_layer)

    try:
        font = ImageFont.truetype("Exo2-Black.ttf", 56)
    except Exception:
        font = ImageFont.load_default()

    def get_wrapped_lines(text, font, max_width):
        lines = []
        for paragraph in text.split("\n"):
            words = paragraph.split()
            current_line = ""
            for word in words:
                test_line = f"{current_line} {word}".strip()
                bbox = draw.textbbox((0, 0), test_line, font=font)
                if bbox[2] - bbox[0] <= max_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
        return lines

    lines = get_wrapped_lines(title_text, font, max_width=920)
    line_height = 70
    start_y = (1080 - len(lines) * line_height) / 2

    shadow_layer = Image.new("RGBA", (1080, 1080), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        shadow_draw.text(((1080 - (bbox[2] - bbox[0])) / 2, start_y + i * line_height),
                         line, font=font, fill=(0, 0, 0, 191))

    img = Image.alpha_composite(img, shadow_layer.filter(ImageFilter.GaussianBlur(30)))

    draw_final = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        bbox = draw_final.textbbox((0, 0), line, font=font)
        draw_final.text(((1080 - (bbox[2] - bbox[0])) / 2, start_y + i * line_height),
                        line, font=font, fill=(255, 255, 255, 255))

    try:
        if os.path.exists("logo.svg"):
            cairosvg.svg2png(url="logo.svg", write_to="logo_temp.png", output_width=320)
            logo = Image.open("logo_temp.png").convert("RGBA")
            img.paste(logo, (60, 60), logo)
    except Exception as e:
        print(f"⚠️ Ошибка при добавлении логотипа: {e}")

    img.convert("RGB").save(output_path, quality=95)

    for tf in ["temp_src.jpg", "logo_temp.png"]:
        if os.path.exists(tf):
            try:
                os.remove(tf)
            except Exception:
                pass

    return output_path


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


def get_buffer_channel_id(token):
    data = buffer_graphql(token, "query { account { organizations { id name } } }")
    orgs = data["account"]["organizations"]
    if not orgs:
        raise Exception("В аккаунте Buffer нет организаций")

    data = buffer_graphql(token,
        'query { channels(input: { organizationId: "%s" }) { id name service } }' % orgs[0]["id"])
    channels = data.get("channels", [])
    for ch in channels:
        if ch.get("service") in ("twitter", "x"):
            return ch["id"]

    if channels:
        print(f"⚠️ X-канал не найден, беру первый: {channels[0]['name']}")
        return channels[0]["id"]

    raise Exception("В Buffer не подключено ни одного канала")


def buffer_schedule_post(token, channel_id, text, image_url, scheduled_at):
    """Планирует пост на конкретное время через customScheduled + dueAt (по документации Buffer)"""
    text_lit = json.dumps(text, ensure_ascii=False)
    ch_lit = json.dumps(channel_id)
    url_lit = json.dumps(image_url)
    # 👇 ISO 8601 с миллисекундами, как в официальной документации Buffer
    due_lit = json.dumps(scheduled_at.strftime("%Y-%m-%dT%H:%M:%S.000Z"))

    query = f'''mutation {{
  createPost(input: {{
    text: {text_lit},
    channelId: {ch_lit},
    schedulingType: automatic,
    mode: customScheduled,
    dueAt: {due_lit},
    assets: [{{ image: {{ url: {url_lit} }} }}]
  }}) {{
    ... on PostActionSuccess {{ post {{ id text dueAt }} }}
    ... on MutationError {{ message }}
  }}
}}'''

    data = buffer_graphql(token, query)
    res = data.get("createPost", {})
    if res.get("post"):
        return True, res["post"].get("id")
    return False, res.get("message", "неизвестная ошибка Buffer")


# ---------- История ----------
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Не удалось прочитать историю: {e}")
    return {"processed": [], "cache_counter": 1, "last_scheduled_at": None}


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ---------- Главная логика ----------
def cmd_generate():
    print("=" * 60)
    print("🚀 Запуск генерации очереди постов")
    print("=" * 60)

    token = os.environ.get("BUFFER_API_KEY", "")
    if not token:
        print("⚠️ BUFFER_API_KEY не задан — выходим.")
        return
    if not os.environ.get("GITHUB_REPOSITORY"):
        print("❌ Нет GITHUB_REPOSITORY (запуск вне GitHub Actions).")
        return

    history = load_history()
    processed = set(history.get("processed", []))
    cache_counter = history.get("cache_counter", 1)
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

    # Начинаем планирование от max(сейчас, last_scheduled + 2 минуты)
    # Это защита: если прошлый запуск запланировал посты на будущее, не пересекаемся с ними
    start_slot = max(now, last_scheduled + timedelta(minutes=POST_INTERVAL_MINUTES))
    print(f"🕐 Текущее время (UTC): {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📅 Последний запланированный пост: {last_scheduled.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"▶️  Первый слот для новых постов: {start_slot.strftime('%Y-%m-%d %H:%M:%S')}")

    # Получаем новости из RSS
    print("\n📡 Получаем новости из RSS-Bridge...")
    posts = get_all_posts_from_rss_bridge(cache_counter)
    if not posts:
        print("❌ Не удалось получить новости.")
        history["cache_counter"] = cache_counter + 1
        save_history(history)
        return

    print(f"📋 Новостей в RSS: {len(posts)}")

    # Находим новые посты (не в истории) — от старых к новым
    new_posts = [p for p in reversed(posts) if p["link"] not in processed]
    print(f"🆕 Новых (не в истории): {len(new_posts)}")

    if not new_posts:
        print("😴 Все новости из RSS уже запланированы или опубликованы.")
        history["cache_counter"] = cache_counter + 1
        save_history(history)
        return

    # Получаем ID канала Buffer
    try:
        channel_id = get_buffer_channel_id(token)
        print(f"📡 X-канал Buffer: {channel_id}")
    except Exception as e:
        print(f"❌ Ошибка получения канала: {e}")
        return

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    branch = os.environ.get("GITHUB_REF_NAME", "main")

    os.makedirs("banners", exist_ok=True)

    # Планируем каждый пост с интервалом 2 минуты
    scheduled_posts = []
    new_last_scheduled = last_scheduled

    for i, post in enumerate(new_posts):
        post_id = post["link"].rstrip("/").split("/")[-1]
        img_name = f"banners/{post_id}.jpg"

        # Генерируем баннер
        print(f"\n🎨 Генерируем баннер для {post_id}: {post['title_clean'][:60]}...")
        generate_card(
            post["image_url"],
            post["title_clean"],
            fallback_context={
                'title': post.get('title_raw', ''),
                'text': '',
                'hashtags': post.get('hashtags', [])
            },
            output_path=img_name
        )

        # Формируем текст твита
        tweet_text = build_tweet_text(post["title_raw"], post["link"], post.get("hashtags", []))
        image_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{img_name}"

        # Вычисляем время публикации
        scheduled_time = start_slot + timedelta(minutes=POST_INTERVAL_MINUTES * i)

        # Отправляем в Buffer
        try:
            ok, info = buffer_schedule_post(token, channel_id, tweet_text, image_url, scheduled_time)
            if ok:
                print(f"✅ Запланировано на {scheduled_time.strftime('%H:%M')} UTC (Buffer id: {info})")
                scheduled_posts.append(post["link"])
                new_last_scheduled = scheduled_time
            else:
                print(f"❌ Ошибка планирования для {post_id}: {info}")
                # Если ошибка "лимит достигнут" — останавливаем цикл, чтобы не тратить запросы впустую
                if "limit reached" in str(info).lower():
                    print("⏸️ Лимит Buffer достигнут — прерываем планирование, остальные добавим в следующий запуск")
                    break
                # Иная ошибка — пробуем сдвинуть время на 2 минуты вперёд и повторить
                print(f"🔄 Пробуем ещё раз со сдвигом +2 минуты...")
                scheduled_time_retry = scheduled_time + timedelta(minutes=2)
                ok2, info2 = buffer_schedule_post(token, channel_id, tweet_text, image_url, scheduled_time_retry)
                if ok2:
                    print(f"✅ Запланировано со сдвигом на {scheduled_time_retry.strftime('%H:%M')} UTC")
                    scheduled_posts.append(post["link"])
                    new_last_scheduled = scheduled_time_retry
                else:
                    print(f"❌ Повторная попытка тоже не удалась: {info2}")
        except Exception as e:
            print(f"❌ Исключение при планировании {post_id}: {e}")
            continue

        # Небольшая задержка между запросами к Buffer, чтобы не упереться в rate limit
        time.sleep(1)

    # Обновляем историю
    if scheduled_posts:
        for link in scheduled_posts:
            processed.add(link)
        history["processed"] = sorted(processed)[-500:]
        history["last_scheduled_at"] = new_last_scheduled.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        print(f"\n📦 Запланировано {len(scheduled_posts)} постов в очередь Buffer")
        print(f"🕐 Последний пост в очереди: {new_last_scheduled.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    else:
        print("\n⚠️ Ни один пост не был запланирован")

    history["cache_counter"] = cache_counter + 1
    save_history(history)

    # Чистим старые баннеры, оставляем последние 70
    if os.path.isdir("banners"):
        files = sorted(os.listdir("banners"), key=lambda n: int(re.sub(r'\D', '', n) or 0))
        for name in files[:-70]:
            try:
                os.remove(os.path.join("banners", name))
            except Exception:
                pass

    print("💾 История обновлена.")
    print("=" * 60)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "generate"
    if command == "generate":
        cmd_generate()
    else:
        print(f"❓ Неизвестная команда: {command}")
