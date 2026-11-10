@echo off
REM Clique duas vezes neste arquivo para instalar o que o robo precisa.
REM So e necessario se o arquivo do Vistoria for PDF (leitura de PDF).
cd /d "%~dp0"
echo Atualizando o pip...
python -m pip install --upgrade pip
echo Instalando leitura de PDF (pypdf) - util se o Vistoria exporta PDF...
python -m pip install pypdf
echo.
echo Pronto. Agora rode o verificar.bat para conferir se esta tudo certo.
pause
