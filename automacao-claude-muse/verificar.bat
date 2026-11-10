@echo off
REM Clique duas vezes para conferir se esta tudo pronto para rodar.
cd /d "%~dp0"
python claude_muse_bot.py --verificar
pause
