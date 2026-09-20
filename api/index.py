import base64
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse

app = FastAPI()

# Ваш исходный плейлист со сложными Base64-ссылками
PLAYLIST_TEXT = os.environ.get("PLAYLIST_DATA", "#EXTM3U")
SECRET_KEY = "tvzatak"

def get_streams_list():
    """Собирает все оригинальные Base64-ссылки из плейлиста"""
    lines = PLAYLIST_TEXT.splitlines()
    return [line.strip() for line in lines if line and not line.startswith("#")]

@app.get("/", response_class=PlainTextResponse)
def get_playlist(request: Request):
    """Отдает плейлист с короткими индексами и защитным ключом"""
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
            # В плейлисте пишем короткую красивую ссылку: /r/0?tv=tvzatak
            full_link = f"{base_url}/r/{stream_index}?tv={SECRET_KEY}"
            new_lines.append(full_link)
            stream_index += 1
        else:
            new_lines.append(line)

    return "\n".join(new_lines)

@app.get("/r/{index}")
def redirect_to_base64(index: int, tv: str = None):
    """
    При открытии короткого индекса проверяет ключ 
    и перенаправляет на ту самую длинную Base64-ссылку («кашу»)
    """
    if tv != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    streams = get_streams_list()
    
    if 0 <= index < len(streams):
        base64_target = streams[index]
        # Делаем редирект (302) прямо на Base64-строку из вашего исходного файла
        return RedirectResponse(url=base64_target, status_code=302)
    
    raise HTTPException(status_code=404, detail="Stream not found")
