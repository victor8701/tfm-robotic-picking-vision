@echo off
title Analizar mercado
echo.
echo  Arrancando la app de Analizar mercado...
echo  Se abrira sola en el navegador. NO cierres la ventana negra que aparece mientras la uses.
echo.
start "Analizar mercado (servidor) - no cerrar" wsl.exe -d Ubuntu-22.04 -e bash -lc "cd /home/ubuntu22/repos/tfm-robotic-picking-vision/experimentos/analisis_mercado && python3 mercado.py app"
timeout /t 6 /nobreak >nul
start "" http://localhost:8766
exit
