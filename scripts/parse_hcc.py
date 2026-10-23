"""新竹市 115學年度 國小／國中學區劃分表（新竹市政府教育處 PDF，114.12 公告）→ zones 格式。
先以 extract_hcc.py 依字元座標還原表格；本程式解析「全部里鄰」「部分里鄰」文字。嚴格模式：無法解析者列入 unparsed。"""
import re,json,collections,os
B='/workspace/taiwan-school-map/'
V=json.load(open(B+'data/c/10018/villages.json'))
VB={};VN={}
for f in V['features']:
    p=f['properties']
    if p.get('v'): VB[(p['t'],p['v'])]=p['L']; VN[p['v'][:-1]]=(p['t'],p['v'])
S=json.load(open(B+'data/c/10018/schools.json'))
SP={s['id']:s for s in S}
FULL={'國立清華大學附設實驗國民小學':'180601e','建功高中國中部':'183313j','成德高中國中部':'183306j','香山高中國中部':'183307j'}
def sid(name,lv):
    if name in FULL: return FULL[name]
    hit=[s['id'] for s in S if s['lv']==lv and s['name']=='市立'+name]
    assert len(hit)==1,(name,hit); return hit[0]
SHORT={'e':{},'j':{}}
for s in S:
    if s['pub']!='公立' or not s['name'].startswith('市立'): continue
    n=s['name'][2:]
    if s['lv']=='e' and n.endswith('國小'): SHORT['e'][n[:-2]]=s['id']; SHORT['e'][n]=s['id']
    if s['lv']=='j' and n.endswith('國中'): SHORT['j'][n[:-2]]=s['id']
SHORT['j'].update({'建功':'183313j','成德':'183306j','香山':'183307j','香中':'183307j'})
SHORT['e'].update({'清大附小':'180601e','國立清華大學附設實驗國民小學':'180601e'})
LV={'hcc_115ps':'e','hcc_115jh':'j'}
claims={l:collections.defaultdict(lambda:collections.defaultdict(lambda:{'own':set(),'named':set(),'t':[],'m':set()})) for l in 'ej'}
unparsed=[];stars={};foot=[];named_unknown=[]
def linset(spec):
    out=set()
    for p in re.split(r'[、，,]',spec.replace(' ','')):
        if not p: continue
        m=re.fullmatch(r'(\d+)(?:-(\d+))?',p)
        if not m: return None
        a=int(m.group(1));b=int(m.group(2) or a); out|=set(range(a,b+1))
    return out
for f,lv in LV.items():
    cells=json.load(open(B+'raw/'+f+'_cells.json'))
    for c in cells:
        name=c['name']; id_=sid(name,lv)
        if c['star']: stars[id_]=True
        if c.get('note'): foot.append(c['note'])
        # 全部里鄰
        for v in [x for x in re.split(r'[、，]',c['whole']) if x]:
            if v not in VN: unparsed.append((name,'全部里鄰:'+v)); continue
            k=VN[v]
            for n in range(1,VB[k]+1):
                a=claims[lv][k][n]; a['own'].add(id_); a['t'].append(f'{name}：全部里鄰「{v}」')
        # 部分里鄰：合併換行
        sp=[]
        for pos,t in c['spec']:
            t=t.replace(' ','')
            vy=any(abs(tuple(p)[1]-pos[1])<4 and tuple(p)[0]==pos[0] for p,_ in c['vill'])
            if sp and not re.match(r'\d',t) and not vy: sp[-1][1]+=t
            else: sp.append([tuple(pos),t])
        vl=[(tuple(p),v.replace(' ','')) for p,v in c['vill']]
        for pos,t in sp:
            cand=[(p,v) for p,v in vl if p<=(pos[0],pos[1]+3)]
            if not cand: unparsed.append((name,'無對應里名:'+t)); continue
            v=cand[-1][1]
            if v not in VN: unparsed.append((name,'里名?'+v)); continue
            k=VN[v]; L=VB[k]
            m1=re.fullmatch(r'([\d、\-]+)鄰?',t); m2=re.fullmatch(r'([\d、\-]+)鄰?(?:為|調整為)(.+?)共同學區',t); m3=re.fullmatch(r'(.+?)共同學區',t)
            m4=re.fullmatch(r'([\d、\-]+)鄰?為(.+?)未能入學者',t); m5=re.fullmatch(r'([\d、\-]+)鄰?（未能入學者分發(.+?)）',t)
            cond=None
            if m4: ls=linset(m4.group(1)); names=[m4.group(2),name]; cond=f'{m4.group(2)}未能入學者分發{name}（依官方表原文）'
            elif m5: ls=linset(m5.group(1)); names=[name,m5.group(2)]; cond=f'{name}未能入學者分發{m5.group(2)}（依官方表原文）'
            elif m1: ls=linset(m1.group(1)); names=[]
            elif m2: ls=linset(m2.group(1)); names=m2.group(2).split('、')
            elif m3 and not re.search(r'\d',m3.group(1)): ls=set(range(1,L+1)); names=m3.group(1).split('、')
            else: unparsed.append((name,v+':'+t)); continue
            if ls is None: unparsed.append((name,v+':'+t)); continue
            ids=[]
            for nm in names:
                nm=re.sub(r'之$','',nm)
                if nm in SHORT[lv]: ids.append(SHORT[lv][nm])
                else: named_unknown.append((name,v,nm,t))
            if names and id_ not in ids: unparsed.append((name,f'{v}:{t}（本校未列於共同學區名單）'))
            for n in ls:
                if n>L: unparsed.append((name,f'{v}{n}鄰 超出戶政司鄰數{L}')); continue
                a=claims[lv][k][n]; a['own'].add(id_); a['named']|=set(ids); a['t'].append(f'{name}：{v}　{t}')
                if cond: a['m'].add(cond)
# 組合
def get(lv,k,n):
    a=claims[lv][k].get(n)
    if not a: return None
    s=sorted(a['own']|a['named']); x={'s':s,'t':sorted(set(a['t']))}
    if len(s)>1: x['f']='shared'
    if a['m']: x['m']=sorted(a['m'])
    return x
def segs(lv,k,L):
    out=[]
    for n in range(1,L+1):
        x=get(lv,k,n); sig=json.dumps(x,ensure_ascii=False,sort_keys=True) if x else None
        if out and out[-1][2]==sig: out[-1][1]=n
        else: out.append([n,n,sig])
    r=[]
    for a,b,sig in out:
        if sig is None: continue
        x=json.loads(sig); x['a']=a; x['b']=999 if b==L else b; r.append(x)
    return r
Z={};gaps={'e':[],'j':[]};incons={'e':[],'j':[]}
for k,L in sorted(VB.items()):
    kk='|'.join(k); Z[kk]={l:segs(l,k,L) for l in 'ej'}
    for l in 'ej':
        miss=[n for n in range(1,L+1) if n not in claims[l][k]]
        if miss: gaps[l].append(f"{kk}:{','.join(map(str,miss))}")
        for n,a in claims[l][k].items():
            if a['named']-a['own']: incons[l].append((kk,n,[SP[i]['name'] for i in a['named']-a['own']]))
print('unparsed',len(unparsed)); [print('  U',u) for u in unparsed]
print('named_unknown',named_unknown)
print('gaps',json.dumps(gaps,ensure_ascii=False))
for l in 'ej':
    ic=collections.defaultdict(list)
    for kk,n,nm in incons[l]: ic[(kk,tuple(nm))].append(n)
    print(l,'named-but-not-listed',len(ic)); [print('  I',k,v) for k,v in ic.items()]
    print(l,'multi segs',sum(1 for v in Z.values() for x in v[l] if len(x['s'])>1))
json.dump({'Z':Z,'gaps':gaps,'unparsed':unparsed,'incons':incons,'stars':stars,'foot':foot},open(B+'raw/hcc_draft.json','w'),ensure_ascii=False)
# 衝突：兩校以上各自列為獨有（未註明共同學區）
def footnotes(f):
    t=open(B+'raw/'+f+'.txt').read(); i=t.index('1、如有新增')
    body=re.sub(r'\s+','',t[i:]).replace('備註','')
    body=re.sub(r'\d+$','',body)  # 頁碼
    return [x for x in re.split(r'(?=\d、)',body) if x]
foot=[]
for f,lv in LV.items():
    for x in footnotes(f):
        x=('國小：' if lv=='e' else '國中：')+x
        foot.append(x)
conf=[]
for l in 'ej':
    for k,d in claims[l].items():
        for n,a in d.items():
            if len(a['own'])>1 and not a['named'] : conf.append((l,'|'.join(k),n,sorted(a['own'])))
print('conflicts',len(conf),conf[:20])
over=[u[1] for u in unparsed if '超出' in u[1]]
meta={'county':'新竹市','years':'115','title':'新竹市115學年度國民小學、國民中學學區劃分表（新竹市政府教育處，114年12月公告）',
 'source_page':'https://www.hc.edu.tw/edub/basic/schoolArea.aspx',
 'source_files':['https://www.hc.edu.tw/edub/basic/schoolarea/115ps.pdf','https://www.hc.edu.tw/edub/basic/schoolarea/115jh.pdf'],
 'publisher':'新竹市政府教育處','method':'自官方 PDF 以字元座標還原表格後，由程式（scripts/extract_hcc.py、parse_hcc.py）解析；未經人工逐筆核對。',
 'notes':foot+['官方表列有部分超出戶政司現行鄰數之鄰別（如光明里28鄰），已無法對應現行鄰界，列於檢核資訊。'],
 'check':{'gaps_e':gaps['e'],'gaps_j':gaps['j'],'unparsed':sorted(set(u[0]+'：'+u[1] for u in unparsed)),'conflicts':[f'{l}:{k}:{n}:{"、".join(SP[i]["name"] for i in s)}' for l,k,n,s in conf]},
 'auto_parsed':True,'multi_label':'共同學區'}
notes={i:'開放學區學校（官方表標示★；開放原則：不增加班級數、額滿不再招收，原有學區不變）' for i in stars}
out={'meta':meta,'v':Z,'school_notes':notes}
json.dump(out,open(B+'data/c/10018/zones.json','w'),ensure_ascii=False,separators=(',',':'))
print('wrote',len(Z),os.path.getsize(B+'data/c/10018/zones.json'))
