import base64
import httpx
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response

app = FastAPI()

# === НАСТРОЙКИ И ССЫЛКИ ===
SECRET_KEY = "tvza"
TELEGRAM_GROUP = "https://t.me/+2lWVU6CKQsVkMWRi"
MAINTENANCE_VIDEO = "https://github.com/brawltop8599-boop/ads-stub/raw/refs/heads/main/v.mp4"
PLAYLIST_TEXT = os.environ.get("PLAYLIST_DATA", "#EXTM3U")

http_client = httpx.AsyncClient(follow_redirects=True, timeout=10.0)

# === ЧЁРНЫЙ СПИСОК IP И ПОДСЕТЕЙ ===
BANNED_IPS = {
    "5.253.66.62", "23.106.249.56", "23.106.253.18", "31.3.156.64", "38.180.180.126", "46.150.71.146", "91.214.82.125", "109.86.19.135", "217.12.223.190", "188.233.60.20",
    "91.195.172.249", "149.102.240.138", "91.194.168.20", "91.195.172.241", "91.195.172.240", "88.218.92.126", "46.150.71.235", "194.44.26.199", "130.0.235.254",
    "46.96.27.147", "194.44.46.82", "213.109.230.149", "77.239.161.129", "192.162.33.80", "192.162.33.73", "46.150.74.185", "195.64.183.231", "62.233.43.122",
    "176.108.27.175", "91.123.158.251", "46.172.86.196", "213.5.196.234", "217.196.164.251", "195.64.183.237", "37.214.2.184", "176.105.213.173", "176.105.213.129",
    "91.194.168.40", "159.194.214.13", "217.107.106.106", "91.195.172.250", "78.111.155.199", "95.83.134.76", "178.120.4.234", "46.53.134.27", "178.150.186.100",
    "46.150.94.187", "45.12.26.251", "80.91.179.217", "85.198.107.131", "176.119.83.194", "46.150.90.146", "85.249.245.196", "176.105.213.137",
    "109.172.30.88", "178.137.26.58", "143.244.45.242", "194.44.57.68", "143.244.46.242", "188.239.94.135", "82.208.115.42",
    "2001:678:6d4:5060::3ead:110", "2003:cc:bf4d:1c1a:77e0:492e:451d:a4", "2003:cc:bf48:c26d:143:5df7:12bc:7686", "2a00:1e98:f2d5:e661:455c:a694:bcaf:17ad",
    "2a0a:4cc0:c1:ea4e:784f:20ff:fe46:d1b1", "2a00:1fa0:c604:e33a:5b7e:e2c6:b58b:5360", "2a00:20:8008:8766:78e8:c27a:537:9d47", "2a00:1fa0:82a8:5b8d:cc51:cf16:701b:71e",
    "2001:9e8:3c3a:d100:96a6:62ce:7b7f:3e06", "2a00:1e98:f022:9877:c1ba:4b65:5e85:1c4f", "2a0d:6fc2:5db2:6600:b0b1:70c1:6721:ca58", "2a00:1e98:f2d5:e661:5a0f:182a:60ea:e4cd",
    "2a02:6ea0:3100:2000:490a:2928:d5eb:e685"
}

BANNED_PREFIXES = (
    "2a09:bac5:", "2a02:3032:", "2a09:bac1:", "2a12:bec4:", "2a01:e5c0:", "2a02:2378:",
    "2a02:4780:", "2001:49f0:", "2a14:a087:", "2a01:4f8:", "2001:ac8:", "2a03:d000:",
    "2001:16b8:", "2a0e:d604:", "2a06:98c0:", "2a01:4f9:", "51.158.201.",
    "149.154.161.", "94.158.58.", "81.19.141.", "93.152.224.", "80.66.72.",
    "91.92.33.", "5.255.", "2a12:5940:", "45.45.", "104.204.", "161.129.",
    "174.136.203.", "104.28.", "87.250.", "2a05:45c2:", "2a01:73c0:",
    "2001:1e98:", "144.31.141.", "213.180.", "95.85.228.", "188.163.", "205.210.31."
)

def get_streams_list():
    lines = PLAYLIST_TEXT.splitlines()
    streams = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            streams.append(line)
    return streams

def get_fake_playlist_response():
    fake_channels = ["TEAM✨TV", "TVPlay✨", "VeleS✨TV", "Oasis✨TV", "Sat✨Tv", "Olsib✨Tv", "TVboom.TV", "Kernel.TV", "Чебур✨", "Velilla.TV"]
    channel_logo = "https://i.ibb.co/MCPX1NK/1.png"
    fake_m3u = '#EXTM3U url-tvg="https://iptvx.one/EPG"\n'
    
    import random
    for i in range(1, 101):
        random_channel = random.choice(fake_channels)
        fake_m3u += f'#EXTINF:-1 tvg-id="fake_{i}" tvg-logo="{channel_logo}" group-title="Инфо.Тв",{random_channel} [✨ {i}]\n{MAINTENANCE_VIDEO}\n'
    
    return Response(
        content=fake_m3u,
        status_code=200,
        media_type="application/x-mpegurl; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="playlist_protected.m3u"'}
    )

@app.get("/")
def get_playlist(request: Request):
    host_url = request.headers.get("host") or os.environ.get("VERCEL_URL", "localhost:8000")
    protocol = "https" if "vercel.app" in host_url or "https" in request.url.scheme else "http"
    base_url = f"{protocol}://{host_url}"
    
    ua = (request.headers.get("user-agent") or "").lower()
    client_ip = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for") or ""
    user_key = request.query_params.get("tv")

    # 1. Перехват для Telegram (превью ссылки на корень)
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
        return Response(content=preview_html, media_type="text/html; charset=utf-8")

    # Проверка IP и поисковых ботов
    is_search_bot = any(b in ua for b in ["google", "bot", "crawler", "spider", "yandex"])
    is_banned_ip = client_ip in BANNED_IPS or client_ip.startswith(BANNED_PREFIXES)
    
    if is_search_bot or is_banned_ip:
        return RedirectResponse(url=TELEGRAM_GROUP, status_code=302)

    # 2. ЖЕСТКИЙ БЛОК ВСЕХ БРАУЗЕРОВ (И ПК, И МОБИЛЬНЫХ)
    browser_keywords = ["chrome", "safari", "firefox", "edg", "opera", "msie", "trident", "ucbrowser", "samsungbrowser", "brave", "vivaldi"]
    is_player = any(p in ua for p in ["vlc", "televizor", "televizo", "tivimate", "kodi", "iptv", "netplayer", "ott", "libvlc"])
    is_any_browser = any(b in ua for b in browser_keywords) and not is_player

    if is_any_browser:
        return RedirectResponse(url=TELEGRAM_GROUP, status_code=302)

    # 3. ПРОВЕРКА СКАНЕРОВ (если нет ключа ?tv=)
    bad_user_agents = ["curl", "wget", "python-requests", "go-http-client", "scanner"]
    if any(agent in ua for agent in bad_user_agents) and not user_key:
        raise HTTPException(status_code=403, detail="Blocked: Bot detected")

    # 4. Если ключ неверный — отдаем фейк-плейлист
    if user_key != SECRET_KEY:
        return get_fake_playlist_response()

    # 5. Генерация настоящего плейлиста
    lines = PLAYLIST_TEXT.splitlines()
    new_lines = []
    stream_index = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if not line.startswith("#"):
            new_lines.append(f"{base_url}/r/{stream_index}?tv={SECRET_KEY}")
            stream_index += 1
        else:
            new_lines.append(line)

    return PlainTextResponse("\n".join(new_lines), media_type="application/vnd.apple.mpegurl")

@app.get("/r/{index:int}")
async def handle_indexed_request(request: Request, index: int, tv: str = None):
    ua = (request.headers.get("user-agent") or "").lower()
    client_ip = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for") or ""

    # Перехват для Telegram-бота (чтобы рисовалась красивая карточка)
    if "telegrambot" in ua:
        host_url = request.headers.get("host") or os.environ.get("VERCEL_URL", "localhost:8000")
        protocol = "https" if "vercel.app" in host_url or "https" in request.url.scheme else "http"
        base_url = f"{protocol}://{host_url}"
        preview_html = f"""<!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta property="og:title" content="📡 𝕏aльвa (Канал #{index + 1}) 📡">
            <meta property="og:description" content="Прямая трансляция канала 👆">
            <meta property="og:image" content="{MAINTENANCE_VIDEO}">
            <meta property="og:url" content="{base_url}/r/{index}?tv={SECRET_KEY}">
            <title>IPTV Stream</title>
        </head>
        <body>Redirecting...</body>
        </html>"""
        return Response(content=preview_html, media_type="text/html; charset=utf-8")

    # ЖЕСТКИЙ БЛОК БРАУЗЕРОВ И ДЛЯ ПРЯМЫХ ССЫЛОК НА КАНАЛЫ (отправляем в Telegram)
    browser_keywords = ["chrome", "safari", "firefox", "edg", "opera", "msie", "trident", "ucbrowser", "samsungbrowser", "brave", "vivaldi"]
    is_player = any(p in ua for p in ["vlc", "televizor", "televizo", "tivimate", "kodi", "iptv", "netplayer", "ott", "libvlc"])
    is_any_browser = any(b in ua for b in browser_keywords) and not is_player

    if is_any_browser or client_ip in BANNED_IPS or client_ip.startswith(BANNED_PREFIXES):
        return RedirectResponse(url=TELEGRAM_GROUP, status_code=302)

    if tv != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    streams = get_streams_list()
    if not (0 <= index < len(streams)):
        raise HTTPException(status_code=404, detail="Stream not found")

    target_url = streams[index]

    host_url = request.headers.get("host") or os.environ.get("VERCEL_URL", "localhost:8000")
    protocol = "https" if "vercel.app" in host_url or "https" in request.url.scheme else "http"
    base_url = f"{protocol}://{host_url}"

    if ".m3u8" in target_url.lower() or "mpegurl" in target_url.lower():
        try:
            client_ua = request.headers.get("user-agent", "VLC/3.0.18 LibVLC/3.0.18")
            r = await http_client.get(target_url, headers={"User-Agent": client_ua})
            
            if r.status_code == 200:
                playlist_text = r.text
                lines = playlist_text.splitlines()
                rewritten_lines = []

                for line in lines:
                    line_str = line.strip()
                    if line_str and not line_str.startswith("#"):
                        if not line_str.startswith("http"):
                            base_path = target_url.rsplit("/", 1)[0]
                            absolute_sub_url = f"{base_path}/{line_str}"
                        else:
                            absolute_sub_url = line_str

                        encoded_sub = base64.urlsafe_b64encode(absolute_sub_url.encode('utf-8')).decode('utf-8').rstrip("=")
                        rewritten_lines.append(f"{base_url}/sub/{encoded_sub}?tv={SECRET_KEY}")
                    else:
                        rewritten_lines.append(line)

                return PlainTextResponse("\n".join(rewritten_lines), status_code=200, media_type="application/vnd.apple.mpegurl")
        except Exception:
            pass

    return RedirectResponse(url=target_url, status_code=302)

@app.get("/sub/{token}")
async def handle_sub_request(request: Request, token: str, tv: str = None):
    if tv != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        padding = 4 - (len(token) % 4)
        if padding < 4:
            token += "=" * padding
        target_url = base64.urlsafe_b64decode(token.encode('utf-8')).decode('utf-8')
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid token")

    return RedirectResponse(url=target_url, status_code=302)
