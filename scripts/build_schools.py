# 教育部115學年度國中小名錄（全國）＋ OSM 座標比對
import pandas as pd, json, re, os, collections
import geopandas as gpd
from shapely.geometry import Point, shape
RAW='/workspace/keelung-school-map/raw/'
OUT='/workspace/taiwan-school-map/data/'
osm=json.load(open('/workspace/taiwan-school-map/raw/osm_schools.json'))['elements']
cty=json.load(open(OUT+'counties.geojson'))['features']
cpoly=[(f['properties']['name'],shape(f['geometry'])) for f in cty]
towns=set(t for f in cty for t in f['properties']['towns'])
cnames=[f['properties']['name'] for f in cty]
ctowns={f['properties']['name']:f['properties']['towns'] for f in cty}
FW=str.maketrans('０１２３４５６７８９','0123456789')
def core(n):
    n=n.replace('台','臺').replace(' ','').replace('　','')
    n=n.replace('國民中小學','國中小').replace('高級中等學校','高中').replace('高級中學','高中').replace('國(中)小','國中小').replace('國中(小)','國中小')
    n=re.sub(r'\(.*?\)|（.*?）','',n)
    n=n.replace('國民小學','國小').replace('國民中學','國中').replace('附設國中部','附設國中')
    for c in cnames:
        if n.startswith(c): n=n[len(c):]
    n=re.sub(r'^(市立|縣立|國立|私立|市|縣)','',n)
    for t in sorted(towns,key=len,reverse=True):
        if n.startswith(t) and len(n)>len(t)+2: n=n[len(t):]; break
    n=re.sub(r'^(市立|縣立|國立|私立)','',n)
    return n
# OSM index
oi=collections.defaultdict(list)
for e in osm:
    t=e.get('tags',{}); 
    lat=e.get('lat') or e.get('center',{}).get('lat'); lon=e.get('lon') or e.get('center',{}).get('lon')
    if lat is None: continue
    names=set(v for k,v in t.items() if k in('name','name:zh','name:zh-Hant','official_name','alt_name','old_name','short_name') and v)
    for nm in names:
        for part in nm.split(';'):
            oi[core(part)].append((lat,lon,e['type']+'/'+str(e['id']),nm))
def county_of(lat,lon):
    p=Point(lon,lat)
    for n,g in cpoly:
        if g.contains(p): return n
    return None
rows=[]
for f,lv in [('e1_new','e'),('j1_new','j'),('aj_new','j')]:
    x=pd.read_excel(RAW+f'moe115_{f}.xlsx',dtype=str,header=None)
    hdr=[i for i,r in x.iterrows() if any('學校名稱'==str(v) for v in r)][0]
    x.columns=x.iloc[hdr]; x=x.iloc[hdr+1:]
    for _,r in x.iterrows():
        if not isinstance(r['學校名稱'],str): continue
        cn=re.sub(r'^\[\d+\]','',r['縣市名稱']).replace('台','臺')
        addr=re.sub(r'^\[\d+\]','',str(r['地址'])).translate(FW)
        rest=addr[len(cn):] if addr.startswith(cn) else addr
        tw=[t for t in ctowns[cn] if rest.startswith(t)]
        rows.append(dict(code=r['代碼'],name=r['學校名稱'],lv=lv,pub=r['公/私立'],county=cn,town=max(tw,key=len) if tw else '',addr=addr,tel=r['電話'],url=r['網址'] if isinstance(r['網址'],str) else ''))
print('MOE rows',len(rows),collections.Counter(r['county'] for r in rows))
stat=collections.Counter()
for r in rows:
    k=core(r['name']); cands=[c for c in oi.get(k,[]) ]
    # also try 國中小 variants
    if not cands and k.endswith('附設國中'): cands=oi.get(k[:-4],[])
    if not cands and '國中(小)' in r['name']: cands=oi.get(k.replace('國中','國中小'),[])
    if not cands and '國中(小)' in r['name']: cands=oi.get(k.replace('國中','國小'),[])
    cands=[c for c in cands if county_of(c[0],c[1])==r['county']]
    # dedupe near-identical
    uniq=[]
    for c in cands:
        if all(abs(c[0]-u[0])+abs(c[1]-u[1])>0.003 for u in uniq): uniq.append(c)
    if len(uniq)==1:
        r.update(lat=round(uniq[0][0],6),lon=round(uniq[0][1],6),src='OSM '+uniq[0][2],osmname=uniq[0][3]); stat['osm']+=1
    elif len(uniq)>1:
        r['amb']=[(round(c[0],5),round(c[1],5),c[2]) for c in uniq]; stat['amb']+=1
    else: stat['none']+=1
print(stat)
json.dump(rows,open('/workspace/taiwan-school-map/raw/schools_stage1.json','w'),ensure_ascii=False,indent=0)
