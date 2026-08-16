import os
import re
import sys
import json
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import cairosvg
import time

BRIDGE_URL = "https://rss-bridge.org/bridge01/?action=display&username=elpaisru&bridge=TelegramBridge&format=Html&_cache_timeout=0"
HISTORY_FILE = "posted_history.json"
PENDING_FILE = "pending_tweet.json"
BUFFER_API = "https://api.buffer.com"


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


def get_all_posts_from_rss_bridge():
    import time
    # Добавляем параметры для сброса кэша RSS-Bridge
    current_time = int(time.time())
    bridge_url = f"https://rss-bridge.org/bridge01/?action=display&username=elpaisru&bridge=TelegramBridge&format=Html&_cache_timeout=0&_t={current_time}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }
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


def generate_card(image_url, title_text, output_path="banner.jpg"):
    if not image_url:
        img = Image.new("RGBA", (1080, 1080), (30, 30, 30, 255))
    else:
        try:
            img_data = requests.get(image_url, timeout=10).content
            with open("temp_src.jpg", "wb") as f:
                f.write(img_data)
            img = Image.open("temp_src.jpg").convert("RGBA")
        except Exception as e:
            print(f"⚠️ Не удалось загрузить картинку: {e}. Используем темный фон.")
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
        print("⚠️ Шрифт Exo2-Black.ttf не найден, используется стандартный.")
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

    # Логотип берётся ТОЛЬКО из файла logo.svg в корне репозитория
    try:
        if os.path.exists("logo.svg"):
            cairosvg.svg2png(url="logo.svg", write_to="logo_temp.png", output_width=320)
            logo = Image.open("logo_temp.png").convert("RGBA")
            img.paste(logo, (60, 60), logo)
        else:
            print("⚠️ Файл logo.svg не найден — картинка будет без логотипа.")
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


def buffer_create_post(token, channel_id, text, image_url):
    text_lit = json.dumps(text, ensure_ascii=False)
    ch_lit = json.dumps(channel_id)
    url_lit = json.dumps(image_url)
    query = f'''mutation {{
  createPost(input: {{
    text: {text_lit},
    channelId: {ch_lit},
    schedulingType: automatic,
    mode: shareNow,
    assets: [{{ image: {{ url: {url_lit} }} }}]
  }}) {{
    ... on PostActionSuccess {{ post {{ id text }} }}
    ... on MutationError {{ message }}
  }}
}}'''
    data = buffer_graphql(token, query)
    res = data.get("createPost", {})
    if res.get("post"):
        return True, res["post"].get("id")
    return False, res.get("message", "неизвестная ошибка Buffer")


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Не удалось прочитать историю: {e}")
    return {"processed": []}


def save_history(processed):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump({"processed": sorted(processed)[-500:]}, f, ensure_ascii=False, indent=2)


def cmd_generate():
    print("Получаем новости из RSS-Bridge...")
    posts = get_all_posts_from_rss_bridge()
    if not posts:
        print("❌ Не удалось получить новости.")
        return

    latest = posts[0]
    generate_card(latest["image_url"], latest["title_clean"], output_path="banner.jpg")
    print("🎨 banner.jpg (последняя новость) создан.")

    first_run = not os.path.exists(HISTORY_FILE)
    history = load_history()
    processed = set(history.get("processed", []))

    if first_run:
        to_post = posts[0]
        for p in posts[1:]:
            processed.add(p["link"])
        print("🆕 Первый запуск: старые новости помечены пропущенными.")
    else:
        unposted = [p for p in reversed(posts) if p["link"] not in processed]
        to_post = unposted[0] if unposted else None

    if to_post:
        post_id = to_post["link"].rstrip("/").split("/")[-1]
        os.makedirs("banners", exist_ok=True)
        img_name = f"banners/{post_id}.jpg"
        generate_card(to_post["image_url"], to_post["title_clean"], output_path=img_name)
        with open(PENDING_FILE, "w", encoding="utf-8") as f:
            json.dump({"link": to_post["link"],
                       "text": build_tweet_text(to_post["title_raw"], to_post["link"],
                                                to_post.get("hashtags", [])),
                       "image": img_name}, f, ensure_ascii=False, indent=2)
        print(f"📦 Подготовлен твит: {to_post['link']}")
    else:
        print("😴 Новых новостей для твита нет.")

    save_history(processed)

    if os.path.isdir("banners"):
        files = sorted(os.listdir("banners"), key=lambda n: int(re.sub(r'\D', '', n) or 0))
        for name in files[:-20]:
            try:
                os.remove(os.path.join("banners", name))
            except Exception:
                pass
    print("💾 История обновлена.")


def cmd_post():
    if not os.path.exists(PENDING_FILE):
        print("😴 Нет отложенного твита.")
        return
    token = os.environ.get("BUFFER_API_KEY", "")
    if not token:
        print("⚠️ BUFFER_API_KEY не задан в секретах — пост отложен.")
        return
    with open(PENDING_FILE, "r", encoding="utf-8") as f:
        pending = json.load(f)

    repo = os.environ.get("GITHUB_REPOSITORY", "")
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    if not repo:
        print("❌ Нет GITHUB_REPOSITORY (запуск вне GitHub Actions).")
        return
    image_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{pending['image']}"

    try:
        channel_id = get_buffer_channel_id(token)
        ok, info = buffer_create_post(token, channel_id, pending["text"], image_url)
    except Exception as e:
        ok, info = False, str(e)

    if ok:
        print(f"✅ Твит опубликован через Buffer, id: {info}")
        history = load_history()
        processed = set(history.get("processed", []))
        processed.add(pending["link"])
        save_history(processed)
        os.remove(PENDING_FILE)
    else:
        print(f"❌ Buffer не опубликовал: {info}. Повторим в следующем запуске.")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "generate"
    if command == "post":
        cmd_post()
    else:
        cmd_generate()
