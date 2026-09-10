import json
import os
import threading
import time
from fastapi import FastAPI, Response, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
import requests

PORTAL_URL = "http://portal.sky2000.ru/stalker_portal/server/load.php"
BASE_PORTAL_ROOT = "http://portal.sky2000.ru/stalker_portal/"

# Актуальные рабочие параметры из успешных логов
MAC_BASE = "00:1A:79:4D:A5:73"
SN_BASE = "B4B46F9171F91"
UID_BASE = "E083654D924637D114AD665CAB20140D47EF4B848AC71AF7CD82BC05E65E3396"
RANDOM_BASE = "738467760e694b5ed83acca3686045239a04f94a"
DEVICE_ID = "A8E9507D432CA3C03C6FC10410D492B5D4C2C924BA7188786264603020B2C402"
SIGNATURE = "74032610A2B99519B2694D22397AE085A99412E8784545E4EDE7613A0C7136D0"
HW_VERSION_2 = "474e96e1873920cd1e6066ba5c6725fbe0f0f0a8"
PREHASH = "10980435162b4213af497d4568c37959deb340f5"

BASE_PROXY_URL = "https://tv-fby3.onrender.com"
SECRET_KEY = "TvZaTak"
TELEGRAM_GROUP_URL = "https://t.me/+2lWVU6CKQsVkMWRi"  

app = FastAPI()

status_data = {
    "last_update": "Hali yangilanmagan",
    "total_channels": 0,
    "status": "Ishga tushmoqda...",
}

global_session = None
session_created_time = 0

def get_session(force_new=False):
    global global_session, session_created_time
    
    if not force_new and global_session and (time.time() - session_created_time) < 300:
        return global_session

    session = requests.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like"
            " Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3"
        ),
        "X-User-Agent": "Model: MAG250; Link: WiFi",
        "Referer": "http://portal.sky2000.ru/stalker_portal/c/index.html",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
        "Pragma": "no-cache",
    }
    session.headers.update(headers)
    session.cookies.set("mac", MAC_BASE, domain="portal.sky2000.ru")
    session.cookies.set("stb_lang", "en", domain="portal.sky2000.ru")
    session.cookies.set("timezone", "Europe/London", domain="portal.sky2000.ru")

    try:
        session.get(BASE_PORTAL_ROOT, timeout=5)
    except Exception:
        pass

    token = ""
    random_val = RANDOM_BASE
    try:
        hs_url = f"{PORTAL_URL}?type=stb&action=handshake&token=&JsHttpRequest=1-xml"
        r = session.get(hs_url, timeout=10).json()
        js_data = r.get("js", {})
        token = js_data.get("token", "")
        random_val = js_data.get("random", random_val)
        
        if token:
            session.cookies.set("token", token, domain="portal.sky2000.ru")
            session.headers.update({"Authorization": f"Bearer {token}"})
    except Exception:
        pass

    metrics_data = json.dumps({
        "type": "stb",
        "model": "MAG254",
        "mac": MAC_BASE,
        "sn": SN_BASE,
        "uid": UID_BASE,
        "random": random_val,
    })

    token_param = f"&token={token}" if token else ""
    prof_url = (
        f"{PORTAL_URL}?type=stb&action=get_profile&JsHttpRequest=1-xml&hd=1"
        f"{token_param}"
        "&ver=ImageDescription: 0.2.18-r23-250; ImageDate: Thu Sep 13 11:31:16 EEST 2018; PORTAL version: 5.3.0; API Version: JS API version: 343; STB API version: 146; Player Engine version: 0x58c"
        f"&num_banks=2&sn={SN_BASE}&stb_type=MAG250&client_type=STB&image_version=218&video_out=hdmi"
        f"&device_id={DEVICE_ID}"
        f"&device_id2={DEVICE_ID}"
        f"&signature={SIGNATURE}"
        "&auth_second_step=1&hw_version=1.7-BD-00&not_valid_token=0"
        f"&metrics={metrics_data}"
        f"&hw_version_2={HW_VERSION_2}&timestamp={int(time.time())}&api_signature=262&prehash={PREHASH}"
    )
    try:
        session.get(prof_url, timeout=10)
    except Exception:
        pass

    try:
        acc_url = f"{PORTAL_URL}?type=account_info&action=get_main_info&JsHttpRequest=1-xml"
        session.get(acc_url, timeout=10)
    except Exception:
        pass

    global_session = session
    session_created_time = time.time()
    return session

def fetch_channels_data(session):
    genres_map = {}
    try:
        genres_url = f"{PORTAL_URL}?type=itv&action=get_genres&JsHttpRequest=1-xml"
        g_resp = session.get(genres_url, timeout=10).json()
        g_data = g_resp.get("js", [])
        if isinstance(g_data, dict):
            g_data = g_data.get("data", [])
        if isinstance(g_data, list):
            for g in g_data:
                gid = g.get("id")
                gtitle = g.get("title", "Boshqa")
                if gid is not None:
                    genres_map[str(gid)] = gtitle
    except Exception:
        pass

    channels = []
    seen_cmds = set()

    try:
        channels_url = f"{PORTAL_URL}?type=itv&action=get_all_channels&JsHttpRequest=1-xml"
        channels_res = session.get(channels_url, timeout=10).json()
        js_data = channels_res.get("js", [])
        data = js_data if isinstance(js_data, list) else (js_data.get("data") or js_data.get("channels") or [])
        if isinstance(data, list):
            channels = data
    except Exception:
        pass

    if not channels:
        try:
            list_url = f"{PORTAL_URL}?type=itv&action=get_ordered_list&genre=*&sortby=number&order=asc&hd=0&fav=0&not_my_genres=0&JsHttpRequest=1-xml"
            res = session.get(list_url, timeout=10).json()
            data = res.get("js", {}).get("data", [])
            if not data and isinstance(res.get("js"), list):
                data = res.get("js", [])
            if isinstance(data, list):
                channels = data
        except Exception:
            pass

    try:
        if genres_map:
            for gid in genres_map.keys():
                sub_url = f"{PORTAL_URL}?type=itv&action=get_ordered_list&genre={gid}&sortby=number&order=asc&hd=0&fav=0&not_my_genres=0&JsHttpRequest=1-xml"
                sub_resp = session.get(sub_url, timeout=5).json()
                sub_data = sub_resp.get("js", {}).get("data", [])
                if isinstance(sub_data, list):
                    for ch in sub_data:
                        cmd = ch.get("cmd", "")
                        if cmd and cmd not in seen_cmds:
                            seen_cmds.add(cmd)
                            channels.append(ch)
    except Exception:
        pass

    return channels, genres_map

def update_playlist():
    global status_data
    status_data["status"] = "Yangilanmoqda..."

    session = get_session(force_new=False)
    channels, genres_map = fetch_channels_data(session)

    if not channels:
        session = get_session(force_new=True)
        channels, genres_map = fetch_channels_data(session)

    channels_list = []
    seen_cmds = set()
    for ch in channels:
        ch_name = ch.get("name", "Kanal")
        cmd = ch.get("cmd", "")
        
        if cmd and cmd not in seen_cmds:
            seen_cmds.add(cmd)
            genre_id = str(ch.get("tv_genre_id", ch.get("genre_id", "")))
            group_title = genres_map.get(genre_id, "Umumiy")

            channels_list.append({
                "name": ch_name,
                "cmd": cmd,
                "group": group_title
            })

    temp_file = "playlist.tmp"
    final_file = "playlist.json"

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(channels_list, f, ensure_ascii=False, indent=4)

    if os.path.exists(final_file):
        os.remove(final_file)
    os.rename(temp_file, final_file)

    status_data["last_update"] = time.strftime(
        "%Y-%m-%d %H:%M:%S", time.localtime()
    )
    status_data["total_channels"] = len(channels_list)
    status_data["status"] = "Muvaffaqiyatli ishlayapti ✅" if len(channels_list) > 0 else "Kanal topilmadi ⚠️"

def background_worker():
    while True:
        try:
            update_playlist()
        except Exception as e:
            print(f"Xatolik: {e}")
        time.sleep(300)

@app.on_event("startup")
def startup_event():
    t = threading.Thread(target=background_worker, daemon=True)
    t.start()

@app.get("/", response_class=RedirectResponse)
def root_redirect():
    return RedirectResponse(url=TELEGRAM_GROUP_URL, status_code=302)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/playlist.json")
def download_json(key: str = ""):
    if key != SECRET_KEY:
        return [{"name": "Reklama / Xatolik", "group": "Stub", "url": "https://github.com/brawltop8599-boop/ads-stub/raw/refs/heads/main/v.mp4"}]

    if os.path.exists("playlist.json"):
        with open("playlist.json", "r", encoding="utf-8") as f:
            channels = json.load(f)
        result = []
        for index, ch in enumerate(channels):
            result.append({
                "name": ch["name"],
                "group": ch.get("group", "Umumiy"),
                "url": f"{BASE_PROXY_URL}/ch/{index}?key={SECRET_KEY}"
            })
        return result
    return JSONResponse(content={"error": "Hali playlist tayyor emas!"}, status_code=404)

@app.get("/pl.m3u8", response_class=PlainTextResponse)
@app.get("/playlist.m3u8", response_class=PlainTextResponse)
def download_m3u8(key: str = ""):
    headers = {"Content-Disposition": "attachment; filename=playlist.m3u8"}

    if key != SECRET_KEY:
        content = (
            "#EXTM3U\n"
            "#EXTINF:-1 tvg-name=\"Xato kalit / Reklama\" group-title=\"Stub\",Xato kalit / Reklama\n"
            "https://github.com/brawltop8599-boop/ads-stub/raw/refs/heads/main/v.mp4"
        )
        return PlainTextResponse(content, headers=headers)

    if not os.path.exists("playlist.json"):
        return PlainTextResponse("#EXTM3U\n# Xatolik: Playlist hali tayyorlanmadi", headers=headers)

    try:
        with open("playlist.json", "r", encoding="utf-8") as f:
            channels = json.load(f)
    except Exception:
        return PlainTextResponse("#EXTM3U\n# Xatolik: Playlistni o'qib bo'lmadi", headers=headers)

    m3u_lines = ["#EXTM3U"]
    for index, ch in enumerate(channels):
        name = ch.get("name", "Kanal")
        group = ch.get("group", "Umumiy")
        stream_link = f"{BASE_PROXY_URL}/ch/{index}?key={SECRET_KEY}"
        
        m3u_line = f"#EXTINF:-1 tvg-name=\"{name}\" group-title=\"{group}\",{name}"
        m3u_lines.append(m3u_line)
        m3u_lines.append(stream_link)

    playlist_content = "\n".join(m3u_lines)
    return PlainTextResponse(playlist_content, headers=headers)

@app.get("/ch/{index}")
def proxy_stream(index: int, key: str = ""):
    if key != SECRET_KEY:
        return RedirectResponse(url="https://github.com/brawltop8599-boop/ads-stub/raw/refs/heads/main/v.mp4", status_code=302)

    if not os.path.exists("playlist.json"):
        return Response("Playlist topilmadi", status_code=404)
    
    try:
        with open("playlist.json", "r", encoding="utf-8") as f:
            channels = json.load(f)
        target = channels[index]
        cmd = target.get("cmd", "")
    except Exception as e:
        return Response(f"Kanal topilmadi: {e}", status_code=404)

    session = get_session()
    stream_url = ""
    
    try:
        clean_cmd = cmd
        for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
            if clean_cmd.startswith(prefix):
                clean_cmd = clean_cmd[len(prefix):].strip()
                
        link_url = f"{PORTAL_URL}?type=itv&action=create_link&cmd={requests.utils.quote(clean_cmd)}&JsHttpRequest=1-xml"
        link_res = session.get(link_url, timeout=10).json()
        
        stream_cmd = link_res.get("js", {}).get("cmd") or link_res.get("js", {}).get("url") or link_res.get("cmd", "")
        if stream_cmd:
            stream_url = stream_cmd
            for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
                if stream_url.startswith(prefix):
                    stream_url = stream_url[len(prefix):].strip()
    except Exception as e:
        print(f"Create link xatolik (stream): {e}")

    if not stream_url or stream_url.startswith("/ch/") or ("://" not in stream_url and not stream_url.startswith("/")):
        fallback_url = cmd
        for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
            if fallback_url.startswith(prefix):
                fallback_url = fallback_url[len(prefix):].strip()
        
        if "://" in fallback_url:
            stream_url = fallback_url

    portal_parsed = requests.utils.urlparse(PORTAL_URL)
    portal_base_domain = f"{portal_parsed.scheme}://{portal_parsed.netloc}"

    if stream_url.startswith("/") and not stream_url.startswith("/ch/"):
        stream_url = f"{portal_base_domain}{stream_url}"
    elif not stream_url.startswith("http") and stream_url and not stream_url.startswith("/ch/"):
        stream_url = f"{portal_base_domain}/{stream_url}"

    if stream_url.startswith("/ch/"):
        stream_url = ""

    if stream_url and "token=" not in stream_url:
        session_token = session.cookies.get("token")
        if session_token:
            separator = "&" if "?" in stream_url else "?"
            stream_url = f"{stream_url}{separator}token={session_token}"

    if not stream_url:
        return Response("Stream URL yaratib bo'lmadi", status_code=500)

    return RedirectResponse(url=stream_url, status_code=302)
