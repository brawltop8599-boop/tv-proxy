import base64
import httpx
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse, RedirectResponse

app = FastAPI()

# Сюда вы вставляете свой исходный плейлист через переменные окружения Vercel (PLAYLIST_DATA)
PLAYLIST_TEXT = os.environ.get("PLAYLIST_DATA", "#EXTM3U")
SECRET_KEY = "tvzatak"

# Создаем глобальный клиент для скорости и стабильности
http_client = httpx.AsyncClient(follow_redirects=True, timeout=30.0)

def encode_url(url: str) -> str:
    """Кодирует длинную ссылку в Base64"""
    return base64.urlsafe_b64encode(url.encode('utf-8')).decode('utf-8').rstrip("=")

def decode_url(encoded_str: str) -> str:
    """Раскодирует Base64 обратно в длинную ссылку"""
    try:
        padding = 4 - (len(encoded_str) % 4)
        if padding < 4:
            encoded_str += "=" * padding
        return base64.urlsafe_b64decode(encoded_str.encode('utf-8')).decode('utf-8')
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid stream token")

def get_encoded_streams():
    """Собирает все потоки из плейлиста в список и кодирует их"""
    lines = PLAYLIST_TEXT.splitlines()
    tokens = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            tokens.append(encode_url(line))
    return tokens

@app.get("/", response_class=PlainTextResponse)
def get_playlist(request: Request):
    # Определяем адрес вашего деплоя на Vercel автоматически
    host_url = request.headers.get("host") or os.environ.get("VERCEL_URL", "localhost:8000")
    protocol = "https" if "vercel.app" in host_url or "https" in request.url.scheme else "http"
    base_url = f"{protocol}://{host_url}"

    lines = PLAYLIST_TEXT.splitlines()
    new_lines = []
    stream_index = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Вместо длинной каши делаем красивые короткие индексы: /r/0, /r/1, /r/2 ...
        if not line.startswith("#"):
            full_link = f"{base_url}/r/{stream_index}?tv={SECRET_KEY}"
            new_lines.append(full_link)
            stream_index += 1
        else:
            new_lines.append(line)

    return "\n".join(new_lines)

@app.get("/r/{token}")
async def handle_request(token: str, tv: str = None):
    """Принимает либо короткий индекс (цифру), либо Base64-токен и проксирует поток"""
    if tv != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    # Если пришла цифра (индекс из плейлиста), перенаправляем на защищенный Base64-токен
    if token.isdigit():
        index = int(token)
        tokens = get_encoded_streams()
        if not (0 <= index < len(tokens)):
            raise HTTPException(status_code=404, detail="Stream not found")
        
        encoded_token = tokens[index]
        host_url = os.environ.get("VERCEL_URL", "localhost:8000")
        return RedirectResponse(url=f"/r/{encoded_token}?tv={SECRET_KEY}", status_code=302)

    # Если пришел сам Base64-токен — расшифровываем и стримим
    target_url = decode_url(token)
    
    try:
        req = http_client.build_request("GET", target_url, headers={"User-Agent": "VLC/3.0.18 LibVLC/3.0.18"})
        r = await http_client.send(req, stream=True)

        return StreamingResponse(
            r.aiter_bytes(),
            status_code=r.status_code,
            media_type=r.headers.get("content-type", "video/mp2t")
        )
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to fetch upstream stream")
