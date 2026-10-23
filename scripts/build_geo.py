# 全國村里界 → 每縣市一檔（簡化），加縣市外框
import geopandas as gpd, json, os, shapely
from shapely.geometry import mapping
SHP='/workspace/keelung-school-map/raw/village/VILLAGE_NLSC_1150817.shp'
OUT='/workspace/taiwan-school-map/data/'
g=gpd.read_file(SHP)
def rnd(geom,nd=5):
    return shapely.set_precision(geom,10**-nd)
def fc(feats): return {"type":"FeatureCollection","features":feats}
counties=[]
for (cc,cn),sub in g.groupby(['COUNTYCODE','COUNTYNAME']):
    os.makedirs(OUT+f'c/{cc}',exist_ok=True)
    feats=[]
    for _,r in sub.iterrows():
        geom=r.geometry.simplify(0.00006,preserve_topology=True)
        geom=rnd(geom)
        if geom.is_empty: continue
        feats.append({"type":"Feature","properties":{"c":r.VILLCODE,"t":r.TOWNNAME,"v":r.VILLNAME if isinstance(r.VILLNAME,str) else "","n":r.NOTE if isinstance(r.NOTE,str) else ""},"geometry":mapping(geom)})
    json.dump(fc(feats),open(OUT+f'c/{cc}/villages.json','w'),ensure_ascii=False,separators=(',',':'))
    outline=sub.geometry.union_all().simplify(0.003,preserve_topology=True)
    outline=rnd(outline,4)
    b=sub.total_bounds
    counties.append({"type":"Feature","properties":{"code":cc,"name":cn,"bbox":[round(x,4) for x in b],"towns":sorted(sub.TOWNNAME.unique().tolist()),"nvill":int(sub.VILLNAME.notna().sum())},"geometry":mapping(outline)})
    print(cc,cn,len(feats),os.path.getsize(OUT+f'c/{cc}/villages.json')//1024,'KB')
json.dump(fc(counties),open(OUT+'counties.geojson','w'),ensure_ascii=False,separators=(',',':'))
print('counties.geojson',os.path.getsize(OUT+'counties.geojson')//1024,'KB')
