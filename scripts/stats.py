import json,os
B=os.path.join(os.path.dirname(__file__),'..','data')
R=json.load(open(B+'/registry.json'));out={}
for r in R:
    c=r['code'];d=f'{B}/c/{c}/'
    V=json.load(open(d+'villages.json'));S=json.load(open(d+'schools.json'))
    vs=[f['properties'] for f in V['features'] if f['properties'].get('v')]
    st={'towns':len({p['t'] for p in vs}),'villages':len(vs),'lins':sum(p.get('L') or 0 for p in vs),
        'e':sum(s['lv']=='e' for s in S),'j':sum(s['lv']=='j' for s in S),'coord':sum(s['lat'] is not None for s in S),'n_s':len(S)}
    if os.path.exists(d+'zones.json'):
        Z=json.load(open(d+'zones.json'));st['zv']=len(Z['v'])
        for l in 'ej':
            st['split_'+l]=sum(1 for k,v in Z['v'].items() if len({tuple(x['s']) for x in v.get(l,[])})>1)
            st['shared_'+l]=sum(1 for k,v in Z['v'].items() if any(len(x['s'])>1 for x in v.get(l,[])))
        st['check']=Z['meta'].get('check'); st['auto']=bool(Z['meta'].get('auto_parsed'))
    out[c]=st
json.dump(out,open(B+'/stats.json','w'),ensure_ascii=False)
print(json.dumps(out,ensure_ascii=False)[:600])
