import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse

app = FastAPI()

# Читаем плейлист из переменной окружения Vercel PLAYLIST_DATA
PLAYLIST_TEXT = os.environ.get("PLAYLIST_DATA", "#EXTM3U\n# Xatolik: Playlist topilmadi")

@app.get("/", response_class=PlainTextResponse)
def get_playlist():
    """Отдает M3U плейлист с подмененными ссылками для редиректа"""
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
        # Если строка — это ссылка на поток (не тег плейлиста)
        if not line.startswith("#"):
            new_lines.append(f"{base_url}/r/{stream_index}")
            stream_index += 1
        else:
            new_lines.append(line)

    return "\n".join(new_lines)

@app.get("/r/{index}")
def redirect_stream(index: int):
    """Делает редирект (302) на реальный адрес потока"""
    lines = PLAYLIST_TEXT.splitlines()
    streams = [line.strip() for line in lines if line and not line.startswith("#")]

    if 0 <= index < len(streams):
        target_url = streams[index]
        return RedirectResponse(url=target_url, status_code=302)
    
    raise HTTPException(status_code=404, detail="Stream not found")
