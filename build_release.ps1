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
RunChecked { & $Python -m PyInstaller --noconfirm --clean --noupx --windowed --onedir --name BakuriFileConverter --icon assets/app.ico --version-file version-resource.txt --add-data 'assets;assets' --add-data 'LICENSES;LICENSES' --add-data 'LICENSE-AGPL-3.0.txt;.' --add-data 'README.md;.' --add-binary 'FilePathCheckerModuleExample.dll;.' --hidden-import win32timezone --hidden-import win32com.shell.shell --collect-submodules pynput --collect-all velopack app.py }
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
if (-not (Test-Path '.vpk-tools\vpk.exe')) { RunChecked { dotnet tool install vpk --version 1.2.161 --tool-path .vpk-tools } }
RunChecked { & '.\.vpk-tools\vpk.exe' pack --packId Bakuri.FileConverter --packVersion $Version --packDir $PackDir --mainExe BakuriFileConverter.exe --channel stable --packTitle '바꾸리' --icon assets/app.ico --releaseNotes RELEASE-NOTES.md --outputDir '.\Releases' }
$Setups=@(Get-ChildItem 'Releases' -File -Filter '*Setup.exe')
if ($Setups.Count -ne 1) { throw 'Expected exactly one generated Setup.exe.' }
Copy-Item $Setups[0].FullName 'Releases\BakuriSetup.exe' -Force
if (-not (Test-Path 'Releases\releases.stable.json')) { throw 'Missing stable update feed.' }
if (-not (Get-ChildItem 'Releases' -Filter '*-full.nupkg')) { throw 'Missing full update package.' }
RunChecked { & $Python prepare_source.py }
Copy-Item "SourcePackages\Bakuri-Source-v$Version.zip" 'Releases' -Force
Get-ChildItem 'Releases' -File | Where-Object Name -ne 'SHA256SUMS.txt' | Sort-Object Name | ForEach-Object { "$((Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower())  $($_.Name)" } | Set-Content -Encoding UTF8 'Releases\SHA256SUMS.txt'
Write-Host "Prepared v$Version in Releases. App update source: $RepositoryUrl"
