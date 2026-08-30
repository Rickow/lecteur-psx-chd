#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iso2chd_gui — interface web locale pour convertir des images CD/DVD en .chd (via chdman).

Lance un petit serveur local (bibliothèque standard uniquement) et ouvre le navigateur.
Tout se passe côté disque : on choisit des fichiers/dossiers dans un explorateur, on clique
« Convertir », et le journal s'affiche en direct. Aucun upload (les gros .iso restent sur place).

Prérequis : chdman (paquet mame-tools).  Utilise la logique de iso2chd.py (même dossier).

Usage :
    python3 iso2chd_gui.py                 # ouvre http://127.0.0.1:8770
    python3 iso2chd_gui.py --port 9000 --no-browser
    CHDMAN=/chemin/chdman python3 iso2chd_gui.py     # chdman explicite
"""

import argparse
import html
import json
import os
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse, parse_qs

# Réutilise le moteur de conversion du CLI (même dossier)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import iso2chd  # noqa: E402

STATE = {
    "running": False,
    "results": [],      # liste de dicts {status, src, out, info}
    "queued": 0,
    "done": 0,
    "log": [],          # lignes de journal
    "chdman": None,
}
LOCK = threading.Lock()


def log(msg):
    with LOCK:
        STATE["log"].append(msg)


def list_places():
    """Raccourcis : dossier perso, racine, et disques montés (/run/media, /media, /mnt)."""
    import getpass
    user = getpass.getuser()
    places = [{"label": "🏠 Dossier perso", "path": str(Path.home())},
              {"label": "💻 Racine /", "path": "/"}]
    seen = {str(Path.home()), "/"}
    for base in (f"/run/media/{user}", f"/media/{user}", "/media", "/mnt"):
        b = Path(base)
        if not b.is_dir():
            continue
        try:
            for entry in sorted(b.iterdir(), key=lambda p: p.name.lower()):
                if entry.is_dir() and str(entry) not in seen:
                    seen.add(str(entry))
                    places.append({"label": "💾 " + entry.name, "path": str(entry)})
        except OSError:
            continue
    return places


def list_dir(path: Path):
    """Liste sous-dossiers + fichiers convertibles d'un répertoire."""
    dirs, files = [], []
    try:
        for entry in sorted(path.iterdir(), key=lambda p: p.name.lower()):
            try:
                if entry.is_dir():
                    dirs.append(entry.name)
                elif entry.is_file() and entry.suffix.lower() in iso2chd.INPUT_EXTS:
                    files.append({"name": entry.name, "size": entry.stat().st_size,
                                  "ext": entry.suffix.lower()})
            except OSError:
                continue
    except (PermissionError, OSError) as e:
        return {"error": str(e)}
    parent = str(path.parent) if path.parent != path else None
    return {"path": str(path), "parent": parent, "dirs": dirs, "files": files}


def run_conversions(items, opts):
    """Thread de conversion : développe les cibles puis convertit une par une."""
    try:
        paths = [Path(p) for p in items]
        files = iso2chd.collect_inputs([str(p) for p in paths], recursive=opts.recursive)
        jobs = iso2chd.build_jobs(files)
        with LOCK:
            STATE["queued"] = len(jobs)
            STATE["done"] = 0
            STATE["results"] = []
        if not jobs:
            log("Rien à convertir (aucune image, ou .bin déjà couverts par des .cue).")
            return
        log(f"{len(jobs)} conversion(s) via {STATE['chdman']}")
        args = SimpleNamespace(
            outdir=opts.outdir or None, force=opts.force, mode=opts.mode,
            bin_track=opts.bin_track, verify=opts.verify, delete_source=opts.delete,
            dry_run=False, numprocessors=0,
        )
        for job in jobs:
            src = job[0]
            log(f"→ {src.name} …")
            status, s, out, info = iso2chd.convert_one(job, args, STATE["chdman"])
            with LOCK:
                STATE["results"].append({"status": status, "src": s.name,
                                         "out": out.name, "info": info})
                STATE["done"] += 1
            icon = {"ok": "✔", "skip": "∘", "fail": "✗"}.get(status, "?")
            log(f"  {icon} {src.name} → {out.name}  ({info})")
        with LOCK:
            n = STATE["results"]
            ok = sum(1 for r in n if r["status"] == "ok")
            sk = sum(1 for r in n if r["status"] == "skip")
            fa = sum(1 for r in n if r["status"] == "fail")
        log(f"Terminé : {ok} OK, {sk} ignoré(s), {fa} échec(s).")
    except Exception as e:
        log(f"Erreur : {e}")
    finally:
        with LOCK:
            STATE["running"] = False


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if "json" in ctype or "html" in ctype else ""))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            return self._send(200, PAGE, "text/html")
        if u.path == "/api/init":
            return self._send(200, {"chdman": STATE["chdman"], "home": str(Path.home()),
                                    "cwd": os.getcwd(), "places": list_places()})
        if u.path == "/api/ls":
            q = parse_qs(u.query)
            raw = q.get("path", [str(Path.home())])[0]
            p = Path(raw).expanduser()
            if not p.is_dir():
                p = Path.home()
            return self._send(200, list_dir(p))
        if u.path == "/api/status":
            with LOCK:
                return self._send(200, {"running": STATE["running"], "queued": STATE["queued"],
                                        "done": STATE["done"], "log": STATE["log"],
                                        "results": STATE["results"]})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length) or b"{}")
        if u.path == "/api/convert":
            if not STATE["chdman"]:
                return self._send(400, {"error": "chdman introuvable — installe mame-tools"})
            with LOCK:
                if STATE["running"]:
                    return self._send(409, {"error": "conversion déjà en cours"})
                STATE["running"] = True
                STATE["log"] = []
            opts = SimpleNamespace(
                recursive=bool(data.get("recursive")), outdir=data.get("outdir") or "",
                mode=data.get("mode", "cd"), force=bool(data.get("force")),
                verify=bool(data.get("verify")), delete=bool(data.get("delete")),
                bin_track=data.get("bin_track", "MODE2/2352"),
            )
            items = data.get("items", [])
            threading.Thread(target=run_conversions, args=(items, opts), daemon=True).start()
            return self._send(200, {"ok": True})
        return self._send(404, {"error": "not found"})


PAGE = r"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ISO/BIN/CUE → CHD</title>
<style>
:root{--bg:#14171c;--panel:#1c2027;--panel2:#232833;--bd:#2c323d;--tx:#e6e9ef;--dim:#8a93a2;
--acc:#4c9df0;--ok:#3fb950;--err:#f05d5d;--skip:#8a93a2}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--tx)}
header{padding:14px 18px;border-bottom:1px solid var(--bd);display:flex;align-items:center;gap:12px}
header h1{font-size:16px;margin:0;font-weight:600}
.badge{font-size:12px;padding:3px 9px;border-radius:20px;border:1px solid var(--bd)}
.badge.ok{color:var(--ok);border-color:#265c33}.badge.no{color:var(--err);border-color:#5c2626}
main{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:16px;max-width:1200px;margin:auto}
@media(max-width:820px){main{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--bd);border-radius:10px;overflow:hidden;display:flex;flex-direction:column}
.card h2{margin:0;font-size:13px;font-weight:600;padding:10px 14px;border-bottom:1px solid var(--bd);color:var(--dim);letter-spacing:.3px;text-transform:uppercase}
.body{padding:12px 14px}
.places{display:flex;flex-wrap:wrap;gap:6px;padding:10px 14px;border-bottom:1px solid var(--bd)}
.places button{font-size:12px}
.crumbs{display:flex;gap:6px;align-items:center;font-size:12px;color:var(--dim);padding:8px 14px;border-bottom:1px solid var(--bd);word-break:break-all}
.crumbs button{font-size:12px}
.list{max-height:340px;overflow:auto}
.row{display:flex;align-items:center;gap:9px;padding:7px 14px;border-bottom:1px solid #20252e;cursor:default}
.row:hover{background:var(--panel2)}
.row .ic{width:18px;text-align:center;opacity:.8}
.row.dir{cursor:pointer}.row .nm{flex:1;word-break:break-all}
.row .sz{color:var(--dim);font-size:12px}
.row .add{font-size:12px;border:1px solid var(--bd);background:transparent;color:var(--acc);border-radius:6px;padding:2px 8px;cursor:pointer}
button{cursor:pointer;background:var(--panel2);color:var(--tx);border:1px solid var(--bd);border-radius:7px;padding:6px 12px}
button:hover{border-color:var(--acc)}
button.primary{background:var(--acc);border-color:var(--acc);color:#06213d;font-weight:600}
button.primary:disabled{opacity:.5;cursor:not-allowed}
.basket{list-style:none;margin:0;padding:0;max-height:150px;overflow:auto}
.basket li{display:flex;gap:8px;align-items:center;padding:5px 14px;border-bottom:1px solid #20252e;font-size:13px}
.basket .x{margin-left:auto;color:var(--err);cursor:pointer;border:none;background:none;font-size:16px}
.opts{display:flex;flex-wrap:wrap;gap:12px 18px;padding:12px 14px;border-top:1px solid var(--bd)}
.opts label{display:flex;align-items:center;gap:6px;font-size:13px}
.opts input[type=text]{background:var(--bg);border:1px solid var(--bd);color:var(--tx);border-radius:6px;padding:5px 8px;width:230px}
.opts select{background:var(--bg);border:1px solid var(--bd);color:var(--tx);border-radius:6px;padding:5px}
.actions{display:flex;gap:10px;align-items:center;padding:12px 14px;border-top:1px solid var(--bd)}
.prog{flex:1;height:8px;background:var(--bg);border-radius:6px;overflow:hidden;border:1px solid var(--bd)}
.prog>i{display:block;height:100%;width:0;background:var(--acc);transition:width .3s}
#log{font:12px/1.55 ui-monospace,Menlo,Consolas,monospace;background:#0f1216;border-top:1px solid var(--bd);
padding:12px 14px;max-height:360px;overflow:auto;white-space:pre-wrap;word-break:break-all;min-height:120px}
.hint{color:var(--dim);font-size:12px;padding:0 14px 12px}
code{background:var(--panel2);padding:1px 5px;border-radius:4px}
</style></head><body>
<header>
  <h1>ISO / BIN / CUE → CHD</h1>
  <span id="chd" class="badge">chdman…</span>
</header>
<main>
  <section class="card">
    <h2>Explorateur</h2>
    <div class="places" id="places"></div>
    <div class="crumbs"><button onclick="up()">⬆ Dossier parent</button><span id="cwd"></span></div>
    <div class="list" id="ls"></div>
    <div class="actions"><button onclick="addFolder()">＋ Ajouter ce dossier</button>
      <span class="hint" style="padding:0">clique un dossier pour l'ouvrir ; « ajouter » un fichier ou le dossier entier</span></div>
  </section>
  <section class="card">
    <h2>À convertir</h2>
    <ul class="basket" id="basket"></ul>
    <div class="opts">
      <label><input type="checkbox" id="recursive" checked> Récursif (dossiers)</label>
      <label><input type="checkbox" id="force"> Réécrire existants</label>
      <label><input type="checkbox" id="verify"> Vérifier (SHA1)</label>
      <label><input type="checkbox" id="delete"> Supprimer source</label>
      <label>Mode <select id="mode"><option value="cd">CD (PS1…)</option>
        <option value="dvd">DVD (PS2)</option><option value="auto">auto</option></select></label>
      <label>Sortie <input type="text" id="outdir" placeholder="(à côté des sources)"></label>
    </div>
    <div class="actions">
      <button class="primary" id="go" onclick="convert()">Convertir</button>
      <div class="prog"><i id="bar"></i></div>
      <span id="count" class="hint" style="padding:0"></span>
    </div>
    <pre id="log">Prêt.</pre>
  </section>
</main>
<script>
let cur=null, basket=[];
async function j(u,o){const r=await fetch(u,o);return r.json();}
function fmtSize(n){const u=['o','Ko','Mo','Go'];let i=0;while(n>=1024&&i<3){n/=1024;i++;}return n.toFixed(i?1:0)+' '+u[i];}
async function init(){const d=await j('/api/init');const b=document.getElementById('chd');
  if(d.chdman){b.textContent='chdman ✓';b.className='badge ok';}
  else{b.textContent='chdman manquant';b.className='badge no';
    document.getElementById('log').textContent='chdman introuvable. Installe-le :\n  sudo apt install mame-tools';}
  document.getElementById('places').innerHTML=(d.places||[]).map(p=>
    `<button onclick="ls('${esc(p.path)}')">${escH(p.label)}</button>`).join('');
  ls(d.home);}
async function ls(path){const d=await j('/api/ls?path='+encodeURIComponent(path));
  if(d.error){document.getElementById('ls').innerHTML='<div class="row">⚠ '+d.error+'</div>';return;}
  cur=d.path;document.getElementById('cwd').textContent=d.path;
  let h='';
  for(const name of d.dirs){h+=`<div class="row dir" onclick="ls('${esc(d.path)}/${esc(name)}')">
    <span class="ic">📁</span><span class="nm">${escH(name)}</span>
    <button class="add" onclick="event.stopPropagation();addItem('${esc(d.path)}/${esc(name)}','${escH(name)}',true)">＋ dossier</button></div>`;}
  for(const f of d.files){h+=`<div class="row"><span class="ic">💿</span>
    <span class="nm">${escH(f.name)}</span><span class="sz">${fmtSize(f.size)}</span>
    <button class="add" onclick="addItem('${esc(d.path)}/${esc(f.name)}','${escH(f.name)}',false)">＋</button></div>`;}
  document.getElementById('ls').innerHTML=h||'<div class="row">(rien de convertible ici)</div>';}
function up(){if(cur){const p=cur.replace(/\/[^\/]+$/,'')||'/';ls(p);}}
function addFolder(){if(cur)addItem(cur,cur.split('/').pop()||cur,true);}
function addItem(path,label,isDir){if(basket.some(x=>x.path===path))return;
  basket.push({path,label,isDir});renderBasket();}
function rm(i){basket.splice(i,1);renderBasket();}
function renderBasket(){document.getElementById('basket').innerHTML=basket.map((x,i)=>
  `<li><span>${x.isDir?'📁':'💿'}</span><span>${escH(x.label)}</span>
   <button class="x" onclick="rm(${i})">×</button></li>`).join('')
  ||'<li style="color:var(--dim)">Ajoute des fichiers ou dossiers depuis l\'explorateur…</li>';}
function esc(s){return s.replace(/\\/g,'\\\\').replace(/'/g,"\\'");}
function escH(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML;}
async function convert(){if(!basket.length){alert('Ajoute au moins un fichier ou dossier.');return;}
  const body={items:basket.map(x=>x.path),recursive:document.getElementById('recursive').checked,
    force:document.getElementById('force').checked,verify:document.getElementById('verify').checked,
    delete:document.getElementById('delete').checked,mode:document.getElementById('mode').value,
    outdir:document.getElementById('outdir').value};
  document.getElementById('go').disabled=true;document.getElementById('log').textContent='Démarrage…';
  const r=await j('/api/convert',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(r.error){document.getElementById('log').textContent='Erreur : '+r.error;document.getElementById('go').disabled=false;return;}
  poll();}
async function poll(){const s=await j('/api/status');
  document.getElementById('log').textContent=s.log.join('\n')||'…';
  const el=document.getElementById('log');el.scrollTop=el.scrollHeight;
  const pct=s.queued?Math.round(100*s.done/s.queued):0;
  document.getElementById('bar').style.width=pct+'%';
  document.getElementById('count').textContent=s.queued?`${s.done}/${s.queued}`:'';
  if(s.running){setTimeout(poll,600);}else{document.getElementById('go').disabled=false;}}
init();
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser(description="Interface web locale pour iso2chd.")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true", help="ne pas ouvrir le navigateur")
    ap.add_argument("--chdman", help="chemin explicite vers chdman")
    args = ap.parse_args()

    explicit = args.chdman or os.environ.get("CHDMAN")
    try:
        STATE["chdman"] = iso2chd.find_chdman(explicit)
    except SystemExit:
        STATE["chdman"] = None  # l'UI affichera le message d'installation

    url = f"http://{args.host}:{args.port}/"
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"iso2chd — interface : {url}")
    print("chdman :", STATE["chdman"] or "INTROUVABLE (installe mame-tools)")
    print("Ctrl+C pour quitter.")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")


if __name__ == "__main__":
    main()
