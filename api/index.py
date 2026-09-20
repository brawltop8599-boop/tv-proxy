import base64
import httpx
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse, RedirectResponse

app = FastAPI()

PLAYLIST_TEXT = os.environ.get("PLAYLIST_DATA", "#EXTM3U")
SECRET_KEY = "tvzatak"

def encode_url(url: str) -> str:
    """Кодирует оригинальную ссылку в Base64-кашу"""
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

def get_encoded_streams():
    """Собирает все потоки и превращает их в Base64-токены"""
    lines = PLAYLIST_TEXT.splitlines()
    tokens = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            tokens.append(encode_url(line))
    return tokens

@app.get("/", response_class=PlainTextResponse)
def get_playlist(request: Request):
    """Отдает плейлист с короткими ссылками-индексами"""
    host_url = os.environ.get("VERCEL_URL", "localhost:8000")
    protocol = "https" if "vercel.app" in host_url or request.url.scheme == "https" else "http"
    base_url = f"{protocol}://{host_url}"

    lines = PLAYLIST_TEXT.splitlines()
    new_lines = []
    stream_index = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if not line.startswith("#"):
            # В плейлисте короткая ссылка с индексом
            full_link = f"{base_url}/r/{stream_index}?tv={SECRET_KEY}"
            new_lines.append(full_link)
            stream_index += 1
        else:
            new_lines.append(line)

    return "\n".join(new_lines)

@app.get("/r/{token}")
async def handle_request(token: str, tv: str = None):
    """
    1. Если это цифра (/r/0) -> редиректим на вашу же Base64-кашу (/r/aHR0c...). 
       В строке адреса теперь видна каша, а не ipservice.tv!
    2. Если это текст (каша) -> расшифровываем и проксируем поток.
    """
    if tv != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    if token.isdigit():
        index = int(token)
        tokens = get_encoded_streams()
        if not (0 <= index < len(tokens)):
            raise HTTPException(status_code=404, detail="Stream not found")
        
        encoded_token = tokens[index]
        # Редирект идет на ВАШ ЖЕ домен с Base64-токеном
        return RedirectResponse(url=f"/r/{encoded_token}?tv={SECRET_KEY}", status_code=302)
    
    else:
        # Срабатывает, когда открыта ссылка с кашей — запускаем проксирование
        target_url = decode_url(token)

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
