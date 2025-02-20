@echo off
setlocal enabledelayedexpansion

:: Получаем текущую директорию скрипта
set "PROJECT_DIR=%~dp0"

:: Проверяем наличие Python
python --version >nul 2>&1
if errorlevel 1 (
   echo Python не установлен! Пожалуйста, установите Python с python.org
   pause
   exit /b 1
)

:: Проверяем наличие виртуального окружения
if not exist "venv" (
   python -m venv venv
   call venv\Scripts\activate
   pip install -r requirements.txt
) else (
   call venv\Scripts\activate
)

:: Устанавливаем PYTHONPATH
set "PYTHONPATH=%PROJECT_DIR%"

:: Запускаем проект
python main.py

pause