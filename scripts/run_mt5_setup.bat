@echo off
chcp 65001 > nul
set "TARGET_DIR=E:\D drive\scalp-bot\scalp_sample"

:: ساخت پوشه در صورت عدم وجود
if not exist "%TARGET_DIR%" (
    mkdir "%TARGET_DIR%"
)

set "PY_FILE=%TARGET_DIR%\run_mt5_setup.py"

:: ساخت فایل پایتون در مسیر مورد نظر
(
echo import subprocess
echo.
echo # Path to the EXE you want to run
echo exe_path = r"E:\D drive\scalp-bot\scalp_sample\mt5setup_for_windows.exe"
echo.
echo subprocess.Popen^(exe_path^)
) > "%PY_FILE%"

:: اجرای فایل پایتون ساخته شده
echo Running the Python script...
python "%PY_FILE%"

pause
