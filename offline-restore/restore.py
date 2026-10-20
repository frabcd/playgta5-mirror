"""Restore the original toolbox and remove only this task's hosted GTA deployments."""
import json, os, time, urllib.error, urllib.request
from pathlib import Path
ACCOUNT="591f8fad9d51a834bf7714007337623c"
PROJECT="fran-abcd-abcd"
ORIGINAL="c704d74b-2451-43e7-ae45-2aa1de2308e9"
PREFIXES={"9104c0b6","497c7e3d","3ad2dd94","f724409d","fe9c58a1","58304ee6","2b9d0132"}
BASE=f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/pages/projects/{PROJECT}"
def api(path="",method="GET"):
    headers={"Authorization":"Bearer "+os.environ["CLOUDFLARE_API_TOKEN"],"Content-Type":"application/json"}
    request=urllib.request.Request(BASE+path,headers=headers,method=method,data=b"{}" if method=="POST" else None)
    try:
        with urllib.request.urlopen(request,timeout=120) as response: result=json.load(response)
    except urllib.error.HTTPError as error:
        details=json.load(error)
        raise RuntimeError("Cloudflare API status "+str(error.code)+": "+json.dumps(details.get("errors"))) from None
    if not result.get("success"): raise RuntimeError("Cloudflare operation failed: "+json.dumps(result.get("errors")))
    return result.get("result")
deployments=api("/deployments?per_page=25")
assert any(d["id"]==ORIGINAL and d["environment"]=="production" for d in deployments),"Original toolbox deployment missing"
targets=[d for d in deployments if d["id"].split("-")[0] in PREFIXES]
assert all(d["id"]!=ORIGINAL for d in targets)
api("/deployments/"+ORIGINAL+"/rollback","POST")
for _ in range(12):
    if api()["production_deployment"]["id"]==ORIGINAL: break
    time.sleep(5)
else: raise RuntimeError("Rollback did not become production")
deleted=[]
for deployment in targets:
    assert api()["production_deployment"]["id"]==ORIGINAL,"Production changed; cleanup stopped"
    api("/deployments/"+deployment["id"]+"?force=true","DELETE")
    deleted.append(deployment["id"])
remaining=api("/deployments?per_page=25")
assert not any(d["id"].split("-")[0] in PREFIXES for d in remaining)
def page(path,host="https://fran-abcd-abcd.pages.dev"):
    request=urllib.request.Request(host+path,headers={"User-Agent":"Fran-Restoration-Check/1.0","Cache-Control":"no-cache"})
    try:
        with urllib.request.urlopen(request,timeout=60) as response:return response.status,response.read()
    except urllib.error.HTTPError as error:return error.code,error.read()
for attempt in range(18):
    status,home=page("/")
    calc_status,calculator=page("/calculator")
    gate_status,gate=page("/calculator/gta-v/play")
    if status==200 and b'href="/calculator"' in home and calc_status==200 and b"/calculator/gta-v/" not in calculator and gate_status==404:break
    time.sleep(5)
else: raise RuntimeError("Original public toolbox has not propagated")
for path in ["/notes","/timer","/wheel","/calculator/games-career"]:
    assert page(path)[0]==200,path
assert page("/calculator/gta-v/")[0]==404
assert page("/chunk-index.js")[0]==404
archive_status=page("/chunk-index.js","https://9104c0b6.fran-abcd-abcd.pages.dev")[0]
assert archive_status in (403,404,410),archive_status
report={"original_toolbox_restored":True,"production_deployment":ORIGINAL,"gta_deployments_removed":deleted,"gta_entry_unavailable":True,"game_chunk_index_unavailable":True,"original_tools_preserved":True,"local_packages_untouched":True}
Path("offline-reports").mkdir(exist_ok=True)
Path("offline-reports/restoration.json").write_text(json.dumps(report,indent=2))
print(json.dumps(report))
