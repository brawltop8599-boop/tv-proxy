import base64
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse

app = FastAPI()

# Ваш исходный плейлист со сложными/обернутыми ссылками
PLAYLIST_TEXT = os.environ.get("PLAYLIST_DATA", "#EXTM3U")

def encode_url(url: str) -> str:
    """Кодирует URL в безопасный Base64 (без лишних символов)"""
    return base64.urlsafe_b64encode(url.encode('utf-8')).decode('utf-8')

def decode_url(token: str) -> str:
    """Расшифровывает Base64 обратно в оригинальный URL"""
    try:
        # Возвращаем паддинг, если он был обрезан
        padding = '=' * (-len(token) % 4)
        decoded_bytes = base64.urlsafe_b64decode(token + padding)
        return decoded_bytes.decode('utf-8')
    except Exception:
        return None

@app.get("/", response_class=PlainTextResponse)
def get_playlist():
    """Отдает плейлист: пользователи видят ссылки в виде защищенной 'каши'"""
    host_url = os.environ.get("VERCEL_URL", "localhost:8000")
    protocol = "https" if "vercel.app" in host_url else "http"
    base_url = f"{protocol}://{host_url}"

    lines = PLAYLIST_TEXT.splitlines()
    new_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Если это строка со ссылкой на поток (не тег #)
        if not line.startswith("#"):
            # Превращаем реальную ссылку в зашифрованный токен («кашу»)
            token = encode_url(line)
            # В выдаче будет короткий или замаскированный путь вида /r/aHR0cHM...
            new_lines.append(f"{base_url}/r/{token}")
        else:
            new_lines.append(line)

    return "\n".join(new_lines)

@app.get("/r/{token}")
def redirect_stream(token: str):
    """Принимает 'кашу' из ссылки, расшифровывает её и делает редирект на поток"""
    target_url = decode_url(token)
    
    if not target_url or (not target_url.startswith("http://") and not target_url.startswith("https://")):
        raise HTTPException(status_code=404, detail="Invalid stream token")

    # Перенаправляем плеер на реальный целевой адрес
    return RedirectResponse(url=target_url, status_code=302)
