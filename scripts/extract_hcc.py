"""新竹市 115學年度 國小／國中學區劃分表 PDF → 以字元座標還原表格（校名／全部里鄰／部分里鄰：里名＋說明）。"""
import pdfplumber,json,re,sys,collections
B='/workspace/taiwan-school-map/raw/'
def lines_of(chars,tol=2.5):
    chars=sorted(chars,key=lambda c:(round(c['top']),c['x0']))
    L=[]
    for c in chars:
        if c['text'].strip()=='' : continue
        for l in L:
            if abs(l['top']-c['top'])<=tol: l['ch'].append(c); break
        else: L.append({'top':c['top'],'ch':[c]})
    for l in L: l['ch'].sort(key=lambda c:c['x0']); l['text']=''.join(c['text'] for c in l['ch'])
    return sorted(L,key=lambda l:l['top'])
def run(f):
    out=[];cur=None
    with pdfplumber.open(B+f+'.pdf') as pdf:
        for pi,pg in enumerate(pdf.pages):
            tabs=sorted(pg.find_tables(),key=lambda t:-(t.bbox[2]-t.bbox[0])*(t.bbox[3]-t.bbox[1]))
            if not tabs: continue
            t=tabs[0]
            xs=sorted(set(round(c[0]) for c in t.cells)); X=xs[:5]+[t.bbox[2]+1]   # 區別,校名,全部,里名,說明
            col=lambda ch:max([i for i,x in enumerate(X[:-1]) if (ch['x0']+ch['x1'])/2>=x-1] or [-1])
            spans=[]
            for c in t.cells:
                if abs(round(c[0])-X[1])<=1:
                    txt=''.join(l['text'] for l in lines_of([ch for ch in pg.chars if c[0]<=(ch['x0']+ch['x1'])/2<c[2] and c[1]<=(ch['top']+ch['bottom'])/2<c[3]]))
                    if txt in ('校名',): continue
                    spans.append([c[1],c[3],txt])
            spans.sort()
            hdr_bottom=max([c[3] for c in t.cells if '全部里鄰' in ''.join(ch['text'] for ch in pg.chars if c[0]<=(ch['x0']+ch['x1'])/2<c[2] and c[1]<=(ch['top']+ch['bottom'])/2<c[3])] or [t.bbox[1]])
            chars=[ch for ch in pg.chars if t.bbox[0]<=(ch['x0']+ch['x1'])/2<=t.bbox[2] and hdr_bottom<=(ch['top']+ch['bottom'])/2<=t.bbox[3]]
            buckets=collections.defaultdict(lambda:collections.defaultdict(list))
            for sp in spans:
                nm=sp[2].replace('★','')
                if nm:
                    cur={'name':nm,'star':'★' in sp[2],'whole':'','vill':[],'spec':[],'page':pi}; out.append(cur)
                sp.append(cur)
            for ch in chars:
                y=(ch['top']+ch['bottom'])/2
                own=[sp for sp in spans if sp[0]<=y<sp[1]]
                if not own: continue
                k=col(ch)
                if k>=2: buckets[id(own[0][3])][k].append(ch); buckets[id(own[0][3])]['obj']=own[0][3]
            for b in buckets.values():
                o=b['obj']
                o['whole']+=''.join(l['text'] for l in lines_of(b[2]))
                for l in lines_of(b[3]): o['vill'].append(((pi,l['top']),l['text']))
                for l in lines_of(b[4]): o['spec'].append(((pi,l['top']),l['text']))
    for s in out:
        m=re.search(r'1、如有新增',s['whole'])
        if m: s['note']=s['whole'][m.start():]; s['whole']=s['whole'][:m.start()]
    return out
if __name__=='__main__':
    for f in ['hcc_115ps','hcc_115jh']:
        o=run(f); json.dump(o,open(B+f+'_cells.json','w'),ensure_ascii=False)
        print(f,len(o))
        for s in o[:3]+o[-2:]: print(json.dumps(s,ensure_ascii=False)[:600])
