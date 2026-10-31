@echo off
rem Runs one paper-trading check and appends the output to logs\paper.log
rem Usage: run_paper.bat daily   or   run_paper.bat hourly
cd /d "%~dp0"
if not exist logs mkdir logs
python paper_trade.py %1 >> logs\paper.log 2>&1
