' Run a console command with no visible window, and still report its exit code.
'
' The hourly backup task runs Git Bash, which is a console program: Task Scheduler
' pops a black window on the desktop every single hour while you are logged in.
' Routing it through wscript.exe fixes that without hiding the failure signal.
'
' Usage: wscript.exe //nologo run-hidden.vbs "<exe>" "<arg>" "<arg>" ...
'
' Waits for the command and exits with its code, so the task's LastTaskResult
' still tells you whether the backup worked. Do not switch this to a
' fire-and-forget call: it would report success forever.

Set shell = CreateObject("WScript.Shell")

If WScript.Arguments.Count = 0 Then
  WScript.Quit 2
End If

cmd = ""
For i = 0 To WScript.Arguments.Count - 1
  cmd = cmd & """" & WScript.Arguments(i) & """ "
Next

' 0 = hidden window, True = wait for it to finish
WScript.Quit shell.Run(cmd, 0, True)
