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
            for k in sorted(set(keys), key=lambda s: ([int(z) for z in re.findall(r'\d+', s)], s)):   # tie-break by text: stable across runs
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

# ---------- community index (臺北市／新北市 公寓大廈管理組織報備；名稱 + 管委會登記門牌) ----------
# Each row gives ONE registered address, so a community = name + its registered doorplate(s) -> 里鄰.
# Same name in the same district on several rows -> several doorplates (UI shows each distinct school result).
import csv
from addrnorm import door_key
APM = [('63000', '臺北市', '/workspace/addr/tpe_apm.csv', '管委會名稱', '管委會設置地址', '行政區',
        '臺北市公寓大廈組織報備查詢（臺北市建築管理工程處，data.gov.tw/dataset/132391，資料更新 2026-10-05）'),
       ('65000', '新北市', '/workspace/addr/ntpc_apm.csv', 'organization', 'address', 'town',
        '新北市公寓大廈管理組織報備清冊（新北市政府工務局，data.gov.tw/dataset/139727，資料更新 2026-10-19）')]
CSUF = re.compile(r'(公寓大廈|公寓大夏|大廈|大夏)?(管理委員會|管理負責人|管委會|管理組織)$')
ADDRISH = re.compile(r'\d+(之\d+)?[號巷弄]|[路街]\d|^\d')
def clean_name(n, dist, county):
    n = unicodedata.normalize('NFKC', n or '').strip().replace(' ', '')
    for p in (county, county.replace('臺', '台'), dist):
        if n.startswith(p) and len(n) > len(p) + 1: n = n[len(p):]
    m = CSUF.sub('', n)
    if len(m) >= 2: n = m
    m = re.sub(r'(公寓大廈|公寓)$', '', n)
    if len(m) >= 2: n = m
    return n
def apm_pre(addr):
    """Keep ranges before norm() turns '~'/'-' into 之: '18~20' / '167-179' -> 18到20 (a '-' whose 2nd number is smaller stays 之: 35-1)."""
    a = unicodedata.normalize('NFKC', addr)
    a = re.sub(r'\((?:雙|單)\)|[-]?\((?:雙|單)\)', '', a)
    a = re.sub(r'(\d)\s*[~～至]\s*(\d)', r'\1到\2', a).replace('&', '.')
    a = re.sub(r'(\d+)-(\d+)', lambda m: m.group(1) + ('或' if int(m.group(2)) > int(m.group(1)) else '之') + m.group(2), a)   # 或 = A之B, else range A..B
    return a
def apm_doors(a, has=lambda k: False):
    """Registered committee addresses are messy: '仁愛路四段巷弄420號' (empty lane placeholder), '福祥街41.43.47號',
    '中和街18到20號', '實踐路93巷81號7樓'. Return door keys for the listed doors only (ranges: same-parity doors, capped at 12)."""
    a = re.sub(r'(?<![0-9])巷弄', '', a); a = re.sub(r'(\d+巷)弄', r'\1', a); a = re.sub(r'(?<![0-9])[巷弄](?=\d+號)', '', a)
    m = re.match(r'^(.*?[^0-9.、,，及到或之])(\d+(?:之\d+)?(?:[.、,，及到或]\d+(?:之\d+)?)*)號', a)
    if not m: return []
    pre, nums = m.group(1), m.group(2)
    out = []
    for tok in re.split(r'[.、,，及]', nums):
        o = re.match(r'^(\d+)或(\d+)$', tok)
        if o:   # '2-11': a real 2之11 door wins; otherwise read it as the range 2..11
            tok = o.group(1) + ('之' if has(door_key(pre + o.group(1) + '之' + o.group(2) + '號')) else '到') + o.group(2)
        r = re.match(r'^(\d+)(?:(之)(\d+))?到(\d+)$', tok)
        if r:
            if r.group(2):   # 35之1到15 -> 35之1 .. 35之15 (ends only)
                out += [f'{r.group(1)}之{r.group(3)}', f'{r.group(1)}之{r.group(4)}']
            else:
                x, y = int(r.group(1)), int(r.group(4))
                step = 2 if (y - x) % 2 == 0 else 1
                out += [str(q) for q in range(x, y + 1, step)][:12] if 0 < y - x <= 40 else [str(x)]
        else:
            out.append(re.sub(r'到.*$', '', tok))
    keys = []
    for nn in out:
        k = door_key(pre + nn + '號')
        if k and k not in keys: keys.append(k)
    return keys
def apm_index(code, county, path, nk, ak, dk):
    door = collections.defaultdict(list)
    for d, k, v, lin in shards(code): door[(d, k)].append((v, lin))
    nc = norm(county); stat = collections.Counter(); by = collections.OrderedDict()
    for r in csv.DictReader(open(path, encoding='utf-8-sig')):
        raw = (r.get(nk) or '').strip(); addr = (r.get(ak) or '').strip(); dist = (r.get(dk) or '').strip()
        if not raw or not addr: stat['blank_csv_rows'] += 1; continue
        n = clean_name(raw, dist, county)
        if len(n) < 2 or ADDRISH.search(n): stat['name_is_address_or_short'] += 1; continue
        a = norm(apm_pre(addr))
        for pre in (nc, norm('臺北縣'), norm('台北縣')):
            if a.startswith(pre): a = a[len(pre):]
        if dist and not a.startswith(norm(dist)):   # pre-2010 names: 板橋市 / 鶯歌鎮 -> 板橋區 / 鶯歌區
            a = re.sub(r'^' + re.escape(norm(dist)[:-1]) + r'[市鎮鄉]', norm(dist), a)
        if not dist or not a.startswith(norm(dist)):
            m = re.match(r'^(.{1,3}?[區鄉鎮市])', a); dist = dist or (m and m.group(1)) or ''
        a = a[len(norm(dist)):] if a.startswith(norm(dist)) else a
        while dist and a.startswith(norm(dist)): a = a[len(norm(dist)):]   # '文山區文山區…'
        a = re.sub(r'^.{1,5}?[里村]\d+鄰', '', a)   # 新北 rows often carry 里N鄰 before the road
        a = re.sub(r'^\d+鄰', '', a)
        ent = by.setdefault((n, dist), {'n': n, 'd': dist, 'addrs': [], 'g': collections.OrderedDict()})
        disp = re.sub(r'^' + re.escape(county), '', unicodedata.normalize('NFKC', addr))
        if disp not in ent['addrs']: ent['addrs'].append(disp)
        hits = []
        has = lambda k: (dist, k) in door
        for cand in apm_doors(a, has) + [x for m in [re.match(r'^.{1,4}?[里村](.+)$', a)] if m for x in apm_doors(m.group(1), has)]:
            hh = door.get((dist, cand), [])
            hits += [(v, lin, cand) for v, lin in hh]
        if not hits: stat['addr_not_in_doorplate_index'] += 1
        for v, lin, k in hits:
            ent['g'].setdefault((dist, v, lin, k), 0); ent['g'][(dist, v, lin, k)] += 1
        stat['rows'] += 1
    out = []
    for ent in by.values():
        g = [[d, v, lin, k, k, 1] for (d, v, lin, k) in ent['g']]
        g.sort(key=lambda z: [int(q) for q in re.findall(r'\d+', z[4])])
        out.append({'n': ent['n'], 'd': ent['d'], 't': '、'.join(ent['addrs'][:4]) + (f' 等{len(ent["addrs"])}址' if len(ent['addrs']) > 4 else ''),
                    'g': g, **({'q': ent['addrs'][0]} if not g else {})})
        stat['with_doorplate' if g else 'no_doorplate'] += 1
        if len({(x[1], x[2]) for x in g}) > 1: stat['multi_lilin'] += 1
    return out, dict(stat)
for code, county, path, nk, ak, dk, srcname in APM:
    if not os.path.exists(path): print('skip', county, path); continue
    out, stat = apm_index(code, county, path, nk, ak, dk)
    b = W(f'{R}/beta/data/comm/{code}.json', {'county': county, 'updated': '2026-10-29', 'kind': 'apm',
          'source': '社區名稱與登記門牌：' + srcname + '，政府資料開放授權條款第1版；門牌→里鄰：本站門牌索引', 'c': out})
    print(county, 'communities', len(out), stat, 'bytes', b, 'gz', len(gzip.compress(open(f'{R}/beta/data/comm/{code}.json','rb').read())))
