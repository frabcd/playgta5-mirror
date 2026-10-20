"""Build and verify multiplayer only in disposable hosted VMs.

No game assets, runtime copies or credentials are included in output artifacts.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / "upstream"
DIST = ROOT / "dist"
LOCK = json.loads((ROOT / "multiplayer/upstream.lock.json").read_text())
LEGAL = ("LICENSE", "NOTICE.md", "NOTICE.zh-CN.md")


def run(*args, cwd=ROOT, **kwargs):
    return subprocess.run([str(a) for a in args], cwd=cwd, check=True, **kwargs)


def digest(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def prepare():
    head = subprocess.check_output(["git", "-C", str(UP), "rev-parse", "HEAD"], text=True).strip()
    if head != LOCK["upstream_commit"]:
        raise ValueError("Upstream checkout differs from pinned source")
    sys.path.insert(0, str(UP / "tools"))
    from build_multiplayer_client import ORIGINAL_WASM_SHA256
    from prepare_release import component_versions
    if ORIGINAL_WASM_SHA256 != LOCK["original_wasm_sha256"]:
        raise ValueError("Pinned mirror engine and launcher do not match")
    engine = next(r for r in LOCK["engine_files"] if r["path"].endswith("game.wasm"))
    if engine["sha256"] != ORIGINAL_WASM_SHA256:
        raise ValueError("Mirror inventory engine hash does not match adapter")
    versions = component_versions()
    write_json(DIST / "source-validation.json", {
        "source_commit": head, "upstream_repository": LOCK["upstream_repository"],
        "mirror_inventory_commit": LOCK["mirror_commit"], "versions": versions,
        "engine_inventory_matches": True, "gameplay_validated": False,
    })
    print(json.dumps({"source_commit": head, "versions": versions, "engine_inventory_matches": True}))


def package(platform):
    sys.path.insert(0, str(UP / "tools"))
    from prepare_release import component_versions
    from check_release_assets import inspect_windows, inspect_server_jar, package_macos, inspect_macos_zip
    versions = component_versions()
    DIST.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="multiplayer-package-") as temporary:
        stage = Path(temporary)
        for name in LEGAL:
            shutil.copyfile(UP / name, stage / name)
        shutil.copyfile(ROOT / "multiplayer/README.md", stage / "README.md")
        metadata = {
            "upstream_repository": LOCK["upstream_repository"],
            "upstream_commit": LOCK["upstream_commit"],
            "integration_commit": os.environ.get("GITHUB_SHA"),
            "platform": platform, "versions": versions,
            "game_assets_included": False, "gameplay_validated": False,
            "macos_notarized": False,
        }
        write_json(stage / "BUILD.json", metadata)
        if platform == "Windows-x64":
            source = UP / "desktop/src-tauri/target/x86_64-pc-windows-msvc/release/gta5data-launcher.exe"
            inspect_windows(source.read_bytes(), versions["launcher"]["version"])
            shutil.copyfile(source, stage / "PlayGTA5-Multiplayer.exe")
        elif platform == "macOS-arm64":
            app = UP / "desktop/src-tauri/target/aarch64-apple-darwin/release/bundle/macos/GTA5Data Launcher.app"
            plan = {"components": {"launcher": versions["launcher"]}}
            package_macos(plan, app, DIST)
            existing = next(DIST.glob("GTA5Data-Launcher-macOS-*.zip"))
            result = DIST / "PlayGTA5-Multiplayer-macOS-arm64.zip"
            existing.rename(result)
            with zipfile.ZipFile(result, "a", compression=zipfile.ZIP_DEFLATED) as z:
                for source in sorted(stage.iterdir()):
                    z.write(source, source.name)
            inspect_macos_zip(result.read_bytes(), versions["launcher"]["version"])
        elif platform == "server":
            jar = UP / "server/multiplayer-server.jar"
            inspect_server_jar(jar.read_bytes(), versions["server"]["runtime_version"], execute=True)
            shutil.copyfile(jar, stage / "multiplayer-server.jar")
            shutil.copyfile(UP / "server/README.md", stage / "UPSTREAM-SERVER.md")
            shutil.copytree(ROOT / "multiplayer/deploy", stage / "deploy")
            if (DIST / "server-smoke.json").exists():
                shutil.copyfile(DIST / "server-smoke.json", stage / "server-smoke.json")
        else:
            raise ValueError("Unknown platform")
        if platform != "macOS-arm64":
            result = DIST / ("PlayGTA5-Multiplayer-" + platform + ".zip")
            with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_DEFLATED) as z:
                for source in sorted(stage.rglob("*")):
                    if source.is_file():
                        z.write(source, source.relative_to(stage).as_posix())
        with zipfile.ZipFile(result) as z:
            if z.testzip():
                raise ValueError("Package CRC verification failed")
            if any(Path(n).suffix.lower() in (".wasm", ".rpf", ".gfx", ".key", ".pem") for n in z.namelist()):
                raise ValueError("Game assets or key files must not enter packages")
        report = {**metadata, "file": result.name, "bytes": result.stat().st_size, "sha256": digest(result)}
        write_json(DIST / (platform + "-artifact.json"), report)
        (DIST / ("SHA256SUMS-" + platform + ".txt")).write_text(
            report["sha256"] + "  " + result.name + "\n", encoding="utf-8")
        print(json.dumps(report))


def smoke():
    log = DIST / "server-smoke.log"
    DIST.mkdir(exist_ok=True)
    with log.open("w", encoding="utf-8") as output:
        process = subprocess.Popen([
            "java", "-Xms64m", "-Xmx512m", "-jar", str(UP / "server/multiplayer-server.jar"),
            "--host", "127.0.0.1", "--port", "18787", "--max-clients", "8",
            "--world-data", str(ROOT / ".vm-world-data"),
        ], stdout=output, stderr=subprocess.STDOUT, cwd=UP)
        try:
            run("node", ROOT / "multiplayer/smoke.mjs", "http://127.0.0.1:18787",
                DIST / "server-smoke.json")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def engine():
    manifest = json.loads((ROOT / "download-manifest.json").read_text())
    records = LOCK["engine_files"] + LOCK["ped_inputs"]
    with tempfile.TemporaryDirectory(prefix="mirror-engine-validation-") as temporary:
        temp = Path(temporary)
        game = temp / "resources"
        game.mkdir()
        before = {}
        for part_name in sorted({r["part"] for r in records}):
            part = next(p for p in manifest["parts"] if p["name"] == part_name)
            archive = temp / part_name
            print("Downloading and verifying " + part_name, flush=True)
            request = urllib.request.Request(part["url"], headers={"User-Agent": "PlayGTA5-VM-validation"})
            with urllib.request.urlopen(request, timeout=120) as response, archive.open("wb") as target:
                shutil.copyfileobj(response, target, length=1024 * 1024)
            if archive.stat().st_size != part["bytes"] or digest(archive) != part["sha256"]:
                raise ValueError("Download size/checksum verification failed")
            with zipfile.ZipFile(archive) as z:
                for record in (r for r in records if r["part"] == part_name):
                    relative = Path(record["path"]).relative_to("mirror/playgta5.com")
                    destination = game / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(record["path"]) as source, destination.open("wb") as target:
                        shutil.copyfileobj(source, target)
                    if destination.stat().st_size != record["bytes"] or digest(destination) != record["sha256"]:
                        raise ValueError("Engine/source file failed published inventory verification")
                    before[str(relative)] = digest(destination)
            archive.unlink()
        world = ROOT / ".vm-world-data"
        world.mkdir(exist_ok=True)
        run(sys.executable, "-B", UP / "tools/export_ped_collision.py",
            "--data", game / "data", "--wasm", game / "b/8b0b5899ed/game.wasm",
            "--output", world / "ped-collision.json")
        # Atomic exporter outputs default to owner-only; the runtime uses a separate UID.
        for derived in world.glob("*.json"):
            derived.chmod(0o644)
        runtime = temp / "isolated-runtime"
        run(sys.executable, "-B", UP / "tools/build_multiplayer_client.py",
            "--game-dir", game, "--runtime-dir", runtime)
        after = {name: digest(game / name) for name in before}
        if before != after:
            raise ValueError("Input resources changed during adapter build")
        if digest(runtime / "offline/game.wasm") != LOCK["original_wasm_sha256"]:
            raise ValueError("Offline copy differs from original")
        report = {
            "archive_sha256_verified": True, "source_files_verified": len(before),
            "ped_collision_models": len(json.loads((world / "ped-collision.json").read_text())["models"]),
            "original_resources_unchanged": before == after,
            "offline_bytes": (runtime / "offline/game.wasm").stat().st_size,
            "online_bytes": (runtime / "online/game.wasm").stat().st_size,
            "online_sha256": digest(runtime / "online/game.wasm"),
            "gameplay_validated": False, "full_asset_installation_validated": False,
        }
        write_json(DIST / "engine-validation.json", report)
        print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "package", "smoke", "engine"])
    parser.add_argument("--platform")
    args = parser.parse_args()
    if args.action == "package":
        package(args.platform)
    else:
        globals()[args.action]()
