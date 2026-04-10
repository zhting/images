@echo off
echo Building Vue Frontend...
cd web
call npm run build
cd ..

echo Generating Empty Base Databases for Package...
if not exist scripts mkdir scripts
python scripts\init_empty_db.py

echo Building Desktop App with PyInstaller...
pyinstaller DeepPhoto.spec --noconfirm

echo Copying Sync Script to Dist Directory...
copy /y sync_existing_db.bat dist\DeepPhoto\sync_existing_db.bat

echo Organizing App Data Directories...
move /y dist\DeepPhoto\_internal\db dist\DeepPhoto\db
echo {"cache_path": "cache", "_comment": "WebView cache directory"} > dist\DeepPhoto\webview_config.json

echo Creating Installer with Inno Setup...
"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" setup.iss

echo Build Complete! Installer is in the Output folder.
