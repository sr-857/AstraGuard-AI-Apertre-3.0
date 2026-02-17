@echo off
cd /d "c:\Open Source Project\AstraGuard-AI-Apertre-3.0"
set GIT_EDITOR=true
set GIT_SEQUENCE_EDITOR=true
git rebase --continue
echo Rebase completed with exit code: %ERRORLEVEL%
