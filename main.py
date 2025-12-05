import sys
import os

if getattr(sys, 'frozen', False):
    import io
    if sys.stdout is not None:
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8', errors='replace')
    if sys.stderr is not None:
        sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8', errors='replace')
    
    import logging
    logging.getLogger("yt_dlp").setLevel(100) 

os.environ["PYTHONIOENCODING"] = "utf-8"

import webview
import yt_dlp
import json
import base64
import threading
import time
import platform
import subprocess
from http.server import SimpleHTTPRequestHandler, socketserver
from webview import FileDialog  

LOGO_SVG = """<svg width="128" height="128" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg">
  <circle cx="64" cy="64" r="60" fill="#ff0055" opacity="0.2"/>
  <circle cx="64" cy="64" r="45" fill="#ff0055" opacity="0.4"/>
  <path d="M64 20 L90 50 L64 80 L38 50 Z" fill="#ff0055"/>
  <circle cx="64" cy="64" r="20" fill="#0e1117"/>
  <path d="M58 58 L74 68 L58 78 Z" fill="#fff"/>
</svg>"""
LOGO_BASE64 = base64.b64encode(LOGO_SVG.encode()).decode()

html_content = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Media Downloader 1.1</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
    :root { --primary:#ff0055; --bg:#0a0e17; --card:#151b2e; }
    * { box-sizing:border-box; margin:0; padding:0; }
    body { background:linear-gradient(135deg,#0a0e17,#1a0033); color:#fff; font-family:'Segoe UI',sans-serif; min-height:100vh; padding:20px; overflow-x:hidden; }
    .container { max-width:960px; margin:0 auto; }
    .header { text-align:center; margin-bottom:40px; }
    .logo-big { width:100px; filter:drop-shadow(0 0 20px var(--primary)); animation:pulse 3s infinite; }
    @keyframes pulse { 0%,100% { filter:drop-shadow(0 0 20px var(--primary)); } 50% { filter:drop-shadow(0 0 30px #ff3399); } }
    h1 { margin:12px 0; font-size:2.7em; background:linear-gradient(90deg,#ff0055,#ffaa00); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
    .support { color:#999; font-size:0.92em; letter-spacing:1px; }
    .input-box { width:100%; padding:18px; border-radius:14px; border:none; background:var(--card); color:#fff; font-size:1.1em; box-shadow:0 6px 20px rgba(0,0,0,0.5); }
    .btn { background:var(--primary); padding:15px 32px; border:none; border-radius:12px; color:#fff; font-weight:bold; cursor:pointer; margin:12px 6px 0 0; transition:all .3s; font-size:1.05em; }
    .btn:hover { background:#cc0044; transform:translateY(-4px); box-shadow:0 10px 25px rgba(255,0,85,.6); }
    .btn-success { background:#00c853; padding:12px 24px; font-size:0.95em; }
    .card { background:var(--card); padding:30px; border-radius:18px; margin:25px 0; box-shadow:0 12px 40px rgba(0,0,0,0.7); display:none; }
    .card.show { display:block; animation:fadeIn 0.6s; }
    @keyframes fadeIn { from { opacity:0; transform:translateY(20px); } to { opacity:1; transform:none; } }
    .info { display:grid; grid-template-columns:260px 1fr; gap:30px; align-items:start; }
    .thumb { width:100%; border-radius:14px; box-shadow:0 12px 30px rgba(0,0,0,0.8); }
    .slider { -webkit-appearance:none; width:100%; height:16px; border-radius:10px; background:#333; outline:none; margin:20px 0; }
    .slider::-webkit-slider-thumb { -webkit-appearance:none; width:36px; height:36px; border-radius:50%; background:var(--primary); cursor:pointer; box-shadow:0 0 25px rgba(255,0,85,0.9); }
    .select-wrapper { position:relative; margin:18px 0; }
    .select-wrapper select { width:100%; padding:16px 45px 16px 18px; border-radius:14px; border:none; background:#222; color:#fff; font-size:1em; cursor:pointer; appearance:none; box-shadow:0 4px 15px rgba(0,0,0,0.4); }
    .select-wrapper::after { content:'Down Arrow'; position:absolute; right:18px; top:50%; transform:translateY(-50%); color:#aaa; font-size:1.1em; pointer-events:none; }
    .total { font-size:1.7em; font-weight:bold; color:var(--primary); margin:15px 0; }
    .status { text-align:center; font-size:1.4em; margin:30px 0; color:var(--primary); min-height:40px; }
    .my-logo { position:fixed; bottom:18px; right:18px; width:56px; opacity:0.75; cursor:pointer; transition:all .4s; border-radius:14px; box-shadow:0 6px 20px rgba(0,0,0,0.8); z-index:9999; }
    .my-logo:hover { opacity:1; transform:scale(1.3); filter:drop-shadow(0 0 30px #ff0055); }
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <img src="data:image/svg+xml;base64,""" + LOGO_BASE64 + """ " class="logo-big" alt="Logo">
        <h1>Media Downloader 1.1</h1>
        <div class="support">YouTube • TikTok • Facebook • Instagram • Twitter • SoundCloud</div>
    </div>
    <input type="text" id="url" class="input-box" placeholder="Paste video/audio URL here..." autofocus>
    <div><button class="btn" onclick="process()">Analyze & Extract</button></div>
    <div class="card" id="media-card">
        <div class="info">
            <img id="thumb" class="thumb" src="" alt="Thumbnail">
            <div>
                <h2 id="title">-</h2>
                <p>Uploader: <span id="uploader">-</span></p>
                <p>Duration: <span id="orig-duration">0:00</span></p>
                <div class="total" id="total-duration">Total after loop: 0:00</div>
                <label>Loop Count: <span id="loop-val">1</span>x</label>
                <input type="range" min="1" max="100" value="1" class="slider" id="loop-slider" oninput="updateLoop()">
                <div class="select-wrapper">
                    <select id="output-type" onchange="toggleVideoQuality()">
                        <option value="video">Video + Audio (MP4)</option>
                        <option value="mp3">Audio Only - MP3 320kbps</option>
                        <option value="wav">Audio Only - WAV Lossless</option>
                    </select>
                </div>
                <div class="select-wrapper" id="video-quality-wrapper">
                    <select id="video-quality"></select>
                </div>
                <button class="btn" onclick="download()" style="width:100%;padding:18px;margin-top:20px;font-size:1.3em;">
                    Download x<span id="loop-display">1</span>
                </button>
                <div id="folder-controls" style="margin-top:15px; text-align:center; display:none;">
                    <button class="btn btn-success" onclick="openFolder()">Open Download Folder</button>
                </div>
            </div>
        </div>
    </div>
    <div class="status" id="status">Ready</div>
</div>
<img src="data:image/svg+xml;base64,""" + LOGO_BASE64 + """ " class="my-logo" alt="GitHub" title="Follow!" onclick="window.open('https://github.com/dat514','_blank')"/>
<script>
    let info = null, origSec = 0, lastFolder = null;

    function formatTime(s) {
        if (!s) return "0:00";
        const h = Math.floor(s / 3600);
        const m = Math.floor((s % 3600) / 60);
        const sec = Math.floor(s % 60);
        return (h > 0 ? h + ":" : "") + String(m).padStart(2, '0') + ":" + String(sec).padStart(2, '0');
    }

    function updateLoop() {
        const v = document.getElementById('loop-slider').value;
        document.getElementById('loop-val').innerText = v;
        document.getElementById('loop-display').innerText = v;
        document.getElementById('total-duration').innerText = "Total after loop: " + formatTime(origSec * v);
    }

    function toggleVideoQuality() {
        document.getElementById('video-quality-wrapper').style.display =
            document.getElementById('output-type').value === 'video' ? 'block' : 'none';
    }

    async function process() {
        const url = document.getElementById('url').value.trim();
        if (!url) return alert("Please paste a URL!");
        document.getElementById('status').textContent = "Analyzing video...";
        try {
            const data = await window.pywebview.api.analyze(url);
            info = JSON.parse(data);
            origSec = info.duration || 0;
            document.getElementById('title').textContent = info.title || "Unknown";
            document.getElementById('uploader').textContent = info.uploader || "-";
            document.getElementById('orig-duration').textContent = formatTime(origSec);
            document.getElementById('thumb').src = info.thumbnail || "";
            document.getElementById('media-card').classList.add('show');

            const sel = document.getElementById('video-quality');
            sel.innerHTML = '<option value="best">Best Quality (incl. 60fps)</option>';
            const seen = new Set();
            (info.formats || []).filter(f => f && f.vcodec !== 'none' && f.height).forEach(f => {
                const key = f.height + "-" + (f.fps || 30);
                if (!seen.has(key)) {
                    seen.add(key);
                    const label = f.height + "p" + (f.fps > 50 ? " 60FPS" : "") + " " + (f.ext || "").toUpperCase();
                    sel.add(new Option(label, f.format_id));
                }
            });

            toggleVideoQuality();
            updateLoop();
            document.getElementById('status').textContent = "Ready to download!";
        } catch (e) {
            document.getElementById('status').textContent = "Error: " + e.message;
        }
    }

    async function download() {
        if (!info) return alert("Please analyze the video first!");
        const folder = await window.pywebview.api.choose_folder();
        if (!folder) return document.getElementById('status').textContent = "Download cancelled";
        lastFolder = folder;

        const loops = parseInt(document.getElementById('loop-slider').value);
        const type = document.getElementById('output-type').value;
        const fmt = type === 'video' ? (document.getElementById('video-quality').value || 'best') : null;

        let title = (info.title || "video")
            .replace(/[<>:"/\\\\|?*\\x00-\\x1F]/g, '')
            .replace(/[\u200B-\u200D\uFEFF]/g, '')
            .replace(/[#❤️♥❤♡➤]/g, '')
            .replace(/\\s+/g, ' ')
            .trim();

        if (title.length > 100) title = title.substring(0, 97) + '...';
        if (!title) title = 'Video';

        const loopSuffix = loops > 1 ? '_x' + loops : '';
        const ext = type === 'video' ? '.mp4' : (type === 'mp3' ? '.mp3' : '.wav');
        let baseName = title + loopSuffix;
        let filePath = folder.replace(/\\\\/g, '/') + '/' + baseName + ext;

        let counter = 1;
        while (await window.pywebview.api.file_exists(filePath)) {
            filePath = folder.replace(/\\\\/g, '/') + '/' + baseName + ' (' + counter++ + ')' + ext;
        }

        const opts = {
            format: type === 'video'
                ? (fmt === 'best' ? 'bestvideo*+bestaudio/best' : fmt + '+bestaudio/best')
                : 'bestaudio/best',
            outtmpl: filePath,
            restrictfilenames: true,
            nooverwrites: false,
        };

        if (type !== 'video') {
            opts.postprocessors = [{
                key: 'FFmpegExtractAudio',
                preferredcodec: type,
                preferredquality: type === 'mp3' ? '320' : '0',
            }];
        } else {
            opts.merge_output_format = 'mp4';
        }

        if (loops > 1) {
            const n = loops - 1;
            opts.postprocessors = opts.postprocessors || [];
            opts.postprocessors.push({
                key: 'FFmpegConcat',
                only_video: false,
                args: ['-filter_complex',
                    `[0:v]loop=loop=${n}:size=clip:duration=clip[v];` +
                    `[0:a]aloop=loop=${n}:size=clip:duration=clip[a];` +
                    `[v][a]concat=n=2:v=1:a=1`
                ]
            });
        }

        document.getElementById('status').textContent = `Downloading x${loops}...`;
        try {
            await window.pywebview.api.download(info.webpage_url || document.getElementById('url').value, JSON.stringify(opts));
            document.getElementById('status').textContent = `Download completed x${loops}!`;
            document.getElementById('folder-controls').style.display = 'block';
        } catch (e) {
            document.getElementById('status').textContent = "Failed: " + e.message;
        }
    }

    function openFolder() {
        if (lastFolder) window.pywebview.api.open_folder(lastFolder);
    }
</script>
</body>
</html>"""

class InMemoryHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ['/', '/index.html']:
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html_content.encode('utf-8'))
        else:
            self.send_error(404, "File not found")

def start_server():
    with socketserver.TCPServer(("127.0.0.1", 8000), InMemoryHandler) as httpd:
        print("Server running at http://127.0.0.1:8000")
        httpd.serve_forever()

class Api:
    def analyze(self, url):
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return json.dumps(ydl.extract_info(url, download=False), ensure_ascii=False)

    def download(self, url, opts_str):
        opts = json.loads(opts_str)
        print(f"Đang tải về → {opts['outtmpl']}")  

        base_opts = {
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
            'logger': None,
        }
        opts.update(base_opts)

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except Exception as e:
            msg = str(e).encode('utf-8', 'replace').decode('utf-8')
            print(f"Lỗi tải: {msg}")
            raise

    def choose_folder(self):
        result = webview.windows[0].create_file_dialog(FileDialog.FOLDER, directory=os.path.expanduser("~/Desktop"))
        return result[0] if result else None

    def open_folder(self, path):
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])

    def file_exists(self, path):
        return os.path.exists(path)

if __name__ == '__main__':
    threading.Thread(target=start_server, daemon=True).start()
    time.sleep(0.8)

    webview.create_window(
        "Media Downloader 1.1",
        "http://127.0.0.1:8000",
        width=1000,
        height=780,
        resizable=True,
        background_color='#0a0e17',
        js_api=Api()
    )
    webview.start(debug=False) 