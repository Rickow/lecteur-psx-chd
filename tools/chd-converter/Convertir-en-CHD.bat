@echo off
rem ============================================================
rem  Convertir en CHD (Windows) — version autonome, sans Python.
rem
rem  UTILISATION : place ce .bat dans un dossier contenant tes
rem  images CD/DVD (.cue/.bin, .iso, .gdi, .toc) et double-clique.
rem  Il convertit tout le dossier en .chd (a cote des sources ;
rem  les sources ne sont jamais supprimees, un .chd deja present
rem  est ignore).
rem
rem  PREREQUIS : chdman.exe (outil MAME). Deux options :
rem    - pose chdman.exe A COTE de ce .bat, OU
rem    - installe-le dans le PATH (distribution MAME Windows).
rem ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem --- localiser chdman.exe ---
set "CHDMAN="
if exist "%~dp0chdman.exe" set "CHDMAN=%~dp0chdman.exe"
if not defined CHDMAN ( where chdman.exe >nul 2>&1 && set "CHDMAN=chdman.exe" )
if not defined CHDMAN (
  echo.
  echo   chdman.exe introuvable.
  echo   - Mets chdman.exe a cote de ce fichier, OU
  echo   - Ajoute chdman au PATH ^(recupere-le dans une distribution MAME^).
  echo.
  pause
  exit /b 1
)

set /a OK=0, SKIP=0, FAIL=0
echo.
echo   chdman  : "%CHDMAN%"
echo   Dossier : "%CD%"
echo.

rem --- descripteurs multipistes (.cue/.gdi/.toc) ---
for %%F in (*.cue *.gdi *.toc) do call :do_cd "%%~fF"

rem --- images a piste unique (.iso) : DVD si >= 1 Go, sinon CD ---
for %%F in (*.iso) do call :do_iso "%%~fF"

rem --- .bin isole (aucun .cue de meme nom) : cue temporaire ---
for %%F in (*.bin) do ( if not exist "%%~dpnF.cue" call :do_bin "%%~fF" )

echo.
echo   Termine : !OK! converti(s), !SKIP! ignore(s), !FAIL! echec(s).
echo.
pause
exit /b 0

rem ------------------------------------------------------------
:do_cd
set "OUT=%~dpn1.chd"
if exist "!OUT!" ( echo   [ignore] %~nx1 & set /a SKIP+=1 & goto :eof )
echo   [chd]    %~nx1
"%CHDMAN%" createcd -i "%~1" -o "!OUT!"
if errorlevel 1 ( echo   [ECHEC]  %~nx1 & set /a FAIL+=1 ) else ( set /a OK+=1 )
goto :eof

:do_iso
set "OUT=%~dpn1.chd"
if exist "!OUT!" ( echo   [ignore] %~nx1 & set /a SKIP+=1 & goto :eof )
set "SZ=%~z1"
rem 10e chiffre present => taille >= 1 000 000 000 octets (~1 Go) => DVD
if not "!SZ:~9,1!"=="" ( set "SUB=createdvd" ) else ( set "SUB=createcd" )
echo   [chd]    %~nx1  ^(!SUB!^)
"%CHDMAN%" !SUB! -i "%~1" -o "!OUT!"
if errorlevel 1 ( echo   [ECHEC]  %~nx1 & set /a FAIL+=1 ) else ( set /a OK+=1 )
goto :eof

:do_bin
set "OUT=%~dpn1.chd"
if exist "!OUT!" ( echo   [ignore] %~nx1 & set /a SKIP+=1 & goto :eof )
set "CUE=%~dpn1.__tmp__.cue"
echo   [chd]    %~nx1  ^(bin isole -^> cue temporaire^)
> "!CUE!"  echo FILE "%~nx1" BINARY
>>"!CUE!"  echo   TRACK 01 MODE2/2352
>>"!CUE!"  echo     INDEX 01 00:00:00
"%CHDMAN%" createcd -i "!CUE!" -o "!OUT!"
if errorlevel 1 ( echo   [ECHEC]  %~nx1 & set /a FAIL+=1 ) else ( set /a OK+=1 )
del "!CUE!" >nul 2>&1
goto :eof
