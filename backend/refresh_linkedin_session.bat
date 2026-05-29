@echo off
cd /d d:\projects\AI_sales\backend
call .venv\Scripts\activate.bat 2>nul || call ..\.venv\Scripts\activate.bat 2>nul
python app/scripts/linkedin/auth_setup.py
