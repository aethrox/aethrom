@echo off
%1 -c "import sys" >nul 2>&1
if not errorlevel 1 exit /b 0
echo {"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"Memory engine warning: the configured Python interpreter is not running. Run the doctor skill."}}
