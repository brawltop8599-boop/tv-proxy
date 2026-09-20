import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse

app = FastAPI()

PLAYLIST_TEXT = os.environ.get("PLAYLIST_DATA", "#EXTM3U\n# Xatolik: Playlist topilmadi")

@app.get("/", response_class=PlainTextResponse)
def get_playlist():
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
        if not line.startswith("#"):
            new_lines.append(f"{base_url}/r/{stream_index}")
            stream_index += 1
        else:
            new_lines.append(line)

    return "\n".join(new_lines)

@app.get("/r/{index}")
def redirect_stream(index: int):
    lines = PLAYLIST_TEXT.splitlines()
    streams = [line.strip() for line in lines if line and not line.startswith("#")]

    if 0 <= index < len(streams):
        target_url = streams[index]
        
        # Распаковываем вложенную ссылку, если она завернута через ipservice
        if "/stream/http" in target_url:
            target_url = "http://" + target_url.split("/stream/http")[1]
        elif "/stream/https" in target_url:
            target_url = "https://" + target_url.split("/stream/https")[1]

        return RedirectResponse(url=target_url, status_code=302)
    
    raise HTTPException(status_code=404, detail="Stream not found")
