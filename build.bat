@echo off
setlocal

pyinstaller .\sortimages_multiview.py --copy-metadata=imageio

endlocal
pause
