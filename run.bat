@echo off
REM Simple run script for MCA Multi-Business Processor

echo Starting MCA Multi-Business Processor...

REM Change to the script directory
cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run the Streamlit app
streamlit run app.py

pause