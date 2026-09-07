@echo off
title Super Captura - Instalar Bibliotecas
cd /d "%~dp0"
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
pause
