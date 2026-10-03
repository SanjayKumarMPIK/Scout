; Inno Setup script for Scout.
; Built automatically by installer\build.ps1, which passes /DAppVersion=x.y.z

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#define AppName "Scout"
#define AppExe  "scout.exe"

[Setup]
AppId={{8F3A6C2E-5B7D-4E19-9C4A-2D61B7E0F5A3}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Scout
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Install per-user by default (no admin prompt); user can choose all-users.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist\installer
OutputBaseFilename=ScoutSetup-{#AppVersion}
SetupIconFile=scout.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ChangesEnvironment=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "addtopath";   Description: "Add Scout to PATH (type 'scout' in any terminal)"; GroupDescription: "Options:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Options:"; Flags: unchecked

[Files]
Source: "..\dist\scout\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}";           Filename: "{app}\{#AppExe}"; WorkingDir: "{%USERPROFILE}"
Name: "{autoprograms}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";            Filename: "{app}\{#AppExe}"; WorkingDir: "{%USERPROFILE}"; Tasks: desktopicon

[Registry]
; Append install dir to the *user* PATH.
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; \
  ValueData: "{olddata};{app}"; Check: NeedsAddPath(ExpandConstant('{app}')); Tasks: addtopath

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch Scout now"; WorkingDir: "{%USERPROFILE}"; \
  Flags: nowait postinstall skipifsilent

[Code]
const
  EnvKey = 'Environment';

function NeedsAddPath(Dir: string): Boolean;
var
  Paths: string;
begin
  if not RegQueryStringValue(HKCU, EnvKey, 'Path', Paths) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Uppercase(Dir) + ';', ';' + Uppercase(Paths) + ';') = 0;
end;

procedure RemoveFromPath(Dir: string);
var
  Paths: string;
begin
  if RegQueryStringValue(HKCU, EnvKey, 'Path', Paths) then
  begin
    StringChangeEx(Paths, ';' + Dir, '', True);
    StringChangeEx(Paths, Dir + ';', '', True);
    StringChangeEx(Paths, Dir, '', True);
    RegWriteExpandStringValue(HKCU, EnvKey, 'Path', Paths);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: string;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    RemoveFromPath(ExpandConstant('{app}'));

    // User data (memories, config, screenshots) lives in %USERPROFILE%\.scout
    // and is kept by default so reinstalling doesn't wipe it.
    DataDir := ExpandConstant('{%USERPROFILE}\.scout');
    if DirExists(DataDir) and (not UninstallSilent) then
      if MsgBox('Also delete your Scout data (memories, settings, screenshots)?' + #13#10 +
                DataDir + #13#10#13#10 +
                'API keys stored in Windows Credential Manager are not affected.',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;
