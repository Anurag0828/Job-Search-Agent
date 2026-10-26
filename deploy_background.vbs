Set objShell = CreateObject("WScript.Shell")
' Run the python script silently without opening a command prompt window
objShell.Run "cmd /c .\venv\Scripts\python.exe -m scheduler.continuous_runner > scheduler_log.txt 2>&1", 0, False
