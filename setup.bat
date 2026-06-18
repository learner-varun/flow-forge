@echo off
echo === Initializing Python Virtual Environment ===

REM 1. Create venv if it doesn't exist
if not exist venv (
    echo Creating virtual environment 'venv'...
    python -m venv venv
) else (
    echo Virtual environment 'venv' already exists.
)

REM 2. Activate the virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM 3. Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM 4. Install requirements
if exist requirements.txt (
    echo Installing dependencies from requirements.txt...
    pip install -r requirements.txt
) else (
    echo Error: requirements.txt not found!
    exit /b 1
)

echo === Setup completed successfully! ===
echo To activate venv in your Command Prompt session run: call venv\Scripts\activate.bat
