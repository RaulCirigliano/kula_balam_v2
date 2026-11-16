@echo off
setlocal
cd /d "%~dp0\backtest_lab"
call "%~dp0\backtest_lab\lanzar_lab.bat"
exit /b %ERRORLEVEL%
