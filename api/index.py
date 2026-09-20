import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse

app = FastAPI()

PLAYLIST_TEXT = os.environ.get("PLAYLIST_DATA", "#EXTM3U")
SECRET_KEY = "tvzatak"  # Тот самый ключ безопасности

@app.get("/", response_class=PlainTextResponse)
def get_playlist(request: Request):
    """Отдает плейлист с короткими индексами и ключом защиты в хвосте"""
    host_url = os.environ.get("VERCEL_URL", "localhost:8000")
    protocol = "https" if "vercel.app" in host_url else "http"
    base_url = f"{protocol}://{host_url}"

    lines = PLAYLIST_TEXT.splitlines()
    new_lines = []
    stream_index = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Если это ссылка на поток, делаем её короткой и добавляем ключ ?tv=tvzatak
        if not line.startswith("#"):
            new_lines.append(f"{base_url}/r/{stream_index}?tv={SECRET_KEY}")
            stream_index += 1
        else:
            new_lines.append(line)

    return "\n".join(new_lines)

@app.get("/r/{index}")
def redirect_stream(index: int, tv: str = None):
    """Проверяет ключ, находит поток по индексу и делает редирект"""
    
    # Защита: если ключ не совпал или отсутствует, отдаем ошибку доступа
    if tv != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access denied: invalid or missing key")

    lines = PLAYLIST_TEXT.splitlines()
    streams = [line.strip() for line in lines if line and not line.startswith("#")]

    if 0 <= index < len(streams):
        target_url = streams[index]
        return RedirectResponse(url=target_url, status_code=302)
    
    raise HTTPException(status_code=404, detail="Stream not found")
