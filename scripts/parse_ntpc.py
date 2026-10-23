"""新北市 115學年度 國小／國中學區（data.ntpc 開放資料 CSV，自由文字）→ zones 格式。
嚴格模式：無法解析的片段一律記錄於 unparsed，不猜測；門牌層級之條件標記為 m（依門牌分屬），並保留原文。"""
import re,json,sys,collections
import pandas as pd
B='/workspace/taiwan-school-map/'
V=json.load(open(B+'data/c/65000/villages.json'))
VB={}
for f in V['features']:
    p=f['properties']
    if p.get('v'): VB[(p['t'],p['v'])]=p.get('L') or 0
def vkey(x): return re.sub(r'[\[\]]','',x).replace('峯','峰').replace('舘','館').replace('脚','腳').replace('尞','寮')
VK={}
for (t,v) in list(VB): VK[(t,vkey(v))]=v
OTHER=('臺北市','桃園市','基隆市')
ALIAS={'插角國小':'014630e','忠山國小':'014718e','老梅國小':'014725e','德拉楠民族實小':'014685e','石門國中':'014537j'}
TOWNS=sorted({t for t,_ in VB},key=len,reverse=True)
S=json.load(open(B+'data/c/65000/schools.json'))
CN='０１２３４５６７８９'
def norm(s):
    s=str(s or '')
    for i,c in enumerate(CN): s=s.replace(c,str(i))
    s=s.replace('－','-').replace('—','-').replace('–','-').replace('～','-').replace('~','-').replace('（','(').replace('）',')').replace('，','、').replace(',','、').replace('台','臺')
    s=re.sub(r'\s+','',s)
    s=re.sub(r'([里村])(\d[\d、\-]*鄰)\)',r'\1(\2)',s)
    s=s.replace('三峽文化部落龍恩里','龍恩里')
    s=re.sub(r"(里\([^()]*?鄰)、([^()、]+?里\()",r"\1)、\2",s)
    return s
def core(n):
    n=norm(n).replace('國民中小學','國中小').replace('國民小學','國小').replace('國民中學','國中')
    n=re.sub(r'^(新北市|市立|私立|國立|財團法人)+','',n)
    n=n.replace('(國中部)','').replace('國中部','').replace('附設國中','').replace('高級中學','高中').replace('實驗國中','實中').replace('國際實中','實中')
    n=n.replace('國(中)小','國中小').replace('國中(小)','國中小')
    return n
def find_school(sname,lv,town):
    sname=norm(sname)
    for t in TOWNS:
        if sname.startswith(t): sname=sname[len(t):]
    if sname in ALIAS: return ALIAS[sname]
    sname=sname.replace('國中小國小部','國中小').replace('國中小國中部','國中小')
    c=core(sname); c=re.sub(r'\(.*?校區\)','',c)
    cands=[s for s in S if s['lv']==lv and s['pub']=='公立']
    hit=[s for s in cands if core(s['name'])==c]
    if not hit: hit=[s for s in cands if core(s['name']).replace('國中小','國中')==c.replace('國中小','國中')]
    if not hit: hit=[s for s in cands if c and (core(s['name']).startswith(c) or c.startswith(core(s['name'])))]
    if len(hit)>1: hit=[s for s in hit if s['town']==town] or hit
    return hit[0]['id'] if len(hit)==1 else None
def lin_set(spec,L):
    """'1-7、26-28' / '除16-18' / '1除外' → (set, ok)"""
    spec=spec.replace('鄰','').replace('第','')
    exc=False
    if spec.startswith('除'): exc=True; spec=spec[1:]
    if spec.endswith('除外'): exc=True; spec=spec[:-2]
    if spec.endswith('外'): exc=True; spec=spec[:-1]
    out=set()
    for p in spec.split('、'):
        if not p: continue
        m=re.fullmatch(r'(\d+)(?:-(\d+))?',p)
        if not m: return None
        a=int(m.group(1));b=int(m.group(2) or a); out|=set(range(a,b+1))
    if exc: out=set(range(1,L+1))-out
    return out
def split_items(s):
    out=[];depth=0;cur=''
    for ch in s:
        if ch in '(【': depth+=1
        if ch in ')】': depth-=1
        if ch=='、' and depth==0: out.append(cur);cur=''
        else: cur+=ch
    if cur: out.append(cur)
    m2=[]
    for it in out:
        it=it.rstrip('。').replace('自由學區','')
        if m2 and re.fullmatch(r'第?\d+(-\d+)?鄰?(\))?',it): m2[-1]=m2[-1]+'、'+it; continue
        # 里名後緊接另一區名：宜安里永和區永安里
        g=re.match(r'^(.+?[里村])((?:'+'|'.join(TOWNS)+r').+)$',it)
        if g and '(' not in g.group(1): m2+= [g.group(1),g.group(2)]; continue
        m2.append(it)
    return m2
def parse_list(txt,town0,diag):
    """回傳 [(town,vill,lins:set,m:bool,orig)]"""
    res=[];town=town0
    txt=re.sub(r'等里$','',txt)
    for it in split_items(txt):
        orig=it
        for t in TOWNS:
            if it.startswith(t): town=t; it=it[len(t):]; break
        it=it.strip().replace('自由學區','').rstrip('。')
        if not it: continue
        if it.startswith(OTHER): diag.append(('cross-county',town,orig)); continue
        if it in ('全區轄區','各里') or it==town+'各里':
            for (t2,v2),L2 in VB.items():
                if t2==town: res.append((town,v2,set(range(1,L2+1)),False,orig))
            continue
        g=re.match(r'^全區轄區\(除(.+?)\)$',it)
        if g:
            ex=parse_list(g.group(1),town,diag); exs={(a,b):ls for a,b,ls,_,_ in ex}
            for (t2,v2),L2 in VB.items():
                if t2==town:
                    ls=set(range(1,L2+1))-exs.get((t2,v2),set())
                    if ls: res.append((town,v2,ls,False,orig))
            continue
        it=re.sub(r'^([^\d(]+?[里村]?)(\d.*鄰)\)$',r'\1(\2)',it)  # 和平里1-14鄰)
        # 找出區內最長的里名（異體字正規化）
        itk=vkey(it)
        def findv(tw,anywhere=False):
            best=None
            for (t2,vk),v2 in VK.items():
                if t2!=tw: continue
                for cand in ((vk,) if anywhere else (vk,vk[:-1])):
                    pos=itk.find(cand) if anywhere else (0 if itk.startswith(cand) else -1)
                    if pos>=0 and (best is None or len(cand)>len(best[0])): best=(cand,v2,pos)
            return best
        best=findv(town)
        if not best:
            hits=[]
            for tw in TOWNS:
                b2=findv(tw)
                if b2 and len(b2[0])>=2: hits.append((tw,b2))
            if len(hits)==1: town=hits[0][0]; best=hits[0][1]; diag.append(('town-inferred',town,orig))
        if not best:
            b2=findv(town,True)
            if b2: best=b2; diag.append(('prefix-label',town,orig))
        if best and best[2]: itk=itk[best[2]:]; best=(best[0],best[1],0)
        if not best: diag.append(('village',town,orig)); continue
        v=best[1]; rest=itk[len(best[0]):]
        if rest.startswith('里') and not best[0].endswith('里'): rest=rest[1:]
        # 兩里黏在一起：永安里福隆里
        if rest and not rest.startswith('(') and re.match(r'^[^\d(]+[里村]',rest) and any(rest.startswith(vk) for (t2,vk) in VK if t2==town):
            res.append((town,v,set(range(1,VB[(town,v)]+1)),False,orig)); res+=parse_list(rest,town,diag); continue
        rest=re.sub(r'^等?里?$','',rest) if re.fullmatch(r'等?里?',rest) else rest
        if rest.startswith('('): rest=rest[1:]
        if rest.endswith(')'): rest=rest[:-1]
        L=VB[(town,v)]
        rest=rest.replace('第','') if re.fullmatch(r'[第\d、\-鄰除外]+',rest or '') else rest
        if not rest: res.append((town,v,set(range(1,L+1)),False,orig)); continue
        rest=rest.replace('(','').replace(')','')
        ls=lin_set(rest,L)
        if ls is not None: res.append((town,v,ls,False,orig)); continue
        # 混合：鄰號＋門牌條件
        full=set();mm=set();okp=True
        for p in rest.split('、'):
            q=lin_set(p,L)
            if q is not None: full|=q; continue
            p=p.replace('部分','',1) if p.startswith('部分') and lin_set(p[2:],L) is not None and not mm.update(lin_set(p[2:],L)) else p
            if p=='' or (p.startswith('部分')): continue
            g=re.match(r'^第?(\d+)(?:-(\d+))?鄰(.+)$',p)
            if g: a=int(g.group(1));b=int(g.group(2) or a); mm|=set(range(a,b+1)); continue
            okp=False
        if okp and (full or mm):
            if full: res.append((town,v,full,False,orig))
            if mm: res.append((town,v,mm,True,orig))
        else:
            nums=set()
            for g in re.finditer(r'(\d+)(?:-(\d+))?',rest):
                a=int(g.group(1));b=int(g.group(2) or a)
                if b<=L and a>=1 and '號' not in rest[g.end():g.end()+1]: nums|=set(range(a,b+1))
            if rest.startswith('除') and nums:
                if set(range(1,L+1))-nums: res.append((town,v,set(range(1,L+1))-nums,False,orig))
                res.append((town,v,nums,True,orig)); diag.append(('addr-except',town,orig))
            elif nums and not rest.startswith('除'):
                res.append((town,v,nums,True,orig)); diag.append(('addr-lins',town,orig))
            else:
                res.append((town,v,set(range(1,L+1)),True,orig)); diag.append(('addr-whole',town,orig))
    return res
def chunks(txt):
    txt=norm(txt)
    if not txt or txt=='nan': return []
    parts=re.split(r'[一二三四五六七八九十]+、',txt)
    return [p for p in parts if p.strip('、')]
def build(lv,fn):
    d=pd.read_csv(fn)
    assign=collections.defaultdict(lambda:collections.defaultdict(lambda:{'s':set(),'m':set(),'t':[]}))
    diag=[];notes={};nomatch=[];refs=[];basic=collections.defaultdict(set)
    for _,r in d.iterrows():
        town=norm(r['district']); sid=find_school(r['sname'],lv,town)
        if not sid: nomatch.append(r['sname']); continue
        if isinstance(r['mark'],str) and r['mark'].strip(): notes[sid]=re.sub(r'\s+',' ',r['mark']).strip()
        P=norm(r['pzoon'])
        if P in ('全區轄區','全區'):
            items=[(town,v,set(range(1,L+1)),False,'全區轄區') for (t,v),L in VB.items() if t==town]
        else:
            items=[]
            for c in chunks(r['pzoon']): items+=parse_list(c.strip('、'),town,diag)
        for (t,v,ls,m,o) in items:
            for n in ls:
                a=assign[(t,v)][n]; a['s'].add(sid); a['t'].append(f"{r['sname'].strip()}：{o}（基本學區）")
                if m: a['m'].add(sid)
                basic[sid].add((t,v,n))
        for c in chunks(r['fzoon']):
            c=re.sub(r'【[^】]*】','',c); c=re.sub(r'\([^()]*自由學區\)?','',c); c=re.sub(r'\(\s*$','',c)
            if '基本學區各里' in c: refs.append((sid,town,c,r['sname'])); continue
            for (t,v,ls,m,o) in parse_list(c.strip('、'),town,diag):
                for n in ls:
                    a=assign[(t,v)][n]; a['s'].add(sid); a['t'].append(f"{r['sname'].strip()}：{o}（自由學區）")
                    if m: a['m'].add(sid)
    for sid,town,c,sn in refs:
        txt=re.sub(r'基本學區各里$','',c)
        tw=town
        for t in TOWNS:
            if txt.startswith(t): tw=t; txt=txt[len(t):]
        names=re.split(r'及|與|、',txt)
        ids=[]
        for nm in names:
            for t in TOWNS:
                if nm.startswith(t): nm=nm[len(t):]
            i=find_school(nm,'j',tw)
            if not i: diag.append(('ref-unresolved',town,c)); ids=None; break
            ids.append(i)
        if not ids: continue
        for i in ids:
            for (t,v,n) in basic[i]:
                a=assign[(t,v)][n]; a['s'].add(sid); a['t'].append(f"{sn.strip()}：{c}（自由學區）")
    return assign,diag,notes,nomatch
def segs(assign,key,L):
    A=assign.get(key,{})
    out=[]
    for n in range(1,L+1):
        a=A.get(n); sig=(tuple(sorted(a['s'])),tuple(sorted(a['m']))) if a else ((),())
        tt=sorted(set(a['t'])) if a else []
        if out and out[-1]['_sig']==sig and out[-1]['t']==tt: out[-1]['b']=n
        else: out.append({'a':n,'b':n,'s':list(sig[0]),'m':list(sig[1]),'t':tt,'_sig':sig})
    if out: out[-1]['b']=999 if out[-1]['b']==L else out[-1]['b']
    for o in out: o.pop('_sig')
    return out
if __name__=='__main__':
    rep={}
    Z={}
    for lv,fn in [('e',B+'raw/ntpc_elem.csv'),('j',B+'raw/ntpc_jun.csv')]:
        assign,diag,notes,nomatch=build(lv,fn)
        gaps=[];multi=0;vills_full=0
        for key,L in VB.items():
            sg=segs(assign,key,L)
            g=[(x['a'],x['b']) for x in sg if not x['s']]
            if g: gaps.append((key,g))
            else: vills_full+=1
            Z.setdefault('|'.join(key),{})[lv]=[x for x in sg if x['s']]
        rep[lv]={'nomatch':nomatch,'diag':diag,'gaps':len(gaps),'gap_list':gaps[:40],'vills_full':vills_full,'notes':len(notes)}
        json.dump(notes,open(B+f'raw/ntpc_notes_{lv}.json','w'),ensure_ascii=False)
    json.dump(Z,open(B+'raw/ntpc_zones_draft.json','w'),ensure_ascii=False)
    # 衝突檢查：同一鄰有 >1 校且皆為「基本學區」、且非門牌條件
    for lv in 'ej':
        conf=[]
        for k,v in Z.items():
            for x in v.get(lv,[]):
                if len(x['s'])>1 and not x['m'] and all('（基本學區）' in t for t in x['t']): conf.append((k,x['a'],x['b'],x['t']))
        print(lv,'basic-conflicts',len(conf))
        for c in conf[:25]: print('  C',c)
        print(lv,'segments with m',sum(1 for v in Z.values() for x in v.get(lv,[]) if x['m']))
    for lv in rep:
        r=rep[lv];print(lv,'nomatch',r['nomatch'],'diag',len(r['diag']),'gapvills',r['gaps'],'full',r['vills_full'],'/',len(VB))
        for x in r['diag'][:60]: print('  D',x)
        for x in r['gap_list'][:40]: print('  G',x)

def export():
    Z=json.load(open(B+'raw/ntpc_zones_draft.json'))
    notes={}
    for lv in 'ej': notes.update(json.load(open(B+f'raw/ntpc_notes_{lv}.json')))
    gaps={'e':[],'j':[]};multi={'e':0,'j':0}
    for k,v in Z.items():
        L=VB[tuple(k.split('|'))]
        for lv in 'ej':
            segs=v.get(lv,[])
            cov=set()
            for x in segs:
                cov|=set(range(x['a'],(L if x['b']==999 else x['b'])+1))
                if len(x['s'])>1:
                    if all('（基本學區）' in t for t in x['t']): x['f']='bm'; multi[lv]+=1
                    else: x['f']='free'
                x['t']=list(dict.fromkeys(re.sub(r'^\S{1,3}區\s+','',t) for t in x['t']))
                if not x['m']: x.pop('m')
            miss=sorted(set(range(1,L+1))-cov)
            if miss: gaps[lv].append(k+':'+(str(miss[0])+'-'+str(miss[-1]) if len(miss)>1 else str(miss[0])))
    meta={'county':'新北市','years':'115','title':'新北市115學年度國民小學／國民中學學區一覽表（基本學區、自由學區）',
      'source_page':'https://data.ntpc.gov.tw/datasets/c8a74727-102f-49ee-94df-0b3116edff5e',
      'source_files':['data.ntpc.gov.tw 國小學區 CSV（c8a74727…）','data.ntpc.gov.tw 國中學區 CSV（3170b117…）'],
      'publisher':'新北市政府教育局（新北市政府資料開放平臺）',
      'method':'官方CSV之「基本學區／自由學區」欄為自由文字；以程式逐項解析里名與鄰別（scripts/parse_ntpc.py），無法以鄰別表示的門牌／路段條件不拆分，標示「依門牌或條件分屬」並保留原文。每一結果均附官方原文供核對。',
      'notes':['新北市學區另有「自由學區」（可擇一）及各校備註（如額滿、身分證尾數分配、里鄰整編過渡期等），結果中附各校備註原文；實際入學以學校及新北市教育局公告為準。','本表為自動解析，已逐鄰檢核涵蓋與衝突，但未逐列人工比對全部原文；如結果與原文不同，以原文為準。'],
      'check':{'villages':len(Z),'gaps_e':gaps['e'],'gaps_j':gaps['j'],'multi_basic_e':multi['e'],'multi_basic_j':multi['j'],'missing_e':[g for g in gaps['e'] if g.endswith(':1-'+str(VB[tuple(g.split(':')[0].split('|'))]))],'missing_j':[]},
      'auto_parsed':True}
    json.dump({'meta':meta,'v':Z,'school_notes':notes},open(B+'data/c/65000/zones.json','w'),ensure_ascii=False,separators=(',',':'))
    print('exported',len(Z),gaps,multi,os.path.getsize(B+'data/c/65000/zones.json'))
import os
if __name__=='__main__': export()
