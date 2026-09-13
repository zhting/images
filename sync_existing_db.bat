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
REM SQLite runs in WAL mode: recent commits live in the -wal sidecar until
REM a checkpoint. A clean app shutdown checkpoints them away, but copy the
REM sidecars too so an unclean exit cannot lose the newest data.
if exist "history.db" copy /y "history.db" "%DB_DIR%\history.db"
if exist "history.db-wal" copy /y "history.db-wal" "%DB_DIR%\history.db-wal"
if exist "history.db-shm" copy /y "history.db-shm" "%DB_DIR%\history.db-shm"

echo Copying search_v2.db...
if exist "search_v2.db" copy /y "search_v2.db" "%DB_DIR%\search_v2.db"
if exist "search_v2.db-wal" copy /y "search_v2.db-wal" "%DB_DIR%\search_v2.db-wal"
if exist "search_v2.db-shm" copy /y "search_v2.db-shm" "%DB_DIR%\search_v2.db-shm"

echo Copying chromadb vector index...
if exist "chroma_v2" xcopy /S /E /Y /I "chroma_v2" "%DB_DIR%\chroma_v2"

echo.
echo Database synchronization complete! You can open the 
echo DeepPhoto Desktop application now.
pause
