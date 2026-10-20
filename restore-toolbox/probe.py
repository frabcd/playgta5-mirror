import argparse, http.cookiejar, json, os, re, urllib.error, urllib.request, time
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument("--origin")
parser.add_argument("--log",type=Path)
args=parser.parse_args()
origin=args.origin or re.findall(r"https://[a-f0-9]+\\.fran-abcd-abcd\\.pages\\.dev",args.log.read_text())[-1]
jar=http.cookiejar.CookieJar()
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def request(path,data=None):
    headers={"User-Agent":"Frान-Toolbox-DeploymentCheck/1.0".replace("Frान","Fran")}
    if data is not None: headers.update({"Content-Type":"application/json","Origin":origin})
    return opener.open(urllib.request.Request(origin+path,data=data,headers=headers),timeout=90)
def get(path):
    for attempt in range(4):
        try:
            with request(path) as response:
                assert response.status==200
                return response.read()
        except urllib.error.HTTPError:
            if attempt==3: raise
            time.sleep(5)
assert b'href="/calculator"' in get("/")
for path in ["/calculator","/notes","/timer","/wheel","/calculator/games-career"]: get(path)
assert b'/calculator/gta-v/' in get("/calculator")
assert b'type="password"' in get("/calculator/gta-v/play")
try: request("/api/game-unlock",json.dumps({"password":"incorrect"}).encode())
except urllib.error.HTTPError as error: assert error.code==401
else: raise AssertionError("Wrong password accepted")
with request("/api/game-unlock",json.dumps({"password":os.environ["GTA_PASSWORD"]}).encode()) as response:
    assert response.status==200
    cookie=response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=Strict" in cookie
assert b"9104c0b6.fran-abcd-abcd.pages.dev" in get("/calculator/gta-v/play")
report={"origin":origin,"toolbox_and_original_routes":True,"calculator_entry":True,"anonymous_access_blocked":True,"wrong_password_rejected":True,"correct_password_accepted":True,"protected_game_frame":True}
Path("reports").mkdir(exist_ok=True)
Path("reports/"+("production" if args.origin else "preview")+".json").write_text(json.dumps(report,indent=2))
print(json.dumps(report))
