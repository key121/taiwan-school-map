# 每縣市 schools.json（教育部名錄＋座標）與已收錄縣市 zones.json（官方學區表 → 里/鄰區段規則）
import json, collections, re, pandas as pd, os
D='/workspace/taiwan-school-map/data/'
rows=json.load(open('/workspace/taiwan-school-map/raw/schools_stage2.json'))
cty=json.load(open(D+'counties.geojson'))['features']
code_of={f['properties']['name']:f['properties']['code'] for f in cty}
# ---- schools per county ----
byc=collections.defaultdict(list)
for r in rows:
    o={k:r.get(k) for k in ('code','name','lv','pub','town','addr','tel','url','lat','lon','src')}
    o['id']=r['code']+r['lv']
    byc[r['county']].append(o)
for cn,L in byc.items():
    json.dump(L,open(D+f'c/{code_of[cn]}/schools.json','w'),ensure_ascii=False,separators=(',',':'))
def find(cn,lv,code=None,name=None):
    L=[s for s in byc[cn] if s['lv']==lv]
    if code:
        c=[s for s in L if s['code']==code.rstrip('J')]
        assert len(c)==1,(cn,lv,code,name,c); return c[0]['id']
    def k(n): return re.sub(r'^(市立|縣立|國立|私立)','',n).replace('附設國中','').replace('(國中部)','').replace('(國小部)','')
    c=[s for s in L if k(s['name'])==k(name)]
    assert len(c)==1,(cn,lv,name,[s['name'] for s in c]); return c[0]['id']
def segs_from_rows(rr):
    """rr: list of (a,b,set_ids,text). 999=至最後一鄰。回傳不重疊區段，每段為覆蓋該段之所有學校聯集"""
    pts=sorted(set([a for a,b,_,_ in rr]+[b+1 for a,b,_,_ in rr]))
    out=[]
    for x,y in zip(pts,pts[1:]):
        s=set(); t=[]
        for a,b,ss,tx in rr:
            if a<=x and y-1<=b: s|=ss; t.append(tx)
        if not s: continue
        if out and out[-1]['s']==sorted(s) and out[-1]['b']==x-1 and sorted(set(out[-1]['t']+t))==sorted(set(out[-1]['t']+t)):
            out[-1]['b']=y-1; out[-1]['t']=sorted(set(out[-1]['t']+t))
        else: out.append(dict(a=x,b=y-1,s=sorted(s),t=sorted(set(t))))
    return out
# ---- 臺北市 ----
def taipei():
    cn='臺北市'; Z=collections.defaultdict(lambda: collections.defaultdict(list)); cross=collections.defaultdict(lambda: collections.defaultdict(list))
    namecode={}
    for fn,lv in [('tpe_elem_115.csv','e'),('tpe_jun_115.csv','j')]:
        d=pd.read_csv('/workspace/taiwan-school-map/raw/'+fn,dtype=str).fillna('')
        d.columns=[c.replace('（','').replace('）','') for c in d.columns]
        for _,r in d.iterrows(): namecode[(lv,r['學校名稱'])]=r['學校代碼']
        for _,r in d.iterrows():
            vill=r['村里'].replace('糖?里','糖廍里').replace('糖\ufffd里','糖廍里')
            sid=find(cn,lv,code=r['學校代碼'])
            ss={sid}
            for sh in re.split('[，,、]',r['共同學區學校']):
                sh=sh.strip()
                if sh: ss.add(find(cn,lv,code=namecode[(lv,sh)]) if (lv,sh) in namecode else find(cn,lv,name=sh))
            a,b=int(r['起始鄰']),int(r['結束鄰'])
            txt=f"{r['學校名稱']}：{r['村里']}{'全里' if (a==1 and b==999) else (f'{a}鄰' if a==b else f'{a}-{b if b!=999 else '末'}鄰')}"+(f"（共同學區：{r['共同學區學校']}）" if r['共同學區學校'] else '')
            tgt=Z if r['縣市']==cn else cross
            tgt[r['鄉鎮市區']+'|'+vill][lv].append((a,b,ss,txt))
    meta=dict(county=cn,years='115',title='臺北市115學年度國民小學／國民中學里鄰學區對照表',
      source_page='https://data.taipei/dataset/detail?id=678c5215-f14a-47e3-92bd-da43f9d7c7a9',
      source_files=['https://data.taipei/api/dataset/678c5215-f14a-47e3-92bd-da43f9d7c7a9/resource/4ebe14e0-5539-4b43-985c-d3a0a5b351c9/download','https://data.taipei/api/dataset/678c5215-f14a-47e3-92bd-da43f9d7c7a9/resource/bb9a06d4-69b1-4987-8660-858790f389b3/download'],
      publisher='臺北市政府教育局（臺北市資料大平臺，政府資料開放授權條款第1版）',
      method='機器可讀CSV（學校、村里、起始鄰、結束鄰、共同學區學校）直接轉換；結束鄰999＝至該里最後一鄰。',
      notes=['表列「共同學區學校」者，該里鄰可擇一就讀；實際入學仍依戶籍、設籍時間及各校額滿／總量管制等規定，以學校及臺北市教育局公告為準。'])
    return cn,Z,meta,cross
def keelung():
    cn='基隆市'; k=json.load(open('/workspace/keelung-school-map/data/schooldata.json'))
    Z=collections.defaultdict(dict)
    for v in k['villages']:
        for lvk,lv in (('elem','e'),('junior','j')):
            g=v[lvk]; rr=[]
            off='；'.join(f"{o['school']}：{v['vill']}{o['text']}" for o in g.get('official',[]))
            for grp in g['groups']:
                ids={find(cn,lv,name=n) for n in grp['schools']}
                L=sorted(grp['lins'])
                # 連續鄰壓成區段
                st=L[0];pv=L[0]
                for x in L[1:]+[None]:
                    if x is not None and x==pv+1: pv=x; continue
                    rr.append((st,pv,ids,off)); 
                    if x is not None: st=pv=x
            segs=segs_from_rows(rr)
            Z[v['dist']+'|'+v['vill']][lv]=segs
        Z[v['dist']+'|'+v['vill']]['lins']=[min(v['lins']),max(v['lins'])]
    m=k['meta']
    meta=dict(county=cn,years=m.get('years','115、116'),title=m['title']+'（115學年度表列逐列相同）',source_page=m['source_page'],source_files=[m['source_pdf'],m.get('prev_pdf')],
      publisher='基隆市政府教育處',method='官方PDF逐列解析，並以內政部戶政司基隆市門牌資料（含鄰）逐筆驗證：97,956門牌、0不符。另有基隆專版（門牌精確比對）。',
      notes=m['notes'],flags=None, doorplate=True)
    return cn,Z,meta,None
reg_cov={}
for fn in (keelung,taipei):
    cn,Z,meta,cross=fn()
    out={'meta':meta,'v':{}}
    for key,lv in Z.items():
        o={}
        for l in ('e','j'):
            if l in lv:
                o[l]=lv[l] if isinstance(lv[l],list) and (not lv[l] or isinstance(lv[l][0],dict)) else segs_from_rows(lv[l])
        if 'lins' in lv: o['lins']=lv['lins']
        out['v'][key]=o
    code=code_of[cn]
    # 覆蓋檢查：每個村里界的里都要有國小、國中規則
    vf=json.load(open(D+f'c/{code}/villages.json'))['features']
    keys=set(f"{f['properties']['t']}|{f['properties']['v']}" for f in vf if f['properties']['v'])
    miss={l:sorted(k for k in keys if not out['v'].get(k,{}).get(l)) for l in 'ej'}
    extra=sorted(set(out['v'])-keys)
    out['meta']['check']=dict(villages=len(keys),missing_e=miss['e'],missing_j=miss['j'],not_in_boundary=extra)
    json.dump(out,open(D+f'c/{code}/zones.json','w'),ensure_ascii=False,separators=(',',':'))
    print(cn,'zones',len(out['v']),'missing',{l:len(miss[l]) for l in miss},miss,'extra',extra,os.path.getsize(D+f'c/{code}/zones.json')//1024,'KB')
    if cross:
        cx={k:{l:segs_from_rows(v[l]) for l in v} for k,v in cross.items()}
        json.dump({'meta':dict(from_county=cn,title='臺北市115學年度國中學區表中列入之新北市里（跨縣市）',source_page=meta['source_page']),'v':cx},open(D+f"c/{code_of['新北市']}/cross_{code}.json",'w'),ensure_ascii=False,separators=(',',':'))
        print(' cross-county',list(cx))
