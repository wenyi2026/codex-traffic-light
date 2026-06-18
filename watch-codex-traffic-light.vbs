Option Explicit

Dim shell, fso, root, exePath
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

root = fso.GetParentFolderName(WScript.ScriptFullName)
exePath = fso.BuildPath(root, "dist\CodexTrafficLight.exe")

shell.Run """" & exePath & """", 0, False
