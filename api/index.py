import base64
import httpx
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse

app = FastAPI()

PLAYLIST_TEXT = os.environ.get("PLAYLIST_DATA", "#EXTM3U")
SECRET_KEY = "tvzatak"

http_client = httpx.AsyncClient(follow_redirects=True, timeout=10.0)

def get_streams_list():
    """Возвращает чистый список всех оригинальных ссылок из плейлиста"""
    lines = PLAYLIST_TEXT.splitlines()
    streams = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            streams.append(line)
    return streams

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
        
        # Вместо огромной Base64 строки подставляем короткий номер: /r/0, /r/1, /r/2...
        if not line.startswith("#"):
            new_lines.append(f"{base_url}/r/{stream_index}?tv={SECRET_KEY}")
            stream_index += 1
        else:
            new_lines.append(line)

    return "\n".join(new_lines)

@app.get("/r/{index:int}")
async def handle_indexed_request(request: Request, index: int, tv: str = None):
    """Принимает короткий номер (индекс), находит ссылку и отдает плейлист или редирект"""
    if tv != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    streams = get_streams_list()
    if not (0 <= index < len(streams)):
        raise HTTPException(status_code=404, detail="Stream not found")

    target_url = streams[index]

    host_url = request.headers.get("host") or os.environ.get("VERCEL_URL", "localhost:8000")
    protocol = "https" if "vercel.app" in host_url or "https" in request.url.scheme else "http"
    base_url = f"{protocol}://{host_url}"

    # Если это m3u8 плейлист, быстренько скачиваем и тоже заменяем его внутренности на короткие индексы
    if ".m3u8" in target_url.lower() or "mpegurl" in target_url.lower():
        try:
            client_ua = request.headers.get("user-agent", "VLC/3.0.18 LibVLC/3.0.18")
            r = await http_client.get(target_url, headers={"User-Agent": client_ua})
            
            if r.status_code == 200:
                playlist_text = r.text
                lines = playlist_text.splitlines()
                rewritten_lines = []
                sub_index = 0

                for line in lines:
                    line_str = line.strip()
                    if line_str and not line_str.startswith("#"):
                        # Внутренние ссылки тоже можно пронумеровать или зашифровать
                        encoded_sub = base64.urlsafe_b64encode(line_str.encode('utf-8')).decode('utf-8').rstrip("=")
                        rewritten_lines.append(f"{base_url}/sub/{encoded_sub}?tv={SECRET_KEY}")
                        sub_index += 1
                    else:
                        rewritten_lines.append(line)

                return PlainTextResponse("\n".join(rewritten_lines), status_code=200, media_type="application/vnd.apple.mpegurl")
        except Exception:
            pass

    # Для видео-потоков делаем быстрый редирект без вылетов
    return RedirectResponse(url=target_url, status_code=302)

@app.get("/sub/{token}")
async def handle_sub_request(request: Request, token: str, tv: str = None):
    """Обработка вложенных под-ссылок из плейлистов"""
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
