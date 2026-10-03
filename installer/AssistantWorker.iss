; ============================================================
;  Assistant Worker — Inno Setup Installer Script
;  Build:  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\AssistantWorker.iss
;  Output: installer\Output\AssistantWorker-Setup-1.0.0.exe
; ============================================================

#define AppName        "Assistant Worker"
#define AppVersion     "1.0.0"
#define AppPublisher   "Surag"
#define AppExeName     "AssistantWorker.exe"
#define AppId          "{{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}"
; Source: the PyInstaller onedir output
#define SourceDir      "..\dist\AssistantWorker"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL=https://github.com/surag
AppSupportURL=https://github.com/surag
AppUpdatesURL=https://github.com/surag
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
LicenseFile=
; No admin required — installs per-user into %LOCALAPPDATA%\Programs
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=Output
OutputBaseFilename=AssistantWorker-Setup-{#AppVersion}
SetupIconFile=..\config\assistant_worker.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Minimum Windows 10
MinVersion=10.0
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
ShowLanguageDialog=no
CloseApplications=yes
CloseApplicationsFilter=*.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";   Description: "Create a &desktop shortcut";   GroupDescription: "Additional icons:"; Flags: unchecked
Name: "launchafter";   Description: "&Launch Assistant Worker after installation"; GroupDescription: "After installation:"; Flags: unchecked

[Files]
; Copy the entire PyInstaller onedir output
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\config\assistant_worker.ico"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
; Desktop (optional)
Name: "{commondesktop}\{#AppName}";   Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\config\assistant_worker.ico"; Tasks: desktopicon

[Run]
; Optional: launch after install
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent; Tasks: launchafter

[UninstallRun]
; Kill the process if running before uninstall
Filename: "taskkill.exe"; Parameters: "/f /im {#AppExeName}"; Flags: runhidden; RunOnceId: "KillApp"

[UninstallDelete]
; Remove compiled Python cache that accumulates at runtime — NOT user data
Type: filesandordirs; Name: "{app}\__pycache__"
Type: filesandordirs; Name: "{app}\actions\__pycache__"
Type: filesandordirs; Name: "{app}\core\__pycache__"
Type: filesandordirs; Name: "{app}\plugins\__pycache__"
; NOTE: User data in %LOCALAPPDATA%\AssistantWorker\ is intentionally
; NOT deleted here.  The user keeps their settings, reminders and memory.

[Code]
// Optionally offer to remove user data on uninstall
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserDataDir: String;
  Response:    Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    UserDataDir := ExpandConstant('{localappdata}') + '\AssistantWorker';
    if DirExists(UserDataDir) then
    begin
      Response := MsgBox(
        'Do you also want to remove your personal Assistant Worker data?' + #13#10 +
        '(settings, reminders, memory, and history)' + #13#10#13#10 +
        UserDataDir,
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2
      );
      if Response = IDYES then
        DelTree(UserDataDir, True, True, True);
    end;
  end;
end;
