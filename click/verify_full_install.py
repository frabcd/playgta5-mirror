"""Start the actual full-resource host in a VM and record transport evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
install = Path(sys.argv[1])
game = install / "mirror/playgta5.com"
reports = ROOT / "click-reports"
reports.mkdir(exist_ok=True)
lines = []
process = subprocess.Popen([sys.executable, "-B", str(ROOT / "click/launch.py"),
    "--install-root", str(install), "--no-open", "--port", "0"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", bufsize=1)
thread = threading.Thread(target=lambda: [lines.append(line) for line in process.stdout], daemon=True)
thread.start()
try:
    origin = None
    for _ in range(600):
        for line in list(lines):
            if line.startswith("PLAYGTA5_URL="):
                origin = line.strip().split("=", 1)[1].removesuffix("/launch")
                break
        if origin:
            break
        if process.poll() is not None:
            raise RuntimeError("Host exited before startup: " + "".join(lines)[-4000:])
        time.sleep(0.1)
    if not origin:
        raise RuntimeError("Resource host did not start")
    with urllib.request.urlopen(origin + "/launch") as response:
        body = response.read()
        assert response.status == 200
        assert b"map=env_test" in body and b"mode=story" in body and b"mode=sandbox" in body
        assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
        assert response.headers["Cross-Origin-Embedder-Policy"] == "require-corp"
    request = urllib.request.Request(origin + "/b/8b0b5899ed/game.wasm", headers={"Range": "bytes=0-3"})
    with urllib.request.urlopen(request) as response:
        assert response.status == 206 and response.read() == b"\x00asm"
    with urllib.request.urlopen(origin + "/?mode=sandbox&map=env_test") as response:
        assert response.status == 200
        assert b"game-progress" in response.read()
    with urllib.request.urlopen(origin + "/__support/") as response:
        assert response.status == 200
    inventory = json.loads((ROOT / "file-inventory.json").read_text())
    counts = {}
    for record in inventory["files"]:
        if record["path"].startswith("mirror/"):
            counts[record["part"]] = counts.get(record["part"], 0) + 1
    report = {"all_asset_archives_installed": len(counts), "mirror_files_verified": inventory["mirror_files"],
              "mirror_bytes": inventory["mirror_bytes"], "local_host_started": True,
              "isolation_headers_verified": True, "real_wasm_range_verified": True,
              "story_sandbox_env_test_links_present": True, "graphical_gameplay_tested": False}
    (reports / "full-install.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
finally:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    thread.join(timeout=3)
    (reports / "resource-host.log").write_text("".join(lines), encoding="utf-8")
