@echo off
setlocal

set "ROOT_DIR=%~dp0"
set "APP_PY=%ROOT_DIR%python_coursework\local_webapp.py"
set "PYTHON_EXE=C:\Users\MSI\AppData\Local\Programs\Python\Python312\python.exe"
set "TESSERACT_CMD=%ROOT_DIR%Tesseract-OCR\tesseract.exe"

if not exist "%APP_PY%" (
    echo [ERROR] Application file not found:
    echo %APP_PY%
    pause
    exit /b 1
)

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python executable not found:
    echo %PYTHON_EXE%
    echo.
    echo Install Python or edit this bat file with the correct path.
    pause
    exit /b 1
)

if exist "%TESSERACT_CMD%" (
    set "TESSERACT_CMD=%TESSERACT_CMD%"
    echo Using Tesseract:
    echo %TESSERACT_CMD%
    echo.
)

echo Starting local payment verification app...
echo Open http://127.0.0.1:8000 in your browser.
echo Press Ctrl+C in this window to stop the server.
echo.

"%PYTHON_EXE%" "%APP_PY%"

echo.
echo Server stopped.
pause
