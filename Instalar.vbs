' Abre la ventana de instalacion, sin consola.
' Instalar.bat sigue siendo el respaldo si esta ventana no arranca.
' ASCII: el host de scripts de Windows no lee UTF-8.

Option Explicit

Dim shell, fso, carpeta, ps1, comando

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
carpeta = fso.GetParentFolderName(WScript.ScriptFullName)
ps1 = carpeta & "\scripts\instalador_ventana.ps1"

If Not fso.FileExists(ps1) Then
  MsgBox "No se encuentra la ventana de instalacion." & vbCrLf & vbCrLf & "Usa Instalar.bat, en la misma carpeta.", vbCritical, "Drako Cam"
  WScript.Quit 1
End If

comando = "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1 & """"
shell.Run comando, 0, False
