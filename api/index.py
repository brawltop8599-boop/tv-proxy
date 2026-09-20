import base64
import httpx
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse, RedirectResponse

app = FastAPI()

PLAYLIST_TEXT = os.environ.get("PLAYLIST_DATA", "#EXTM3U")
SECRET_KEY = "tvzatak"

def encode_url(url: str) -> str:
    return base64.urlsafe_b64encode(url.encode('utf-8')).decode('utf-8').rstrip("=")

def decode_url(encoded_str: str) -> str:
    try:
        padding = 4 - (len(encoded_str) % 4)
        if padding < 4:
            encoded_str += "=" * padding
        return base64.urlsafe_b64decode(encoded_str.encode('utf-8')).decode('utf-8')
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid stream token")

def get_encoded_streams():
    lines = PLAYLIST_TEXT.splitlines()
    tokens = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            tokens.append(encode_url(line))
    return tokens

@app.get("/", response_class=PlainTextResponse)
def get_playlist(request: Request):
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
            full_link = f"{base_url}/r/{stream_index}?tv={SECRET_KEY}"
            new_lines.append(full_link)
            stream_index += 1
        else:
            new_lines.append(line)

    return "\n".join(new_lines)

@app.get("/r/{token}")
async def handle_request(request: Request, token: str, tv: str = None):
    if tv != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Access denied")

    if token.isdigit():
        index = int(token)
        tokens = get_encoded_streams()
        if not (0 <= index < len(tokens)):
            raise HTTPException(status_code=404, detail="Stream not found")
        
        encoded_token = tokens[index]
        return RedirectResponse(url=f"/r/{encoded_token}?tv={SECRET_KEY}", status_code=302)
    
    else:
        target_url = decode_url(token)

        host_url = os.environ.get("VERCEL_URL", "localhost:8000")
        protocol = "https" if "vercel.app" in host_url or request.url.scheme == "https" else "http"
        base_url = f"{protocol}://{host_url}"

        client = httpx.AsyncClient(follow_redirects=True, timeout=30.0)
        
        try:
            # Запрашиваем контент у провайдера
            req = client.build_request("GET", target_url, headers={"User-Agent": "Mozilla/5.0"})
            r = await client.send(req)

            content_type = r.headers.get("content-type", "")

            # Если провайдер отдал плейлист (.m3u8), переписываем ссылки внутри него!
            if "mpegurl" in content_type or "vnd.apple.mpegurl" in content_type or target_url.endswith(".m3u8"):
                playlist_content = r.text
                lines = playlist_content.splitlines()
                rewritten_lines = []

                for line in lines:
                    line_str = line.strip()
                    if line_str and not line_str.startswith("#"):
                        # Если ссылка внутри плейлиста относительная, превращаем в абсолютную к источнику
                        if not line_str.startswith("http"):
                            base_path = target_url.rsplit("/", 1)[0]
                            absolute_sub_url = f"{base_path}/{line_str}"
                        else:
                            absolute_sub_url = line_str

                        # Заворачиваем внутреннюю ссылку в наш Base64-прокси
                        sub_token = encode_url(absolute_sub_url)
                        rewritten_lines.append(f"{base_url}/r/{sub_token}?tv={SECRET_KEY}")
                    else:
                        rewritten_lines.append(line)

                return PlainTextResponse("\n".join(rewritten_lines), status_code=r.status_code)

            else:
                # Если это сам видеопоток (трансляция сегментов TS), стримим его как есть
                async def stream_generator():
                    async for chunk in r.aiter_bytes():
                        yield chunk

                return StreamingResponse(
                    stream_generator(),
                    status_code=r.status_code,
                    media_type=content_type or "video/mp2t"
                )

        except Exception:
            raise HTTPException(status_code=502, detail="Failed to fetch upstream stream")
