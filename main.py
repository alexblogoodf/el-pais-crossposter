import os
import re
import sys
import json
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import cairosvg

# Твой SVG-логотип — тот же блок, что в прошлой версии (не меняй его)
SVG_LOGO = """<svg version="1.1" id="Layer_1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" x="0px" y="0px"
	 width="760px" height="180px" viewBox="0 0 760 180" enable-background="new 0 0 760 180" xml:space="preserve">
<g>
	<path fill="#FFFFFF" d="M98.325,21.841c-55.209,0-68.159,12.95-68.159,68.159c0,55.209,12.95,68.159,68.159,68.159
		c55.209,0,68.159-12.95,68.159-68.159C166.484,34.791,153.534,21.841,98.325,21.841z M129.917,68.273
		c-1.025,10.778-5.464,36.931-7.722,49.004c-0.954,5.106-2.837,6.819-4.658,6.986c-3.959,0.366-6.964-2.616-10.798-5.129
		c-5.998-3.931-9.386-6.379-15.211-10.215c-6.728-4.436-2.366-6.873,1.468-10.857c1.005-1.042,18.443-16.904,18.781-18.344
		c0.043-0.179,0.082-0.852-0.315-1.204c-0.4-0.355-0.988-0.233-1.411-0.136c-0.602,0.136-10.187,6.469-28.752,19.002
		c-2.721,1.866-5.183,2.777-7.39,2.729c-2.434-0.051-7.117-1.375-10.596-2.508c-4.268-1.386-7.662-2.121-7.367-4.476
		c0.156-1.23,1.846-2.485,5.072-3.766c19.868-8.659,33.12-14.365,39.748-17.122c18.929-7.872,22.862-9.241,25.426-9.287
		c0.562-0.009,1.823,0.131,2.641,0.792c0.69,0.56,0.878,1.315,0.968,1.846C129.894,66.12,130.008,67.328,129.917,68.273z"/>
	<path fill="#FFFFFF" d="M233.8,66.922h-16.283l0.02,10.156l-6.502,0.339v9.337h6.522l0.038,19.138c0,3.396,1.105,6.046,3.318,7.948
		c2.211,1.903,5.195,2.855,8.951,2.855c1.235,0,2.663-0.077,4.283-0.231s3.228-0.374,4.823-0.656
		c1.594-0.282,2.933-0.655,4.013-1.118l-1.775-10.341h-4.09c-1.184,0-2.033-0.219-2.546-0.656c-0.515-0.437-0.771-1.145-0.771-2.122
		V86.755h9.337v-9.724H233.8V66.922z"/>
	<path fill="#FFFFFF" d="M255.869,101.339h-3.627c-2.11,0-3.563,0.399-4.36,1.196c-0.798,0.798-1.196,2.251-1.196,4.359v3.164
		c0,2.059,0.398,3.499,1.196,4.321c0.797,0.824,2.25,1.235,4.36,1.235h3.627c2.109,0,3.562-0.411,4.36-1.235
		c0.797-0.822,1.196-2.263,1.196-4.321v-3.164c0-2.108-0.399-3.562-1.196-4.359C259.431,101.739,257.978,101.339,255.869,101.339z"
		/>
	<path fill="#FFFFFF" d="M318.144,75.951c-2.882,0-5.415,0.592-7.601,1.775c-1.736,0.939-3.495,2.273-5.278,3.989
		c-0.459-1.182-1.098-2.197-1.938-3.025c-1.852-1.825-4.553-2.739-8.103-2.739c-2.933,0-5.479,0.592-7.64,1.775
		c-2.016,1.105-4.078,2.753-6.184,4.932l-1.379-5.627h-12.655v38.585h16.128V90.424c0.398-0.141,0.762-0.261,1.081-0.352
		c0.72-0.205,1.337-0.334,1.852-0.386c0.514-0.051,1.003-0.077,1.466-0.077c0.926,0,1.594,0.167,2.006,0.501
		c0.411,0.335,0.617,0.939,0.617,1.813v23.691h15.588V90.512c0.478-0.182,0.905-0.33,1.273-0.44
		c0.694-0.205,1.285-0.334,1.775-0.386c0.488-0.051,0.965-0.077,1.428-0.077c0.977,0,1.646,0.167,2.006,0.501
		c0.359,0.335,0.54,0.939,0.54,1.813v23.691h16.128V86.755c0-3.55-0.939-6.238-2.817-8.064
		C324.561,76.865,321.796,75.951,318.144,75.951z"/>
	<path fill="#FFFFFF" d="M373.048,97.481c2.186-1.594,3.253-4.192,3.202-7.794c-0.052-4.526-1.595-7.948-4.63-10.263
		c-3.036-2.315-8.18-3.473-15.434-3.473c-5.299,0-9.557,0.669-12.771,2.006c-3.216,1.338-5.544,3.511-6.984,6.521
		c-1.441,3.01-2.161,7.061-2.161,12.155c0,4.373,0.707,8.038,2.122,10.996c1.415,2.959,3.743,5.184,6.984,6.675
		c3.241,1.492,7.536,2.238,12.887,2.238c2.315,0,4.565-0.104,6.752-0.309c2.186-0.206,4.308-0.566,6.367-1.08
		c2.057-0.514,3.986-1.235,5.788-2.161l-1.466-9.724c-3.293,0.361-6.341,0.593-9.145,0.695c-2.805,0.104-4.978,0.154-6.521,0.154
		c-1.904,0-3.345-0.282-4.322-0.85c-0.978-0.565-1.634-1.517-1.968-2.854c-0.041-0.164-0.072-0.36-0.108-0.54h9.638
		C366.939,99.874,370.861,99.076,373.048,97.481z M360.046,91.732c-0.463,0.335-1.57,0.502-3.318,0.502h-5.418
		c0.067-1.28,0.188-2.296,0.364-3.049c0.282-1.208,0.811-1.993,1.582-2.354c0.772-0.359,1.903-0.514,3.396-0.463
		c1.492,0,2.546,0.181,3.164,0.541c0.617,0.36,0.926,1.157,0.926,2.392C360.74,90.588,360.508,91.398,360.046,91.732z"/>
	<polygon fill="#FFFFFF" points="408.585,62.369 378.257,121.712 390.99,121.712 421.318,62.369 	"/>
	<path fill="#FFFFFF" d="M458.938,97.481c2.187-1.594,3.253-4.192,3.202-7.794c-0.052-4.526-1.595-7.948-4.63-10.263
		c-3.036-2.315-8.18-3.473-15.434-3.473c-5.299,0-9.557,0.669-12.771,2.006c-3.216,1.338-5.544,3.511-6.983,6.521
		c-1.441,3.01-2.161,7.061-2.161,12.155c0,4.373,0.707,8.038,2.122,10.996c1.415,2.959,3.743,5.184,6.984,6.675
		c3.241,1.492,7.536,2.238,12.887,2.238c2.315,0,4.565-0.104,6.752-0.309c2.187-0.206,4.309-0.566,6.367-1.08
		c2.057-0.514,3.986-1.235,5.787-2.161l-1.466-9.724c-3.293,0.361-6.342,0.593-9.145,0.695c-2.805,0.104-4.978,0.154-6.521,0.154
		c-1.904,0-3.345-0.282-4.322-0.85c-0.978-0.565-1.634-1.517-1.968-2.854c-0.041-0.164-0.072-0.36-0.108-0.54h9.638
		C452.828,99.874,456.75,99.076,458.938,97.481z M445.935,91.732c-0.463,0.335-1.569,0.502-3.318,0.502h-5.418
		c0.066-1.28,0.187-2.296,0.363-3.049c0.282-1.208,0.811-1.993,1.582-2.354c0.772-0.359,1.903-0.514,3.396-0.463
		c1.492,0,2.547,0.181,3.164,0.541c0.617,0.36,0.926,1.157,0.926,2.392C446.629,90.588,446.398,91.398,445.935,91.732z"/>
	<path fill="#FFFFFF" d="M487.143,104.349c-1.286,0-2.251-0.219-2.894-0.656c-0.645-0.437-0.965-1.145-0.965-2.122V61.597h-16.128
		v44.295c0,3.396,1.157,6.046,3.473,7.948c2.314,1.903,5.504,2.855,9.568,2.855c1.028,0,2.276-0.077,3.743-0.231
		c1.466-0.154,2.905-0.374,4.321-0.656c1.414-0.282,2.508-0.655,3.279-1.118l-1.774-10.341H487.143z"/>
	<path fill="#FFFFFF" d="M523.179,76.105c-2.212,0-4.321,0.322-6.327,0.964c-2.007,0.644-3.743,1.493-5.209,2.547
		c-1.12,0.805-2.003,1.679-2.658,2.619l-1.317-5.204h-12.964v52.475h16.205v-7.64c0.051-1.801,0.025-3.679-0.077-5.633
		c-0.051-0.962-0.108-1.886-0.171-2.773c1.064,0.819,2.262,1.464,3.604,1.924c2.547,0.874,5.286,1.312,8.219,1.312
		c3.189,0,5.865-0.554,8.025-1.659c2.161-1.105,3.794-3.099,4.9-5.98c1.105-2.881,1.659-6.971,1.659-12.27
		c0-6.585-1.055-11.678-3.164-15.28C531.795,77.906,528.22,76.105,523.179,76.105z M519.977,102.999
		c-0.283,1.312-0.746,2.16-1.39,2.547c-0.644,0.386-1.504,0.578-2.585,0.578c-1.595,0-2.868-0.18-3.819-0.54
		c-0.417-0.157-0.843-0.314-1.273-0.472V89.115c0.74-0.361,1.462-0.677,2.161-0.934c0.771-0.282,1.825-0.424,3.163-0.424
		c0.977,0,1.775,0.181,2.393,0.54c0.617,0.361,1.067,1.196,1.351,2.508c0.282,1.312,0.424,3.357,0.424,6.135
		C520.401,99.669,520.259,101.687,519.977,102.999z"/>
	<path fill="#FFFFFF" d="M574.149,77.379c-2.496-0.952-5.569-1.428-9.222-1.428c-1.956,0-4.271,0.09-6.945,0.27
		c-2.676,0.181-5.363,0.413-8.063,0.694c-2.701,0.284-5.029,0.605-6.984,0.965l1.467,10.263c3.291-0.154,6.392-0.257,9.299-0.309
		c2.905-0.05,5.363-0.077,7.369-0.077c1.698,0,2.867,0.309,3.511,0.926c0.644,0.617,0.99,1.595,1.042,2.932v0.309h-12.038
		c-3.91,0-7.01,0.888-9.299,2.663c-2.29,1.774-3.434,4.205-3.434,7.292v3.858c0,2.419,0.604,4.438,1.813,6.058
		c1.208,1.621,2.828,2.844,4.861,3.666c2.031,0.822,4.231,1.234,6.598,1.234c2.675,0,4.978-0.451,6.907-1.351
		c1.929-0.899,3.549-2.019,4.861-3.356c0.583-0.595,1.105-1.19,1.582-1.785l1.466,5.412h12.888V91.693
		c0-4.013-0.656-7.163-1.968-9.453C578.547,79.951,576.644,78.331,574.149,77.379z M559.834,105.738
		c-1.081,0-1.891-0.231-2.431-0.694c-0.541-0.463-0.811-1.028-0.811-1.698v-1.234c0-0.72,0.243-1.299,0.733-1.736
		c0.488-0.437,1.221-0.655,2.199-0.655h6.096v4.14c-0.631,0.37-1.273,0.701-1.929,0.991
		C562.354,105.443,561.068,105.738,559.834,105.738z"/>
	<rect x="588.386" y="77.031" fill="#FFFFFF" width="16.128" height="38.585"/>
	<path fill="#FFFFFF" d="M599.884,59.359h-6.868c-3.139,0-4.707,1.595-4.707,4.785v3.936c0,3.19,1.568,4.784,4.707,4.784h6.868
		c3.137,0,4.707-1.594,4.707-4.784v-3.936C604.591,60.955,603.021,59.359,599.884,59.359z"/>
	<path fill="#FFFFFF" d="M639.085,92.079l-8.874-2.238c-1.853-0.514-3.075-0.849-3.666-1.003c-0.592-0.154-0.888-0.437-0.888-0.849
		c0-0.359,0.128-0.591,0.387-0.694c0.257-0.103,0.797-0.167,1.62-0.193c0.822-0.025,2.083-0.039,3.781-0.039
		c2.365,0,4.849,0,7.446,0s5.183,0,7.756,0l1.003-9.415c-1.595-0.359-3.55-0.656-5.864-0.888c-2.315-0.231-4.695-0.424-7.139-0.579
		s-4.695-0.231-6.752-0.231c-4.527,0-8.091,0.451-10.688,1.351c-2.599,0.9-4.451,2.187-5.557,3.858
		c-1.106,1.672-1.659,3.692-1.659,6.058c0,2.006,0.257,3.808,0.771,5.402c0.514,1.595,1.492,2.997,2.933,4.205
		c1.439,1.21,3.575,2.227,6.405,3.049l8.488,2.314c2.007,0.566,3.344,0.939,4.013,1.119c0.668,0.181,1.004,0.502,1.004,0.965
		c0,0.36-0.182,0.63-0.541,0.81c-0.36,0.182-1.132,0.284-2.314,0.31c-1.185,0.026-3.01,0.038-5.479,0.038c-1.801,0-3.64,0-5.518,0
		s-3.55,0-5.016,0s-2.534,0-3.202,0l-1.004,9.415c4.27,0.721,8.219,1.169,11.846,1.35c3.627,0.18,6.366,0.271,8.219,0.271
		c4.476,0,8.089-0.386,10.842-1.157c2.752-0.772,4.746-2.084,5.98-3.936c1.235-1.853,1.853-4.399,1.853-7.64
		c0-3.344-0.837-5.877-2.508-7.602C645.091,94.408,642.531,93.057,639.085,92.079z"/>
	<path fill="#FFFFFF" d="M675.508,77.726c-2.496,1.105-4.924,2.753-7.285,4.931l-1.434-5.626h-12.655v38.585h16.205V91.577
		c2.006-0.308,3.699-0.516,5.055-0.617c1.723-0.128,3.279-0.193,4.669-0.193h4.09l1.389-14.816h-2.238
		C680.781,75.951,678.183,76.543,675.508,77.726z"/>
	<path fill="#FFFFFF" d="M713.552,77.031v25.141c-0.985,0.324-1.844,0.555-2.547,0.672c-1.08,0.181-2.135,0.27-3.163,0.27
		c-0.979,0-1.698-0.192-2.161-0.578s-0.694-0.99-0.694-1.813V77.031h-16.205v28.861c0,7.203,3.807,10.804,11.421,10.804
		c2.88,0,5.606-0.592,8.18-1.774c2.404-1.107,4.832-2.759,7.282-4.945l1.437,5.64h12.732V77.031H713.552z"/>
</g>
</svg>"""

BRIDGE_URL = "https://rss-bridge.org/bridge01/?action=display&username=elpaisru&bridge=TelegramBridge&format=Html"
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
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(BRIDGE_URL, headers=headers, timeout=15)
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
    """Примерный подсчёт символов по правилам Twitter: эмодзи/широкие символы = 2, остальные = 1."""
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

    # Если твит слишком длинный — отбрасываем хештеги поста (обязательные остаются)
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

# ---------- ГЕНЕРАЦИЯ КАРТИНКИ (без изменений) ----------
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

        try:
        if os.path.exists("logo.svg"):
            cairosvg.svg2png(url="logo.svg", write_to="logo_temp.png", output_width=320)
        else:
            cairosvg.svg2png(bytestring=SVG_LOGO.encode('utf-8'), write_to="logo_temp.png", output_width=320)
        logo = Image.open("logo_temp.png").convert("RGBA")
        img.paste(logo, (60, 60), logo)
    except Exception as e:
        print(f"⚠️ Ошибка при добавлении логотипа: {e}")

    img.convert("RGB").save(output_path, quality=95)
    for tf in ["temp_src.jpg", "logo_temp.png"]:
        if os.path.exists(tf):
            try: os.remove(tf)
            except: pass
    return output_path

# ---------- BUFFER API ----------
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

# ---------- РЕЖИМЫ ----------
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Не удалось прочитать историю: {e}")
    return {"processed": []}

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

    history["processed"] = sorted(processed)[-500:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    # Чистим папку banners, оставляем 20 последних
    if os.path.isdir("banners"):
        files = sorted(os.listdir("banners"), key=lambda n: int(re.sub(r'\D', '', n) or 0))
        for name in files[:-20]:
            try: os.remove(os.path.join("banners", name))
            except: pass
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
        history["processed"] = sorted(processed)[-500:]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        os.remove(PENDING_FILE)
    else:
        print(f"❌ Buffer не опубликовал: {info}. Повторим в следующем запуске.")

if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "generate"
    if command == "post":
        cmd_post()
    else:
        cmd_generate()
