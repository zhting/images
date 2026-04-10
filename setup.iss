[Setup]
AppName=Deep Photo
AppVersion=2.0
DefaultDirName={userappdata}\DeepPhoto
DefaultGroupName=Deep Photo
OutputDir=Output
OutputBaseFilename=DeepPhoto_Setup
Compression=lzma
SolidCompression=yes
UninstallDisplayIcon={app}\DeepPhoto.exe
PrivilegesRequired=lowest

[Files]
; Base application files (Overwrite allowed)
Source: "dist\DeepPhoto\*"; DestDir: "{app}"; Excludes: "db\*,webview_config.json"; Flags: ignoreversion recursesubdirs createallsubdirs

; User Data files (Never overwrite if they already exist)
Source: "dist\DeepPhoto\db\*"; DestDir: "{app}\db"; Flags: onlyifdoesntexist recursesubdirs createallsubdirs
Source: "dist\DeepPhoto\webview_config.json"; DestDir: "{app}"; Flags: onlyifdoesntexist

[Icons]
Name: "{group}\Deep Photo"; Filename: "{app}\DeepPhoto.exe"
Name: "{autodesktop}\Deep Photo"; Filename: "{app}\DeepPhoto.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\DeepPhoto.exe"; Description: "Launch Deep Photo"; Flags: nowait postinstall skipifsilent
