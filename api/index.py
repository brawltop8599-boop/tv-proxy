import hashlib
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse

app = FastAPI()

# Ваш исходный плейлист, где ссылки содержат ту самую «кашу» в Base64
PLAYLIST_TEXT = os.environ.get("PLAYLIST_DATA", "#EXTM3U")
SECRET_KEY = "tvzatak"

def get_stream_mapping():
    """Создает карту: короткий безопасный хэш -> длинная оригинальная ссылка"""
    lines = PLAYLIST_TEXT.splitlines()
    mapping = {}
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            # Создаем короткий уникальный ID (хеш) на основе длинной ссылки
            short_id = hashlib.md5(line.encode('utf-8')).hexdigest()[:8]
            mapping[short_id] = line
    return mapping

@app.get("/", response_class=PlainTextResponse)
def get_playlist():
    """Отдает плейлист: ссылки короткие и красивые, а длинная 'каша' надежно спрятана внутри сервера"""
    host_url = os.environ.get("VERCEL_URL", "localhost:8000")
    protocol = "https" if "vercel.app" in host_url else "http"
    base_url = f"{protocol}://{host_url}"

    lines = PLAYLIST_TEXT.splitlines()
    new_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if not line.startswith("#"):
            # Генерируем короткий хэш для этой длинной ссылки
            short_id = hashlib.md5(line.encode('utf-8')).hexdigest()[:8]
            # На выходе получаем короткую красивую ссылку вида: /r/a3f9c21b?tv=tvzatak
            new_lines.append(f"{base_url}/r/{short_id}?tv={SECRET_KEY}")
        else:
            new_lines.append(line)

    return "\n".join(new_lines)

@app.get("/r/{short_id}")
def redirect_stream(short_id: str, tv: str = None):
    """Принимает короткий ключ, проверяет защиту и перенаправляет на скрытый источник"""
    if tv != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    mapping = get_stream_mapping()
    
    if short_id in mapping:
        target_url = mapping[short_id]
        return RedirectResponse(url=target_url, status_code=302)
    
    raise HTTPException(status_code=404, detail="Stream not found")
