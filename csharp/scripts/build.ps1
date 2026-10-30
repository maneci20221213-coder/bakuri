$ErrorActionPreference='Stop'
Set-Location (Resolve-Path "$PSScriptRoot/../..")
$Artifacts=Join-Path $PWD 'csharp/artifacts'
New-Item -ItemType Directory -Force $Artifacts | Out-Null
function Run([scriptblock]$Command) { & $Command; if ($LASTEXITCODE -ne 0) { throw "Command failed: $Command" } }
Run { dotnet build csharp/src/Bakuri.Desktop/Bakuri.Desktop.csproj -c Release -r win-x64 }
Run { dotnet build csharp/tests/Bakuri.Checks/Bakuri.Checks.csproj -c Release -r win-x64 }
$Checks=(Get-ChildItem csharp/tests/Bakuri.Checks/bin/Release -Filter Bakuri.Checks.dll -Recurse | Select-Object -First 1).FullName
Run { dotnet $Checks --check "$Artifacts/checks" }
Run { dotnet list csharp/src/Bakuri.Desktop/Bakuri.Desktop.csproj package --include-transitive --format json | Out-File -Encoding utf8 "$Artifacts/dependencies.json" }
$Results=@()
foreach ($Kind in @('FrameworkDependent','SelfContained')) {
 $Folder=Join-Path $Artifacts $Kind
 $SelfContained=($Kind -eq 'SelfContained').ToString().ToLower()
 Run { dotnet publish csharp/src/Bakuri.Desktop/Bakuri.Desktop.csproj -c Release -r win-x64 --self-contained $SelfContained -o $Folder }
 Copy-Item LICENSE-AGPL-3.0.txt "$Folder/LICENSE-AGPL-3.0.txt" -Force
 $Notice=Join-Path $Folder 'third-party-notices';New-Item -ItemType Directory -Force $Notice | Out-Null
 Get-ChildItem "$env:USERPROFILE/.nuget/packages" -Recurse -File | Where-Object { $_.Name -match '^(LICENSE|COPYING|NOTICE)' -and $_.Extension -notin @('.dll','.nupkg') } | ForEach-Object {
  $Relative=$_.FullName.Substring((Join-Path $env:USERPROFILE '.nuget/packages').Length+1);$Target=Join-Path $Notice $Relative
  New-Item -ItemType Directory -Force (Split-Path $Target) | Out-Null;Copy-Item $_.FullName $Target -Force
 }
 $Zip=Join-Path $Artifacts "Bakuri-CSharp-0.16.0-exp.1-$Kind.zip"
 Compress-Archive -Path $Folder -DestinationPath $Zip -Force
 $Results+=@{Kind=$Kind;ZipBytes=(Get-Item $Zip).Length;ExtractedBytes=(Get-ChildItem $Folder -Recurse -File | Measure-Object Length -Sum).Sum}
}
$Benchmark=Join-Path $Artifacts 'comparison';New-Item -ItemType Directory -Force $Benchmark | Out-Null
Run { dotnet $Checks --corpus $Benchmark }
$Clock=[Diagnostics.Stopwatch]::StartNew();Run { dotnet $Checks --benchmark $Benchmark };$Clock.Stop();$NativeWall=$Clock.Elapsed.TotalMilliseconds
Run { python -m pip install Pillow==11.3.0 PyMuPDF==1.26.7 }
$Clock.Restart();Run { python csharp/scripts/benchmark_python.py $Benchmark };$Clock.Stop();$PythonWall=$Clock.Elapsed.TotalMilliseconds
$Report=@{Packages=$Results;NativeProcessWallMs=$NativeWall;PythonProcessWallMs=$PythonWall;Scenario='12 synthetic 1600x1200 PNG files -> one PDF; one fresh process per implementation';Native=(Get-Content "$Benchmark/native-benchmark.json" -Raw|ConvertFrom-Json);Python=(Get-Content "$Benchmark/python-benchmark.json" -Raw|ConvertFrom-Json)}
$Report|ConvertTo-Json -Depth 6|Set-Content -Encoding utf8 "$Artifacts/comparison.json"
Copy-Item "$Benchmark/*benchmark.json" $Artifacts
& "$PSScriptRoot/verify-window.ps1" -Exe "$Artifacts/SelfContained/BakuriCSharpTrial.exe" -Corpus $Benchmark -Screenshot "$Artifacts/Bakuri-CSharp-UI.png"
$Source=Join-Path $Artifacts 'Source';New-Item -ItemType Directory -Force $Source | Out-Null
Get-ChildItem csharp -Recurse -File | Where-Object { $_.FullName -notmatch '[\\/](bin|obj|artifacts)[\\/]' } | ForEach-Object {
 $Relative=$_.FullName.Substring($PWD.Path.Length+1);$Target=Join-Path $Source $Relative
 New-Item -ItemType Directory -Force (Split-Path $Target) | Out-Null;Copy-Item $_.FullName $Target -Force
}
Copy-Item assets,FilePathCheckerModuleExample.dll,LICENSE,LICENSE-AGPL-3.0.txt $Source -Recurse
Compress-Archive -Path "$Source/*" -DestinationPath "$Artifacts/Bakuri-CSharp-Source.zip" -Force
Write-Host ($Report|ConvertTo-Json -Depth 6)
