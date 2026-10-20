"""Self-contained click-to-play installer and local browser-game launcher."""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.request
import webbrowser
import zipfile

import download_game as installer
import serve_local as mirror_host

BUNDLE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
APP = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
installer.HERE = BUNDLE
# The embedded interpreter replaces the release's Windows-only Python runtime.
installer.payload = lambda name, windows=None: name.startswith("mirror/")
mirror_host.SUPPORT = BUNDLE / "support"

PORTAL = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PlayGTA5 Local</title><style>
body{margin:0;background:#101914;color:#edf3e9;font:18px system-ui;line-height:1.6}main{max-width:760px;margin:8vh auto;padding:24px}
small{color:#a7bd9e}h1{font-size:52px;line-height:1.1}a{display:block;color:#142016;background:#d5efaa;text-decoration:none;padding:16px 22px;margin:14px 0;border-radius:8px}
p{color:#b8c8b2}.note{font-size:15px;border-top:1px solid #52604b;padding-top:20px}
</style></head><body><main><small>LOCAL GAME / AVAILABLE WORLDS</small><h1>Choose your session.</h1>
<p>The game runs in this browser. Use current Chrome or Edge with hardware acceleration enabled.</p>
<a href="/?mode=story&low=1&fps=30&res=1280x720&shadows=0">Continue story</a>
<a href="/?mode=story&newgame=1&low=1&fps=30&res=1280x720&shadows=0">New story</a>
<a href="/?mode=sandbox&low=1&fps=30&res=1280x720&shadows=0">Los Santos free roam</a>
<a href="/?mode=sandbox&map=env_test&low=1&fps=30&res=1280x720&shadows=0">Experimental env_test level</a>
<a href="/__support/">Device checks and graphics settings</a>
<p class="note">env_test is the snapshot's development level; its completeness is unverified. It is not a complete GTA VI game.
For multiplayer, use the separate Play-Multiplayer launch file in your ZIP. Keep the launcher window open while playing.
First world loading and shader preparation may take several minutes.</p>
</main></body></html>"""


class LocalHandler(mirror_host.Handler):
    def send_head(self):
        if mirror_host.urlsplit(self.path).path == "/launch":
            self.byte_range = None
            body = PORTAL.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return io.BytesIO(body)
        return super().send_head()


@contextlib.contextmanager
def install_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    stream = (root / ".playgta5.lock").open("a+b")
    try:
        if os.name == "nt":
            import msvcrt
            stream.seek(0)
            if not stream.read(1):
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        stream.close()
        raise ValueError("Another installer or game window is using this folder. Close it first.")
    try:
        yield
    finally:
        stream.close()


def verify(root):
    inventory = json.loads((BUNDLE / "file-inventory.json").read_text(encoding="utf-8"))
    records = [r for r in inventory["files"] if r["path"].startswith("mirror/")]
    for index, record in enumerate(records):
        source = installer.target_path(root, record["path"])
        if not source.is_file() or source.stat().st_size != record["bytes"] or installer.digest(source) != record["sha256"]:
            raise ValueError("Asset verification failed: " + record["path"] + ". Existing assets were not overwritten.")
        if index % 1000 == 0:
            print("Verifying assets: " + str(index) + "/" + str(len(records)), flush=True)
    print(json.dumps({"verified_mirror_files": len(records), "verified_mirror_bytes": sum(r["bytes"] for r in records)}), flush=True)
    return len(records)


def open_game_browser(address):
    if sys.platform == "darwin":
        for name in ("Google Chrome", "Microsoft Edge"):
            if any((base / (name + ".app")).is_dir() for base in (Path("/Applications"), Path.home() / "Applications")):
                subprocess.run(["open", "-a", name, address], check=True)
                return
    elif os.name == "nt":
        for base in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
            parent = os.environ.get(base)
            if not parent:
                continue
            for relative in ("Google/Chrome/Application/chrome.exe", "Microsoft/Edge/Application/msedge.exe"):
                exe = Path(parent) / relative
                if exe.is_file():
                    subprocess.Popen([str(exe), address], close_fds=True)
                    return
    webbrowser.open(address)


def serve(game, port, no_open=False):
    mirror_host.ROOT = game.resolve()
    if not (game / "index.html").is_file():
        raise ValueError("Game page is missing")
    with mirror_host.ThreadingHTTPServer(("127.0.0.1", port), LocalHandler) as server:
        address = "http://localhost:" + str(server.server_port) + "/launch"
        print("PLAYGTA5_URL=" + address, flush=True)
        print("Keep this window open while playing. Ctrl+C stops this local server.", flush=True)
        if not no_open:
            open_game_browser(address)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def multiplayer(game):
    print("If asked for game resources, select: " + str(game), flush=True)
    if sys.platform == "darwin":
        app = APP / "multiplayer/GTA5Data Launcher.app"
        if not app.is_dir():
            raise ValueError("Extract the complete click-to-play ZIP; multiplayer App is missing")
        subprocess.run(["open", str(app)], check=True)
    elif os.name == "nt":
        exe = APP / "multiplayer/PlayGTA5-Multiplayer.exe"
        if not exe.is_file():
            raise ValueError("Extract the complete click-to-play ZIP; multiplayer EXE is missing")
        subprocess.Popen([str(exe)], cwd=str(game.parent.parent), close_fds=True)
    else:
        raise ValueError("Multiplayer desktop package is supplied for Windows and Apple Silicon Mac")


def self_test():
    import unittest
    class Checks(unittest.TestCase):
        def test_install_resume_verify_and_read_only_serving(self):
            global BUNDLE
            original_bundle, original_here = BUNDLE, installer.HERE
            original_root = mirror_host.ROOT
            with tempfile.TemporaryDirectory() as temporary:
                top = Path(temporary)
                source, destination = top / "source", top / "install"
                source.mkdir()
                archive = source / "part.zip"
                bodies = {"mirror/playgta5.com/index.html": b"<html><body>fixture</body></html>",
                          "mirror/playgta5.com/b/8b0b5899ed/game.wasm": b"\\0asm-fixture-0123456789",
                          "mirror/playgta5.com/data/manifest.json": b"{}"}
                records = [{"path": name, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                            "part": "part.zip"} for name, body in bodies.items()]
                with zipfile.ZipFile(archive, "w") as z:
                    for name, body in bodies.items():
                        z.writestr(name, body)
                mirror_host.ROOT = source
                httpd = mirror_host.ThreadingHTTPServer(("127.0.0.1", 0), LocalHandler)
                thread = threading.Thread(target=httpd.serve_forever, daemon=True)
                thread.start()
                try:
                    url = "http://127.0.0.1:" + str(httpd.server_port)
                    manifest = {"parts": [{"name": "part.zip", "bytes": archive.stat().st_size,
                        "sha256": installer.digest(archive), "url": url + "/part.zip"}]}
                    (source / "download-manifest.json").write_text(json.dumps(manifest))
                    (source / "file-inventory.json").write_text(json.dumps({"files": records}))
                    BUNDLE = source
                    installer.HERE = source
                    cache = destination / ".downloads"
                    cache.mkdir(parents=True)
                    (cache / "part.zip.partial").write_bytes(archive.read_bytes()[:31])
                    installer.install(destination)
                    self.assertEqual(verify(destination), 3)
                    installer.install(destination)
                    mirror_host.ROOT = destination / "mirror/playgta5.com"
                    request = urllib.request.Request(url + "/b/8b0b5899ed/game.wasm", headers={"Range": "bytes=0-3"})
                    with urllib.request.urlopen(request) as response:
                        self.assertEqual(response.status, 206)
                        self.assertEqual(response.headers["Cross-Origin-Opener-Policy"], "same-origin")
                        self.assertEqual(response.headers["Cross-Origin-Embedder-Policy"], "require-corp")
                        self.assertEqual(response.read(), bodies["mirror/playgta5.com/b/8b0b5899ed/game.wasm"][:4])
                    with urllib.request.urlopen(url + "/launch") as response:
                        self.assertIn(b"map=env_test", response.read())
                    target = destination / records[0]["path"]
                    target.write_bytes(b"modified")
                    with self.assertRaises(ValueError):
                        installer.extract_payload(archive, destination, records, windows=False)
                    self.assertEqual(target.read_bytes(), b"modified")
                    with self.assertRaises(ValueError):
                        verify(destination)
                    bad = source / "unsafe.zip"
                    with zipfile.ZipFile(bad, "w") as z:
                        z.writestr("../escape", b"bad")
                    with self.assertRaises(ValueError):
                        installer.extract_payload(bad, destination, [], windows=False)
                    self.assertFalse((top / "escape").exists())
                finally:
                    BUNDLE, installer.HERE = original_bundle, original_here
                    mirror_host.ROOT = original_root
                    httpd.shutdown()
                    httpd.server_close()
                    thread.join(timeout=3)
        def test_lock(self):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                with install_lock(root):
                    with self.assertRaises(ValueError):
                        with install_lock(root):
                            pass
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    if not result.wasSuccessful():
        raise SystemExit(1)
    print("CLICK_TO_PLAY_SELF_TEST_PASSED", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", type=Path, default=Path.home() / "PlayGTA5-Local")
    parser.add_argument("--install-only", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--multiplayer", action="store_true")
    parser.add_argument("--no-open", action="store_true")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    root = args.install_root.expanduser().resolve()
    print("PlayGTA5 Local - Windows / Apple Silicon Mac", flush=True)
    print("Game folder: " + str(root), flush=True)
    print("First installation downloads about 21.2 GB. Allow at least 25 GB free.", flush=True)
    with install_lock(root):
        if args.verify:
            verify(root)
            return
        installer.install(root)
        game = root / "mirror/playgta5.com"
        if args.install_only:
            return
        if args.multiplayer:
            multiplayer(game)
        else:
            serve(game, args.port, args.no_open)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        print("Stopped: " + str(error), file=sys.stderr, flush=True)
        print("Run the same launch file again to resume. Existing game files are preserved.", flush=True)
        if sys.stdin.isatty():
            input("Press Enter to close.")
        raise SystemExit(1)
