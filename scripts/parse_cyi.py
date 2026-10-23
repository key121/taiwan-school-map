"""嘉義市 115學年度 國中小學區劃分表（data.gov.tw 52485／data.chiayi.gov.tw CSV，自由文字，依校列出）→ zones 格式。
嚴格模式：無法解析者記入 unparsed，不猜測；路段／門牌／年度條件標記為 m 並保留原文；國中依男、女生分校者標記 f='g'。"""
import re,json,csv,collections,os
B='/workspace/taiwan-school-map/'
V=json.load(open(B+'data/c/10020/villages.json'))
VB={};VN={}
for f in V['features']:
    p=f['properties']
    if p.get('v'):
        VB[(p['t'],p['v'])]=p['L']; VN[re.sub(r'[\[\]]','',p['v'])]=(p['t'],p['v'])
S=json.load(open(B+'data/c/10020/schools.json'))
def sid(name,lv):
    n=re.sub(r'[（(].*?[)）]','',name).strip()
    n={'大業實中':'大業實驗國中','嘉大附小':'嘉義大學附小'}.get(n,n)
    hit=[s for s in S if s['lv']==lv and s['pub']=='公立' and n in s['name']]
    assert len(hit)==1,(name,hit); return hit[0]['id']
def norm(s):
    for i,c in enumerate('０１２３４５６７８９'): s=s.replace(c,str(i))
    return s.replace('～','-').replace('~','-').replace('－','-').replace('（','(').replace('）',')').replace('〈','(').replace('〉',')').replace(' ','').replace('磚?里','磚磘里')
EXTRA={}
rows=list(csv.DictReader(open(B+'raw/cyi_115.csv',encoding='utf-8-sig')))
unparsed=[];notes=collections.defaultdict(list)
A={'e':collections.defaultdict(lambda:collections.defaultdict(lambda:{'s':set(),'m':[],'t':[]})),
   'j':{'女':collections.defaultdict(lambda:collections.defaultdict(lambda:{'s':set(),'m':[],'t':[]})),'男':collections.defaultdict(lambda:collections.defaultdict(lambda:{'s':set(),'m':[],'t':[]}))}}
def linset(spec,L):
    spec=spec.replace('鄰','')
    exc=False
    m=re.fullmatch(r'\((?:不含)?([\d、\-]+)(?:除外)?\)',spec)
    if m and ('除外' in spec or '不含' in spec): exc=True; spec=m.group(1)
    out=set()
    if spec=='' : return set(range(1,L+1))
    for p in spec.split('、'):
        mm=re.fullmatch(r'(\d+)(?:-(\d+))?',p)
        if not mm: return None
        a=int(mm.group(1));b=int(mm.group(2) or a); out|=set(range(a,b+1))
    return set(range(1,L+1))-out if exc else out
for r in rows:
    name=r['校名'].strip(); raw=r['學區範圍'].strip()
    lv='j' if '國中' in name or '實中' in name else 'e'
    gender='女' if '女生' in name else '男' if '男生' in name else None
    id_=sid(name,lv)
    s=norm(raw)
    # 抽出說明文字（不作為範圍）
    for pat in [r'附註：.*$',r'※.*$',r'、?由宣信國小發入學通知單.*$']:
        m=re.search(pat,s)
        if m: notes[id_].append(m.group(0).lstrip('、')); s=s[:m.start()]
    s=re.sub(r'(興安與宣信共同學區|宣信與興安之共同學區)：',lambda m:(notes[id_].append(m.group(1)+'（下列里鄰）') or '、'),s)
    s=re.sub(r'。\d\.','、',s); s=re.sub(r'、?\d\.(?=\S+里)','、',s)
    s=re.sub(r'—(南興與大業共同學區)。?',lambda m:(notes[id_].append('興仁里：'+m.group(1)) or ''),s)
    extra=[]
    def drop(m):
        notes[id_].append(m.group(0).strip()[1:-1])
        mm=re.fullmatch(r'\s*\((\S+?里)([\d、\-]+鄰)與\S+?共同學區\)',m.group(0))
        if mm and mm.group(1) in VN: extra.append(mm.group(1)+mm.group(2)); EXTRA[(name,mm.group(1))]=m.group(0).strip()   # 例：嘉大附小列「(中山里18鄰與林森國小共同學區)」即本校亦含中山里18鄰
        return ''
    s=re.sub(r'\s*\([^()]*共同學區\)',drop,s)
    if extra: s=s.rstrip('。')+'、'+'、'.join('¤'+x for x in extra)
    s=s.rstrip('。').replace('，','、').replace('，','、')
    # 保護括號內容
    P=[]
    s=re.sub(r'\(([^()]*)\)',lambda m:(P.append(m.group(1)) or f'§{len(P)-1}§'),s)
    s=re.sub(r'及(?=\d)','、',s)
    pieces=[x for x in re.split(r'[、，。]',s) if x]
    groups=[]  # [vname, [ (linspec, cond) ]]
    for pc in pieces:
        isx=pc.startswith('¤'); pc=pc.lstrip('¤')
        m=re.match(r'^(\S+?里)(.*)$',pc)
        if m and m.group(1) in VN: groups.append([m.group(1),[],isx]); rest=m.group(2)
        elif groups and re.match(r'^[\d\-]',pc): rest=pc
        else: unparsed.append((name,pc)); continue
        cond=None
        mm=re.search(r'§(\d+)§',rest)
        if mm:
            c=P[int(mm.group(1))]
            if re.fullmatch(r'(不含)?[\d、\-]+鄰(除外)?',c) and ('除外' in c or '不含' in c): rest=rest.replace(mm.group(0),'('+c+')')
            else: cond=c; rest=rest.replace(mm.group(0),'')
        m2=re.match(r'^(\([^()]*\)|[\d\-]*鄰?)(.*)$',rest)
        spec,tail=m2.group(1),m2.group(2)
        if tail: cond=(cond+'；' if cond else '')+tail
        groups[-1][1].append([spec,cond])
    for vname,items,isx in groups:
        t,v=VN[vname]; L=VB[(t,v)]
        # 若條件出現在群組最後一項且該項以「鄰」結尾 → 套用整組（保守）
        if len(items)>1 and items[-1][1] and items[-1][0].endswith('鄰') and not any(c for _,c in items[:-1]):
            for it in items: it[1]=items[-1][1]
        # 群組中「1-7、9-18鄰」：鄰字只在最後
        rawtxt=vname+'、'.join((sp or '')+(f'({c})' if c else '') for sp,c in items)
        if isx: rawtxt=EXTRA[(name,vname)]
        for spec,cond in items:
            ls=linset(spec,L)
            if ls is None: unparsed.append((name,vname+spec)); continue
            over=[n for n in ls if n>L]
            if over: unparsed.append((name,f'{vname}{spec} 超出戶政司鄰數{L}'))
            tgt=[A['e']] if lv=='e' else ([A['j'][gender]] if gender else [A['j']['女'],A['j']['男']])
            for T in tgt:
                for n in ls:
                    if n>L: continue
                    a=T[(t,v)][n]; a['s'].add(id_); a['t'].append(f"{name}：{rawtxt}")
                    if cond: a['m'].append(f"{re.sub(r'[（(].*?[)）]','',name)}：{vname}{spec}（{cond}）")
def segs(get,key,L):
    out=[]
    for n in range(1,L+1):
        x=get(key,n)
        if not x: sig=None
        else: sig=json.dumps(x,ensure_ascii=False,sort_keys=True)
        if out and out[-1][2]==sig: out[-1][1]=n
        else: out.append([n,n,sig])
    res=[]
    for a,b,sig in out:
        if sig is None: continue
        x=json.loads(sig); x['a']=a; x['b']=999 if b==L else b; res.append(x)
    return res
def getE(key,n):
    a=A['e'][key].get(n)
    if not a: return None
    x={'s':sorted(a['s']),'t':sorted(set(a['t']))}
    if a['m']: x['m']=sorted(set(a['m']))
    if len(x['s'])>1: x['f']='shared'
    return x
def getJ(key,n):
    g=A['j']['女'][key].get(n); b=A['j']['男'][key].get(n)
    if not g and not b: return None
    G=sorted(g['s']) if g else []; Bo=sorted(b['s']) if b else []
    s=sorted(set(G)|set(Bo)); t=sorted(set((g['t'] if g else [])+(b['t'] if b else [])))
    m=sorted(set((g['m'] if g else [])+(b['m'] if b else [])))
    x={'s':s,'t':t}
    if m: x['m']=m
    if G!=Bo: x['f']='g'; x['g']={'女':G,'男':Bo}
    elif len(s)>1: x['f']='shared'
    return x
Z={};gaps={'e':[],'j':[]};half={'j':[]}
for key,L in sorted(VB.items()):
    k='|'.join(key); Z[k]={'e':segs(getE,key,L),'j':segs(getJ,key,L)}
    for lv in 'ej':
        cov=set()
        for x in Z[k][lv]: cov|=set(range(x['a'],(L if x['b']==999 else x['b'])+1))
        miss=sorted(set(range(1,L+1))-cov)
        if miss: gaps[lv].append(f"{k}:{','.join(map(str,miss))}")
    for x in Z[k]['j']:
        if x.get('f')=='g' and (not x['g']['女'] or not x['g']['男']): half['j'].append((k,x['a'],x['b'],x['g']))
print('unparsed',len(unparsed)); [print('  U',u) for u in unparsed]
print('gaps',json.dumps(gaps,ensure_ascii=False))
print('one-gender-only segments',len(half['j'])); [print('  H',h) for h in half['j']]
for lv in 'ej':
    print(lv,'multi',sum(1 for v in Z.values() for x in v[lv] if len(x['s'])>1),'cond',sum(1 for v in Z.values() for x in v[lv] if x.get('m')),'gender',sum(1 for v in Z.values() for x in v[lv] if x.get('f')=='g'))
json.dump({'Z':Z,'notes':notes,'gaps':gaps,'unparsed':unparsed,'half':half},open(B+'raw/cyi_draft.json','w'),ensure_ascii=False)

# ---------- export ----------
for k,v in Z.items():
    for lv in 'ej':
        for x in v[lv]:
            x['t']=list(dict.fromkeys(x['t']))
SN={}
for i,n in notes.items():
    keep=[x for x in n if x.startswith(('附註','※','由宣信'))]
    if keep: SN[i]='；'.join(dict.fromkeys(keep))
meta={'county':'嘉義市','years':'115','title':'嘉義市115學年度國中小學區劃分表',
 'source_page':'https://data.gov.tw/dataset/52485',
 'source_files':['嘉義市政府 開放資料「嘉義市國中小學區劃分表」115學年度學區劃分 CSV（data.chiayi.gov.tw getResource oid=926c08ec…，rid=e5d36aee…；資料集更新 2026-01-16）'],
 'publisher':'嘉義市政府（教育處）',
 'method':'官方CSV「學區範圍」欄為依校列出之文字敘述；以程式逐項解析里名與鄰別（scripts/parse_cyi.py），路段／門牌／年度等條件不拆分，標示「依門牌或條件分屬」並保留原文；國中依男、女生分校者分別標示。每一結果均附官方原文供核對。',
 'notes':['嘉義市部分國中依性別分校（嘉義國中：女生；蘭潭國中：男生；北興國中分列男生、女生學區），結果分列男生／女生就讀學校；表列「共同學區」者可擇一（仍依各校規定）。實際入學以學校及嘉義市政府教育處公告為準。','本表為自動解析，已逐鄰檢核涵蓋（84里每一鄰均有國小、國中）並人工抽查原文；如結果與原文不同，以原文為準。','官方CSV將「磚磘里」之「磘」字存為「?」，本站依村里名稱對應為磚磘里。'],
 'check':{'villages':len(Z),'gaps_e':gaps['e'],'gaps_j':gaps['j'],'unparsed':[f"{a}：{b}" for a,b in unparsed]},
 'auto_parsed':True,'multi_label':'共同學區'}
json.dump({'meta':meta,'v':Z,'school_notes':SN},open(B+'data/c/10020/zones.json','w'),ensure_ascii=False,separators=(',',':'))
print('exported',len(Z),os.path.getsize(B+'data/c/10020/zones.json'))
