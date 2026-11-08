@echo off
rem YouTube ad blocker - one-click installer for Chrome / Edge / Firefox (Windows).
rem Double-click this file, then click "Yes" on the administrator (UAC) prompt.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0youtube-adblock.ps1" -Action Install %*
