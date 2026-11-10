@echo off
REM Clique duas vezes neste arquivo para instalar as bibliotecas necessarias.
cd /d "%~dp0"
echo Instalando bibliotecas (requests, pyautogui, pyperclip)...
python -m pip install --upgrade pip
python -m pip install requests pyautogui pyperclip
echo.
echo Pronto. Agora rode o verificar.bat para conferir se esta tudo certo.
pause
