# Developer verification on the isolated Windows CI runner, never shipped in the app.
param([Parameter(Mandatory=$true)][string]$Setup)
$ErrorActionPreference='Stop'
$Destination=Join-Path $env:TEMP ('BakuriInstallTest-'+[guid]::NewGuid().ToString('N'))
$Desktop=[Environment]::GetFolderPath('Desktop')
$Link=Join-Path $Desktop '바꾸리.lnk'
if (Test-Path $Link) { throw 'Refusing to modify an existing desktop shortcut during verification.' }
$Child=$null
try {
 $Process=Start-Process $Setup -ArgumentList @('--silent','--installto',('"'+$Destination+'"')) -Wait -PassThru
 if ($Process.ExitCode -ne 0) { throw "Installation failed: $($Process.ExitCode)" }
 $Exe=Join-Path $Destination 'current\BakuriFileConverter.exe'
 if (-not (Test-Path $Exe)) { throw 'Installed executable missing.' }
 if (Test-Path $Link) { throw 'Installer unexpectedly created a desktop shortcut without a choice.' }
 foreach ($Choice in @('1','0')) {
  $Child=Start-Process $Exe -ArgumentList @('--background',"--desktop-shortcut=$Choice") -PassThru
  $Expected=$Choice -eq '1';$Observed=$false
  for ($Attempt=0;$Attempt -lt 30;$Attempt++) {
   Start-Sleep -Milliseconds 500
   if ((Test-Path $Link) -eq $Expected) { $Observed=$true;break }
   if ($Child.HasExited) { break }
  }
  if (-not $Observed) { throw "Desktop shortcut choice $Choice was not applied." }
  if ($Expected) {
   $Shell=New-Object -ComObject WScript.Shell
   $Target=$Shell.CreateShortcut($Link).TargetPath
   if (-not (Test-Path $Target) -or (Split-Path $Target) -ne $Destination) { throw 'Shortcut does not target the stable installed launcher.' }
  }
  if (-not $Child.HasExited) { & taskkill /PID $Child.Id /T /F | Out-Null }
  $Child=$null
 }
 Write-Host 'Installed app shortcut create/remove verification passed.'
} finally {
 if ($Child -and -not $Child.HasExited) { & taskkill /PID $Child.Id /T /F | Out-Null }
 if (Test-Path $Link) { Remove-Item $Link -Force }
 $Update=Join-Path $Destination 'Update.exe'
 if (Test-Path $Update) { Start-Process $Update -ArgumentList @('uninstall','--silent') -Wait | Out-Null }
}
