@echo off
REM Executa o robo uma vez (usado pelo Agendador de Tarefas do Windows as 16:00).
REM Ajuste o caminho abaixo se mover a pasta.
cd /d "%~dp0"
python claude_muse_bot.py --agora
