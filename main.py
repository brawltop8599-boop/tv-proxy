from fastapi import FastAPI, Response, Request
from fastapi.responses import RedirectResponse, PlainTextResponse, JSONResponse
import httpx
import time
import json
import urllib.parse
import os

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

async def get_valid_session_and_channels():
    global cached_channels, cached_token, session_time
    now = time.time()
    
    if cached_channels and cached_token and (now - session_time < 300):
        return cached_token, cached_channels

    initial_cookies = {
        "mac": MAC,
        "stb_lang": "en",
        "timezone": "Europe/London"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
        "X-User-Agent": "Model: MAG250; Link: WiFi",
        "Referer": "http://portal.sky2000.ru/stalker_portal/c/index.html",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
        "Pragma": "no-cache",
    }

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, cookies=initial_cookies, headers=headers) as client:
        try:
            await client.get(BASE_PORTAL_ROOT)

            hs_url = f"{PORTAL_URL}?type=stb&action=handshake&token=&JsHttpRequest=1-xml"
            hs_res = await client.get(hs_url)
            try:
                hs_data = hs_res.json()
            except Exception:
                print(f"Handshake non-JSON response: {hs_res.text[:200]}")
                return cached_token, cached_channels

            js_resp = hs_data.get("js", {})
            token = js_resp.get("token", "")
            rand_val = js_resp.get("random", RANDOM)

            if token:
                client.cookies.set("token", token)
                client.headers["Authorization"] = f"Bearer {token}"

            metrics_data = json.dumps({
                "type": "stb", "model": "MAG254", "mac": MAC, "sn": SN, "uid": UID, "random": rand_val
            })
            token_param = f"&token={token}" if token else ""
            prof_url = (
                f"{PORTAL_URL}?type=stb&action=get_profile&JsHttpRequest=1-xml&hd=1"
                f"{token_param}"
                "&ver=ImageDescription: 0.2.18-r23-250; ImageDate: Thu Sep 13 11:31:16 EEST 2018; PORTAL version: 5.3.0; API Version: JS API version: 343; STB API version: 146; Player Engine version: 0x58c"
                f"&num_banks=2&sn={SN}&stb_type=MAG250&client_type=STB&image_version=218&video_out=hdmi"
                f"&device_id={DEVICE_ID}&device_id2={DEVICE_ID}&signature={SIGNATURE}"
                f"&auth_second_step=1&hw_version=1.7-BD-00&not_valid_token=0"
                f"&metrics={urllib.parse.quote(metrics_data)}"
                f"&hw_version_2={HW_VERSION_2}&timestamp={int(now)}&api_signature=262&prehash={PREHASH}"
            )
            
            await client.get(prof_url)
            await client.get(f"{PORTAL_URL}?type=account_info&action=get_main_info&JsHttpRequest=1-xml")

            genres_map = {}
            try:
                genres_url = f"{PORTAL_URL}?type=itv&action=get_genres&JsHttpRequest=1-xml{token_param}"
                genres_res = await client.get(genres_url)
                g_text = genres_res.text.strip()
                if g_text.startswith("{") or g_text.startswith("["):
                    g_data = genres_res.json().get("js", [])
                    if isinstance(g_data, dict):
                        g_data = g_data.get("data", [])
                    for g in g_data:
                        gid = g.get("id")
                        gtitle = g.get("title", "Umumiy")
                        if gid is not None:
                            genres_map[str(gid)] = gtitle
                else:
                    print(f"Genres non-JSON response: {g_text[:150]}")
            except Exception as e:
                print(f"Genres error: {e}")

            channels = []
            seen_cmds = set()

            try:
                ch_url = f"{PORTAL_URL}?type=itv&action=get_all_channels&JsHttpRequest=1-xml{token_param}"
                ch_res = await client.get(ch_url)
                ch_text = ch_res.text.strip()
                if ch_text.startswith("{") or ch_text.startswith("["):
                    ch_json = ch_res.json()
                    js_data = ch_json.get("js", [])
                    data = js_data if isinstance(js_data, list) else (js_data.get("data") or js_data.get("channels") or [])
                    if isinstance(data, list):
                        channels = data
                else:
                    print(f"Channels non-JSON response: {ch_text[:150]}")
            except Exception as e:
                print(f"Get all channels error: {e}")

            if not channels:
                try:
                    list_url = f"{PORTAL_URL}?type=itv&action=get_ordered_list&genre=*&sortby=number&order=asc&hd=0&fav=0&not_my_genres=0&JsHttpRequest=1-xml{token_param}"
                    res = await client.get(list_url)
                    res_text = res.text.strip()
                    if res_text.startswith("{") or res_text.startswith("["):
                        res_json = res.json()
                        data = res_json.get("js", {}).get("data", [])
                        if not data and isinstance(res_json.get("js"), list):
                            data = res_json.get("js", [])
                        if isinstance(data, list):
                            channels = data
                    else:
                        print(f"Ordered list non-JSON response: {res_text[:150]}")
                except Exception as e:
                    print(f"Get ordered list error: {e}")

            formatted_channels = []
            for ch in channels:
                cmd = ch.get("cmd", "")
                if cmd:
                    if cmd in seen_cmds:
                        continue
                    seen_cmds.add(cmd)
                    
                    genre_id = str(ch.get("tv_genre_id", ch.get("genre_id", "")))
                    logo = ch.get("logo", "")
                    if logo and not logo.startswith("http"):
                        logo = f"http://portal.sky2000.ru/stalker_portal/misc/logos/{logo}"
                    
                    formatted_channels.append({
                        "name": ch.get("name", "Kanal"),
                        "cmd": cmd,
                        "timeshift": ch.get("timeshift", 0),
                        "group_title": genres_map.get(genre_id, "Umumiy"),
                        "logo": logo
                    })

            if formatted_channels:
                cached_channels = formatted_channels
                cached_token = token
                session_time = now
                print(f"Успешно загружено каналов: {len(cached_channels)}")

        except Exception as e:
            print(f"Session error: {e}")

    return cached_token, cached_channels

@app.get("/")
async def root():
    return RedirectResponse(url=TELEGRAM_GROUP, status_code=302)

@app.get("/pl.m3u8")
async def get_m3u8(request: Request):
    _, channels = await get_valid_session_and_channels()
    
    base_url = str(request.base_url).rstrip("/")
    
    m3u = ["#EXTM3U"]
    for idx, ch in enumerate(channels):
        shift = f' tvg-shift="{ch["timeshift"]}" catchup="default" catchup-days="3"' if ch["timeshift"] else ""
        group = f' group-title="{ch["group_title"]}"' if ch["group_title"] else ""
        logo = f' tvg-logo="{ch["logo"]}"' if ch["logo"] else ""
        m3u.append(f'#EXTINF:-1{group}{shift}{logo},{ch["name"]}')
        m3u.append(f"{base_url}/stream/{idx}?key={STREAM_KEY}")
        
    return Response(content="\n".join(m3u), media_type="audio/x-mpegurl; charset=utf-8")

@app.get("/stream/{idx}")
async def get_stream(idx: int, key: str):
    if key != STREAM_KEY:
        return RedirectResponse(url=STUB_VIDEO_URL, status_code=302)
        
    token, channels = await get_valid_session_and_channels()
    
    if idx < 0 or idx >= len(channels):
        return RedirectResponse(url=STUB_VIDEO_URL, status_code=302)
        
    target = channels[idx]
    stream_url = ""
    
    cookies = {"mac": MAC, "stb_lang": "en", "timezone": "Europe/London"}
    if token:
        cookies["token"] = token
        
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
        "X-User-Agent": "Model: MAG250; Link: WiFi",
        "Referer": "http://portal.sky2000.ru/stalker_portal/c/index.html",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, cookies=cookies, headers=headers) as client:
        try:
            token_param = f"&token={token}" if token else ""
            link_url = f"{PORTAL_URL}?type=itv&action=create_link&cmd={urllib.parse.quote(target['cmd'])}&JsHttpRequest=1-xml{token_param}"
            link_res = await client.get(link_url)
            link_text = link_res.text.strip()
            
            if link_text.startswith("{") or link_text.startswith("["):
                link_data = link_res.json()
                stream_cmd = link_data.get("js", {}).get("cmd") or link_data.get("js", {}).get("url") or link_data.get("cmd", "")
            else:
                print(f"Create link non-JSON response: {link_text[:150]}")
                stream_cmd = ""
            
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
        except Exception as e:
            print(f"Create link error: {e}")
            
        if not stream_url and target["cmd"]:
            fallback = target["cmd"]
            for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
                if fallback.startswith(prefix):
                    fallback = fallback[len(prefix):].strip()
            if fallback.startswith("http://") or fallback.startswith("https://"):
                stream_url = fallback
                
    if not stream_url:
        return RedirectResponse(url=STUB_VIDEO_URL, status_code=302)
        
    return RedirectResponse(url=stream_url, status_code=302)
