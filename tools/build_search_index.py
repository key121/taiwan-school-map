#!/usr/bin/env python3
"""Build the beta search helper indexes (re-runnable, reads only):
  beta/data/r/{0..7}.json.gz  road name -> ["<county code>.<district idx>", ...]  (bucket = rhash(road, 8))
  beta/data/r/names.json.gz   all road names (for near-miss suggestions; loaded only on a miss)
  beta/data/comm/<code>.json  community name -> doorplates grouped by 區|里|鄰 (基隆 from the 查行情 snapshot)
Run after tools/import_codex.py.  Usage: python3 tools/build_search_index.py [--snap /workspace/line-oa/seo/snapshots]"""
import json, gzip, glob, os, re, sys, argparse, unicodedata, collections
sys.path.insert(0, os.path.dirname(__file__))
from addrnorm import norm, road_of
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ap = argparse.ArgumentParser(); ap.add_argument('--snap', default='/workspace/line-oa/seo/snapshots'); A = ap.parse_args()
NB = 8
def rhash(s, nb): return sum(ord(c) for c in s) % nb
def W(p, o, gz=False):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    b = json.dumps(o, ensure_ascii=False, separators=(',', ':')).encode()
    if gz: b = gzip.compress(b, 9, mtime=0)
    open(p, 'wb').write(b); return len(b)

# ---------- road index across counties ----------
idx = collections.defaultdict(list)
for f in sorted(glob.glob(f'{R}/beta/data/a/*/roads.json.gz')):
    code = f.split('/')[-2]
    for road, ds in json.loads(gzip.open(f).read()).items():
        idx[road] += [f'{code}.{i}' for i in ds]
# near-miss suggestions (never auto-answered): longer roads ending with this name (孝東路 -> 忠孝東路),
# and the 段 roads of a name typed without 段 (忠孝東路 -> 忠孝東路1段…)
sug = collections.defaultdict(set)
names = set(idx)
for r in names:
    for i in range(1, len(r) - 1):
        if r[i:] in names: sug[r[i:]].add(r)
    m = re.match(r'^(.+?)(\d+)段$', r)
    if m: sug[m.group(1)].add(r)
buckets = [dict() for _ in range(NB)]
for road in sorted(idx): buckets[rhash(road, NB)][road] = idx[road]
for road in sorted(sug):
    L = sorted(sug[road], key=lambda x: (len(x), [int(z) for z in re.findall(r'\d+', x)], x))[:8]
    buckets[rhash(road, NB)]['~' + road] = L
sz = [W(f'{R}/beta/data/r/{i}.json.gz', b, True) for i, b in enumerate(buckets)]
nsz = W(f'{R}/beta/data/r/names.json.gz', sorted(idx), True)
print('roads', len(idx), 'bucket gz bytes', sz, 'names gz', nsz)

# ---------- community index (基隆 snapshot) ----------
def shards(code):
    M = json.load(open(f'{R}/beta/data/a/{code}/meta.json'))
    for d, f in M['f'].items():
        for b in range(f['nb']):
            S = json.loads(gzip.open(f'{R}/beta/data/a/{code}/{f["i"]}_{b}.json.gz').read())
            for k, v in S['k'].items():
                for r in (v if isinstance(v[0], list) else [v]):
                    yield d, k, S['v'][r[0]], r[1]
RNG = re.compile(r'^(.+?)(\d+(?:之\d+)?)(?:T(\d+(?:之\d+)?))?((?:、\d+(?:之\d+)?)*)號([（(]([單雙])號[）)])?$')
KEY = re.compile(r'^(.*?)(\d+)(?:之(\d+))?號$')
def parse_range(t):
    """'觀海街1–223號（單號）' -> (prefix, lo, hi, parity, singles) ; '中和路85巷' -> (prefix, None...)"""
    t = norm(re.sub(r'[–~～\-]', 'T', t)); m = RNG.match(t)
    if not m: return (t, None, None, None, None)
    pre, lo, hi, more, _, par = m.groups()
    nums = lambda s: int(s.split('之')[0])
    singles = [nums(lo)] + [nums(x) for x in more.split('、') if x] if not hi else None
    return (pre, nums(lo), nums(hi) if hi else nums(lo), {'單': 1, '雙': 0}.get(par), singles)
def comm_index(code, county):
    files = [f for f in glob.glob(f'{A.snap}/{county}/*/*.json') if not os.path.basename(f).startswith('_')]
    if not files: return None
    byPre = collections.defaultdict(list)
    for d, k, v, lin in shards(code):
        m = KEY.match(k)
        if m: byPre[m.group(1)].append((int(m.group(2)), d, k, v, lin))
    out = []; stat = collections.Counter()
    for f in sorted(files):
        e = json.load(open(f)); I = e['identity']; B = e['basics']
        hits = []
        for t in B.get('address_ranges') or []:
            pre, lo, hi, par, singles = parse_range(t)
            if lo is None:   # whole road / 巷弄
                hits += [(t, x) for p, L in byPre.items() if p == pre or (re.search(r'[巷弄]$', pre) and p.startswith(pre)) for x in L]; continue
            for x in byPre.get(pre, []):
                n = x[0]
                if singles is not None: ok = n in singles
                else: ok = lo <= n <= hi and (par is None or n % 2 == par)
                if ok: hits.append((t, x))
        # prefer the snapshot's district when the same road exists in several districts
        if any(x[1] == I['district'] for _, x in hits): hits = [(t, x) for t, x in hits if x[1] == I['district']]
        g = collections.OrderedDict()
        for t, (n, d, k, v, lin) in hits:
            gk = (d, v, lin); g.setdefault(gk, {'r': set(), 'k': []})
            g[gk]['r'].add(t); g[gk]['k'].append(k)
        def span(keys):   # actual doorplates in this 里鄰 -> '孝東路108–114號、…'
            by = collections.OrderedDict()
            for k in sorted(set(keys), key=lambda s: [int(z) for z in re.findall(r'\d+', s)]):
                m = KEY.match(k); by.setdefault(m.group(1), []).append(int(m.group(2)))
            return '、'.join(p + (f'{min(n)}號' if min(n) == max(n) else f'{min(n)}–{max(n)}號') for p, n in by.items())
        groups = [[d, v, lin, span(x['k']), sorted(x['k'], key=lambda s: [int(z) for z in re.findall(r'\d+', s)])[0], len(x['k'])] for (d, v, lin), x in g.items()]
        groups.sort(key=lambda z: [int(q) for q in re.findall(r'\d+', z[4])])
        stat['with_doorplate' if groups else 'no_doorplate'] += 1
        out.append({'n': I['name'], 'a': I.get('aliases') or [], 'd': I['district'], 't': B.get('address_text') or '', 'g': groups})
    return out, dict(stat)
src = None
try:
    ix = json.load(open(f'{A.snap}/index.json')); src = ix.get('updated_at')
except Exception: pass
for code, county in [('10017', '基隆市')]:
    r = comm_index(code, county)
    if not r: continue
    out, stat = r
    b = W(f'{R}/beta/data/comm/{code}.json', {'county': county, 'updated': src,
          'source': '社區名稱：內政部實價登錄社區彙整；社區門牌：基隆市公寓大廈管理組織報備資料（政府資料開放授權條款第1版）；門牌→里鄰：本站門牌索引', 'c': out})
    print(county, 'communities', len(out), stat, 'bytes', b, 'gz', len(gzip.compress(open(f'{R}/beta/data/comm/{code}.json','rb').read())))
