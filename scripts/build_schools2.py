# 驗證OSM座標所在鄉鎮市區＝名錄地址鄉鎮市區；歧義者以鄉鎮挑選；其餘以ArcGIS地址定位（score>=90且落在同鄉鎮）
import json, glob, collections, urllib.request, urllib.parse, time, os
from shapely.geometry import Point, shape
from shapely.strtree import STRtree
D='/workspace/taiwan-school-map/data/'
rows=json.load(open('/workspace/taiwan-school-map/raw/schools_stage1.json'))
geoms=[];props=[]
for f in glob.glob(D+'c/*/villages.json'):
    for ft in json.load(open(f))['features']:
        geoms.append(shape(ft['geometry'])); props.append(ft['properties'])
tree=STRtree(geoms)
def where(lat,lon):
    p=Point(lon,lat)
    for i in tree.query(p):
        if geoms[i].contains(p): return props[i]
    return None
cache_f='/workspace/taiwan-school-map/raw/arcgis_cache.json'
cache=json.load(open(cache_f)) if os.path.exists(cache_f) else {}
def arc(addr):
    if addr in cache: return cache[addr]
    u='https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?'+urllib.parse.urlencode(dict(SingleLine=addr,countryCode='TWN',maxLocations=1,outFields='Score,Addr_type,Match_addr',f='json'))
    try:
        j=json.load(urllib.request.urlopen(u,timeout=20)); c=j.get('candidates',[])
        cache[addr]=c[0] if c else None
    except Exception as e: cache[addr]={'err':str(e)}
    time.sleep(0.15); return cache[addr]
st=collections.Counter()
for r in rows:
    ok=False
    if 'lat' in r:
        w=where(r['lat'],r['lon'])
        if w and w['t']==r['town']: ok=True; r['vill_at']=w['v']
        else: st['osm_town_mismatch']+=1; r['osm_rej']=r.pop('src'); r.pop('lat');r.pop('lon')
    elif 'amb' in r:
        good=[c for c in r['amb'] if (lambda w: w and w['t']==r['town'])(where(c[0],c[1]))]
        if len(good)==1: r.update(lat=good[0][0],lon=good[0][1],src='OSM '+good[0][2]); ok=True; st['amb_resolved']+=1
    if ok: st['osm_ok']+=1; continue
    c=arc(r['addr'])
    if c and 'location' in c and c.get('score',0)>=90:
        w=where(c['location']['y'],c['location']['x'])
        if w and w['t']==r['town']:
            r.update(lat=round(c['location']['y'],6),lon=round(c['location']['x'],6),src=f"ArcGIS地址定位 {c['attributes'].get('Addr_type','')} {c['score']}"); st['arcgis_ok']+=1; continue
    st['no_coord']+=1; r['src']='無可靠座標'
# 同地址（同校區、名錄分列國小/國中部）沿用已驗證座標
byaddr={}
for r in rows:
    if 'lat' in r: byaddr.setdefault(r['addr'],r)
for r in rows:
    if r['src']=='無可靠座標' and r['addr'] in byaddr:
        b=byaddr[r['addr']]; r.update(lat=b['lat'],lon=b['lon'],src=b['src']+'（同地址：'+b['name']+'）'); st['no_coord']-=1; st['same_addr']+=1
json.dump(cache,open(cache_f,'w'),ensure_ascii=False)
print(st)
json.dump(rows,open('/workspace/taiwan-school-map/raw/schools_stage2.json','w'),ensure_ascii=False,indent=0)
for r in rows:
    if r['src']=='無可靠座標': print(r['county'],r['town'],r['name'],r['addr'])
