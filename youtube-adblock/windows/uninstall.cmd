@echo off
rem YouTube ad blocker - remove the browser policies added by install.cmd (Windows).
rem Double-click this file, then click "Yes" on the administrator (UAC) prompt.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0youtube-adblock.ps1" -Action Uninstall %*
