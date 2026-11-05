$ErrorActionPreference='Stop'
python tools/stage_libredwg.py runtime/libredwg DevArtifacts
if ($LASTEXITCODE -ne 0) { throw 'LibreDWG staging failed' }
python build_metadata.py
if ($LASTEXITCODE -ne 0) { throw 'Metadata failed' }
python -m PyInstaller --noconfirm --clean --noupx --windowed --onedir --name BakuriDevelopment --icon assets/app.ico --version-file version-resource.txt --add-data 'assets;assets' --add-data 'runtime/libredwg;cad_tools' --add-data 'USER-GUIDE.md;.' --add-data 'RENAME-GUIDE.md;.' --add-data 'PATCH-NOTES.md;.' --add-data 'LICENSES;LICENSES' --add-data 'LICENSE-AGPL-3.0.txt;.' --add-binary 'FilePathCheckerModuleExample.dll;.' --hidden-import win32timezone --hidden-import win32com.shell.shell --collect-data ezdxf --exclude-module PIL.AvifImagePlugin --exclude-module PIL._avif app.py
if ($LASTEXITCODE -ne 0) { throw 'Developer build failed' }
python verify_development.py dist/BakuriDevelopment/BakuriDevelopment.exe
if ($LASTEXITCODE -ne 0) { throw 'Developer startup verification failed' }
python verify_libredwg.py dist/BakuriDevelopment/_internal/cad_tools DevArtifacts/libredwg-0.14.tar.xz
if ($LASTEXITCODE -ne 0) { throw 'Bundled DWG conversion verification failed' }
Compress-Archive -Path dist/BakuriDevelopment -DestinationPath DevArtifacts/Bakuri-Development-1.0.0-dev.17.zip -Force
Write-Host ('Developer Windows ZIP bytes: ' + (Get-Item DevArtifacts/Bakuri-Development-1.0.0-dev.17.zip).Length)
python prepare_source.py
if ($LASTEXITCODE -ne 0) { throw 'Source packaging failed' }
Copy-Item SourcePackages/*.zip DevArtifacts/
