#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iso2chd — convertit des images CD/DVD (.cue / .bin / .iso / .gdi / .toc / .nrg) en .chd
en s'appuyant sur `chdman` (outil officiel de MAME). Fonctionne partout où chdman existe
(Linux, macOS, Windows).

Installation de chdman :
  • Debian/Ubuntu/Kubuntu :  sudo apt install mame-tools
  • Fedora :                 sudo dnf install mame-tools
  • Arch :                   sudo pacman -S mame-tools
  • macOS (brew) :           brew install rom-tools     (ou mame)
  • Windows :                récupérer chdman.exe depuis une distribution MAME

Exemples :
  python3 iso2chd.py jeu.cue                 # -> jeu.chd (à côté de la source)
  python3 iso2chd.py *.cue *.iso             # plusieurs fichiers
  python3 iso2chd.py /mnt/roms -r            # tout un dossier, en récursif
  python3 iso2chd.py /mnt/roms -r -o /sortie --jobs 2
  python3 iso2chd.py disque.bin              # .bin isolé -> cue temporaire auto
  python3 iso2chd.py gros.iso --mode dvd     # image DVD (PS2) -> createdvd

Par défaut : ne réécrit pas un .chd déjà présent, ne supprime jamais la source.
"""

import argparse
import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Descripteurs multi-pistes que chdman sait lire directement
DESCRIPTOR_EXTS = {".cue", ".gdi", ".toc"}
# Images « à piste unique » acceptées directement par chdman createcd/createdvd
IMAGE_EXTS = {".iso", ".nrg"}
# Extensions acceptées en entrée (on ajoute .bin, géré à part)
INPUT_EXTS = DESCRIPTOR_EXTS | IMAGE_EXTS | {".bin"}

DVD_SIZE_THRESHOLD = 900 * 1024 * 1024  # au-delà, une .iso est probablement un DVD


class Colors:
    if sys.stdout.isatty():
        GREEN, RED, YEL, DIM, BOLD, END = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
    else:
        GREEN = RED = YEL = DIM = BOLD = END = ""


def find_chdman(explicit=None):
    if explicit:
        p = Path(explicit)
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
        sys.exit(f"chdman introuvable à : {explicit}")
    exe = shutil.which("chdman") or shutil.which("chdman.exe")
    if not exe:
        sys.exit(
            f"{Colors.RED}chdman introuvable.{Colors.END}\n"
            "Installe-le :\n"
            "  • Debian/Ubuntu/Kubuntu : sudo apt install mame-tools\n"
            "  • Fedora :                sudo dnf install mame-tools\n"
            "  • Arch :                  sudo pacman -S mame-tools\n"
            "  • macOS :                 brew install rom-tools\n"
            "Ou passe le chemin avec --chdman /chemin/vers/chdman"
        )
    return exe


def parse_referenced_files(descriptor: Path):
    """Retourne les noms de fichiers référencés par un .cue/.toc/.gdi (lignes FILE \"...\")."""
    refs = set()
    try:
        text = descriptor.read_text(errors="replace")
    except Exception:
        return refs
    # .cue / .toc :  FILE "xxx.bin" BINARY
    for m in re.finditer(r'FILE\s+"([^"]+)"', text, re.IGNORECASE):
        refs.add(descriptor.parent.joinpath(m.group(1)).resolve())
    # .cue sans guillemets : FILE xxx.bin BINARY
    for m in re.finditer(r'^\s*FILE\s+(\S+\.\w+)\s', text, re.IGNORECASE | re.MULTILINE):
        refs.add(descriptor.parent.joinpath(m.group(1)).resolve())
    # .gdi : lignes « n lba type secsize nom offset »
    for m in re.finditer(r'\s(\S+\.(?:bin|raw|iso))\b', text, re.IGNORECASE):
        refs.add(descriptor.parent.joinpath(m.group(1)).resolve())
    return refs


def collect_inputs(paths, recursive):
    """Développe fichiers/dossiers en une liste de fichiers candidats."""
    files = []
    for raw in paths:
        p = Path(raw).expanduser()
        if p.is_dir():
            it = p.rglob("*") if recursive else p.glob("*")
            files += [f for f in it if f.is_file() and f.suffix.lower() in INPUT_EXTS]
        elif p.is_file():
            files.append(p)
        else:
            print(f"{Colors.YEL}Ignoré (introuvable) : {raw}{Colors.END}", file=sys.stderr)
    return files


def build_jobs(files):
    """
    Détermine la liste des conversions à faire :
      - chaque descripteur (.cue/.gdi/.toc) et image (.iso/.nrg) devient un job ;
      - un .bin n'est un job que s'il n'est référencé par AUCUN descripteur collecté
        (sinon c'est le descripteur qui le prend en charge).
    Retourne une liste de tuples (source_path, is_lone_bin).
    """
    descriptors = [f for f in files if f.suffix.lower() in DESCRIPTOR_EXTS]
    images = [f for f in files if f.suffix.lower() in IMAGE_EXTS]
    bins = [f for f in files if f.suffix.lower() == ".bin"]

    covered = set()
    for d in descriptors:
        covered |= parse_referenced_files(d)

    jobs = []
    seen = set()
    for d in descriptors + images:
        r = d.resolve()
        if r not in seen:
            seen.add(r)
            jobs.append((d, False))
    for b in bins:
        if b.resolve() in covered:
            continue  # pris en charge par un cue
        jobs.append((b, True))
    return jobs


def decide_mode(src: Path, mode: str):
    if mode != "auto":
        return mode
    if src.suffix.lower() == ".iso":
        try:
            if src.stat().st_size > DVD_SIZE_THRESHOLD:
                return "dvd"
        except OSError:
            pass
    return "cd"


def make_temp_cue(bin_path: Path, track_mode: str):
    """Crée un .cue temporaire à côté du .bin isolé. Retourne le Path du cue (à supprimer après)."""
    cue = bin_path.with_suffix(bin_path.suffix + ".iso2chd.tmp.cue")
    cue.write_text(
        f'FILE "{bin_path.name}" BINARY\n'
        f"  TRACK 01 {track_mode}\n"
        f"    INDEX 01 00:00:00\n"
    )
    return cue


def human(n):
    for u in ("o", "Ko", "Mo", "Go"):
        if n < 1024 or u == "Go":
            return f"{n:.0f} {u}" if u == "o" else f"{n:.1f} {u}"
        n /= 1024


def convert_one(job, args, chdman):
    src, is_lone_bin = job
    out_dir = Path(args.outdir).expanduser() if args.outdir else src.parent
    out = out_dir / (src.stem + ".chd")
    label = src.name

    if out.exists() and not args.force:
        return ("skip", src, out, "déjà présent (--force pour réécrire)")

    if args.dry_run:
        return ("dry", src, out, "à convertir")

    out_dir.mkdir(parents=True, exist_ok=True)

    temp_cue = None
    try:
        mode = decide_mode(src, args.mode)
        if is_lone_bin:
            temp_cue = make_temp_cue(src, args.bin_track)
            input_path = temp_cue
        else:
            input_path = src

        sub = "createdvd" if mode == "dvd" else "createcd"
        cmd = [chdman, sub, "-i", str(input_path), "-o", str(out)]
        if args.force:
            cmd.append("-f")
        if args.numprocessors:
            cmd += ["--numprocessors", str(args.numprocessors)]

        t0 = time.time()
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        dt = time.time() - t0

        if proc.returncode != 0:
            # nettoyer une sortie partielle
            if out.exists():
                try: out.unlink()
                except OSError: pass
            tail = "\n".join(proc.stdout.strip().splitlines()[-4:])
            return ("fail", src, out, tail or f"chdman a renvoyé {proc.returncode}")

        if args.verify:
            v = subprocess.run([chdman, "verify", "-i", str(out)],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if v.returncode != 0:
                return ("fail", src, out, "échec de la vérification chdman")

        if args.delete_source and not is_lone_bin:
            # supprime la source + ses .bin référencés (uniquement pour un descripteur)
            to_del = {src}
            if src.suffix.lower() in DESCRIPTOR_EXTS:
                to_del |= parse_referenced_files(src)
            for f in to_del:
                try:
                    Path(f).unlink()
                except OSError:
                    pass

        try:
            # taille source = données réelles (pour un descripteur, somme des .bin référencés)
            if src.suffix.lower() in DESCRIPTOR_EXTS:
                refs = parse_referenced_files(src)
                in_size = sum((Path(f).stat().st_size for f in refs if Path(f).exists()), 0) or src.stat().st_size
            else:
                in_size = src.stat().st_size
            ratio = out.stat().st_size / max(1, in_size)
            info = f"{human(out.stat().st_size)} ({ratio*100:.0f}% de {human(in_size)}), {dt:.0f}s, {sub}"
        except OSError:
            info = f"{dt:.0f}s, {sub}"
        return ("ok", src, out, info)

    except Exception as e:
        return ("fail", src, out, str(e))
    finally:
        if temp_cue is not None:
            try: temp_cue.unlink()
            except OSError: pass


def main():
    ap = argparse.ArgumentParser(
        description="Convertit des images CD/DVD (.cue/.bin/.iso/.gdi/.toc/.nrg) en .chd via chdman.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Astuce : les .bin référencés par un .cue sont gérés automatiquement via le .cue.",
    )
    ap.add_argument("paths", nargs="+", help="fichiers et/ou dossiers à convertir")
    ap.add_argument("-o", "--outdir", help="dossier de sortie (défaut : à côté de chaque source)")
    ap.add_argument("-r", "--recursive", action="store_true", help="explorer les dossiers en récursif")
    ap.add_argument("-f", "--force", action="store_true", help="réécrire un .chd déjà présent")
    ap.add_argument("-j", "--jobs", type=int, default=1,
                    help="conversions en parallèle (défaut 1 ; chdman utilise déjà tous les cœurs par job)")
    ap.add_argument("--numprocessors", type=int, default=0,
                    help="limite le nb de threads chdman par conversion (0 = auto)")
    ap.add_argument("--mode", choices=["auto", "cd", "dvd"], default="cd",
                    help="cd (createcd, défaut) / dvd (createdvd, images PS2) / auto (dvd si .iso > 900 Mo)")
    ap.add_argument("--bin-track", default="MODE2/2352",
                    help="mode de piste pour un .bin isolé sans cue (défaut MODE2/2352, typique PS1)")
    ap.add_argument("--verify", action="store_true", help="vérifier chaque .chd après création")
    ap.add_argument("--delete-source", action="store_true",
                    help="supprimer la source (et ses .bin) après une conversion réussie")
    ap.add_argument("--dry-run", action="store_true", help="lister ce qui serait fait, sans convertir")
    ap.add_argument("--chdman", help="chemin explicite vers l'exécutable chdman")
    args = ap.parse_args()

    # En --dry-run on tolère l'absence de chdman (simple aperçu)
    chdman = None
    if args.dry_run:
        try:
            chdman = find_chdman(args.chdman)
        except SystemExit:
            chdman = "(chdman non installé)"
    else:
        chdman = find_chdman(args.chdman)

    files = collect_inputs(args.paths, args.recursive)
    if not files:
        sys.exit("Aucun fichier .cue/.bin/.iso/.gdi/.toc/.nrg trouvé.")

    jobs = build_jobs(files)
    if not jobs:
        sys.exit("Rien à convertir (les .bin trouvés sont déjà couverts par des .cue).")

    print(f"{Colors.BOLD}{len(jobs)} conversion(s){Colors.END} "
          f"via {chdman}{'  [DRY-RUN]' if args.dry_run else ''}\n")

    counts = {"ok": 0, "skip": 0, "fail": 0, "dry": 0}
    results = []

    def emit(res):
        status, src, out, info = res
        counts[status] += 1
        icon = {"ok": f"{Colors.GREEN}✔{Colors.END}", "skip": f"{Colors.DIM}∘{Colors.END}",
                "fail": f"{Colors.RED}✗{Colors.END}", "dry": f"{Colors.YEL}·{Colors.END}"}[status]
        line = {"ok": "OK", "skip": "ignoré", "fail": "ÉCHEC", "dry": "prévu"}[status]
        print(f"  {icon} {line:6} {src.name}  {Colors.DIM}→ {out.name}  {info}{Colors.END}")
        results.append(res)

    if args.jobs > 1 and not args.dry_run:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
            for res in ex.map(lambda j: convert_one(j, args, chdman), jobs):
                emit(res)
    else:
        for j in jobs:
            emit(convert_one(j, args, chdman))

    print(f"\n{Colors.BOLD}Résumé :{Colors.END} "
          f"{Colors.GREEN}{counts['ok']} OK{Colors.END}, "
          f"{counts['skip']} ignoré(s), "
          f"{Colors.RED if counts['fail'] else ''}{counts['fail']} échec(s){Colors.END}"
          + (f", {counts['dry']} prévu(s)" if args.dry_run else ""))

    if counts["fail"]:
        print(f"\n{Colors.RED}Détail des échecs :{Colors.END}")
        for status, src, out, info in results:
            if status == "fail":
                print(f"  • {src.name} : {info}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nInterrompu.")
