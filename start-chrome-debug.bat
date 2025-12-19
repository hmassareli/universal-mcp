@echo off
setlocal

REM Mata o Chrome se estiver rodando
taskkill /F /IM chrome.exe /T 2>nul
timeout /t 2 /nobreak >nul

REM Copia os dados de login do Chrome para a pasta de debug
set "USER_DATA=%LOCALAPPDATA%\Google\Chrome\User Data"
set "SRC=%USER_DATA%\Default"
set "DST=%TEMP%\chrome-debug-profile\Default"

if not exist "%DST%" mkdir "%DST%"

echo Copiando perfil...

REM IMPORTANTE: Copiar Local State que contem a chave de criptografia dos cookies
copy /Y "%USER_DATA%\Local State" "%TEMP%\chrome-debug-profile\" 2>nul

REM Copiar arquivos do Default
copy /Y "%SRC%\Cookies" "%DST%\" 2>nul
copy /Y "%SRC%\Cookies-journal" "%DST%\" 2>nul
copy /Y "%SRC%\Login Data" "%DST%\" 2>nul
copy /Y "%SRC%\Login Data-journal" "%DST%\" 2>nul
copy /Y "%SRC%\Preferences" "%DST%\" 2>nul
copy /Y "%SRC%\Secure Preferences" "%DST%\" 2>nul
copy /Y "%SRC%\Web Data" "%DST%\" 2>nul
copy /Y "%SRC%\Web Data-journal" "%DST%\" 2>nul
echo Perfil copiado!

echo Iniciando Chrome...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%TEMP%\chrome-debug-profile" --remote-allow-origins=* "https://google.com"

timeout /t 5 /nobreak >nul
netstat -ano | findstr "9222"
