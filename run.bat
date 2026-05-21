@echo off
REM Быстрый запуск Jarvis на Windows.
REM Перед первым запуском: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt

if not exist .venv\Scripts\python.exe (
    echo [Jarvis] Виртуальное окружение не найдено. Создаю...
    python -m venv .venv || goto :error
    .venv\Scripts\python.exe -m pip install --upgrade pip || goto :error
    .venv\Scripts\python.exe -m pip install -r requirements.txt || goto :error
)

.venv\Scripts\python.exe -m jarvis %*
goto :eof

:error
echo [Jarvis] Установка завершилась с ошибкой.
exit /b 1
