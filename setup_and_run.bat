@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

REM --- Configuration ---
SET PROJECT_DIR=%~dp0
SET PYTHON_EXE=python
SET REQUIREMENTS_FILE=requirements.txt
SET APP_FILE=app.py
SET DATA_DIR=data
SET LOG_DIR=logs
SET CSS_DIR=static\css
SET JS_DIR=static\js
SET TEMPLATES_DIR=templates

REM --- Ensure necessary directories exist ---
echo Creating necessary directories...
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if not exist "%CSS_DIR%" mkdir "%CSS_DIR%"
if not exist "%JS_DIR%" mkdir "%JS_DIR%"
if not exist "%TEMPLATES_DIR%" mkdir "%TEMPLATES_DIR%"
echo Directories created.

REM --- Create/Check requirements.txt ---
echo Checking for requirements.txt...
if not exist "%REQUIREMENTS_FILE%" (
    echo "%REQUIREMENTS_FILE%" not found. Creating it with common dependencies.
    echo flask>>"%REQUIREMENTS_FILE%"
    echo pandas>>"%REQUIREMENTS_FILE%"
    echo sentence-transformers>>"%REQUIREMENTS_FILE%"
    echo torch>>"%REQUIREMENTS_FILE%"
    echo Pillow>>"%REQUIREMENTS_FILE%"
    echo Creating "%REQUIREMENTS_FILE%" failed if this message is followed by an error.
) else (
    echo "%REQUIREMENTS_FILE%" found.
)

REM --- Create/Check core Python files ---
REM IMPORTANT: These are placeholders. You need to manually create these files
REM with the correct Python code or download them. This batch script cannot
REM reliably create complex Python files with specific content.

REM Example: Create dummy files if they don't exist (replace with your actual code)
REM You should have these files already if you followed previous steps.
REM If you are running this script for the first time, you MUST manually
REM create app.py, logic.py, data_utils.py and paste the correct code into them.

REM --- Install Dependencies ---
echo Installing Python dependencies (this may take a while)...
"%PYTHON_EXE%" -m pip install -r "%REQUIREMENTS_FILE%" --upgrade
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install dependencies. Please check your Python installation, ensure pip is up-to-date, and verify the requirements.txt file.
    pause
    EXIT /B 1
)

echo Dependencies installed successfully.

REM --- Prepare Data ---
echo Ensuring data directory and dummy data file exist...
REM This assumes you have your original 'diseases.csv' in the same directory as the script.
REM If not, adjust the path or place it there.
IF NOT EXIST "%DATA_DIR%\diseases.csv" (
    echo "%DATA_DIR%\diseases.csv" not found.
    echo Please place your original 'diseases.csv' file in the '%DATA_DIR%' folder.
    echo You might need to run the data cleaning script manually first if you don't have cleaned_diseases.csv.
    REM Optionally, create a minimal dummy file for testing:
    REM echo Creating dummy diseases.csv...
    REM (
    REM     echo disease,symptoms,treatment
    REM     echo Flu,"fever, cough","rest"
    REM ) > "%DATA_DIR%\diseases.csv"
    echo Continuing without original data. The application might fail if cleaned_diseases.csv is also missing.
) ELSE (
    echo "%DATA_DIR%\diseases.csv" found.
)

REM --- Run Data Cleaning (Optional, if needed) ---
REM You might want to uncomment and run this if you don't have cleaned_diseases.csv
REM echo Running data cleaning script...
REM "%PYTHON_EXE%" data_utils.py
REM IF %ERRORLEVEL% NEQ 0 (
REM     echo ERROR: Data cleaning script failed.
REM     pause
REM     EXIT /B 1
REM )
REM echo Data cleaning finished.

REM --- Create/Check Static and Template Files ---
REM IMPORTANT: Ensure your main.css, index.html, 404.html, 500.html are correctly placed.
REM This script assumes they are present.

REM --- Run the Application ---
echo Starting the Flask application...
echo Press Ctrl+C to stop the application.
"%PYTHON_EXE%" "%APP_FILE%"

IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to start the Flask application. Check "%APP_FILE%" for errors.
    pause
    EXIT /B 1
)
