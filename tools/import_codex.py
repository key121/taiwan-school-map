#!/usr/bin/env python3
"""Re-runnable importer: Codex school-map data (key121/mortgage-lab public/school-map) + our
county data  ->  beta/data/ of this repo.  Ours stays primary wherever both exist.

Usage:  python3 tools/import_codex.py [--codex DIR] [--county-data DIR] [--log DIR]
Re-run after Codex pushes new data (git pull mortgage-lab first). Live pages are never touched:
it only writes beta/data/**. Disagreements are logged to --log (default /workspace/school-map-beta-qa).
Source data: government open data (政府資料開放授權條款第1版); credits are kept in registry.json.
"""
import json, gzip, os, re, sys, argparse, hashlib, collections, shutil
sys.path.insert(0, os.path.dirname(__file__))
from addrnorm import norm, door_key, road_of, canon, wild_regex

ap=argparse.ArgumentParser()
ap.add_argument('--codex',default='/workspace/mortgage-lab/public/school-map')
ap.add_argument('--county-data',default='/workspace/county-data')
ap.add_argument('--log',default='/workspace/school-map-beta-qa')
ap.add_argument('--repo',default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
A=ap.parse_args()
R=A.repo; CX=A.codex; OUT=os.path.join(R,'beta','data'); os.makedirs(A.log,exist_ok=True)
J=lambda p:json.load(open(p,encoding='utf-8'))
def W(p,o,gz=False):
    os.makedirs(os.path.dirname(p),exist_ok=True)
    b=json.dumps(o,ensure_ascii=False,separators=(',',':')).encode()
    if gz:
        with open(p,'wb') as f: f.write(gzip.compress(b,9,mtime=0))
    else: open(p,'wb').write(b)
    return os.path.getsize(p)

REG=J(os.path.join(R,'data/registry.json')); REGBY={r['code']:r for r in REG}
NAME2CODE={r['name']:r['code'] for r in REG}
OURS_LIVE=['10017','63000','65000','10018','10020']            # already in data/c/*/zones.json
OURS_NEW={'66000':'臺中市','67000':'臺南市','64000':'高雄市','10015':'花蓮縣'}   # /workspace/county-data
RISK={'10002':'宜蘭資料的來源頁是 2018 年宜蘭縣教網部落格頁（標題為108學年度），檔案標示為115學年度（府教學字第1140220776號），尚未在縣府官網直接核對；請以宜蘭縣政府教育處公告為準。'}
PARTIAL={'10010':'嘉義縣','09020':'金門縣','09007':'連江縣'}   # 苗栗 left PARTIAL 2026-10-29: Codex now has the full 151-school current table
RISK['10005']='苗栗縣資料為教育處現行動態查詢表（149列＋2個跨市選項，共151校）；115年公函指定此查詢，但原表未標學年度。門牌／地名特殊條件只列候選，請以教育處學區查詢為準。'
cov=J(os.path.join(CX,'coverage.json'))
CXR={}
for r in cov['regions']:
    city=r['city'].replace('台','臺'); CXR[NAME2CODE[city]]=r
LOG=collections.defaultdict(list)    # code -> disagreement rows
SUM=collections.OrderedDict()

def geo(code):
    v=J(os.path.join(R,f'data/c/{code}/villages.json'))
    out={}
    for f in v['features']:
        p=f['properties']
        if p.get('v'): out[p['t']+'|'+p['v']]=p.get('L') or 0
    return out
def polys(code):
    v=J(os.path.join(R,f'data/c/{code}/villages.json')); out=[]
    for f in v['features']:
        p=f['properties']; g=f['geometry']
        if not p.get('v') or not g: continue
        P=g['coordinates'] if g['type']=='MultiPolygon' else [g['coordinates']]
        xs=[c[0] for poly in P for c in poly[0]]; ys=[c[1] for poly in P for c in poly[0]]
        out.append((p['t']+'|'+p['v'],(min(xs),min(ys),max(xs),max(ys)),P))
    return out
def in_ring(x,y,ring):
    c=False; j=len(ring)-1
    for i in range(len(ring)):
        xi,yi=ring[i][0],ring[i][1]; xj,yj=ring[j][0],ring[j][1]
        if (yi>y)!=(yj>y) and x<(xj-xi)*(y-yi)/(yj-yi+1e-15)+xi: c=not c
        j=i
    return c
def pip(PL,lng,lat,dist=None):
    for key,(a,b,c,d),P in PL:
        if dist and not key.startswith(dist+'|'): continue
        if a<=lng<=c and b<=lat<=d:
            for poly in P:
                if in_ring(lng,lat,poly[0]) and not any(in_ring(lng,lat,h) for h in poly[1:]): return key
    return None
def schools(code): return J(os.path.join(R,f'data/c/{code}/schools.json'))

# ---------------- school-name matching ----------------
ALIAS={'北市大附':'臺北市立大學附','南大附':'臺南大學附','教大實':'教大附','教大附':'教大附','中科實驗':'中科'}
TYPE=re.compile(r'(國際)?(實驗)?(國民)?(高級中等學校|高級中學|完全中學|高中|中學|國中小|國\(中\)小|國\(小\)|國中|國小|小學|實中|實小|附中|附小|附設|工商|商工|中小學)')
def score_name(n): return canon(n).replace('台','臺')
class SchoolMap:
    def __init__(s,code):
        s.list=schools(code); s.code=code; s.by={}
        s.towns=sorted({x['town'] for x in s.list if x.get('town')}|{k.split('|')[0] for k in geo(code)},key=len,reverse=True)
        s.cname=REGBY[code]['name']
        for x in s.list:
            s.by.setdefault((s.base(x['name']),x['lv']),[]).append(x)
        s.extra={}; s.miss=[]; s.cache={}
    def base(s,n):
        n=score_name(n); n=re.sub(r'^(私立|市立|縣立|國立|公立)','',n)
        n=re.sub('^'+s.cname[:2]+'[市縣]?立?','',n)
        for t in s.towns:
            if n.startswith(t) and len(n)>len(t)+2: n=n[len(t):]; break
        for k,v in ALIAS.items():
            if n.startswith(k): n=v+n[len(k):]
        n=re.sub(r'[()（）]','',n)
        if '分校' in n: return n
        m=TYPE.search(n)
        return n[:m.start()] if m and m.start()>0 else n
    def get(s,name,lv,district=None):
        ck=(name,lv,district)
        if ck in s.cache: return s.cache[ck]
        b=s.base(name); c=s.by.get((b,lv))
        if not c and re.search(r'[?？]',name):
            rx=re.compile('^'+re.escape(s.base(re.sub(r'[?？]','Ⓠ',name))).replace('Ⓠ','.')+'$')
            c=[x for (bb,l),xs in s.by.items() if l==lv and rx.match(bb) for x in xs] or None
        if not c:  # loose: unique our school whose base ends/starts with codex base
            c=[x for (bb,l),xs in s.by.items() if l==lv and len(b)>=2 and (bb.endswith(b) or b.endswith(bb) and len(bb)>=2) for x in xs]
            if len({x['id'] for x in c})>1 and district: c=[x for x in c if x['town']==district]
            if len({x['id'] for x in c})!=1: c=None
        if c and district and len({x['id'] for x in c})>1:
            c=[x for x in c if x['town']==district] or None   # same name in several districts: must match district
        if c:
            r=c[0]['id']
        else:
            r='x'+hashlib.md5((name+lv+(district or '')).encode()).hexdigest()[:8]+lv
            if r not in s.extra:
                s.extra[r]={'id':r,'name':name,'lv':lv,'town':district or '','src':'Codex 學校名（未對到教育部名錄）'}
                s.miss.append(name)
        s.cache[ck]=r; return r
    def name(s,i):
        for x in s.list:
            if x['id']==i: return x['name']
        return s.extra.get(i,{}).get('name',i)

# ---------------- Codex rule resolution (mirrors Codex logic.js) ----------------
def matches(r,n): return r['mode']=='all' or (r['mode']=='include' and n in r['neighbors']) or (r['mode']=='exclude' and n not in r['neighbors'])
def possible(r,n): return r['mode']=='conditional' and (not r.get('neighbors') or n in r['neighbors'])
LVL={'elementary':'e','junior':'j'}
def codex_zones(code):
    r=CXR.get(code); loc=r.get('local') if r and isinstance(r.get('local'),dict) else {}
    if not loc.get('zones'): return None
    return J(os.path.join(CX,loc['zones']))
def codex_index(code,city,G,SM,addr_lin):
    """-> {ourkey: {lv: {n: (frozenset confirmed, frozenset possible, texts)}}}, Lmax, dropped"""
    z=codex_zones(code)
    if not z: return None,{},{}
    gcanon={}
    for k in G: t,v=k.split('|'); gcanon[canon(t)+'|'+canon(v)]=k
    per=collections.defaultdict(lambda: collections.defaultdict(list))   # key -> lv -> [(sid,rule)]
    stats=collections.Counter(); unk=set()
    for s in z['schools']:
        lv=LVL.get(s.get('level'));
        if not lv: continue
        sid=None
        for ru in s['rules']:
            rc=(ru.get('city') or city).replace('台','臺')
            if rc!=city: stats['dropped_crosscity']+=1; continue
            if not ru.get('district') or not ru.get('village'): stats['no_village']+=1; continue
            ck=canon(ru['district'])+'|'+canon(ru['village'])
            key=gcanon.get(ck)
            if not key: key=ru['district']+'|'+ru['village']; unk.add(key)
            sid=SM.get(s['name'],lv,s.get('district') or ru['district'])
            per[key][lv].append((sid,ru,s))
    out={}; Lm={}
    for key,lvs in per.items():
        L=G.get(key,0); mx=max([L]+[addr_lin.get(key,0)]+[n for l in lvs.values() for _,ru,_ in l for n in (ru.get('neighbors') or []) if n<999]+[n for l in lvs.values() for _,ru,_ in l for n in (ru.get('knownNeighbors') or [])])
        if mx==0: mx=1
        Lm[key]=mx; out[key]={}
        for lv,lst in lvs.items():
            d={}
            for n in range(1,mx+1):
                C=set();P=set();T=[];F=set()
                for sid,ru,s in lst:
                    if matches(ru,n): C.add(sid); T.append(s['name']+'：'+str(ru.get('raw',''))[:160])
                for sid,ru,s in lst:
                    if sid not in C and possible(ru,n): P.add(sid); T.append(s['name']+'：'+str(ru.get('raw',''))[:160])
                d[n]=(frozenset(C),frozenset(P),tuple(dict.fromkeys(T)))
            out[key][lv]=d
    return out,Lm,{'stats':dict(stats),'unmatched_villages':sorted(unk)}
def segs_from(d,mx):
    """compress {n:(C,P,T)} into our segment list"""
    out=[];cur=None
    for n in range(1,mx+1):
        C,P,T=d.get(n,(frozenset(),frozenset(),()))
        sig=(C,P)
        if not C and not P: cur=None; continue
        if cur and cur['_sig']==sig and cur['b']==n-1:
            cur['b']=n; cur['_t'].update(dict.fromkeys(T)); continue
        cur={'a':n,'b':n,'_sig':sig,'_t':dict.fromkeys(T)}; out.append(cur)
    res=[]
    for c in out:
        C,P=c['_sig']; x={'a':c['a'],'b':c['b'],'s':sorted(C)+sorted(P),'t':list(c['_t'])[:6]}
        if P: x['m']=['條件式（路段、門牌、身分或分發條件）：'+('、'.join(sorted(P)))]; x['p']=sorted(P)
        res.append(x)
    return res

def flags_from_codex(code,SM):
    z=codex_zones(code); fl={}
    if not z: return fl
    for s in z['schools']:
        lv=LVL.get(s.get('level'))
        if not lv: continue
        f=[]
        if s.get('capacityControlled'): f.append('總量管制')
        if s.get('citywideExperimental') or s.get('experimentalEducation'): f.append('實驗教育／全市（縣）學區')
        if f: fl[SM.get(s['name'],lv,s.get('district'))]=f
    return fl

# ---------------- address index ----------------
def addr_manifest(code):
    r=CXR.get(code); loc=r.get('local') if r and isinstance(r.get('local'),dict) else {}
    p=loc.get('addresses')
    return (J(os.path.join(CX,p)),p) if p else (None,None)
def keelung_rows():
    AI=J(os.path.join(R,'keelung/data/address_index.json')); VG=J(os.path.join(R,'keelung/data/villages.geojson'))
    vn={f['properties']['i']:(f['properties']['dist'],f['properties']['vill']) for f in VG['features']}
    for d,sts in AI.items():
        for st,la in sts.items():
            for lk,lst in la.items():
                lane,alley=lk.split('|')
                for rec in lst:
                    num=rec[0].replace('-','之'); t,v=vn[rec[1]]
                    yield (d+st+(lane+'巷' if lane else '')+(alley+'弄' if alley else '')+num+'號', v, d, rec[2], rec[4], rec[3])
RVR={}   # review reason -> 1-based index (per county; reset in write_addr's caller)
def build_addr(code,city,rows_iter,G,meta_src):
    RVR.clear()
    gcanon={}
    for k in G: t,v=k.split('|'); gcanon[canon(t)+'|'+canon(v)]=k
    PL=None; resolved={}; ncity=norm(city)
    by=collections.defaultdict(dict); cnt=collections.Counter(); unknown=collections.Counter(); maxlin={}
    for addr,vill,dist,lin,lat,lng,*ex in rows_iter:
        if not addr or lin is None: cnt['skip']+=1; continue
        rv=None   # Codex optionalBoundaryProvenance: official row flagged for review -> keep, but UI must warn
        if ex and isinstance(ex[0],dict) and ex[0].get('requiresReview'):
            rv=RVR.setdefault(ex[0].get('reviewReason') or '官方資料標記需核對',len(RVR)+1); cnt['requires_review']+=1
        a=norm(addr)
        if a.startswith(ncity): a=a[len(ncity):]
        if a.startswith(norm(dist)): rest=a[len(norm(dist)):]
        else: cnt['nodist']+=1; continue
        rest=re.sub(r'^.{1,5}?[里村]\d+鄰','',rest)
        k=door_key(rest)
        if not k: cnt['nokey']+=1; continue
        orig=None
        key=gcanon.get(canon(dist)+'|'+canon(vill))
        if not key:
            rk=(dist,vill)
            if rk not in resolved:
                rx=wild_regex(vill); cands=[g for g in G if g.startswith(dist+'|') and rx and rx.match(canon(g.split('|')[1]))]
                resolved[rk]=('wild',cands[0]) if len(cands)==1 else ('pip',[c for c in cands])
            how,val=resolved[rk]
            if how=='wild': key=val; cnt['wildcard_resolved']+=1
            else:
                if PL is None: PL=polys(code)
                kk=pip(PL,lng,lat,dist) if lat and lng else None
                if kk and (not val or kk in val):
                    key=kk; orig=vill; cnt['pip_resolved']+=1; unknown[dist+'|'+vill+' →座標判定']+=1
                else:
                    cnt['dropped_unresolved_village']+=1; unknown[dist+'|'+vill+' →丟棄']+=1; continue
        vname=key.split('|')[1]
        rec=[vname,int(lin),round(lat,5) if lat else None,round(lng,5) if lng else None]+([orig] if orig or rv else [])+([rv] if rv else [])
        cur=by[dist].get(k)
        if cur is None: by[dist][k]=[rec]
        elif all((c[0],c[1])!=(rec[0],rec[1]) for c in cur): cur.append(rec)
        if not orig and not rv: maxlin[key]=max(maxlin.get(key,0),int(lin))
        cnt['rows']+=1
    return by,cnt,unknown,maxlin
SHARD_MAX=180_000   # gz bytes; bigger districts are split by road hash (same hash in beta/js)
def rhash(road,nb): return sum(ord(c) for c in road)%nb
def write_addr(code,by,src):
    base=os.path.join(OUT,'a',code); shutil.rmtree(base,ignore_errors=True)
    dists=sorted(by); files={}; roads=collections.defaultdict(set); total=0; amb=0; biggest=0
    for i,d in enumerate(dists):
        vl=sorted({r[0] for recs in by[d].values() for r in recs}); vi={v:j for j,v in enumerate(vl)}
        k={}
        for key,recs in by[d].items():
            if len(recs)>1: amb+=1
            enc=[[vi[r[0]]]+r[1:] for r in recs]
            k[key]=enc[0] if len(enc)==1 else enc
            roads[road_of(key)].add(i)
        for key in list(k):
            if '臨' in key:
                alt=key.replace('臨','')
                if alt not in k: k[alt]=k[key]
        est=len(gzip.compress(json.dumps(k,ensure_ascii=False).encode(),6))
        nb=max(1,-(-est//SHARD_MAX))
        parts=[{} for _ in range(nb)]
        for key,val in k.items(): parts[rhash(road_of(key),nb)][key]=val
        sizes=[]
        for b,part in enumerate(parts):
            sh={'d':d,'v':vl,'k':part}
            if RVR: sh['r']=[t for t,_ in sorted(RVR.items(),key=lambda x:x[1])]
            sz=W(os.path.join(base,f'{i}_{b}.json.gz'),sh,gz=True); sizes.append(sz); total+=sz; biggest=max(biggest,sz)
        files[d]={'i':i,'nb':nb,'keys':len(k),'bytes':sizes}
    rz=W(os.path.join(base,'roads.json.gz'),{r:sorted(v) for r,v in roads.items()},gz=True)
    W(os.path.join(base,'meta.json'),{'d':dists,'f':files,'src':src,'roadsBytes':rz})
    return total,rz,amb,sum(len(v) for v in by.values()),biggest
# ---------------- main per county ----------------
registry=[]; towns=collections.defaultdict(set)
for r in REG:
    code=r['code']; city=r['name']; G=geo(code)
    for k in G: towns[k.split('|')[0]].add(code)
    SM=SchoolMap(code); info={'code':code,'name':city}
    # --- address index (needed first: max 鄰 per 里) ---
    addr_lin={}; ainfo=None
    man,mp=addr_manifest(code)
    if code=='10017':
        by,cnt,unknown,addr_lin=build_addr(code,city,keelung_rows(),G,None)
        src={'name':'內政部戶政司 門牌（本站基隆專版逐筆驗證）','version':'2026-08','url':'https://www.ris.gov.tw/'}
    elif man:
        def it():
            for d,sh in man['shards'].items():
                for row in J_gz(os.path.join(CX,sh['file'])): yield row
        def J_gz(p): return json.load(gzip.open(p))['rows']
        by,cnt,unknown,addr_lin=build_addr(code,city,it(),G,None)
        src={'name':'門牌與里鄰開放資料（Codex 整理）','version':str(man.get('version')),'updated':man.get('updated'),'url':man.get('sourceUrl')}
    else: by=None
    if by:
        tb,rz,amb,keys,big=write_addr(code,by,src)
        ainfo={'keys':keys,'maxShardBytes':big,'counts':dict(cnt),'rows':cnt['rows'],'gzBytes':tb,'roadsBytes':rz,'ambiguous':amb,'unknownVillageRows':sum(unknown.values()),'unknownVillages':dict(unknown.most_common(40)),**src}
    # --- zones ---
    meta_extra={}
    if code in OURS_LIVE or code in OURS_NEW:
        zp=os.path.join(R,f'data/c/{code}/zones.json') if code in OURS_LIVE else os.path.join(A.county_data,code,'zones.json')
        Z=J(zp); origin='ours'
        if code in OURS_NEW:
            re_=J(os.path.join(A.county_data,code,'registry_entry.json'))
        else: re_=r
    else:
        Z=None; origin=None; re_=r
    cx,Lm,cxinfo=codex_index(code,city,G,SM,addr_lin)
    if Z is None and cx:
        v={}
        for key,lvs in cx.items():
            v[key]={lv:segs_from(d,Lm[key]) for lv,d in lvs.items()}
        z=codex_zones(code)
        Z={'meta':{'county':city,'years':str(z.get('year') or ''),'title':city+(str(z.get('year'))+'學年度' if z.get('year') else '')+'國民中小學學區（Codex 由官方公告整理）',
                   'source_page':z.get('sourceUrl'),'source_files':[s if isinstance(s,str) else (s.get('url') or s.get('title') or '') for s in (z.get('sources') or [])][:8],
                   'publisher':city+'政府教育局（處）','method':'由 Codex 整理之官方學區規則轉入（tools/import_codex.py）；條件式規則保留原文、不拆分。',
                   'notes':[str(x) for x in (z.get('limitations') or z.get('notes') or [])][:6] if isinstance(z.get('limitations') or z.get('notes'),list) else [str(z.get('limitations') or z.get('notes') or '')],
                   'auto_parsed':True,'multi_label':'共同／自由學區','updated':z.get('updated'),'incomplete':z.get('incompleteDistricts') or [],
                   'warnings':[str(w)[:300] for w in (z.get('sourceWarnings') or [])][:5]+([RISK[code]] if code in RISK else [])},'v':v}
        origin='codex'
    # disagreements (ours primary)
    if origin=='ours' and cx:
        gname=lambda ids:'、'.join(SM.name(i) for i in sorted(ids))
        n_cmp=n_diff=0
        for key,lvs in Z['v'].items():
            L=G.get(key) or max([x['b'] for l in lvs.values() for x in l if x['b']<999]+[1])
            for lv in ('e','j'):
                segs=lvs.get(lv,[]); cd=(cx.get(key) or {}).get(lv)
                prev=None
                for n in range(1,L+1):
                    o=next((x for x in segs if x['a']<=n<=x['b']),None)
                    on=gname(o['s']) if o else '（未列）'
                    if cd and n in cd: C,P,_=cd[n]; cn=gname(C|P)+('〔含條件式〕' if P else '')
                    else: cn='（Codex 無此里規則）'
                    n_cmp+=1
                    if on!=cn.replace('〔含條件式〕',''):
                        n_diff+=1
                        if prev and prev[3]==n-1 and prev[4]==on and prev[5]==cn: prev[3]=n
                        else: prev=[key,lv,n,n,on,cn]; LOG[code].append(prev)
                    else: prev=None
        for key in cx:
            if key not in Z['v']: LOG[code].append([key,'*',0,0,'（本站無此里）','Codex 有規則'])
        meta_extra['compare']={'checked_lin_levels':n_cmp,'differ':n_diff,'segments':len(LOG[code])}
    if Z is not None:
        Z.setdefault('meta',{}); Z['meta']['origin']=origin
        fl=flags_from_codex(code,SM)
        if fl: Z['sf']={k:v for k,v in fl.items()}
        if SM.extra: Z['extra_schools']=list(SM.extra.values())
        if code=='09007' or code in PARTIAL: Z['meta']['partial']=True
        rl=os.path.join(A.county_data,code,'work','remap_log.json')
        if origin=='ours' and os.path.exists(rl):   # 高雄 115/7/1 里鄰調整
            ren={}; old={}
            for d,olds,new,*_ in J(rl):
                news=new.lstrip('→').split('/')
                for n in news: ren[d+'|'+n]='115.7.1 里鄰調整（原'+olds.replace('+','、')+'）'
                for o in olds.split('+'): old[d+'|'+o]=[d+'|'+n for n in news]
            Z['meta']['renamed']=ren; Z['meta']['old2new']=old
        W(os.path.join(OUT,'c',code,'zones.json'),Z)
    else:
        p=os.path.join(OUT,'c',code,'zones.json')
        if os.path.exists(p): os.remove(p)
    # registry entry
    cxz=codex_zones(code) or {}
    status = 'partial' if code in PARTIAL else ('verified' if origin=='ours' else ('merged' if origin=='codex' else 'none'))
    e={'code':code,'name':city,'status':status,'origin':origin,'hasZones':Z is not None,
       'years':(Z or {}).get('meta',{}).get('years') or re_.get('years',''),
       'source':re_.get('source') if origin=='ours' else ('Codex 整理：'+(cxz.get('sourceUrl') or '') if origin=='codex' else r.get('source')),
       'official':r.get('official') if origin!='codex' else (cxz.get('sourceUrl') or r.get('official')),
       'officialNotice':r.get('official'),
       'verification':re_.get('verification','table-checked') if origin=='ours' else ('machine-parsed-by-codex' if origin=='codex' else None),
       'updated':cxz.get('updated') if origin=='codex' else None,
       'addr':ainfo and {k:ainfo[k] for k in ('keys','name','version','updated','url','gzBytes') if k in ainfo},
       'incomplete':(Z or {}).get('meta',{}).get('incomplete') or [],'cross':r.get('cross'),'warning':RISK.get(code),'villages':len(G),'zoneVillages':len((Z or {}).get('v',{}))}
    if code in PARTIAL:
        e['partialNote']={'10010':'僅收錄 11 校 115 學年度官方公告（太保國中、祥和國小、義竹國小、下楫國小、大同國小、南新國小、福樂國小、圓崇國小、永慶高中國中部、朴子國中、大吉國中），非全縣；查不到的學校不代表不屬該學區，請看官方公告。',
                          '09020':'僅有門牌→里鄰索引，尚無學區規則；學區請看官方公告。',
                          '09007':'尚無資料；請看官方公告。'}[code]
    registry.append(e)
    SUM[code]={'name':city,'status':status,'origin':origin,'zoneVillages':e['zoneVillages'],'geoVillages':len(G),
               'addr':ainfo and {k:ainfo[k] for k in ('keys','rows','gzBytes','roadsBytes','maxShardBytes','ambiguous','unknownVillageRows','counts')},
               'codex':cxinfo and {'stats':cxinfo['stats'],'unmatchedVillages':len(cxinfo['unmatched_villages'])},
               'extraSchools':len(SM.extra),**meta_extra}
    if cxinfo and cxinfo['unmatched_villages']: SUM[code]['codexUnmatchedVillages']=cxinfo['unmatched_villages'][:60]
    if ainfo and ainfo['unknownVillages']: SUM[code]['addrUnknownVillages']=ainfo['unknownVillages']
    print(code,city,status,origin,SUM[code]['zoneVillages'],ainfo and (ainfo['keys'],ainfo['gzBytes']),'diff',meta_extra.get('compare'),'extra',len(SM.extra),flush=True)

W(os.path.join(OUT,'registry.json'),{'built':__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')+' (UTC+8)','codexCheckedAt':cov.get('checkedAt'),'counties':registry})
W(os.path.join(OUT,'towns.json'),{t:sorted(c) for t,c in towns.items()})
json.dump(SUM,open(os.path.join(A.log,'import-summary.json'),'w'),ensure_ascii=False,indent=1)
with open(os.path.join(A.log,'merge-disagreements.tsv'),'w') as f:
    f.write('county\tdistrict|village\tlevel\tfrom_lin\tto_lin\tours(primary)\tcodex\n')
    for code,rows in LOG.items():
        for k,lv,a,b,o,c in rows: f.write(f'{REGBY[code]["name"]}\t{k}\t{lv}\t{a}\t{b}\t{o}\t{c}\n')
print('done')
