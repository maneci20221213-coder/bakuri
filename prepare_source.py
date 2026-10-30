"""Package version-matched public app source from a strict repository allowlist."""

from pathlib import Path
import zipfile
from version import VERSION

ROOT = Path(__file__).resolve().parent


def create_source(root=ROOT):
    root = Path(root)
    output = root / "SourcePackages" / f"Bakuri-Source-v{VERSION}.zip"
    output.parent.mkdir(exist_ok=True)
    files = [
        p
        for p in root.iterdir()
        if p.is_file()
        and (
            p.suffix in {".py", ".ps1", ".bat", ".cmd", ".c", ".cs", ".md"}
            or p.name
            in {
                "requirements.txt",
                "requirements-dev.txt",
                "pyproject.toml",
                "LICENSE-AGPL-3.0.txt",
                "LICENSE",
                "FilePathCheckerModuleExample.dll",
                "update-config.json",
            }
        )
    ]
    for folder in ["assets", "LICENSES", ".github", "bakuri", "tools", "docs"]:
        if (root / folder).exists():
            files.extend(p for p in (root / folder).rglob("*") if p.is_file())
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(set(files)):
            if "__pycache__" not in p.parts:
                z.write(p, Path("Bakuri") / p.relative_to(root))
    return output


if __name__ == "__main__":
    print(create_source())
