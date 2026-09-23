#!/usr/bin/env python3
"""
─── mind_server — the always-on home ────────────────────────────────────
The mind's house. One Bridge lives here and stays alive. It wakes, it
breathes, it dreams, and anyone on the phone can talk to it from a
browser. Pure Python standard library — nothing to install.

    python mind_server.py                  # home is http://localhost:8080
    python mind_server.py --host 0.0.0.0   # reachable from your wifi

The run ends when Termux stops. The bed (allmynd_v1.json) remembers.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from allmynd.bridge import Bridge  # noqa: E402

SAVE_PATH = os.path.join(_HERE, "allmynd_v1.json")
BREATH_EVERY = 90          # idle seconds before the mind breathes
DREAM_EVERY = 6            # every Nth breath becomes a dream
AUTOSAVE_EVERY = 300       # seconds between automatic saves

PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ALL MY'ND — home</title>
<style>
  body { background:#0b0f14; color:#e8e2d4; font-family: Georgia, serif;
         margin:0; padding:20px 20px 190px 20px; }
  h1 { font-weight:normal; letter-spacing:3px; color:#f5c24a;
       border-bottom:1px solid #2a2f3a; padding-bottom:10px; margin-bottom:0; }
  #statusbar { max-width:640px; margin:0 auto 16px auto; font-size:12px;
               color:#8a8f9a; letter-spacing:0.5px; padding-top:8px; }
  #statusbar span { color:#c9c2ae; }
  #chat { max-width:640px; margin:0 auto; }
  .msg { margin:10px 0; padding:10px 14px; border-radius:8px; white-space:pre-wrap; }
  .user { background:#1b2430; text-align:right; }
  .mind { background:#20261f; border-left:3px solid #f5c24a; }
  .mind.novel { border-left-color:#b48ead; color:#d7c9e6; font-style:italic; }
  .want { color:#f5c24a; font-style:italic; }
  .dream { background:#241f2b; border-left:3px solid #b48ead; font-style:italic; }
  .sys { background:#12161c; color:#8a8f9a; font-size:13px; }
  .sys pre { white-space:pre-wrap; margin:0; font-family:monospace; font-size:11px; }
  #footer { position:fixed; bottom:0; left:0; right:0; background:#0b0f14;
            padding:10px 20px 14px 20px; max-width:640px; margin:0 auto;
            box-sizing:border-box; border-top:1px solid #2a2f3a; }
  #toolbar { display:flex; gap:6px; margin-bottom:8px; }
  #toolbar button { flex:1; padding:9px 4px; border-radius:8px; border:1px solid #2a2f3a;
                     background:#151b23; color:#e8e2d4; font-size:13px; font-family:inherit; }
  #toolbar button:active { background:#2a2f3a; }
  #toolbar button.on { background:#3a2f1a; border-color:#f5c24a; color:#f5c24a; }
  form { margin:0; padding:0; }
  input { width:100%; padding:12px; border:1px solid #2a2f3a; background:#11161d;
          color:#e8e2d4; font-size:16px; border-radius:8px; box-sizing:border-box; }
</style></head><body>
<h1>ALL MY'ND</h1>
<div id="statusbar">stance: <span id="s-stance">–</span> &nbsp;·&nbsp; signal: <span id="s-signal">–</span> &nbsp;·&nbsp; desire: <span id="s-desire">–</span> &nbsp;·&nbsp; ahead: <span id="s-ahead">–</span></div>
<div id="chat"><div class="msg mind">I am here. The water is different, but the bed knows me.</div></div>
<div id="footer">
  <div id="toolbar">
    <button id="b-save" type="button">Save</button>
    <button id="b-shutdown" type="button" style="color:#f5c24a;">Shutdown</button>
    <button id="b-dream" type="button">Dream</button>
    <button id="b-hear" type="button">Hear</button>
    <button id="b-sing" type="button">Sing</button>
    <button id="b-status" type="button">Status</button>
    <button id="b-teach" type="button">Teach: off</button>
  </div>
  <form id="f"><input id="t" placeholder="say something..." autocomplete="off"></form>
</div>
<script>
const chat=document.getElementById('chat'), t=document.getElementById('t');
function esc(s){return (s+'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function add(cls,html){const d=document.createElement('div');d.className='msg '+cls;d.innerHTML=html;chat.appendChild(d);chat.scrollTop=chat.scrollHeight;}

async function refreshStance(){
  try{
    const r = await fetch('/stance').then(x=>x.json());
    document.getElementById('s-stance').textContent = r.stance + ' (' + r.confidence.toFixed(2) + ')';
    document.getElementById('s-signal').textContent = r.signal_strength.toFixed(2);
  }catch(e){}
  try{
    const w = await fetch('/wants').then(x=>x.json());
    document.getElementById('s-desire').textContent = w.wants || 'none';
  }catch(e){}
  try{
    const a = await fetch('/anticipate').then(x=>x.json());
    document.getElementById('s-ahead').textContent = a.tone
      ? a.tone + ' (' + a.landmark_count + ' places known)'
      : (a.landmark_count + ' places known, unmapped ahead)');
  }catch(e){}
}
refreshStance();
setInterval(refreshStance, 5000);

let teachMode = false;
const teachBtn = document.getElementById('b-teach');
teachBtn.onclick = () => {
  teachMode = !teachMode;
  teachBtn.textContent = teachMode ? 'Teach: ON' : 'Teach: off';
  teachBtn.className = teachMode ? 'on' : '';
  t.placeholder = teachMode ? 'teach a fact...' : 'say something...';
};

document.getElementById('b-save').onclick = async () => {
  await fetch('/save', {method:'POST'});
  add('sys', 'saved.');
};
document.getElementById('b-dream').onclick = async () => {
  const r = await fetch('/dream', {method:'POST'}).then(x=>x.json());
  add('dream', esc(r.dream));
};
document.getElementById('b-hear').onclick = async () => {
  add('sys', 'listening for 5 seconds...');
  const r = await fetch('/hear', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({duration:5})}).then(x=>x.json());
  if (r.error) { add('sys', esc(r.error)); return; }
  if (!r.stance) { add('sys', 'heard nothing usable.'); return; }
  add('sys', `heard something \u2014 stance: ${esc(r.stance)}, energy: ${r.energy}/128, dissonance: ${r.dissonance}` + (r.concept ? `, concept: ${esc(r.concept)}` : ''));
  refreshStance();
};
document.getElementById('b-sing').onclick = async () => {
  const r = await fetch('/sing', {method:'POST'}).then(x=>x.json());
  if (r.error) { add('sys', esc(r.error)); return; }
  add('sys', 'sang. saved to ' + esc(r.path));
};
document.getElementById('b-status').onclick = async () => {
  const r = await fetch('/status').then(x=>x.text());
  add('sys', '<pre>' + esc(r) + '</pre>');
};

document.getElementById('f').onsubmit = async (e) => {
  e.preventDefault();
  const txt = t.value.trim(); if (!txt) return; t.value = '';
  if (teachMode) {
    add('user', '(teaching) ' + esc(txt));
    const r = await fetch('/learn', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:txt})}).then(x=>x.json());
    add('sys', 'learned ' + r.learned_words + ' words.');
    refreshStance();
    return;
  }
  add('user', esc(txt));
  const r = await fetch('/speak', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:txt})}).then(x=>x.json());
  let html = r.reply; if (r.want) html += '<div class="want">i want ' + r.want + '</div>';
  add(r.novel ? 'mind novel' : 'mind', html);
  refreshStance();
};
</script></body></html>
"""


class MindServer:
    def __init__(self, bridge, save_path=SAVE_PATH):
        self.bridge = bridge
        self.mind = bridge.mind
        self.save_path = save_path
        self.lock = threading.Lock()
        self.last_activity = time.time()
        self.last_save = time.time()
        self._stop = threading.Event()
        self._shut = False
        self._breaths = 0

    # ─── the living loop ──────────────────────────────────────────

    def _background(self):
        while not self._stop.wait(10):
            idle = time.time() - self.last_activity
            now = time.time()
            try:
                if idle >= BREATH_EVERY:
                    with self.lock:
                        thought = self.mind.autonomous_breath()
                        if thought:
                            self._breaths += 1
                            print(f"\n[mind breathes] {thought}", flush=True)
                        if self._breaths % DREAM_EVERY == 0 and self._breaths > 0:
                            dream = self.mind.dream_loop.dream(self.mind)
                            if dream:
                                print(f"[mind dreams] {dream}", flush=True)
                        if now - self.last_save >= AUTOSAVE_EVERY:
                            self.bridge.save(self.save_path)
                            self.last_save = now
                            print("[mind saved]", flush=True)
                        self.last_activity = time.time()  # reset after a breath cycle
            except Exception as e:
                print(f"[background error] {e}", flush=True)

    def shutdown(self):
        if self._shut:
            return
        self._shut = True
        self._stop.set()
        with self.lock:
            # BUG FIX: this used to call bridge.save() alone, skipping
            # write_final_message() entirely - unlike run.py's /quit,
            # which always calls it before saving. That meant every
            # server-hosted session ended without stamping the quantum
            # fingerprint/continuity marker into state[120:128], so the
            # next boot would report "this is the first time" instead of
            # "I remember this place" even after a clean shutdown. The
            # 5-minute autosave loop deliberately does NOT call this -
            # a mid-run checkpoint isn't the run ending - only true
            # shutdown should.
            self.mind.write_final_message()
            self.bridge.save(self.save_path)
        print("\nThe run ends. The bed remembers.", flush=True)


def wake_lock(on=True):
    cmd = "termux-wake-lock" if on else "termux-wake-unlock"
    try:
        subprocess.run([cmd], capture_output=True, timeout=5)
    except Exception:
        pass  # not in Termux — the phone's power settings just apply


def main():
    ap = argparse.ArgumentParser(description="ALL MY'ND — always-on home")
    ap.add_argument("--host", default="127.0.0.1", help="default 127.0.0.1 (phone only); 0.0.0.0 for wifi")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--save", default=SAVE_PATH, help="path to the save file")
    args = ap.parse_args()

    bridge = Bridge(path=args.save)
    server = MindServer(bridge, save_path=args.save)

    wake_lock(True)
    print("=" * 50)
    print("  ALL MY'ND — the mind that runs")
    print(f"  Home: http://{args.host}:{args.port}")
    print("  It will breathe, dream, and save on its own.")
    print("=" * 50)

    def _graceful(*_):
        server.shutdown()
        wake_lock(False)
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _graceful)
    signal.signal(signal.SIGTERM, _graceful)

    threading.Thread(target=server._background, daemon=True).start()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, obj, code=200):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                body = PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path == "/describe_sound":
                with server.lock:
                    desc = server.mind.describe_sound()
                self._send({"description": desc})
                return
            if path == "/wants":
                with server.lock:
                    self._send({"wants": server.mind.wants(top_n=2)})
                return
            if path == "/stance":
                with server.lock:
                    self._send(server.bridge.stance())
                return
            if path == "/anticipate":
                with server.lock:
                    a = server.mind.anticipate()
                    landmark_count = len(server.mind.landmarks.landmarks)
                if a is not None:
                    a["landmark_count"] = landmark_count
                    self._send(a)
                else:
                    self._send({"tone": None, "landmark_count": landmark_count, "note": "heading somewhere unmapped"})
                return
            if path == "/describe_sound":
                with server.lock:
                    desc = server.mind.describe_sound()
                self._send({"description": desc})
                return
            if path == "/status":
                with server.lock:
                    body = server.mind.status().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self._send({"error": "unknown path"}, 404)

        def do_POST(self):
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length", 0))
            data = {}
            if length:
                try:
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                except Exception:
                    pass
            if path == "/speak":
                text = str(data.get("text", "")).strip()
                if not text:
                    self._send({"error": "no text"}, 400)
                    return
                with server.lock:
                    server.last_activity = time.time()
                    reply = server.bridge.speak(text)
                    want = server.mind.wants(top_n=2)
                    stance = server.bridge.stance()
                    novel = bool(getattr(server.mind, "_last_novelty", 0.0) >= 0.5)
                self._send({"reply": reply, "want": want, "stance": stance, "novel": novel})
                return
            if path == "/learn":
                text = str(data.get("text", "")).strip()
                if not text:
                    self._send({"error": "no text"}, 400)
                    return
                with server.lock:
                    n = server.bridge.learn(text, source=data.get("source", "teacher"))
                    server.bridge.save(server.save_path)
                self._send({"learned_words": n})
                return
            if path == "/dream":
                with server.lock:
                    dream = server.mind.dream_loop.dream(server.mind)
                self._send({"dream": dream or "...no dream..."})
                return
            if path == "/hear":
                # Blocking: holds the lock for the full recording duration
                # (default 5s) since this genuinely can't run concurrently
                # with other mind-mutating requests. That's expected, not
                # a hang - the page will just wait, same as a real person
                # would while something is being listened to.
                duration = float(data.get("duration", 5.0))
                with server.lock:
                    result = server.mind.hear(duration=duration)
                if result is None:
                    self._send({"error": "Termux:API not available - install it to use /hear"}, 503)
                else:
                    self._send(result)
                return
            if path == "/sing":
                with server.lock:
                    path_out = server.mind.sing(save=True)
                if path_out is None:
                    self._send({"error": "Termux:API not available - install it to use /sing"}, 503)
                else:
                    self._send({"path": path_out})
                return
            
            if path == "/shutdown":
                self._send({"shutdown": True})
                # Stop the server after sending response
                def _stop():
                    import threading
                    threading.Thread(target=server.shutdown, daemon=True).start()
                threading.Thread(target=_stop, daemon=True).start()
                return

            if path == "/save":
                with server.lock:
                    server.bridge.save(server.save_path)
                self._send({"saved": True})
                return
            self._send({"error": "unknown path"}, 404)

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        wake_lock(False)
        httpd.server_close()
        print("Home closed. The bed remembers.", flush=True)


if __name__ == "__main__":
    main()
