; pywinhello Inno Setup Script
; Build with: iscc pywinhello.iss

[Setup]
AppName=pywinhello
AppVersion=1.0.0
AppPublisher=obichan117
AppPublisherURL=https://github.com/obichan117/pywinhello
DefaultDirName={localappdata}\pywinhello
DefaultGroupName=pywinhello
OutputBaseFilename=pywinhello_setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
; TODO: SetupIconFile=assets\pywinhello.ico

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\dist\pywinhello-monitor.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\pywinhello.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\firmware\build\*.uf2"; DestDir: "{app}\firmware"; Flags: ignoreversion

[Icons]
Name: "{group}\pywinhello"; Filename: "{app}\pywinhello.exe"
Name: "{group}\Uninstall pywinhello"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\pywinhello.exe"; Description: "pywinhelloを起動"; Flags: postinstall nowait skipifsilent

[Registry]
; Add monitor to Windows Startup
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "pywinhello"; \
    ValueData: """{app}\pywinhello-monitor.exe"""; \
    Flags: uninsdeletevalue

[UninstallRun]
; Clean up Task Scheduler tasks on uninstall
Filename: "schtasks.exe"; Parameters: "/delete /tn pywinhello-wake /f"; Flags: runhidden; RunOnceId: "DelTask"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
