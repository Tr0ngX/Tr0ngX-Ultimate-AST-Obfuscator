@echo off
rem Tr0ngX Ultimate AST Obfuscator - one-shot launcher (no cd needed)
rem Usage: Tr0ngX.bat [flags]        (no flags = interactive TUI)
python "%~dp0main.py" %*
exit /b %ERRORLEVEL%
