import base64
import httpx
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse

app = FastAPI()

PLAYLIST_TEXT = os.environ.get("PLAYLIST_DATA", "#EXTM3U")
SECRET_KEY = "tvzatak"

def encode_url(url: str) -> str:
    """Кодирует ссылку в Base64 и делает безопасной для URL"""
    return base64.urlsafe_b64encode(url.encode('utf-8')).decode('utf-8').rstrip("=")

def decode_url(encoded_str: str) -> str:
    """Раскодирует Base64 обратно в оригинальный URL"""
    try:
        # Возвращаем недостающие символы заполнения '=' если они были обрезанны
        padding = 4 - (len(encoded_str) % 4)
        if padding < 4:
            encoded_str += "=" * padding
        return base64.urlsafe_b64decode(encoded_str.encode('utf-8')).decode('utf-8')
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid stream token")

@app.get("/", response_class=PlainTextResponse)
def get_playlist(request: Request):
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
            # Прячем оригинальную ссылку внутри Base64 «каши»
            encoded_token = encode_url(line)
            new_lines.append(f"{base_url}/r/{encoded_token}?tv={SECRET_KEY}")
        else:
            new_lines.append(line)

    return "\n".join(new_lines)

@app.get("/r/{encoded_token}")
async def proxy_stream(encoded_token: str, tv: str = None):
    """Принимает закодированный Base64 токен, расшифровывает и проксирует поток"""
    if tv != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    # Достаем оригинальную ссылку из Base64 каши на лету
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
