import base64
import httpx
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse

app = FastAPI()

# Сюда вы вставляете свой исходный плейлист через переменные окружения Vercel (PLAYLIST_DATA)
PLAYLIST_TEXT = os.environ.get("PLAYLIST_DATA", "#EXTM3U")
SECRET_KEY = "tvzatak"

def encode_url(url: str) -> str:
    """Кодирует длинную ссылку в безопасную Base64 кашу"""
    return base64.urlsafe_b64encode(url.encode('utf-8')).decode('utf-8').rstrip("=")

def decode_url(encoded_str: str) -> str:
    """Раскодирует Base64 обратно в длинную ссылку при запросе от плеера"""
    try:
        padding = 4 - (len(encoded_str) % 4)
        if padding < 4:
            encoded_str += "=" * padding
        return base64.urlsafe_b64decode(encoded_str.encode('utf-8')).decode('utf-8')
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid stream token")

@app.get("/", response_class=PlainTextResponse)
def get_playlist(request: Request):
    # Определяем адрес вашего деплоя на Vercel автоматически
    host_url = request.headers.get("host") or os.environ.get("VERCEL_URL", "localhost:8000")
    protocol = "https" if "vercel.app" in host_url or "https" in request.url.scheme else "http"
    base_url = f"{protocol}://{host_url}"

    lines = PLAYLIST_TEXT.splitlines()
    new_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Если строка не является тегом (начинается с http), оборачиваем её в Base64
        if not line.startswith("#"):
            encoded_token = encode_url(line)
            new_lines.append(f"{base_url}/r/{encoded_token}?tv={SECRET_KEY}")
        else:
            new_lines.append(line)

    return "\n".join(new_lines)

@app.get("/r/{encoded_token}")
async def proxy_stream(encoded_token: str, tv: str = None):
    """Принимает Base64 токен, расшифровывает длинную ссылку и проксирует поток"""
    if tv != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    # Получаем ту самую длинную исходную ссылку из Base64
    target_url = decode_url(encoded_token)

    client = httpx.AsyncClient(follow_redirects=True, timeout=30.0)
    
    try:
        req = client.build_request("GET", target_url, headers={"User-Agent": "VLC/3.0.18 LibVLC/3.0.18"})
        r = await client.send(req, stream=True)

        return StreamingResponse(
            r.aiter_bytes(),
            status_code=r.status_code,
            media_type=r.headers.get("content-type", "video/mp2t")
        )
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to fetch upstream stream")
