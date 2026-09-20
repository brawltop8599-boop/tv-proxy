import base64
import httpx
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse

app = FastAPI()

PLAYLIST_TEXT = os.environ.get("PLAYLIST_DATA", "#EXTM3U")
SECRET_KEY = "tvzatak"

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

@app.get("/", response_class=PlainTextResponse)
def get_playlist(request: Request):
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
        
        if not line.startswith("#"):
            # Красивые короткие ссылки для плейлиста
            full_link = f"{base_url}/r/{stream_index}?tv={SECRET_KEY}"
            new_lines.append(full_link)
            stream_index += 1
        else:
            new_lines.append(line)

    return "\n".join(new_lines)

@app.get("/r/{token}")
async def handle_request(request: Request, token: str, tv: str = None):
    if tv != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    # Если пришла цифра — преобразуем в base64-токен
    if token.isdigit():
        index = int(token)
        tokens = get_encoded_streams()
        if not (0 <= index < len(tokens)):
            raise HTTPException(status_code=404, detail="Stream not found")
        
        encoded_token = tokens[index]
        host_url = request.headers.get("host") or os.environ.get("VERCEL_URL", "localhost:8000")
        protocol = "https" if "vercel.app" in host_url or "https" in request.url.scheme else "http"
        base_url = f"{protocol}://{host_url}"
        return RedirectResponse(url=f"{base_url}/r/{encoded_token}?tv={SECRET_KEY}", status_code=302)

    # Если пришел токен — расшифровываем и делаем прямой редирект плееру на источник
    target_url = decode_url(token)
    
    # Плеер перенаправляется напрямую на ipservice.tv, избегая блокировок 403 на сервере Vercel
    return RedirectResponse(url=target_url, status_code=302)
