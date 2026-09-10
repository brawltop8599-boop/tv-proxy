from fastapi import FastAPI, Response, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
import requests
import threading
import time
import json
import os

PORTAL_URL = "http://iptv.ria-link.tv/stalker_portal/server/load.php"
MAC_BASE = "00:1A:79:0D:27:10"  # Skrinshohdagi ishlayotgan MAC manzil
BASE_PROXY_URL = "https://tv-fby3.onrender.com"

app = FastAPI()

status_data = {
    "last_update": "Hali yangilanmagan",
    "total_channels": 0,
    "status": "Ishga tushmoqda...",
}

def get_session():
    print("get_session: сессия yaratilmoqda...")
    session = requests.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like"
            " Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3"
        ),
        "X-User-Agent": "Model: MAG250; Link: WiFi",
        "Referer": "http://iptv.ria-link.tv/stalker_portal/c/index.html",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
        "Pragma": "no-cache",
    }
    session.headers.update(headers)
    session.cookies.set("mac", MAC_BASE, domain="iptv.ria-link.tv")
    session.cookies.set("stb_lang", "en", domain="iptv.ria-link.tv")
    session.cookies.set("timezone", "Europe/London", domain="iptv.ria-link.tv")
    
    try:
        session.get("http://iptv.ria-link.tv/stalker_portal/c/", timeout=5)
        session.get("http://iptv.ria-link.tv/stalker_portal/c/version.js", timeout=5)
    except Exception:
        pass
        
    token = ""
    try:
        hs_url = "http://iptv.ria-link.tv/stalker_portal/server/load.php?type=stb&action=handshake&token=&JsHttpRequest=1-xml"
        resp = session.get(hs_url, timeout=10)
        r = resp.json()
        token = r.get("js", {}).get("token", "")
        if token:
            session.cookies.set("token", token, domain="iptv.ria-link.tv")
            session.headers.update({"Authorization": f"Bearer {token}"})
            print(f"Handshake token olindi: {token}")
    except Exception as e:
        print(f"Handshake xatolik: {e}")
        
    metrics_data = json.dumps({
        "type": "stb",
        "model": "MAG254",
        "mac": MAC_BASE,
        "sn": "EC2587E8E3526",
        "uid": "4B1F3F65BC57384B9D02562E5C907B1296D5A36A28B400DF0A6EB805CC38F430",
        "random": "719f4589c102473af519069d92bb1c619784c03f",
    })
    token_param = f"&token={token}" if token else ""
    prof_url = (
        f"{PORTAL_URL}?type=stb&action=get_profile&JsHttpRequest=1-xml&hd=1"
        f"{token_param}"
        "&ver=ImageDescription: 0.2.18-r23-250; ImageDate: Thu Sep 13 11:31:16 EEST 2018; PORTAL version: 5.3.0; API Version: JS API version: 343; STB API version: 146; Player Engine version: 0x58c"
        "&num_banks=2&sn=EC2587E8E3526&stb_type=MAG250&client_type=STB&image_version=218&video_out=hdmi"
        "&device_id=CEDAE642ABBA74E97D816E9DA90BA9DEF2BD00751B16D9DE92EF2CC4E89C3401"
        "&device_id2=CEDAE642ABBA74E97D816E9DA90BA9DEF2BD00751B16D9DE92EF2CC4E89C3401"
        "&signature=BE897368966112541E6710E75FEFCEDB9A17B5AB34DBE27025E6ED8CF1278904"
        "&auth_second_step=1&hw_version=1.7-BD-00&not_valid_token=0"
        f"&metrics={metrics_data}"
        f"&hw_version_2=664706d2663465ad4cbae0db0c8cff6d48dd02c8&timestamp={int(time.time())}&api_signature=262&prehash=4dc5be07506806521482ae0f0e385a88182091a2"
    )
    try:
        session.get(prof_url, timeout=10)
        session.get(f"{PORTAL_URL}?type=account_info&action=get_main_info&JsHttpRequest=1-xml", timeout=10)
    except Exception as e:
        print(f"Profile/Account xatolik: {e}")
        
    return session

def update_playlist():
    global status_data
    print("--- UPDATE_PLAYLIST BOSHLANDI ---")
    status_data["status"] = "Yangilanmoqda..."
    
    session = get_session()
    channels = []
    
    try:
        channels_url = f"{PORTAL_URL}?type=itv&action=get_all_channels&JsHttpRequest=1-xml"
        channels_resp = session.get(channels_url, timeout=10)
        res_json = channels_resp.json()
        
        # Stalkerdan keladigan javob tuzilmasini tekshirish
        data = res_json.get("js", [])
        if isinstance(data, dict):
            channels = data.get("data", [])
        elif isinstance(data, list):
            channels = data
    except Exception as e:
        print(f"Каналларни олишда хатолик: {e}")

    print(f"Жами топилган каналлар сони: {len(channels)}")

    channels_list = []
    for target_channel in channels:
        ch_name = target_channel.get("name", "Kanal")
        cmd = target_channel.get("cmd", "")
        if cmd:
            channels_list.append({
                "name": ch_name,
                "cmd": cmd
            })

    temp_file = "playlist.tmp"
    final_file = "playlist.json"
    
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(channels_list, f, ensure_ascii=False, indent=4)
        
    if os.path.exists(final_file):
        os.remove(final_file)
    os.rename(temp_file, final_file)
    
    status_data["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    status_data["total_channels"] = len(channels_list)
    status_data["status"] = "Muvaffaqiyatli ishlayapti ✅" if len(channels_list) > 0 else "Kanal topilmadi ⚠️"
    print("--- UPDATE_PLAYLIST TUGADI ---")

def background_worker():
    while True:
        try:
            update_playlist()
        except Exception as e:
            print(f"BACKGROUND WORKER XATOLIGI: {e}")
        time.sleep(300)

@app.on_event("startup")
def startup_event():
    t = threading.Thread(target=background_worker, daemon=True)
    t.start()

@app.get("/", response_class=HTMLResponse)
def admin_panel():
    return f"""
    <!DOCTYPE html>
    <html lang="uz">
    <head>
        <meta charset="UTF-8">
        <title>IPTV Admin Panel</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #0f172a; color: #f8fafc; text-align: center; padding: 50px; }}
            .card {{ background: #1e293b; padding: 30px; border-radius: 12px; display: inline-block; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }}
            .badge {{ background: #22c55e; color: white; padding: 5px 12px; border-radius: 20px; font-weight: bold; }}
            a {{ color: #38bdf8; text-decoration: none; display: block; margin-top: 15px; font-size: 18px; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>🚀 IPTV Proxy Admin Panel</h2>
            <p>Holati: <span class="badge">{status_data["status"]}</span></p>
            <p><b>Kanallar soni:</b> {status_data["total_channels"]} ta</p>
            <p><b>Oxirgi yangilangan vaqt:</b> {status_data["last_update"]}</p>
            <hr style="border: 0.5px solid #334155; margin: 20px 0;">
            <a href="/pl.m3u8" target="_blank">📥 M3U Playlist (/pl.m3u8)</a>
            <a href="/playlist.json" target="_blank" style="color: #94a3b8; font-size: 14px;">📄 JSON ni ko'rish (/playlist.json)</a>
        </div>
    </body>
    </html>
    """

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/playlist.json")
def download_json():
    if os.path.exists("playlist.json"):
        with open("playlist.json", "r", encoding="utf-8") as f:
            channels = json.load(f)
        result = []
        for index, ch in enumerate(channels):
            result.append({
                "name": ch["name"],
                "url": f"{BASE_PROXY_URL}/stream/{index}"
            })
        return result
    return {"error": "Hali playlist tayyor emas!"}, 404

@app.get("/pl.m3u8", response_class=PlainTextResponse)
def download_m3u8():
    if not os.path.exists("playlist.json"):
        return "#EXTM3U\n# Xatolik: Playlist hali tayyorlanmadi"
    try:
        with open("playlist.json", "r", encoding="utf-8") as f:
            channels = json.load(f)
    except Exception:
        return "#EXTM3U\n# Xatolik: Playlistni o'qib bo'lmadi"
        
    m3u_lines = ["#EXTM3U"]
    for index, ch in enumerate(channels):
        name = ch.get("name", "Kanal")
        stream_link = f"{BASE_PROXY_URL}/stream/{index}"
        m3u_lines.append(f"#EXTINF:-1,{name}")
        m3u_lines.append(stream_link)
    return "\n".join(m3u_lines)

@app.get("/stream/{index}")
def proxy_stream(index: int):
    if not os.path.exists("playlist.json"):
        return Response("Playlist topilmadi", status_code=404)
    
    try:
        with open("playlist.json", "r", encoding="utf-8") as f:
            channels = json.load(f)
        target = channels[index]
        cmd = target["cmd"]
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
        
        stream_cmd = link_res.get("js", {}).get("cmd")
        if stream_cmd:
            stream_url = stream_cmd
            for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
                if stream_url.startswith(prefix):
                    stream_url = stream_url[len(prefix):].strip()
    except Exception as e:
        print(f"Create link xatolik (stream): {e}")

    if not stream_url and "http" in cmd:
        stream_url = cmd
        for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
            if stream_url.startswith(prefix):
                stream_url = stream_url[len(prefix):].strip()

    if stream_url and "token=" not in stream_url:
        session_token = session.cookies.get("token")
        if session_token:
            separator = "&" if "?" in stream_url else "?"
            stream_url = f"{stream_url}{separator}token={session_token}"
    
    if not stream_url:
        return Response("Stream URL яратиб бўлмади", status_code=500)

    return RedirectResponse(url=stream_url, status_code=302)
