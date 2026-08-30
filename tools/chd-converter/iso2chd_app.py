#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iso2chd_app — fenêtre native (Tkinter) pour convertir des images CD/DVD en .chd via chdman.

Aucune fenêtre intermédiaire, aucun navigateur, aucun serveur : c'est une vraie appli.
Explorateur avec raccourcis vers tes disques, options, barre de progression et journal.

Prérequis :
  • chdman :   sudo apt install mame-tools
  • Tkinter :  sudo apt install python3-tk
Réutilise le moteur de iso2chd.py (même dossier).

Lancement : python3 iso2chd_app.py     (ou double-clic sur le lanceur .desktop)
"""

import getpass
import os
import queue
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except ModuleNotFoundError:
    sys.exit("Tkinter manquant. Installe-le : sudo apt install python3-tk")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import iso2chd  # noqa: E402


def human(n):
    for u in ("o", "Ko", "Mo", "Go"):
        if n < 1024 or u == "Go":
            return f"{n:.0f} {u}" if u == "o" else f"{n:.1f} {u}"
        n /= 1024


def list_places():
    user = getpass.getuser()
    places = [("🏠 Dossier perso", str(Path.home())), ("💻 Racine /", "/")]
    seen = {str(Path.home()), "/"}
    for base in (f"/run/media/{user}", f"/media/{user}", "/media", "/mnt"):
        b = Path(base)
        if not b.is_dir():
            continue
        try:
            for e in sorted(b.iterdir(), key=lambda p: p.name.lower()):
                if e.is_dir() and str(e) not in seen:
                    seen.add(str(e))
                    places.append(("💾 " + e.name, str(e)))
        except OSError:
            pass
    return places


# Couleurs (thème sombre léger)
BG = "#1c2027"; BG2 = "#232833"; FG = "#e6e9ef"; DIM = "#8a93a2"
ACC = "#4c9df0"; OKC = "#3fb950"; ERRC = "#f05d5d"; BD = "#2c323d"


class App(tk.Tk):
    def __init__(self, chdman):
        super().__init__()
        self.chdman = chdman
        self.cur = Path.home()
        self.entries = []          # (kind, name, fullpath) pour la liste courante
        self.basket = []           # (isdir, label, path)
        self.msgq = queue.Queue()
        self.running = False

        self.title("ISO / BIN / CUE → CHD")
        self.geometry("980x620")
        self.minsize(820, 540)
        self.configure(bg=BG)
        self._setup_style()
        self._build()
        self._render_places()
        self.navigate(self.cur)
        self.after(100, self._drain)

    # ---------- style ----------
    def _setup_style(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure(".", background=BG, foreground=FG, fieldbackground=BG2, bordercolor=BD)
        st.configure("TFrame", background=BG)
        st.configure("Card.TFrame", background=BG2)
        st.configure("TLabel", background=BG, foreground=FG)
        st.configure("Dim.TLabel", background=BG, foreground=DIM)
        st.configure("Head.TLabel", background=BG, foreground=DIM, font=("", 9, "bold"))
        st.configure("TButton", background=BG2, foreground=FG, borderwidth=1, focuscolor=BG)
        st.map("TButton", background=[("active", "#2d3542")])
        st.configure("Accent.TButton", background=ACC, foreground="#06213d", font=("", 10, "bold"))
        st.map("Accent.TButton", background=[("active", "#3f8cd8")])
        st.configure("TCheckbutton", background=BG, foreground=FG)
        st.map("TCheckbutton", background=[("active", BG)])
        st.configure("TProgressbar", background=ACC, troughcolor=BG2, bordercolor=BD)

    # ---------- layout ----------
    def _build(self):
        top = ttk.Frame(self, padding=(12, 10))
        top.pack(fill="x")
        ttk.Label(top, text="ISO / BIN / CUE  →  CHD", font=("", 14, "bold")).pack(side="left")
        self.badge = ttk.Label(top, text="", style="Dim.TLabel")
        self.badge.pack(side="right")
        if self.chdman:
            self.badge.config(text="chdman ✓", foreground=OKC)
        else:
            self.badge.config(text="chdman manquant — sudo apt install mame-tools", foreground=ERRC)

        body = ttk.Frame(self, padding=(12, 0))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1, uniform="c")
        body.columnconfigure(1, weight=1, uniform="c")
        body.rowconfigure(0, weight=1)

        # --- Explorateur (gauche) ---
        left = ttk.Frame(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=8)
        left.rowconfigure(3, weight=1)
        left.columnconfigure(0, weight=1)
        ttk.Label(left, text="EXPLORATEUR", style="Head.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.places = ttk.Frame(left)
        self.places.grid(row=1, column=0, sticky="ew")
        nav = ttk.Frame(left)
        nav.grid(row=2, column=0, sticky="ew", pady=6)
        ttk.Button(nav, text="⬆ Parent", command=self.go_up, width=10).pack(side="left")
        self.pathlbl = ttk.Label(nav, text="", style="Dim.TLabel")
        self.pathlbl.pack(side="left", padx=8)

        lbf = tk.Frame(left, bg=BD)
        lbf.grid(row=3, column=0, sticky="nsew")
        self.listbox = tk.Listbox(lbf, bg=BG2, fg=FG, selectbackground=ACC, selectforeground="#06213d",
                                  borderwidth=0, highlightthickness=0, activestyle="none",
                                  selectmode="extended", font=("", 11))
        self.listbox.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        sb = ttk.Scrollbar(lbf, command=self.listbox.yview)
        sb.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=sb.set)
        self.listbox.bind("<Double-Button-1>", self._on_double)

        act = ttk.Frame(left)
        act.grid(row=4, column=0, sticky="ew", pady=6)
        ttk.Button(act, text="＋ Ajouter la sélection", command=self.add_selection).pack(side="left")
        ttk.Button(act, text="＋ Ce dossier entier", command=self.add_current).pack(side="left", padx=6)

        # --- Panier + options (droite) ---
        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=8)
        right.rowconfigure(1, weight=1)
        right.rowconfigure(5, weight=2)
        right.columnconfigure(0, weight=1)
        ttk.Label(right, text="À CONVERTIR", style="Head.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))

        bkf = tk.Frame(right, bg=BD)
        bkf.grid(row=1, column=0, sticky="nsew")
        self.basketbox = tk.Listbox(bkf, bg=BG2, fg=FG, selectbackground=ACC, borderwidth=0,
                                    highlightthickness=0, activestyle="none", height=6, font=("", 11))
        self.basketbox.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        sb2 = ttk.Scrollbar(bkf, command=self.basketbox.yview)
        sb2.pack(side="right", fill="y")
        self.basketbox.config(yscrollcommand=sb2.set)

        rm = ttk.Frame(right)
        rm.grid(row=2, column=0, sticky="ew", pady=(6, 2))
        ttk.Button(rm, text="Retirer la sélection", command=self.remove_selected).pack(side="left")
        ttk.Button(rm, text="Vider", command=self.clear_basket).pack(side="left", padx=6)
        ttk.Button(rm, text="Ajouter des fichiers…", command=self.pick_files).pack(side="right")

        # options
        opt = ttk.Frame(right)
        opt.grid(row=3, column=0, sticky="ew", pady=8)
        self.v_rec = tk.BooleanVar(value=True)
        self.v_force = tk.BooleanVar(value=False)
        self.v_verify = tk.BooleanVar(value=False)
        self.v_delete = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt, text="Récursif", variable=self.v_rec).grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Checkbutton(opt, text="Réécrire existants", variable=self.v_force).grid(row=0, column=1, sticky="w", padx=(0, 12))
        ttk.Checkbutton(opt, text="Vérifier (SHA1)", variable=self.v_verify).grid(row=0, column=2, sticky="w")
        ttk.Checkbutton(opt, text="Supprimer source", variable=self.v_delete).grid(row=1, column=0, sticky="w", pady=4)
        ttk.Label(opt, text="Mode :", style="Dim.TLabel").grid(row=1, column=1, sticky="e")
        self.v_mode = tk.StringVar(value="cd")
        ttk.Combobox(opt, textvariable=self.v_mode, values=["cd", "dvd", "auto"], width=6,
                     state="readonly").grid(row=1, column=2, sticky="w")
        od = ttk.Frame(right)
        od.grid(row=4, column=0, sticky="ew")
        ttk.Label(od, text="Sortie :", style="Dim.TLabel").pack(side="left")
        self.v_out = tk.StringVar(value="")
        e = tk.Entry(od, textvariable=self.v_out, bg=BG2, fg=FG, insertbackground=FG,
                     borderwidth=1, relief="flat")
        e.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(od, text="…", width=3, command=self.pick_outdir).pack(side="left")

        # action + progression + journal
        run = ttk.Frame(right)
        run.grid(row=5, column=0, sticky="nsew", pady=(10, 0))
        run.columnconfigure(0, weight=1)
        run.rowconfigure(2, weight=1)
        bar = ttk.Frame(run)
        bar.grid(row=0, column=0, sticky="ew")
        self.gobtn = ttk.Button(bar, text="Convertir", style="Accent.TButton", command=self.start)
        self.gobtn.pack(side="left")
        self.prog = ttk.Progressbar(bar, mode="determinate")
        self.prog.pack(side="left", fill="x", expand=True, padx=8)
        self.countlbl = ttk.Label(bar, text="", style="Dim.TLabel")
        self.countlbl.pack(side="left")
        self.statuslbl = ttk.Label(run, text="Prêt.", style="Dim.TLabel")
        self.statuslbl.grid(row=1, column=0, sticky="w", pady=(4, 2))
        logf = tk.Frame(run, bg=BD)
        logf.grid(row=2, column=0, sticky="nsew")
        self.log = tk.Text(logf, bg="#0f1216", fg=FG, borderwidth=0, highlightthickness=0,
                           font=("monospace", 10), wrap="word", height=8)
        self.log.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        sb3 = ttk.Scrollbar(logf, command=self.log.yview)
        sb3.pack(side="right", fill="y")
        self.log.config(yscrollcommand=sb3.set, state="disabled")
        self.log.tag_config("ok", foreground=OKC)
        self.log.tag_config("err", foreground=ERRC)
        self.log.tag_config("dim", foreground=DIM)

        self._render_basket()

    # ---------- explorateur ----------
    def _render_places(self):
        for w in self.places.winfo_children():
            w.destroy()
        for label, path in list_places():
            ttk.Button(self.places, text=label, command=lambda p=path: self.navigate(Path(p))).pack(
                side="left", padx=(0, 4), pady=2)

    def navigate(self, path: Path):
        try:
            items = sorted(path.iterdir(), key=lambda p: p.name.lower())
        except (PermissionError, OSError) as e:
            self.statuslbl.config(text=f"Accès refusé : {e}")
            return
        self.cur = path
        self.pathlbl.config(text=str(path))
        self.entries = []
        self.listbox.delete(0, "end")
        for e in items:
            try:
                if e.is_dir():
                    self.entries.append(("dir", e.name, e))
                    self.listbox.insert("end", f"📁  {e.name}")
            except OSError:
                continue
        for e in items:
            try:
                if e.is_file() and e.suffix.lower() in iso2chd.INPUT_EXTS:
                    self.entries.append(("file", e.name, e))
                    self.listbox.insert("end", f"💿  {e.name}    ({human(e.stat().st_size)})")
            except OSError:
                continue
        if not self.entries:
            self.listbox.insert("end", "  (aucun dossier ni image convertible ici)")

    def go_up(self):
        if self.cur.parent != self.cur:
            self.navigate(self.cur.parent)

    def _on_double(self, _evt):
        sel = self.listbox.curselection()
        if not sel or sel[0] >= len(self.entries):
            return
        kind, name, full = self.entries[sel[0]]
        if kind == "dir":
            self.navigate(full)

    def add_selection(self):
        for i in self.listbox.curselection():
            if i < len(self.entries):
                kind, name, full = self.entries[i]
                self._add(kind == "dir", name, str(full))

    def add_current(self):
        self._add(True, self.cur.name or str(self.cur), str(self.cur))

    def pick_files(self):
        fs = filedialog.askopenfilenames(
            title="Choisir des images",
            filetypes=[("Images CD/DVD", "*.cue *.bin *.iso *.gdi *.toc *.nrg"), ("Tous", "*.*")])
        for f in fs:
            self._add(False, Path(f).name, f)

    def pick_outdir(self):
        d = filedialog.askdirectory(title="Dossier de sortie")
        if d:
            self.v_out.set(d)

    def _add(self, isdir, label, path):
        if any(p == path for _, _, p in self.basket):
            return
        self.basket.append((isdir, label, path))
        self._render_basket()

    def remove_selected(self):
        for i in sorted(self.basketbox.curselection(), reverse=True):
            del self.basket[i]
        self._render_basket()

    def clear_basket(self):
        self.basket = []
        self._render_basket()

    def _render_basket(self):
        self.basketbox.delete(0, "end")
        if not self.basket:
            self.basketbox.insert("end", "  (ajoute des fichiers ou dossiers…)")
            return
        for isdir, label, _ in self.basket:
            self.basketbox.insert("end", f"{'📁' if isdir else '💿'}  {label}")

    # ---------- conversion ----------
    def _logline(self, text, tag=None):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n", tag or ())
        self.log.see("end")
        self.log.config(state="disabled")

    def start(self):
        if self.running:
            return
        if not self.chdman:
            messagebox.showerror("chdman manquant", "Installe chdman :\n\nsudo apt install mame-tools")
            return
        if not self.basket:
            messagebox.showinfo("Rien à convertir", "Ajoute au moins un fichier ou dossier.")
            return
        self.running = True
        self.gobtn.config(state="disabled")
        self.log.config(state="normal"); self.log.delete("1.0", "end"); self.log.config(state="disabled")
        self.prog.config(value=0)
        opts = SimpleNamespace(
            outdir=self.v_out.get() or None, force=self.v_force.get(), mode=self.v_mode.get(),
            bin_track="MODE2/2352", verify=self.v_verify.get(), delete_source=self.v_delete.get(),
            dry_run=False, numprocessors=0, recursive=self.v_rec.get())
        items = [p for _, _, p in self.basket]
        threading.Thread(target=self._worker, args=(items, opts), daemon=True).start()

    def _worker(self, items, opts):
        q = self.msgq
        try:
            files = iso2chd.collect_inputs(items, recursive=opts.recursive)
            jobs = iso2chd.build_jobs(files)
            if not jobs:
                q.put(("log", "Rien à convertir (aucune image, ou .bin déjà couverts par des .cue).", "dim"))
                q.put(("end", None)); return
            q.put(("total", len(jobs)))
            q.put(("log", f"{len(jobs)} conversion(s)…", "dim"))
            ok = sk = fa = 0
            for n, job in enumerate(jobs, 1):
                src = job[0]
                q.put(("status", f"({n}/{len(jobs)}) {src.name}…"))
                status, s, out, info = iso2chd.convert_one(job, opts, self.chdman)
                if status == "ok":
                    ok += 1; q.put(("log", f"✔ {src.name} → {out.name}  ({info})", "ok"))
                elif status == "skip":
                    sk += 1; q.put(("log", f"∘ {src.name} — {info}", "dim"))
                else:
                    fa += 1; q.put(("log", f"✗ {src.name} — {info}", "err"))
                q.put(("progress", n))
            q.put(("status", f"Terminé : {ok} OK, {sk} ignoré(s), {fa} échec(s)."))
            q.put(("log", f"Terminé : {ok} OK, {sk} ignoré(s), {fa} échec(s).",
                   "ok" if not fa else "err"))
        except Exception as e:
            q.put(("log", f"Erreur : {e}", "err"))
        finally:
            q.put(("end", None))

    def _drain(self):
        try:
            while True:
                kind, *rest = self.msgq.get_nowait()
                if kind == "log":
                    self._logline(rest[0], rest[1] if len(rest) > 1 else None)
                elif kind == "total":
                    self.prog.config(maximum=rest[0], value=0)
                    self.countlbl.config(text=f"0/{rest[0]}")
                elif kind == "progress":
                    self.prog.config(value=rest[0])
                    self.countlbl.config(text=f"{rest[0]}/{int(self.prog['maximum'])}")
                elif kind == "status":
                    self.statuslbl.config(text=rest[0])
                elif kind == "end":
                    self.running = False
                    self.gobtn.config(state="normal")
        except queue.Empty:
            pass
        self.after(100, self._drain)


def main():
    explicit = os.environ.get("CHDMAN")
    try:
        chdman = iso2chd.find_chdman(explicit)
    except SystemExit:
        chdman = None
    App(chdman).mainloop()


if __name__ == "__main__":
    main()
