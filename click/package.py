"""Freeze a portable installer and wrap the previously verified native launcher."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "click-dist"
SOURCE_RUN = 39369607000

def run(*args):
    subprocess.run([str(x) for x in args], cwd=ROOT, check=True)

def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def main(platform):
    OUT.mkdir(exist_ok=True)
    manifest = json.loads((ROOT / "download-manifest.json").read_text())
    inventory = json.loads((ROOT / "file-inventory.json").read_text())
    if len(manifest["parts"]) != 14 or inventory["mirror_files"] != 12482:
        raise ValueError("Unexpected asset inventory")
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--console",
        "--name", "PlayGTA5", "--paths", ROOT,
        "--distpath", ROOT / "frozen", "--workpath", ROOT / ".click-build", "--specpath", ROOT / ".click-build",
        "--add-data", str(ROOT / "download-manifest.json") + ":.",
        "--add-data", str(ROOT / "file-inventory.json") + ":.",
        "--add-data", str(ROOT / "support") + ":support",
        ROOT / "click/launch.py")
    exe = ROOT / "frozen" / ("PlayGTA5.exe" if platform == "Windows-x64" else "PlayGTA5")
    run(exe, "--self-test")
    run(exe, "--help")
    with tempfile.TemporaryDirectory(prefix="click-play-package-") as temporary:
        stage = Path(temporary) / "PlayGTA5"
        stage.mkdir()
        shutil.copy2(exe, stage / exe.name)
        native_meta = json.loads((ROOT / "native" / (platform + "-artifact.json")).read_text())
        native_zip = ROOT / "native" / native_meta["file"]
        if digest(native_zip) != native_meta["sha256"]:
            raise ValueError("Native launcher artifact checksum mismatch")
        native = stage / "multiplayer"
        native.mkdir()
        if platform == "macOS-arm64":
            run("ditto", "-x", "-k", native_zip, native)
            run("codesign", "--verify", "--deep", "--strict", native / "GTA5Data Launcher.app")
            run("codesign", "--verify", "--strict", stage / exe.name)
            with (native / "GTA5Data Launcher.app/Contents/Info.plist").open("rb") as stream:
                assert plistlib.load(stream)["CFBundleShortVersionString"] == "0.2.21"
            (stage / "Play.command").write_text('#!/bin/bash\nset -e\nDIR="$(cd -- "$(dirname -- "$0")" && pwd)"\nexec "$DIR/PlayGTA5" "$@"\n')
            (stage / "Play-Multiplayer.command").write_text('#!/bin/bash\nset -e\nDIR="$(cd -- "$(dirname -- "$0")" && pwd)"\nexec "$DIR/PlayGTA5" --multiplayer "$@"\n')
            (stage / "Verify-Game.command").write_text('#!/bin/bash\nset -e\nDIR="$(cd -- "$(dirname -- "$0")" && pwd)"\nexec "$DIR/PlayGTA5" --verify "$@"\n')
            for script in stage.glob("*.command"):
                script.chmod(0o755)
        else:
            with zipfile.ZipFile(native_zip) as archive:
                archive.extractall(native)
            (stage / "Play.cmd").write_bytes(b'@echo off\r\n"%~dp0PlayGTA5.exe" %*\r\nif errorlevel 1 pause\r\n')
            (stage / "Play-Multiplayer.cmd").write_bytes(b'@echo off\r\n"%~dp0PlayGTA5.exe" --multiplayer %*\r\nif errorlevel 1 pause\r\n')
            (stage / "Verify-Game.cmd").write_bytes(b'@echo off\r\n"%~dp0PlayGTA5.exe" --verify %*\r\nif errorlevel 1 pause\r\n')
        shutil.copy2(ROOT / "click/README.md", stage / "START-HERE.txt")
        notices = stage / "notices"
        notices.mkdir()
        for name in ("LICENSE", "NOTICE.md", "NOTICE.zh-CN.md"):
            shutil.copy2(native / name, notices / name)
        for candidate in (Path(sys.base_prefix) / "LICENSE.txt", Path(sys.base_prefix) / "Resources/Python.app/Contents/Resources/LICENSE.txt"):
            if candidate.is_file():
                shutil.copy2(candidate, notices / "Python-LICENSE.txt")
                break
        dist = importlib.metadata.distribution("pyinstaller")
        for item in dist.files or ():
            if "dist-info" in str(item) and ("COPYING" in str(item) or "LICENSE" in str(item)):
                path = Path(dist.locate_file(item))
                if path.is_file():
                    shutil.copy2(path, notices / ("PyInstaller-" + path.name))
        result = OUT / ("PlayGTA5-Click-to-Play-" + platform + ".zip")
        if platform == "macOS-arm64":
            run("ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", stage, result)
        else:
            with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                for path in stage.rglob("*"):
                    if path.is_file():
                        archive.write(path, "PlayGTA5/" + path.relative_to(stage).as_posix())
        with zipfile.ZipFile(result) as archive:
            assert archive.testzip() is None
            assert not any(Path(n).suffix.lower() in (".wasm", ".rpf", ".gfx", ".pem", ".key") for n in archive.namelist())
        report = {"file": result.name, "bytes": result.stat().st_size, "sha256": digest(result),
                  "native_source_run": SOURCE_RUN, "asset_archives": len(manifest["parts"]),
                  "asset_download_bytes": sum(x["bytes"] for x in manifest["parts"]),
                  "installed_mirror_bytes": inventory["mirror_bytes"],
                  "game_assets_bundled": False, "python_install_required": False,
                  "gameplay_validated": False, "macos_notarized": False}
        (OUT / (platform + "-package.json")).write_text(json.dumps(report, indent=2) + "\n")
        (OUT / ("SHA256SUMS-" + platform + ".txt")).write_text(report["sha256"] + "  " + result.name + "\n")
        print(json.dumps(report))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, choices=["Windows-x64", "macOS-arm64"])
    main(parser.parse_args().platform)
