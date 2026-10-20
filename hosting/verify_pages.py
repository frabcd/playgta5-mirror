"""Check the generated static game and, after deployment, production responses."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('output', type=Path)
parser.add_argument('--origin')
args = parser.parse_args()
root = args.output
index_text = (root / 'chunk-index.js').read_text()
manifest = json.loads(index_text.removeprefix('globalThis.GAME_CHUNKS=').strip().removesuffix(';'))
files = [p for p in root.rglob('*') if p.is_file()]
assert len(files) <= 20000
assert all(p.stat().st_size <= 25 * 1024**2 for p in files)
engine = next((key, item) for key, item in manifest['files'].items() if key.endswith('/game.wasm'))
key, item = engine
first_chunk = item['prefix'] + '/0000.bin'
assert (root / first_chunk.lstrip('/')).read_bytes()[:4] == b'\x00asm'
headers = (root / '_headers').read_text()
assert 'Cross-Origin-Opener-Policy: same-origin' in headers
assert 'Cross-Origin-Embedder-Policy: require-corp' in headers
assert (root / '404.html').is_file()
assert (root / '__support/index.html').is_file()
assert (root / 'chunk-fetch.js').is_file()
report = {'static_files': len(files), 'static_bytes': sum(p.stat().st_size for p in files),
          'engine': key, 'engine_first_chunk': first_chunk, 'pages_limits_checked': True,
          'production_verified': False, 'graphical_gameplay_verified': False}
if args.origin:
    for path in ['/', '/chunk-index.js', first_chunk, '/__support/']:
        with urllib.request.urlopen(args.origin.rstrip('/') + path, timeout=120) as response:
            body = response.read()
            assert response.status == 200
            assert response.headers['Cross-Origin-Opener-Policy'] == 'same-origin'
            assert response.headers['Cross-Origin-Embedder-Policy'] == 'require-corp'
            expected = root / ('index.html' if path == '/' else path.lstrip('/') + ('index.html' if path.endswith('/') else ''))
            assert hashlib.sha256(body).digest() == hashlib.sha256(expected.read_bytes()).digest(), path
    report['production_verified'] = True
destination = Path('pages-reports')
destination.mkdir(exist_ok=True)
(destination / ('production.json' if args.origin else 'build.json')).write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
