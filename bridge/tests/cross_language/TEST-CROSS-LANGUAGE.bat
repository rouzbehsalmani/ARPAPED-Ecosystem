@echo off
setlocal
cd /d "%~dp0\..\..\.."

echo ARPAPED Cross-Language Bridge Test
echo =================================
echo.

python bridge\tests\cross_language\test_python_bridge_rust_capability.py
if errorlevel 1 goto :fail

python bridge\tests\cross_language\test_rust_bridge_python_capability.py
if errorlevel 1 goto :fail

echo.
echo =================================
echo ALL CROSS-LANGUAGE TESTS PASSED
echo =================================
exit /b 0

:fail
echo.
echo =================================
echo CROSS-LANGUAGE TEST FAILED
echo =================================
exit /b 1
