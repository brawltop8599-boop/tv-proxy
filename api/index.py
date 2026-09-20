import base64
import hashlib
import httpx
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse, RedirectResponse

app = FastAPI()

PLAYLIST_TEXT = os.environ.get("PLAYLIST_DATA", "#EXTM3U")
SECRET_KEY = "tvzatak"

def encode_url(url: str) -> str:
    """Кодирует ссылку в Base64 (та самая каша)"""
    return base64.urlsafe_b64encode(url.encode('utf-8')).decode('utf-8').rstrip("=")

def decode_url(encoded_str: str) -> str:
    """Раскодирует Base64 обратно в оригинальный URL"""
    try:
        padding = 4 - (len(encoded_str) % 4)
        if padding < 4:
            encoded_str += "=" * padding
        return base64.urlsafe_b64decode(encoded_str.encode('utf-8')).decode('utf-8')
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid stream token")

def get_mapping():
    """Создает карту короткий ID -> Base64 каша"""
    lines = PLAYLIST_TEXT.splitlines()
    mapping = {}
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            encoded_token = encode_url(line)
            # Делаем короткий хэш-ключ для ссылки
            short_id = hashlib.md5(line.encode('utf-8')).hexdigest()[:6]
            mapping[short_id] = encoded_token
    return mapping

@app.get("/", response_class=PlainTextResponse)
def get_playlist(request: Request):
    """Отдает плейлист с короткими ссылками"""
    host_url = os.environ.get("VERCEL_URL", "localhost:8000")
    protocol = "https" if "vercel.app" in host_url or request.url.scheme == "https" else "http"
    base_url = f"{protocol}://{host_url}"

    lines = PLAYLIST_TEXT.splitlines()
    new_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if not line.startswith("#"):
            # Создаем короткий идентификатор для канала
            short_id = hashlib.md5(line.encode('utf-8')).hexdigest()[:6]
            
            # Короткая ссылка, которая прячет внутри себя кашу
            full_link = f"{base_url}/s/{short_id}?tv={SECRET_KEY}"
            new_lines.append(full_link)
        else:
            new_lines.append(line)

    return "\n".join(new_lines)

@app.get("/s/{short_id}")
async def redirect_to_base64(short_id: str, tv: str = None):
    """
    При вскрытии короткой ссылки перенаправляет на путь с Base64-кашей, 
    либо сразу проксирует поток.
    """
    if tv != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    mapping = get_mapping()
    if short_id not in mapping:
        raise HTTPException(status_code=404, detail="Stream not found")
    
    encoded_token = mapping[short_id]
    
    # Редиректим на ваш классический маршрут с Base64-кашей (/r/)
    return RedirectResponse(url=f"/r/{encoded_token}?tv={SECRET_KEY}", status_code=307)

@app.get("/r/{encoded_token}")
async def proxy_stream(encoded_token: str, tv: str = None):
    """Тот самый ваш обработчик Base64-каши, который запускает поток"""
    if tv != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    target_url = decode_url(encoded_token)

    client = httpx.AsyncClient(follow_redirects=True, timeout=30.0)
    
    try:
        req = client.build_request("GET", target_url, headers={"User-Agent": "Mozilla/5.0"})
        r = await client.send(req, stream=True)

        return StreamingResponse(
            r.aiter_bytes(),
            status_code=r.status_code,
            media_type=r.headers.get("content-type", "video/mp2t")
        )
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to fetch upstream stream")
