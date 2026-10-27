"""Publish only the reviewed static bundle, preserving every original toolbox byte."""
import concurrent.futures
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / 'manifest.json').read_text())
ORIGIN = 'https://fran-abcd-abcd.pages.dev'
API = 'https://api.cloudflare.com/client/v4/accounts/591f8fad9d51a834bf7714007337623c/pages/projects/fran-abcd-abcd'
REPORTS = Path('crown-reports')
REPORTS.mkdir(exist_ok=True)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def project():
    request = urllib.request.Request(API, headers={'Authorization':'Bearer '+os.environ['CLOUDFLARE_API_TOKEN']})
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.load(response)
    assert result.get('success'), 'Cloudflare project lookup failed'
    data = result['result']
    assert data['name'] == 'fran-abcd-abcd' and data['production_branch'] == 'main'
    return data

def verify(file):
    request = urllib.request.Request(ORIGIN+'/'+urllib.parse.quote(file['path'], safe='/'), headers={'User-Agent':'Mozilla/5.0', 'Cache-Control':'no-cache'})
    try:
        response = urllib.request.urlopen(request, timeout=60)
    except urllib.error.HTTPError as error:
        if error.code != 404 or file['path'] != '404.html':
            raise
        response = error
    with response:
        data = response.read()
    assert digest(data) == file['sha256'], 'Production bytes differ: '+file['path']
    return file['path']

def check_files(files):
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(verify, files))

mode = sys.argv[1]
current = project()
if mode == 'before':
    assert digest((ROOT/'bundle.zip').read_bytes()) == MANIFEST['bundleSha256']
    checked = check_files(MANIFEST['originals'])
    with zipfile.ZipFile(ROOT/'bundle.zip') as archive:
        assert all(not Path(p).is_absolute() and '..' not in Path(p).parts for p in archive.namelist())
        assert set(archive.namelist()) == {f['path'] for f in MANIFEST['files']}
        for file in MANIFEST['files']:
            assert digest(archive.read(file['path'])) == file['sha256'], file['path']
        archive.extractall('site')
    result = {'phase':mode,'originalFilesVerified':len(checked),'previousDeployment':current['canonical_deployment']['id'],'bundleVerified':True}
elif mode == 'after':
    entry = next(f for f in MANIFEST['files'] if f['path']=='crown-clash/index.html')
    for attempt in range(24):
        try:
            verify(entry)
            break
        except (AssertionError,urllib.error.HTTPError,urllib.error.URLError):
            if attempt==23:raise
            time.sleep(5)
    checked = check_files(MANIFEST['files'])
    result = {'phase':mode,'filesVerified':len(checked),'originalFilesPreserved':len(MANIFEST['originals']),
              'url':ORIGIN+'/crown-clash/','deployment':project()['canonical_deployment']['id']}
else:
    raise RuntimeError('Expected before or after')
(REPORTS/(mode+'.json')).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
