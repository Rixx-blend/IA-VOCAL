; Installateur IA VOCAL (Inno Setup). Installation par utilisateur, sans administrateur.
; Désinstallation possible depuis Paramètres > Applications.

[Setup]
AppId={{3A5B7D9E-1F20-4C6A-8B3D-5E7F9A1C2B4D}
AppName=IA VOCAL
AppVersion=1.0
AppPublisher=Rixx
DefaultDirName={localappdata}\Programs\IA-VOCAL
DefaultGroupName=IA VOCAL
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=IA-VOCAL-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=IA VOCAL
UninstallDisplayIcon={app}\IA-VOCAL.exe

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "bureau"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"

[Files]
Source: "dist\IA-VOCAL.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\IA VOCAL"; Filename: "{app}\IA-VOCAL.exe"
Name: "{group}\Désinstaller IA VOCAL"; Filename: "{uninstallexe}"
Name: "{autodesktop}\IA VOCAL"; Filename: "{app}\IA-VOCAL.exe"; Tasks: bureau

[Run]
Filename: "{app}\IA-VOCAL.exe"; Description: "Lancer IA VOCAL"; Flags: nowait postinstall skipifsilent
