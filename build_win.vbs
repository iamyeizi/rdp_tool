' build_win.vbs - Construye EXE con icono usando PyInstaller (no instala el app)
' Ejecutar con doble click en Windows

Option Explicit
Dim fso, shell, cwd, pyExe, cmd, result, hasPip, venvDir
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
cwd = fso.GetAbsolutePathName(".")
venvDir = cwd & "\venv"

Sub Echo(msg)
  WScript.Echo msg
End Sub

Function FileExists(path)
  FileExists = fso.FileExists(path)
End Function

Function DirExists(path)
  DirExists = fso.FolderExists(path)
End Function

Function Which(prog)
  On Error Resume Next
  Dim e
  e = shell.Run("cmd /c where " & prog & " >nul 2>nul", 0, True)
  If e = 0 Then
    Which = True
  Else
    Which = False
  End If
End Function

' 1) Encontrar Python
If Which("python.exe") Then
  pyExe = "python"
ElseIf Which("py.exe") Then
  pyExe = "py -3"
Else
  Echo "No se encontró Python. Instalá Python 3 y agregalo al PATH."
  WScript.Quit 1
End If

' 2) Crear venv local
If Not DirExists(venvDir) Then
  Echo "Creando entorno virtual..."
  result = shell.Run("cmd /c " & pyExe & " -m venv venv", 1, True)
  If result <> 0 Then
    Echo "No se pudo crear venv (" & result & ")"
    WScript.Quit result
  End If
End If

Dim pipCmd
pipCmd = """" & venvDir & "\Scripts\python.exe"" -m pip"

' 3) Actualizar pip y deps
Echo "Actualizando pip..."
shell.Run "cmd /c " & pipCmd & " install --upgrade pip setuptools wheel", 1, True

If FileExists(cwd & "\requirements.txt") Then
  Echo "Instalando requirements..."
  result = shell.Run("cmd /c " & pipCmd & " install -r requirements.txt", 1, True)
  If result <> 0 Then
    Echo "Fallo instalando requirements (" & result & ")"
    WScript.Quit result
  End If
End If

' 4) Instalar PyInstaller si hace falta
Echo "Instalando PyInstaller..."
shell.Run "cmd /c " & pipCmd & " install pyinstaller", 1, True

' 5) Construir EXE con icono y datos
Dim iconPath, addData, pyiCmd
iconPath = cwd & "\utils\app.ico"
If Not FileExists(iconPath) Then
  Echo "Advertencia: utils\\app.ico no existe, el EXE no tendrá icono personalizado."
End If

' Incluir archivos de datos necesarios
addData = " --add-data ""credential.json;."" --add-data ""utils\template.rdp;utils"" --add-data ""utils\app.ico;utils"" --add-data ""utils\app.png;utils"""

pyiCmd = """" & venvDir & "\Scripts\pyinstaller.exe"" --noconfirm --onefile --windowed" _
  & IIf(FileExists(iconPath), " --icon """ & iconPath & """", "") _
  & addData _
  & " main.py"

Echo "Construyendo EXE..."
result = shell.Run("cmd /c " & pyiCmd, 1, True)
If result <> 0 Then
  Echo "Fallo PyInstaller (" & result & ")"
  WScript.Quit result
End If

Echo "Listo. EXE generado en dist\\main.exe"
Echo "Podés crear un acceso directo a dist\\main.exe y fijarlo a la barra."

' 6) Limpiar launcher.vbs si existe
If FileExists(cwd & "\launcher.vbs") Then
  On Error Resume Next
  fso.DeleteFile cwd & "\launcher.vbs", True
End If

WScript.Quit 0
