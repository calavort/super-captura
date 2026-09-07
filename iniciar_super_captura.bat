@echo off
REM Abre o Super Captura SEM a janela preta (console).
REM Usado como reserva pelo atalho do Menu Iniciar (que abre direto no pyw.exe).
REM Para ver logs/erros, use "Abrir Super Captura.bat".
cd /d "%~dp0"
where pyw >nul 2>nul
if %errorlevel%==0 (
  start "" pyw "%~dp0app.py"
) else (
  start "" pythonw "%~dp0app.py"
)
