@echo off
echo ==========================================================
echo DeepPhoto Database Synchronization Tool
echo ==========================================================
echo This script will copy your DEVELOPMENT environment databases 
echo into the installation folder, replacing the empty defaults.
echo Please make sure the Desktop Application is CLOSED.
pause

echo.
echo Locating source databases...
set "SOURCE_DIR=%~dp0..\src" 
set "DB_DIR=%~dp0db"

if not exist "%DB_DIR%" mkdir "%DB_DIR%"

echo Copying history.db...
if exist "history.db" copy /y "history.db" "%DB_DIR%\history.db"

echo Copying search_v2.db...
if exist "search_v2.db" copy /y "search_v2.db" "%DB_DIR%\search_v2.db"

echo Copying chromadb vector index...
if exist "chroma_v2" xcopy /S /E /Y /I "chroma_v2" "%DB_DIR%\chroma_v2"

echo.
echo Database synchronization complete! You can open the 
echo DeepPhoto Desktop application now.
pause
