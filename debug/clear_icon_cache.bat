@echo off
REM Clear Windows Icon Cache
REM Run this script to force Windows to reload icons

echo Stopping Windows Explorer...
taskkill /f /im explorer.exe

echo Deleting icon cache files...
cd /d %userprofile%\AppData\Local\Microsoft\Windows\Explorer
attrib -h iconcache_*.db
del iconcache_*.db /a
del thumbcache_*.db /a

echo.
echo Icon cache cleared!
echo Restarting Windows Explorer...
start explorer.exe

echo.
echo Done! Your icons should now update.
echo If icons still don't show, try logging out and back in.
pause
