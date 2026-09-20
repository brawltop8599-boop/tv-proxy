import base64
import httpx
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse

app = FastAPI()

# Сюда вы вставляете свой исходный плейлист через переменные окружения Vercel (PLAYLIST_DATA)
PLAYLIST_TEXT = os.environ.get("PLAYLIST_DATA", "#EXTM3U")
SECRET_KEY = "tvzatak"

def encode_url(url: str) -> str:
    """Кодирует длинную ссылку в безопасную Base64 кашу"""
    return base64.urlsafe_b64encode(url.encode('utf-8')).decode('utf-8').rstrip("=")

def decode_url(encoded_str: str) -> str:
    """Раскодирует Base64 обратно в длинную ссылку при запросе от плеера"""
    try:
        padding = 4 - (len(encoded_str) % 4)
        if padding < 4:
            encoded_str += "=" * padding
        return base64.urlsafe_b64decode(encoded_str.encode('utf-8')).decode('utf-8')
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid stream token")

@app.get("/", response_class=PlainTextResponse)
def get_playlist(request: Request):
    host_url = request.headers.get("host") or os.environ.get("VERCEL_URL", "localhost:8000")
    protocol = "https" if "vercel.app" in host_url or "https" in request.url.scheme else "http"
    base_url = f"{protocol}://{host_url}"

    lines = PLAYLIST_TEXT.splitlines()
    new_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Если строка не является тегом, оборачиваем её в Base64
        if not line.startswith("#"):
            encoded_token = encode_url(line)
            new_lines.append(f"{base_url}/r/{encoded_token}?tv={SECRET_KEY}")
        else:
            new_lines.append(line)

    return "\n".join(new_lines)

@app.get("/r/{encoded_token}")
async def proxy_stream(request: Request, encoded_token: str, tv: str = None):
    """Принимает Base64 токен, расшифровывает и маскирует содержимое или проксирует поток"""
    if tv != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    target_url = decode_url(encoded_token)

    host_url = request.headers.get("host") or os.environ.get("VERCEL_URL", "localhost:8000")
    protocol = "https" if "vercel.app" in host_url or "https" in request.url.scheme else "http"
    base_url = f"{protocol}://{host_url}"

    client = httpx.AsyncClient(follow_redirects=True, timeout=30.0)
    
    try:
        client_ua = request.headers.get("user-agent", "VLC/3.0.18 LibVLC/3.0.18")
        req = client.build_request("GET", target_url, headers={"User-Agent": client_ua})
        r = await client.send(req, stream=True)

        content_type = r.headers.get("content-type", "")

        # Если провайдер отдал m3u8 плейлист — перехватываем и ЗАМАСКИРОВЫВАЕМ все ссылки внутри него в Base64
        if "mpegurl" in content_type or "vnd.apple.mpegurl" in content_type or target_url.endswith(".m3u8"):
            playlist_content = await r.aread()
            playlist_text = playlist_content.decode('utf-8', errors='ignore')
            lines = playlist_text.splitlines()
            rewritten_lines = []

            for line in lines:
                line_str = line.strip()
                if line_str and not line_str.startswith("#"):
                    if not line_str.startswith("http"):
                        base_path = target_url.rsplit("/", 1)[0]
                        absolute_sub_url = f"{base_path}/{line_str}"
                    else:
                        absolute_sub_url = line_str

                    # Прячем каждую строчку вложенного плейлиста в Base64 токен
                    sub_token = encode_url(absolute_sub_url)
                    rewritten_lines.append(f"{base_url}/r/{sub_token}?tv={SECRET_KEY}")
                else:
                    rewritten_lines.append(line)

            return PlainTextResponse("\n".join(rewritten_lines), status_code=r.status_code, media_type="application/vnd.apple.mpegurl")

        # Если это видеопоток (чанки), отдаем через стандартный стриминг
        return StreamingResponse(
            r.aiter_bytes(),
            status_code=r.status_code,
            media_type=content_type or "video/mp2t"
        )
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to fetch upstream stream")
