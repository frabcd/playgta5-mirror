"""Fetch hash-pinned public release assets; no expiring CI artifact dependency."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "click/native-release.lock.json").read_text())

def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def main(platform):
    native = ROOT / "native"
    native.mkdir(exist_ok=True)
    suffix = ".exe" if platform == "Windows-x64" else "-development.zip"
    chosen = next(r for r in LOCK["assets"] if r["name"].endswith(suffix))
    legal = [r for r in LOCK["assets"] if r["name"] in ("LICENSE", "NOTICE.md", "NOTICE.zh-CN.md")]
    downloaded = []
    for record in [chosen, *legal]:
        target = native / record["name"]
        request = urllib.request.Request(record["url"], headers={"User-Agent": "PlayGTA5-click-package"})
        with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as output:
            shutil.copyfileobj(response, output)
        if target.stat().st_size != record["bytes"] or digest(target) != record["sha256"]:
            raise ValueError("Native release checksum mismatch: " + record["name"])
        downloaded.append(record)
    source = native / chosen["name"]
    packed = native / ("native-" + platform + ".zip")
    if platform == "macOS-arm64":
        shutil.copyfile(source, packed)
        mode = "a"
    else:
        mode = "w"
    with zipfile.ZipFile(packed, mode, compression=zipfile.ZIP_DEFLATED) as archive:
        if platform == "Windows-x64":
            archive.write(source, "PlayGTA5-Multiplayer.exe")
        for record in legal:
            archive.write(native / record["name"], record["name"])
    report = {"file": packed.name, "sha256": digest(packed), "release": LOCK["tag"],
              "commit": LOCK["commit"], "repository": LOCK["repository"], "verified_inputs": downloaded}
    (native / (platform + "-artifact.json")).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"native_release": LOCK["tag"], "verified_assets": len(downloaded)}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, choices=["Windows-x64", "macOS-arm64"])
    main(parser.parse_args().platform)
