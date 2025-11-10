; Inno Setup Script for VideoCutter
; Build the app first with PyInstaller (onedir):
;   pyinstaller --noconfirm --windowed --onedir --name VideoCutter \
;     video_cutter_gui.py --collect-all PySide6 \
;     --hidden-import PySide6.QtMultimedia --hidden-import PySide6.QtMultimediaWidgets \
;     --add-binary ".\vendors\ffmpeg\bin\ffmpeg.exe;." 
; Then compile this installer with Inno Setup (ISCC).

#define MyAppId "A2C4E2A5-6B1F-4E0A-9B7E-8D6E6C11F9C1"
#define MyAppName "VideoCutter"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "VideoCutter"
#define MyAppURL "https://example.com/videocutter"
#define MyAppExeName "VideoCutter.exe"

; Adjust these paths as needed. This script assumes you run ISCC from the project root.
#define DistDir "..\\dist\\VideoCutter"
#define SetupIcon ".\\assets\\app.ico"
#define VC_Redist "..\\vendors\\VC_redist.x64.exe"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={pf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=no
OutputBaseFilename=VideoCutter-Setup-{#MyAppVersion}
OutputDir=..\dist\installer
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern
PrivilegesRequired=admin
DisableReadyMemo=yes
; Optional setup icon if available
SetupIconFile={#SetupIcon}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear icono en el escritorio"; GroupDescription: "Tareas adicionales:"; Flags: unchecked

[Files]
; Main application files from PyInstaller onedir output
Source: "{#DistDir}\\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

; Optionally include VC++ Redistributable and run it silently. If the file doesn't exist, it's skipped at compile time.
Source: "{#VC_Redist}"; DestDir: "{tmp}"; Flags: deleteafterinstall skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Launch app after install (optional)
; Filename: "{app}\\{#MyAppExeName}"; Description: "Iniciar {#MyAppName}"; Flags: nowait postinstall skipifsilent

; Install VC++ Redist if bundled (optional)
Filename: "{tmp}\\VC_redist.x64.exe"; Parameters: "/install /quiet /norestart"; Flags: waituntilterminated; \
  StatusMsg: "Instalando Microsoft Visual C++ Redistributable..."; \
  Check: FileExists(ExpandConstant('{tmp}\\VC_redist.x64.exe'))

[UninstallDelete]
; No special uninstall deletions; the app directory is removed automatically.

