"""Verify public production transport and reconstruct/hash the published engine."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

ORIGIN = "https://fran-abcd-abcd.pages.dev"
report = {"origin": ORIGIN, "responses": [], "graphical_gameplay_verified": False}
out = Path("pages-reports")
out.mkdir(exist_ok=True)

def get(path):
    for attempt in range(5):
        try:
            request = urllib.request.Request(ORIGIN + path, headers={"User-Agent": "PlayGTA5-DeploymentVerifier/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response:
                data = response.read()
                assert response.status == 200, path
                assert response.headers.get("Cross-Origin-Opener-Policy") == "same-origin", path
                assert response.headers.get("Cross-Origin-Embedder-Policy") == "require-corp", path
                return data
        except urllib.error.HTTPError as error:
            if attempt == 4:
                report["failure"] = {"path": path, "status": error.code, "body_excerpt": error.read(1000).decode("utf-8", errors="replace")}
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 4:
                raise
        time.sleep(10 * (attempt + 1))

try:
    page = get("/")
    assert b"game-progress" in page and b"/chunk-fetch.js" in page
    report["responses"].append("/")
    support = get("/__support/")
    assert b"WebGPU" in support
    report["responses"].append("/__support/")
    source = get("/chunk-index.js").decode("utf-8")
    manifest = json.loads(source.removeprefix("globalThis.GAME_CHUNKS=").strip().removesuffix(";"))
    key, engine = next((k, v) for k, v in manifest["files"].items() if k.endswith("/game.wasm"))
    count = (engine["size"] + manifest["chunkSize"] - 1) // manifest["chunkSize"]
    paths = [engine["prefix"] + "/" + str(i).zfill(4) + ".bin" for i in range(count)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        chunks = list(executor.map(get, paths))
    data = b"".join(chunks)
    expected = engine["prefix"].rsplit("/", 1)[1]
    assert len(data) == engine["size"]
    assert data[:4] == b"\x00asm"
    assert hashlib.sha256(data).hexdigest() == expected
    report.update({"production_verified": True, "engine_bytes": len(data), "engine_sha256": expected,
                   "engine_chunks": count, "isolation_headers_verified": True, "indexed_resources": len(manifest["files"])})
finally:
    (out / "public-production.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
