' Abre Drako Cam sin ventana de consola.
' Lo usa el acceso directo del escritorio y del menu Inicio.
' El archivo va en ASCII: el host de scripts de Windows no lee UTF-8.
' Los acentos del cuadro de error se arman con ChrW.

Option Explicit

Dim shell, fso, carpeta, compilado, pythonw, ffmpegBin, codigo, entorno

If WScript.Arguments.Count > 0 Then
  If WScript.Arguments(0) = "--comprobar" Then
    WScript.Echo "Arrancar.vbs listo"
    WScript.Quit 0
  End If
End If

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
carpeta = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))
compilado = carpeta & "\DrakoCam.exe"
pythonw = carpeta & "\.venv\Scripts\pythonw.exe"

If fso.FileExists(compilado) Then
  shell.CurrentDirectory = carpeta
  ffmpegBin = carpeta & "\dependencies\ffmpeg\ffmpeg-7.1.1-essentials_build\bin"
  If fso.FileExists(ffmpegBin & "\ffmpeg.exe") Then
    Set entorno = shell.Environment("PROCESS")
    entorno("PATH") = ffmpegBin & ";" & entorno("PATH")
  End If
  codigo = shell.Run("""" & compilado & """", 1, True)
  If codigo <> 0 Then
    MsgBox "Drako Cam se ha cerrado con un error (c" & ChrW(243) & "digo " & codigo & ")." & vbCrLf & vbCrLf & "El registro est" & ChrW(225) & " en:" & vbCrLf & shell.ExpandEnvironmentStrings("%APPDATA%") & "\DrakoCam\logs", vbExclamation, "Drako Cam"
  End If
  WScript.Quit codigo
End If

If Not fso.FileExists(pythonw) Then
  MsgBox "No se encuentra Drako Cam en esta carpeta:" & vbCrLf & vbCrLf & carpeta & vbCrLf & vbCrLf & "Vuelve a ejecutar Instalar.bat.", vbCritical, "Drako Cam"
  WScript.Quit 1
End If

ffmpegBin = carpeta & "\dependencies\ffmpeg\ffmpeg-7.1.1-essentials_build\bin"
shell.CurrentDirectory = carpeta
If fso.FileExists(ffmpegBin & "\ffmpeg.exe") Then
  Set entorno = shell.Environment("PROCESS")
  entorno("PATH") = ffmpegBin & ";" & entorno("PATH")
End If

codigo = shell.Run("""" & pythonw & """ """ & carpeta & "\main.py""", 1, True)
If codigo <> 0 Then
  MsgBox "Drako Cam se ha cerrado con un error (c" & ChrW(243) & "digo " & codigo & ")." & vbCrLf & vbCrLf & "El registro est" & ChrW(225) & " en:" & vbCrLf & shell.ExpandEnvironmentStrings("%APPDATA%") & "\DrakoCam\logs", vbExclamation, "Drako Cam"
End If
