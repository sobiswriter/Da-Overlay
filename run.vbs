Set WshShell = CreateObject("WScript.Shell")
Set FileSystem = CreateObject("Scripting.FileSystemObject")
WshShell.CurrentDirectory = FileSystem.GetParentFolderName(WScript.ScriptFullName)
If FileSystem.FileExists(".venv\Scripts\pythonw.exe") Then
    WshShell.Run """.venv\Scripts\pythonw.exe"" ""main.py""", 0, False
Else
    WshShell.Run """run.bat""", 1, False
End If
Set WshShell = Nothing
