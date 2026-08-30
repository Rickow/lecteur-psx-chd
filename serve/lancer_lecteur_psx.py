#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lance le lecteur PSX correctement : il ne peut PAS marcher en double-clic (file://),
car le core threadé exige l'isolation crossOrigin (COOP/COEP), impossible sur file://.
Ce script sert le dossier en http AVEC les bons en-têtes et ouvre le navigateur.

Usage : python3 lancer_lecteur_psx.py   (ou double-clic sur le lanceur .desktop)
Ctrl+C (ou fermer la fenêtre) pour arrêter.
"""
import http.server
import os
import socketserver
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # racine du dépôt
PAGE = "lecteur-psx.html"
PORT = 8901


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def end_headers(self):
        # en-têtes d'isolation crossOrigin (SharedArrayBuffer / threads)
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


def main():
    socketserver.TCPServer.allow_reuse_address = True
    url = f"http://127.0.0.1:{PORT}/{PAGE}"
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print("Lecteur PSX servi ici :", url)
        print("(garde cette fenêtre ouverte pendant que tu joues ; ferme-la pour arrêter)")
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nArrêt.")


if __name__ == "__main__":
    main()
