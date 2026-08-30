#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ré-inline le core emscripten (js + wasm) dans les blobs base64 de lecteur-psx.html.
À lancer après le build + patch_core.py.

Usage : python3 inline_core.py <lecteur-psx.html> <core.js> <core.wasm>
"""
import base64
import re
import sys


def enc(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def repl(html, script_id, b64):
    pat = re.compile(r'(<script type="text/plain" id="' + re.escape(script_id) + r'">)(.*?)(</script>)', re.DOTALL)
    html, n = pat.subn(lambda m: m.group(1) + b64 + m.group(3), html)
    assert n == 1, f"{script_id}: {n} occurrence(s) (attendu 1)"
    return html


def main():
    if len(sys.argv) != 4:
        sys.exit("Usage : python3 inline_core.py <lecteur-psx.html> <core.js> <core.wasm>")
    html_path, js_path, wasm_path = sys.argv[1:4]
    html = open(html_path, encoding="utf-8").read()
    html = repl(html, "core-js", enc(js_path))
    html = repl(html, "core-wasm", enc(wasm_path))
    open(html_path, "w", encoding="utf-8").write(html)
    js = open(js_path, encoding="utf-8").read()
    assert "__PSX_CORE_URL" in js, "ATTENTION : patch_core.py n'a pas ete applique au core !"
    print("inline_core : OK (core-js + core-wasm re-inlines)")


if __name__ == "__main__":
    main()
