@echo off
REM Clique duas vezes para rodar o dia inteiro SEM enviar ao muse (teste seguro).
cd /d "%~dp0"
python claude_muse_bot.py --simular
pause
