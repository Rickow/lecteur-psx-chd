#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
applyppf — applique un patch PPF (1.0 / 2.0 / 3.0) à une image disque (.bin / .iso).

Sert à appliquer AVANT la conversion en CHD :
  • un patch **60 Hz** (PAL60) → le jeu PAL tourne à pleine vitesse,
  • un patch **anti-libcrypt** → retire la protection (plus besoin du .sbi),
  • ou tout autre correctif distribué en .ppf.

Usage :
  python3 applyppf.py jeu.bin patch.ppf            # patche jeu.bin (sauvegarde jeu.bin.bak)
  python3 applyppf.py jeu.bin patch.ppf -o sortie.bin   # écrit une copie patchée, ne touche pas l'original
  python3 applyppf.py jeu.bin patch.ppf --no-backup

Ensuite : convertis l'image patchée en CHD (iso2chd.py / le .bat / le .sh).
Le PPF s'applique à la piste DONNÉES (le .bin), pas au .cue.
"""

import argparse
import shutil
import sys
from pathlib import Path


def parse_header(ppf: bytes):
    """Retourne (pos_debut_records, taille_offset, a_undo, taille_base_ou_None)."""
    magic = ppf[:5]
    if magic == b"PPF30":
        if ppf[5] != 0x02:
            print(f"  (avertissement) méthode PPF3 inattendue: 0x{ppf[5]:02x}")
        blockcheck = ppf[57]
        undo = ppf[58]
        pos = 60 + (1024 if blockcheck else 0)
        return pos, 8, undo == 0x01, None
    if magic == b"PPF20":
        base = int.from_bytes(ppf[56:60], "little")  # taille du fichier d'origine
        return 1084, 4, False, base          # blockcheck (1024) toujours présent en 2.0
    if magic == b"PPF10":
        return 56, 4, False, None
    raise ValueError("Ce n'est pas un fichier PPF (magic PPF10/PPF20/PPF30 attendu).")


def apply_ppf(image_path: Path, ppf_path: Path):
    ppf = ppf_path.read_bytes()
    pos, off_size, has_undo, base_size = parse_header(ppf)

    img_size = image_path.stat().st_size
    if base_size is not None and base_size != img_size:
        print(f"  (avertissement) taille image {img_size} ≠ taille attendue par le PPF {base_size} "
              f"— vérifie que c'est la bonne image/piste.")

    n = 0
    with open(image_path, "r+b") as img:
        end = len(ppf)
        while pos + off_size + 1 <= end:
            offset = int.from_bytes(ppf[pos:pos + off_size], "little"); pos += off_size
            length = ppf[pos]; pos += 1
            data = ppf[pos:pos + length]; pos += length
            if len(data) != length:
                raise ValueError("PPF tronqué (données de patch incomplètes).")
            if has_undo:
                pos += length  # on saute les données d'annulation
            if offset + length > img_size:
                raise ValueError(f"Le patch écrit à {offset}+{length} au-delà de la taille de "
                                 f"l'image ({img_size}) — mauvaise image ?")
            img.seek(offset)
            img.write(data)
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description="Applique un patch PPF (1/2/3) à une image .bin/.iso.")
    ap.add_argument("image", help="image disque à patcher (.bin ou .iso)")
    ap.add_argument("ppf", help="fichier patch .ppf")
    ap.add_argument("-o", "--output", help="écrit une copie patchée ici (sinon patch en place)")
    ap.add_argument("--no-backup", action="store_true", help="ne pas créer de .bak (patch en place)")
    args = ap.parse_args()

    image = Path(args.image)
    ppf = Path(args.ppf)
    if not image.is_file():
        sys.exit(f"Image introuvable : {image}")
    if not ppf.is_file():
        sys.exit(f"PPF introuvable : {ppf}")

    if args.output:
        target = Path(args.output)
        shutil.copy2(image, target)
        print(f"Copie → {target}")
    else:
        target = image
        if not args.no_backup:
            bak = image.with_suffix(image.suffix + ".bak")
            if not bak.exists():
                shutil.copy2(image, bak)
                print(f"Sauvegarde → {bak}")

    try:
        count = apply_ppf(target, ppf)
    except Exception as e:
        sys.exit(f"Échec : {e}")
    print(f"OK — {count} enregistrement(s) appliqué(s) sur {target}")
    print("→ Convertis maintenant l'image patchée en CHD.")


if __name__ == "__main__":
    main()
