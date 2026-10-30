$ErrorActionPreference='Stop'
python build_metadata.py
if ($LASTEXITCODE -ne 0) { throw 'Metadata failed' }
python -m PyInstaller --noconfirm --clean --noupx --windowed --onedir --name BakuriDevelopment --icon assets/app.ico --version-file version-resource.txt --add-data 'assets;assets' --add-data 'USER-GUIDE.md;.' --add-data 'RENAME-GUIDE.md;.' --add-data 'PATCH-NOTES.md;.' --add-data 'LICENSES;LICENSES' --add-data 'LICENSE-AGPL-3.0.txt;.' --add-binary 'FilePathCheckerModuleExample.dll;.' --hidden-import win32timezone --hidden-import win32com.shell.shell --exclude-module PIL.AvifImagePlugin --exclude-module PIL._avif app.py
if ($LASTEXITCODE -ne 0) { throw 'Developer build failed' }
python verify_development.py dist/BakuriDevelopment/BakuriDevelopment.exe
if ($LASTEXITCODE -ne 0) { throw 'Developer startup verification failed' }
New-Item -ItemType Directory -Force DevArtifacts | Out-Null
Compress-Archive -Path dist/BakuriDevelopment -DestinationPath DevArtifacts/Bakuri-Development-0.15.0-dev.14.zip -Force
python prepare_source.py
if ($LASTEXITCODE -ne 0) { throw 'Source packaging failed' }
Copy-Item SourcePackages/*.zip DevArtifacts/
