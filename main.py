from fastapi import FastAPI, Response, HTTPException, Request
from fastapi.responses import RedirectResponse
import httpx
import time
import json
import urllib.parse

app = FastAPI()

PORTAL_URL = "http://portal.sky2000.ru/stalker_portal/server/load.php"
BASE_PORTAL_ROOT = "http://portal.sky2000.ru/stalker_portal/"

MAC = "00:1A:79:4D:A5:73"
SN = "B4B46F9171F91"
UID = "E083654D924637D114AD665CAB20140D47EF48848AC71AF7CD82BC05E65E3396"
RANDOM = "a14652139f8947b0e4ed4d2046942614374a4c62"
DEVICE_ID = "A8E9507D432CA3C03C6FC104100D492B5D4C2C924BA7188786264603020B2C402"
SIGNATURE = "74032610A2B995182694D22397AE085A99412E8784545E4EDE7613A0C7136D08"
HW_VERSION_2 = "474e96e1873920cd1e6066ba5c6725fbe0f0f0a8"
PREHASH = "10980435162b4213af497d4568c3795deb340f5"

TELEGRAM_GROUP = "https://t.me/+2lWVU6CKQsVkMWRi"
STREAM_KEY = "TvZaTak"
STUB_VIDEO_URL = "https://github.com/brawltop8599-boop/ads-stub/raw/refs/heads/main/v.mp4?password=TvZaTak"

cached_channels = []
cached_token = ""
session_time = 0

def get_base_headers(token=""):
    cookie_str = f"mac={MAC}; stb_lang=en; timezone=Europe/London"
    if token:
        cookie_str += f"; token={token}"
    return {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
        "X-User-Agent": "Model: MAG250; Link: WiFi",
        "Referer": "http://portal.sky2000.ru/stalker_portal/c/index.html",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
        "Pragma": "no-cache",
        "Cookie": cookie_str
    }

async def get_valid_session():
    global cached_token, session_time
    now = time.time()
    if cached_token and (now - session_time < 300):
        return cached_token

    headers = get_base_headers()
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        try:
            await client.get(BASE_PORTAL_ROOT, headers=headers)
            
            hs_url = f"{PORTAL_URL}?type=stb&action=handshake&token=&JsHttpRequest=1-xml"
            hs_res = await client.get(hs_url, headers=headers)
            hs_data = hs_res.json()
            token = hs_data.get("js", {}).get("token") or hs_data.get("token", "")

            if token:
                cached_token = token
                session_time = now
                headers = get_base_headers(token)

            timestamp = int(now)
            metrics = json.dumps({
                "type": "stb", "model": "MAG254", "mac": MAC, "sn": SN, "uid": UID, "random": RANDOM
            })
            
            prof_url = f"{PORTAL_URL}?type=stb&action=get_profile&JsHttpRequest=1-xml&hd=1&ver=ImageDescription: 0.2.18-r23-250; ImageDate: Thu Sep 13 11:31:16 EEST 2018; PORTAL version: 5.3.0; API Version: JS API version: 343; STB API version: 146; Player Engine version: 0x58c&num_banks=2&sn={SN}&stb_type=MAG250&client_type=STB&image_version=218&video_out=hdmi&device_id={DEVICE_ID}&device_id2={DEVICE_ID}&signature={SIGNATURE}&auth_second_step=1&hw_version=1.7-BD-00&not_valid_token=0&metrics={urllib.parse.quote(metrics)}&hw_version_2={HW_VERSION_2}&timestamp={timestamp}&api_signature=262&prehash={PREHASH}"
            
            await client.get(prof_url, headers=headers)
            await client.get(f"{PORTAL_URL}?type=account_info&action=get_main_info&JsHttpRequest=1-xml", headers=headers)
        except Exception as e:
            print(f"Session error: {e}")

    return cached_token

async def update_channels_list():
    global cached_channels
    token = await get_valid_session()
    headers = get_base_headers(token)
    
    genres_map = {}
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        try:
            genres_url = f"{PORTAL_URL}?type=itv&action=get_genres&JsHttpRequest=1-xml"
            genres_res = await client.get(genres_url, headers=headers)
            print(f"Genres raw text: {genres_res.text[:300]}")
            genres_json = genres_res.json()
            genres_data = genres_json.get("js", [])
            if isinstance(genres_data, dict):
                genres_data = genres_data.get("data", [])
            for g in genres_data:
                if g.get("id") and g.get("title"):
                    genres_map[g["id"]] = g["title"]
        except Exception as e:
            print(f"Genres error details: {e}")

        try:
            channels_url = f"{PORTAL_URL}?type=itv&action=get_all_channels&JsHttpRequest=1-xml"
            res = await client.get(channels_url, headers=headers)
            print(f"Channels raw text: {res.text[:300]}")
            res_json = res.json()
            js_data = res_json.get("js", [])
            data = js_data if isinstance(js_data, list) else (js_data.get("data") or js_data.get("channels") or [])
            
            if data:
                seen = set()
                new_channels = []
                for ch in data:
                    cmd = ch.get("cmd")
                    if cmd and cmd not in seen:
                        seen.add(cmd)
                        genre_id = ch.get("tv_genre_id") or ch.get("genre_id") or ""
                        new_channels.append({
                            "name": ch.get("name") or ch.get("title") or "Kanal",
                            "cmd": cmd,
                            "timeshift": ch.get("timeshift", 0),
                            "group_title": genres_map.get(genre_id, "Umumiy")
                        })
                if new_channels:
                    cached_channels = new_channels
                    print(f"Successfully cached {len(cached_channels)} channels.")
        except Exception as e:
            print(f"Channels fetch error details: {e}")

@app.get("/")
async def root():
    return RedirectResponse(url=TELEGRAM_GROUP, status_code=302)

@app.get("/pl.m3u8")
async def get_m3u8(request: Request):
    if not cached_channels:
        await update_channels_list()
    
    base_url = str(request.base_url).rstrip("/")
    
    m3u = ["#EXTM3U"]
    for idx, ch in enumerate(cached_channels):
        shift = f' tvg-shift="{ch["timeshift"]}" catchup="default" catchup-days="3"' if ch["timeshift"] else ""
        group = f' group-title="{ch["group_title"]}"' if ch["group_title"] else ""
        m3u.append(f'#EXTINF:-1{group}{shift},{ch["name"]}')
        m3u.append(f"{base_url}/stream/{idx}?key={STREAM_KEY}")
        
    return Response(content="\n".join(m3u), media_type="audio/x-mpegurl; charset=utf-8")

@app.get("/stream/{idx}")
async def get_stream(idx: int, key: str):
    if key != STREAM_KEY:
        return RedirectResponse(url=STUB_VIDEO_URL, status_code=302)
        
    if not cached_channels or idx >= len(cached_channels):
        await update_channels_list()
        
    if idx < 0 or idx >= len(cached_channels):
        return RedirectResponse(url=STUB_VIDEO_URL, status_code=302)
        
    target = cached_channels[idx]
    stream_url = ""
    
    token = await get_valid_session()
    headers = get_base_headers(token)
    
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        try:
            link_url = f"{PORTAL_URL}?type=itv&action=create_link&cmd={urllib.parse.quote(target['cmd'])}&JsHttpRequest=1-xml"
            link_res = await client.get(link_url, headers=headers)
            link_data = link_res.json()
            
            stream_cmd = link_data.get("js", {}).get("cmd") or link_data.get("js", {}).get("url") or link_data.get("cmd", "")
            
            for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
                if stream_cmd.startswith(prefix):
                    stream_cmd = stream_cmd[len(prefix):].strip()
                    
            if stream_cmd.startswith("http://") or stream_cmd.startswith("https://"):
                stream_url = stream_cmd
            elif stream_cmd.startswith("/"):
                portal_parsed = urllib.parse.urlparse(PORTAL_URL)
                stream_url = f"{portal_parsed.scheme}://{portal_parsed.netloc}{stream_cmd}"
                
            if stream_url and "token=" not in stream_url and token:
                sep = "&" if "?" in stream_url else "?"
                stream_url = f"{stream_url}{sep}token={token}"
        except Exception:
            pass
            
        if not stream_url and target["cmd"]:
            fallback = target["cmd"]
            for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
                if fallback.startswith(prefix):
                    fallback = fallback[len(prefix):].strip()
            if fallback.startswith("http://") or fallback.startswith("https://"):
                stream_url = fallback
                
    9  # placeholder
    if not stream_url:
        return RedirectResponse(url=STUB_VIDEO_URL, status_code=302)
        
    return RedirectResponse(url=stream_url, status_code=302)
