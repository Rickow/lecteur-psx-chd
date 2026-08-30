#!/usr/bin/env python3
"""Patches à appliquer au core threadé APRÈS chaque link RetroArch (build_link_threaded.sh).

Contexte : le core est inliné en base64 dans lecteur-psx.html et chargé par Nostalgist
depuis un blob URL. Or emscripten (ES6 + pthreads) crée ses workers/worklets ainsi :
  - pthread     : new Worker(new URL("pcsx_rearmed_libretro.js", import.meta.url), {type:module})
  - audioworklet: audioWorklet.addModule(locateFile("pcsx_rearmed_libretro.js"))
Deux problèmes quand le core vient d'un blob :
  1. import.meta.url est un blob URL → new URL("relatif", blob:) lève "Invalid base URL".
  2. le blob de Nostalgist n'a PAS de type MIME → un module worker le refuse
     ("non-JavaScript MIME type") .
Fix : charger le worker/worklet depuis globalThis.__PSX_CORE_URL (blob URL au bon MIME,
publié par l'app dans coreBlobs()), avec repli import.meta.url (contexte worker imbriqué).
"""
import sys

PATCHES = [
    ('new Worker(new URL("pcsx_rearmed_libretro.js",import.meta.url),{type:"module",name:"em-pthread"})',
     'new Worker((globalThis.__PSX_CORE_URL||import.meta.url),{type:"module",name:"em-pthread"})'),
    ('audioWorklet.addModule(locateFile("pcsx_rearmed_libretro.js"))',
     'audioWorklet.addModule((globalThis.__PSX_CORE_URL||locateFile("pcsx_rearmed_libretro.js")))'),
    # Garde-fou : deleteContext ne doit pas planter si le contexte GL n'existe pas dans ce thread
    # (arrive quand WebGL est indisponible → contexte jamais créé → évite de tuer le thread de rendu).
    ('deleteContext:contextHandle=>{if(GL.currentContext===GL.contexts[contextHandle]){GL.currentContext=null}',
     'deleteContext:contextHandle=>{if(!GL.contexts[contextHandle]){return;}if(GL.currentContext===GL.contexts[contextHandle]){GL.currentContext=null}'),
]

def main(path):
    s = open(path, encoding='utf-8').read()
    for old, new in PATCHES:
        if new in s:
            print(f'  déjà patché: {new[:45]}…'); continue
        c = s.count(old)
        if c != 1:
            print(f'  ERREUR: {c} occurrence(s) pour {old[:45]}…'); sys.exit(1)
        s = s.replace(old, new); print(f'  patché: {old[:45]}…')
    open(path, 'w', encoding='utf-8').write(s)
    print('patch_core: OK')

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else
         'vendor/core-workerfs-threaded/pcsx_rearmed_libretro.js')
