@echo off
REM Tao moi truong ao va cai thu vien (Windows). Chay: setup.bat
py -3.11 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements-holistic.txt
echo.
echo Xong. Mo VS Code, chon interpreter .venv, nhan F5 de chay "Holistic + Sim (webcam)".
pause
