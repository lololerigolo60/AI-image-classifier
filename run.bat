@echo off
title AI Image Classifier - Auto-Setup
setlocal

echo ====================================================
echo   Verification de l'environnement Python
echo ====================================================

:: 1. Verifier si le dossier venv existe, sinon le creer
if not exist "venv" (
    echo [INFO] Environnement virtuel introuvable. Creation en cours...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERREUR] Impossible de creer l'environnement virtuel. Verifiez que Python est installe.
        pause
        exit /b
    )
)

:: 2. Activer l'environnement
call .\venv\Scripts\activate

:: 3. Verifier les librairies et installer si necessaire
echo [INFO] Verification des dependances...

:: On tente d'importer les modules clefs pour tester leur presence
python -c "import customtkinter, PIL, ollama" 2>nul

if %errorlevel% neq 0 (
    echo [PS] Des librairies sont manquantes. Installation via requirements.txt...
    if exist "requirements.txt" (
        pip install -r requirements.txt
    ) else (
        echo [!] requirements.txt introuvable. Installation manuelle des modules de base...
        pip install customtkinter Pillow ollama
    )
) else (
    echo [OK] Toutes les librairies sont deja installees.
)

:: 4. Lancer le script principal
echo.
echo [INFO] Lancement de AI_images_classifier.py...
echo ----------------------------------------------------
python AI_images_classifier.py

if %errorlevel% neq 0 (
    echo.
    echo [ERREUR] Le programme s'est arrete anormalement.
    pause
)

deactivate