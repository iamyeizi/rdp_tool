Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
Set oShell = CreateObject("WScript.Shell")

' Rutas
currentFolder = fso.GetParentFolderName(WScript.ScriptFullName)
venvMarker = currentFolder & "\.venv_ok"
agentScript = currentFolder & "\itool.py"
requirements = currentFolder & "\requirements.txt"

' Instalar dependencias si no están
If Not fso.FileExists(venvMarker) Then
    MsgBox "Instalando dependencias, por favor espere...", 64, "Itool"
    cmd = "cmd /c cd /d """ & currentFolder & """ && python -m pip install --upgrade pip && python -m pip install -r requirements.txt && echo ok > .venv_ok"
    WshShell.Run cmd, 1, True
End If

' Cerrar itool.py si ya esta corriendo
Set objWMI = GetObject("winmgmts:\\.\root\cimv2")
Set procesos = objWMI.ExecQuery("SELECT * FROM Win32_Process WHERE Name = 'python.exe'")

For Each proceso In procesos
    If InStr(LCase(proceso.CommandLine), "itool.py") > 0 Then
        proceso.Terminate()
    End If
Next

' Mostrar notificación
oShell.Popup "Iniciando programa...", 3, "Itool", 64

' Ejecutar el programa sin mostrar consola (0 = oculto)
WshShell.Run "python """ & agentScript & """", 0, False
