param([string]$RepositoryUrl='https://github.com/maneci20221213-coder/bakuri')
$ErrorActionPreference='Stop'
Set-Location $PSScriptRoot
if ($RepositoryUrl -notmatch '^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?$') { throw 'Use a public GitHub repository URL.' }
$RepositoryUrl=$RepositoryUrl.TrimEnd('/')
$Version=[regex]::Match((Get-Content 'version.py' -Raw),'VERSION\s*=\s*"([^"]+)"').Groups[1].Value
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid app version.' }
function RunChecked([scriptblock]$Command) { & $Command; if ($LASTEXITCODE -ne 0) { throw "Command failed: $Command" } }
if (-not (Test-Path '.release-venv\Scripts\python.exe')) { RunChecked { py -3.12 -m venv .release-venv } }
$Python=Join-Path $PSScriptRoot '.release-venv\Scripts\python.exe'
RunChecked { & $Python -m pip install -r requirements.txt pyinstaller==6.16.0 }
RunChecked { & $Python build_metadata.py }
RunChecked { & $Python -m PyInstaller --noconfirm --clean --noupx --windowed --onedir --name BakuriFileConverter --icon assets/app.ico --version-file version-resource.txt --add-data 'assets;assets' --add-data 'USER-GUIDE.md;.' --add-data 'PATCH-NOTES.md;.' --add-data 'LICENSES;LICENSES' --add-data 'LICENSE-AGPL-3.0.txt;.' --add-data 'README.md;.' --add-binary 'FilePathCheckerModuleExample.dll;.' --hidden-import win32timezone --hidden-import win32com.shell.shell --exclude-module PIL.AvifImagePlugin --exclude-module PIL._avif --collect-submodules pynput --collect-all velopack app.py }
$PackDir=Join-Path $PSScriptRoot 'dist\BakuriFileConverter'
@{source='github';url=$RepositoryUrl;channel='stable'} | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $PackDir 'update-config.json')
Copy-Item 'LICENSES' (Join-Path $PackDir 'LICENSES') -Recurse -Force
Copy-Item 'LICENSE-AGPL-3.0.txt','README.md','requirements.txt' $PackDir -Force
# Include unmodified upstream wheel notices (PyInstaller normally omits dist-info).
$NoticeDir=Join-Path $PackDir 'third-party-notices'
New-Item -ItemType Directory -Path $NoticeDir -Force | Out-Null
Get-ChildItem '.release-venv\Lib\site-packages' -Directory -Filter '*.dist-info' | ForEach-Object {
 $Destination=Join-Path $NoticeDir $_.Name
 New-Item -ItemType Directory -Path $Destination -Force | Out-Null
 Get-ChildItem $_.FullName -Recurse -File | Where-Object { $_.Name -match '^(LICENSE|COPYING|NOTICE|AUTHORS)' -or $_.FullName -match '[\\/]licenses[\\/]' } | ForEach-Object {
  $Relative=$_.FullName.Substring((Join-Path $PSScriptRoot '.release-venv\Lib\site-packages').Length+1)
  $Target=Join-Path $NoticeDir $Relative
  New-Item -ItemType Directory -Path (Split-Path $Target) -Force | Out-Null
  Copy-Item $_.FullName $Target -Force
 }
}
# Verify the frozen executable reaches its IPC server, after Qt and Window
# initialization. Background mode avoids network checks; disable shell hooks.
$PreviousIntegration=$env:BAKURI_DISABLE_SHELL_INTEGRATION
$env:BAKURI_DISABLE_SHELL_INTEGRATION='1'
$Smoke=Start-Process (Join-Path $PackDir 'BakuriFileConverter.exe') -ArgumentList '--background' -PassThru
try {
 $Ready=$false
 for ($Attempt=0; $Attempt -lt 15; $Attempt++) {
  & $Python -c "from PySide6.QtCore import QCoreApplication; from PySide6.QtNetwork import QLocalSocket; app=QCoreApplication([]); s=QLocalSocket(); s.connectToServer('BakuriPythonTrial'); raise SystemExit(0 if s.waitForConnected(1000) else 1)"
  if ($LASTEXITCODE -eq 0) { $Ready=$true; break }
  if ($Smoke.HasExited) { break }
  Start-Sleep -Milliseconds 500
 }
 if (-not $Ready) { throw 'Frozen executable did not reach the application IPC server.' }
 Write-Host 'Frozen executable startup smoke check passed.'
} finally {
 if (-not $Smoke.HasExited) { & taskkill /PID $Smoke.Id /T /F | Out-Null }
 $env:BAKURI_DISABLE_SHELL_INTEGRATION=$PreviousIntegration
}
if (-not (Test-Path '.vpk-tools\vpk.exe')) { RunChecked { dotnet tool install vpk --version 1.2.161 --tool-path .vpk-tools } }
RunChecked { & '.\.vpk-tools\vpk.exe' pack --packId Bakuri.FileConverter --packVersion $Version --packDir $PackDir --mainExe BakuriFileConverter.exe --runtime win-x64 --channel stable --shortcuts StartMenuRoot --packTitle '바꾸리' --icon assets/app.ico --releaseNotes RELEASE-NOTES.md --outputDir '.\Releases' }
$Setups=@(Get-ChildItem 'Releases' -File -Filter '*Setup.exe')
if ($Setups.Count -ne 1) { throw 'Expected exactly one generated Setup.exe.' }
# Windows includes .NET Framework: no new runtime is bundled for this small UI.
$Compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
RunChecked { & $Compiler /nologo /target:winexe /optimize+ /platform:anycpu /codepage:65001 /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /win32icon:assets/app.ico "/resource:$($Setups[0].FullName),Bakuri.Setup" /out:Releases\BakuriSetup.exe installer.cs }
RunChecked { & $Compiler /nologo /target:exe /optimize+ /codepage:65001 /main:VerifyInstaller /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Core.dll /out:verify-installer.exe installer.cs verify_installer.cs }
RunChecked { & '.\verify-installer.exe' }
& (Join-Path $PSScriptRoot 'verify_installation.ps1') -Setup (Join-Path $PSScriptRoot 'Releases\BakuriSetup.exe')
# Only expose the installer that offers the shortcut choice.
Remove-Item $Setups[0].FullName
if (-not (Test-Path 'Releases\releases.stable.json')) { throw 'Missing stable update feed.' }
if (-not (Get-ChildItem 'Releases' -Filter '*-full.nupkg')) { throw 'Missing full update package.' }
RunChecked { & $Python prepare_source.py }
Copy-Item "SourcePackages\Bakuri-Source-v$Version.zip" 'Releases' -Force
Get-ChildItem 'Releases' -File | Where-Object Name -ne 'SHA256SUMS.txt' | Sort-Object Name | ForEach-Object { "$((Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower())  $($_.Name)" } | Set-Content -Encoding UTF8 'Releases\SHA256SUMS.txt'
Write-Host "Prepared v$Version in Releases. App update source: $RepositoryUrl"
