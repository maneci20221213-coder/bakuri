"""Stage pinned LibreDWG binaries and publish the matching upstream source."""

import argparse
import hashlib
from pathlib import Path
import shutil
import tarfile
from tempfile import TemporaryDirectory
from urllib.request import urlopen
import zipfile

VERSION = "0.14"
BASE = f"https://github.com/LibreDWG/libredwg/releases/download/{VERSION}"
WIN64 = f"libredwg-{VERSION}-win64.zip"
SOURCE = f"libredwg-{VERSION}.tar.xz"
BINARIES = ("dwg2dxf.exe", "libredwg-0.dll")
HASHES = {
    WIN64: "1ad7e15344d20b3426c3435b078d82fb84b35062815946b2cca9c5fc9810fea8",
    SOURCE: "62ebb73b984f865960f20ed26619ea5f8789d5e3fd088fa40a2598384da81275",
}


def download(name, target):
    with urlopen(f"{BASE}/{name}", timeout=60) as response, target.open("wb") as output:
        shutil.copyfileobj(response, output)
    with target.open("rb") as data:
        if hashlib.file_digest(data, "sha256").hexdigest() != HASHES[name]:
            raise ValueError(f"LibreDWG checksum mismatch: {name}")


def stage(destination, artifacts):
    destination.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as directory:
        folder = Path(directory)
        binary = folder / WIN64
        source = folder / SOURCE
        download(WIN64, binary)
        download(SOURCE, source)
        with zipfile.ZipFile(binary) as archive:
            for name in BINARIES:
                (destination / name).write_bytes(archive.read(name))
        with tarfile.open(source) as archive:
            license_text = archive.extractfile(f"libredwg-{VERSION}/COPYING")
            (destination / "COPYING").write_bytes(license_text.read())
        shutil.copyfile(source, artifacts / SOURCE)
    (destination / "NOTICE.txt").write_text(
        f"GNU LibreDWG {VERSION} · GPLv3 or later (see COPYING).\n"
        f"Unmodified Windows x64 files from {BASE}/{WIN64}\n"
        f"Corresponding upstream source is supplied alongside this build as {SOURCE}.\n"
        f"Upstream source: {BASE}/{SOURCE}\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("artifacts", type=Path)
    args = parser.parse_args()
    stage(args.destination, args.artifacts)


if __name__ == "__main__":
    main()
