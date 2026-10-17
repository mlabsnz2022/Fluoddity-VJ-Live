@echo off
title Push Fluoddity-VJ-Live to GitHub
echo ============================================================
echo Pushing Fluoddity-VJ-Live to your GitHub fork:
echo https://github.com/mlabsnz2022/Fluoddity-VJ-Live
echo ============================================================
echo.
echo If a browser window pops up, click "Authorize" or sign in.
echo.
git push -u origin dist
git push -u origin live-performance
echo.
echo ============================================================
echo Push complete! Check https://github.com/mlabsnz2022/Fluoddity-VJ-Live
echo ============================================================
pause
