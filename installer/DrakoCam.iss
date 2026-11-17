; Instalador ligero de Drako Cam.
; Copia el programa y, al terminar, ejecuta Instalar.bat
; (uv, Python 3.12, FFmpeg 7.1.1, componentes y accesos directos).
; Compilar con Inno Setup 6.7: ISCC.exe /DAppVersion=0.1.0 DrakoCam.iss

#ifndef AppVersion
#define AppVersion "0.1.0"
#endif
#define AppVersionQuad AppVersion + ".0"

[Setup]
AppId={{8F4E2C1A-6B37-4D9E-A15C-2E7F9B0D4C83}}
AppName=Drako Cam
AppVersion={#AppVersion}
AppVerName=Drako Cam {#AppVersion}
AppPublisher=Drako
AppCopyright=Copyright (C) 2026 Drako
VersionInfoVersion={#AppVersionQuad}
VersionInfoProductName=Drako Cam
VersionInfoDescription=Instalador de Drako Cam
DefaultDirName={localappdata}\Drako Cam
DefaultGroupName=Drako Cam
DisableProgramGroupPage=yes
DisableReadyPage=no
OutputDir=..\dist
OutputBaseFilename=DrakoCam-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=logo.ico
UninstallDisplayIcon={app}\installer\logo.ico
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
SetupLogging=yes
ShowLanguageDialog=no
UninstallDisplayName=Drako Cam
LicenseFile=..\LICENSE
InfoBeforeFile=info-antes.txt
InfoAfterFile=info-despues.txt

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
; Carpetas que el programa necesita para arrancar. Sin .git, pruebas,
; secretos ni pesos de modelo (se descargan en el primer arranque).
Source: "..\app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo,*.log,*.onnx,*.pth,*.safetensors,*.engine,*.ckpt,*.dfm,*.trt,*.pb,*.npy,*.bin,*.onnx.data"
Source: "..\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\scripts\*"; DestDir: "{app}\scripts"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo"
Source: "..\tools\*"; DestDir: "{app}\tools"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*,*.pyc,*.pyo,*.onnx,*.pth,*.safetensors,*.engine,*.ckpt,*.dfm,*.trt,*.pb,*.npy,*.bin"
Source: "..\model_assets\*"; DestDir: "{app}\model_assets"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.onnx,*.pth,*.safetensors,*.engine,*.ckpt,*.dfm,*.trt,*.pb,*.npy,*.bin,*.onnx.data"
Source: "..\installer\*"; DestDir: "{app}\installer"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dependencies\.gitkeep"; DestDir: "{app}\dependencies"; Flags: ignoreversion
Source: "..\Instalar.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Desinstalar.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Start.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Start_mac.sh"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\main.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\DrakoCam.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\integridad_manifiesto.json"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\launcher.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\download_models.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\requirements_cu13.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\requirements_mac.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\pyproject.toml"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\version.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\NOTICE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Step by step guide to install Conda and Visomaster for RTX 50xx series.pdf"; DestDir: "{app}"; Flags: ignoreversion
Source: "wizard-logo.bmp"; Flags: dontcopy

[Icons]
Name: "{autodesktop}\Drako Cam"; Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: """{app}\main.py"""; WorkingDir: "{app}"; IconFilename: "{app}\installer\logo.ico"; Comment: "Abrir Drako Cam"
Name: "{autoprograms}\Drako Cam"; Filename: "{app}\.venv\Scripts\pythonw.exe"; Parameters: """{app}\main.py"""; WorkingDir: "{app}"; IconFilename: "{app}\installer\logo.ico"; Comment: "Abrir Drako Cam"

[Run]
Filename: "{app}\Instalar.bat"; Parameters: "-DesdeInstalador"; WorkingDir: "{app}"; StatusMsg: "Preparando Python, FFmpeg y los componentes. Puede tardar mucho. No cierres la ventana negra."; Flags: waituntilterminated

[UninstallRun]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\desinstalar.ps1"" -Silencioso"; WorkingDir: "{app}"; Flags: waituntilterminated

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\dependencies\ffmpeg"
Type: filesandordirs; Name: "{app}\logs"

[Registry]
; GpuPreference=2 pide la GPU de alto rendimiento (NVIDIA dedicada).
; Python no puede exportar NvOptimusEnablement; Windows lee esta clave.
Root: HKCU; Subkey: "Software\Microsoft\DirectX\UserGpuPreferences"; ValueType: string; ValueName: "{app}\.venv\Scripts\python.exe"; ValueData: "GpuPreference=2;"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\DirectX\UserGpuPreferences"; ValueType: string; ValueName: "{app}\.venv\Scripts\pythonw.exe"; ValueData: "GpuPreference=2;"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\DirectX\UserGpuPreferences"; ValueType: string; ValueName: "{app}\main.py"; ValueData: "GpuPreference=2;"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Microsoft\DirectX\UserGpuPreferences"; ValueType: string; ValueName: "{app}\DrakoCam.exe"; ValueData: "GpuPreference=2;"; Flags: uninsdeletevalue

[Code]
procedure InitializeWizard;
var
  Logo: TBitmapImage;
begin
  ExtractTemporaryFile('wizard-logo.bmp');
  Logo := TBitmapImage.Create(WizardForm);
  Logo.Parent := WizardForm;
  Logo.Bitmap.LoadFromFile(ExpandConstant('{tmp}\wizard-logo.bmp'));
  Logo.Stretch := True;
  Logo.Width := 72;
  Logo.Height := 72;
  Logo.Left := ScaleX(16);
  Logo.Top := ScaleY(8);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Datos: String;
begin
  if CurUninstallStep <> usUninstall then
    Exit;
  if UninstallSilent then
    Exit;
  Datos := ExpandConstant('{userappdata}\DrakoCam');
  if not DirExists(Datos) then
    Exit;
  if MsgBox('¿Borrar también la configuración, la contraseña y los registros de Drako Cam?' + #13#10 + #13#10 +
            'Si eliges No, se conservan en:' + #13#10 + Datos, mbConfirmation, MB_YESNO) = IDYES then
  begin
    if not DelTree(Datos, True, True, True) then
      MsgBox('No se pudieron borrar todos los datos. Cierra Drako Cam y borra esta carpeta a mano:' + #13#10 + Datos, mbError, MB_OK);
  end;
end;
