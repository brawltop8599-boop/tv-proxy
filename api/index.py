import base64
import httpx
import os
import random
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse, RedirectResponse, HTMLResponse

app = FastAPI()

PLAYLIST_TEXT = os.environ.get("PLAYLIST_DATA", "#EXTM3U")
SECRET_KEY = "tvzatak"
TELEGRAM_GROUP = "https://t.me/+2lWVU6CKQsVkMWRi"
MAINTENANCE_VIDEO = "https://github.com/brawltop8599-boop/ads-stub/raw/refs/heads/main/v.mp4"

# Черный список IP (из вашего скрипта)
BANNED_IPS = {
    "5.253.66.62", "23.106.249.56", "23.106.253.18", "31.3.156.64", "38.180.180.126", "46.150.71.146", "91.214.82.125", "109.86.19.135", "217.12.223.190", "188.233.60.20",
    "91.195.172.249", "149.102.240.138", "91.194.168.20", "91.195.172.241", "91.195.172.240", "88.218.92.126", "46.150.71.235", "194.44.26.199", "130.0.235.254",
    "46.96.27.147", "194.44.46.82", "213.109.230.149", "77.239.161.129", "192.162.33.80", "192.162.33.73", "46.150.74.185", "195.64.183.231", "62.233.43.122",
    "176.108.27.175", "91.123.158.251", "46.172.86.196", "213.5.196.234", "217.196.164.251", "195.64.183.237", "37.214.2.184", "176.105.213.173", "176.105.213.129",
    "91.194.168.40", "159.194.214.13", "217.107.106.106", "91.195.172.250", "78.111.155.199", "95.83.134.76", "178.120.4.234", "46.53.134.27", "178.150.186.100",
    "46.150.94.187", "45.12.26.251", "80.91.179.217", "85.198.107.131", "176.119.83.194", "46.150.90.146", "85.249.245.196", "176.105.213.137",
    "109.172.30.88", "178.137.26.58", "143.244.45.242", "194.44.57.68", "143.244.46.242", "188.239.94.135", "82.208.115.42"
}

# Подсети для блокировки
BANNED_PREFIXES = (
    "2a09:bac5:", "2a02:3032:", "2a09:bac1:", "2a12:bec4:", "2a01:e5c0:", "2a02:2378:", "2a02:4780:", "2001:49f0:", 
    "2a14:a087:", "2a01:4f8:", "2001:ac8:", "2a03:d000:", "2001:16b8:", "2a0e:d604:", "2a06:98c0:", "2a01:4f9:", 
    "51.158.201.", "149.154.161.", "94.158.58.", "81.19.141.", "93.152.224.", "80.66.72.", "91.92.33.", "5.255.", 
    "2a12:5940:", "45.45.", "104.204.", "161.129.", "174.136.203.", "104.28.", "87.250.", "2a05:45c2:", 
    "2a01:73c0:", "2001:1e98:", "144.31.141.", "213.180.", "95.85.228.", "188.163.", "205.210.31."
)

def encode_url(url: str) -> str:
    return base64.urlsafe_b64encode(url.encode('utf-8')).decode('utf-8').rstrip("=")

def decode_url(encoded_str: str) -> str:
    try:
        padding = 4 - (len(encoded_str) % 4)
        if padding < 4:
            encoded_str += "=" * padding
        return base64.urlsafe_b64decode(encoded_str.encode('utf-8')).decode('utf-8')
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid stream token")

def get_encoded_streams():
    lines = PLAYLIST_TEXT.splitlines()
    tokens = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            tokens.append(encode_url(line))
    return tokens

def get_fake_playlist():
    fake_channels = ["TEAM✨TV", "TVPlay✨", "VeleS✨TV", "Oasis✨TV", "Sat✨Tv", "Olsib✨Tv", "TVboom.TV", "Kernel.TV", "Чебур✨", "Velilla.TV"]
    channel_logo = "https://i.ibb.co/MCPX1NK/1.png"
    fake_m3u = '#EXTM3U url-tvg="https://iptvx.one/EPG"\n'
    for i in range(1, 101):
        random_channel = random.choice(fake_channels)
        fake_m3u += f'#EXTINF:-1 tvg-id="fake_{i}" tvg-logo="{channelLogo}" group-title="Инфо.Тв",{random_channel} [✨ {i}]\n{MAINTENANCE_VIDEO}\n'
    return fake_m3u

@app.get("/")
def get_playlist(request: Request, tv: str = None):
    client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    ua = (request.headers.get("user-agent", "")).lower()
    host_url = os.environ.get("VERCEL_URL", "localhost:8000")
    protocol = "https" if "vercel.app" in host_url or request.url.scheme == "https" else "http"
    base_url = f"{protocol}://{host_url}"

    # 1. Проверка на ботов и черные списки IP
    is_search_bot = any(b in ua for b in ["google", "bot", "crawler", "spider", "yandex"])
    is_banned_ip = client_ip in BANNED_IPS or client_ip.startswith(BANNED_PREFIXES)
    
    if is_search_bot or is_banned_ip:
        return RedirectResponse(TELEGRAM_GROUP, status_code=302)

    # 2. Telegram Open Graph превью
    if "telegrambot" in ua:
        preview_html = f"""<!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta property="og:title" content="📡 𝕏aльвa 📡">
            <meta property="og:description" content="Ссылка для друзей 👆&#10;Напоминаю в группе бот...">
            <meta property="og:image" content="{MAINTENANCE_VIDEO}">
            <meta property="og:url" content="{base_url}/">
            <title>IPTV Playlist</title>
        </head>
        <body>Redirecting...</body>
        </html>"""
        return HTMLResponse(content=preview_html)

    # 3. Блокировка ПК и обычных браузеров -> отправка в Telegram
    is_desktop_or_browser = any(b in ua for b in ["windows", "macintosh", "chrome", "safari", "firefox", "edg", "opera", "msie", "trident"]) or ("linux" in ua and "android" not in ua)
    if is_desktop_or_browser:
        return RedirectResponse(TELEGRAM_GROUP, status_code=302)

    # 4. Если ключ неверный — отдаем фейковый плейлист вместо ошибки
    if tv != SECRET_KEY:
        return PlainTextResponse(get_fake_playlist(), media_type="application/x-mpegurl")

    # 5. Если всё ок — отдаем реальный плейлист с индексами
    lines = PLAYLIST_TEXT.splitlines()
    new_lines = []
    stream_index = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if not line.startswith("#"):
            full_link = f"{base_url}/r/{stream_index}?tv={SECRET_KEY}"
            new_lines.append(full_link)
            stream_index += 1
        else:
            new_lines.append(line)

    return PlainTextResponse("\n".join(new_lines), media_type="application/x-mpegurl")

@app.get("/r/{token}")
async def handle_request(request: Request, token: str, tv: str = None):
    if tv != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    if token.isdigit():
        index = int(token)
        tokens = get_encoded_streams()
        if not (0 <= index < len(tokens)):
            raise HTTPException(status_code=404, detail="Stream not found")
        
        encoded_token = tokens[index]
        return RedirectResponse(url=f"/r/{encoded_token}?tv={SECRET_KEY}", status_code=302)
    
    else:
        target_url = decode_url(token)
        host_url = os.environ.get("VERCEL_URL", "localhost:8000")
        protocol = "https" if "vercel.app" in host_url or request.url.scheme == "https" else "http"
        base_url = f"{protocol}://{host_url}"

        client = httpx.AsyncClient(follow_redirects=True, timeout=30.0)
        try:
            req = client.build_request("GET", target_url, headers={"User-Agent": "Mozilla/5.0"})
            r = await client.send(req)

            content_type = r.headers.get("content-type", "")

            if "mpegurl" in content_type or "vnd.apple.mpegurl" in content_type or target_url.endswith(".m3u8"):
                playlist_content = r.text
                lines = playlist_content.splitlines()
                rewritten_lines = []

                for line in lines:
                    line_str = line.strip()
                    if line_str and not line_str.startswith("#"):
                        if not line_str.startswith("http"):
                            base_path = target_url.rsplit("/", 1)[0]
                            absolute_sub_url = f"{base_path}/{line_str}"
                        else:
                            absolute_sub_url = line_str

                        sub_token = encode_url(absolute_sub_url)
                        rewritten_lines.append(f"{base_url}/r/{sub_token}?tv={SECRET_KEY}")
                    else:
                        rewritten_lines.append(line)

                return PlainTextResponse("\n".join(rewritten_lines), status_code=r.status_code, media_type="application/vnd.apple.mpegurl")

            else:
                async def stream_generator():
                    async for chunk in r.aiter_bytes():
                        yield chunk

                return StreamingResponse(
                    stream_generator(),
                    status_code=r.status_code,
                    media_type=content_type or "video/mp2t"
                )

        except Exception:
            raise HTTPException(status_code=502, detail="Failed to fetch upstream stream")
