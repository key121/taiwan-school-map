"""嘉義縣 115學年度 國民中小學學區劃分表（全縣）→ beta/data/c/10010/zones.json（Issue #1 P2-A）。

來源：嘉義縣政府教育處 法規及公告 https://edu.cyhg.gov.tw/News3.aspx?n=418&sms=12453（上版日期 115-11-04，更新 115-11-25）
  國小：「115學年度嘉義縣國小學區劃分表」https://edu.cyhg.gov.tw/News_Content.aspx?n=418&s=258337
        → raw/10010/115_cyhg_es_zones_20261126.pdf（★115嘉義縣國小學區劃分表.pdf，12頁；表頭日期 106年8月1日）
  國中：「115學年度嘉義縣國中學區劃分表」https://edu.cyhg.gov.tw/News_Content.aspx?n=418&s=258338
        → raw/10010/115_cyhg_jh_zones_20261126.pdf（★115嘉義縣國中學區劃分表.pdf，2頁；表頭日期 105年8月1日）
PDF 有文字層（Excel 轉出），以 PyMuPDF find_tables() 直接讀表格儲存格，不需 OCR；每次重跑都由 raw/ 原檔重新解析。

規則（嚴格，不臆造）：
  * 「學區範圍」欄 → s（確定學區）。同一鄰被兩校「學區範圍」同時列入、原表未標共同 → s 兩校＋f='bm'＋m 待確認。
  * 「共同學區」欄 → 列出該欄的每一校都加入 s（雙方表列皆有才算；不對稱者列入 check.asym）。
  * 「得免遷戶籍就讀學區」欄 → 不是學區，只放 p（另可能）＋m 原文。
  * 原表村名與圖資對不上（下楫／頂楫 vs 圖資 下揖／頂揖、舊卑里 vs 舊埤里）→ 不改鍵、不定案，只寫條件候選 s=[]、p=[候選]、m=待確認。
  * 原表村名在該鄉鎮圖資不存在（建國四村、凌雲二村、竹崎鄉茄苳村）→ 不寫，列入 check.unmatched。
  * 原表儲存格截斷（鹿滿國小「和平村12-」）→ 條件候選，不定案。
  * 圖資村里 L 以 data/c/10010/villages.json 為準（略過空村名）；比對時用 tools/addrnorm.canon()，另加 豊→豐（canon 未收）。
  * 既有 13 校單校公告（Codex 匯入）不刪：與全縣表一致者把原文併入 t；不一致者把該校加入 p 並加 m 待確認（見 check.prev_compare）。
  * registry 中嘉義縣那一筆由本腳本產生（可重跑；rebase 衝突時重跑本腳本即可）。
"""
import json, os, re, sys, collections, copy
import pymupdf

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'tools'))
from addrnorm import canon

CODE = '10010'
TODAY = '2026-11-26'
ZP = os.path.join(R, f'beta/data/c/{CODE}/zones.json')
RP = os.path.join(R, 'beta/data/registry.json')
VP = os.path.join(R, f'data/c/{CODE}/villages.json')
SP = os.path.join(R, f'data/c/{CODE}/schools.json')
PDF = {'e': os.path.join(R, 'raw/10010/115_cyhg_es_zones_20261126.pdf'),
       'j': os.path.join(R, 'raw/10010/115_cyhg_jh_zones_20261126.pdf')}
PAGE = 'https://edu.cyhg.gov.tw/News3.aspx?n=418&sms=12453'
SRC_URL = {
    'e': 'https://ws-tm.cyhg.gov.tw/Download.ashx?u=LzAwMS9VcGxvYWQvMTM0OC9yZWxmaWxlLzEyNDUzLzI1ODMzNy9jNTkyMGE0NC05NjcwLTQ4YmItOWViYS1lYzczNjYxZWZmZGQucGRm&n=4piFMTE15ZiJ576p57ij5ZyL5bCP5a245Y2A5YqD5YiG6KGoIC5wZGY%3d',
    'j': 'https://ws-tm.cyhg.gov.tw/Download.ashx?u=LzAwMS9VcGxvYWQvMTM0OC9yZWxmaWxlLzEyNDUzLzI1ODMzOC81YzhhYmM1YS02NDI2LTQ4OWYtODc4Yy05MzcwNjUwYjQ2NGEucGRm&n=4piFMTE15ZiJ576p57ij5ZyL5Lit5a245Y2A5YqD5YiG6KGoIC5wZGY%3d',
}
NEWS = {'e': 'https://edu.cyhg.gov.tw/News_Content.aspx?n=418&s=258337',
        'j': 'https://edu.cyhg.gov.tw/News_Content.aspx?n=418&s=258338'}
TBL = {'e': '115學年度嘉義縣國小學區劃分表', 'j': '115學年度嘉義縣國中學區劃分表'}
LVN = {'e': '國小', 'j': '國中'}

def load(p): return json.load(open(p, encoding='utf-8'))
def dump(o, p):
    with open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(o, ensure_ascii=False, separators=(',', ':')))

# ---------- 圖資 ----------
VL = {}                       # (town, village) -> L
for f in load(VP)['features']:
    p = f['properties']
    if p.get('v'): VL[(p['t'], p['v'])] = p['L']
TOWNS = sorted({t for t, _ in VL}, key=len, reverse=True)
def cn(s): return canon(s).replace('豊', '豐')
VBY = collections.defaultdict(dict)   # town -> canon(village) -> village
for t, v in VL: VBY[t][cn(v)] = v
SCH = {s['id']: s for s in load(SP)}

# ---------- 學校名稱 → 校碼 ----------
ALIAS = {
    ('e', '排路國小'): '104618e',            # schools.json：縣立排路華德福實驗國小
    ('e', '大埔國中小(國小部)'): '104726e',
    ('e', '豐山實驗教育學校'): '104731e',
    ('e', '阿里山國中小(國小部)'): '104734e',
    ('j', '竹崎高中(國中部)'): '104319j',
    ('j', '永慶高中(國中部)'): '104326j',
    ('j', '大埔國中小(國中部)'): '104524j',
    ('j', '阿里山國中小(國中部)'): '104526j',
}
# 原表列出、但已不在教育部國小名錄者（stats.moe.gov.tw/files/school/{105,112,113,114}/e1_new.csv 核對）：
# 碧潭 104658、灣潭 104692、太和 104724 在 105 學年度名錄、112 起已無；大湖 104696 在 113 名錄、114 已無。
# 本站不推定其學生改分到哪一校 → 不寫 s，只寫 m 待確認。
CLOSED = {'碧潭國小': ('104658', '105 學年度名錄有，112 學年度起已無'),
          '灣潭國小': ('104692', '105 學年度名錄有，112 學年度起已無'),
          '太和國小': ('104724', '105 學年度名錄有，112 學年度起已無'),
          '大湖國小': ('104696', '113 學年度名錄有，114 學年度已無')}
def sid(lv, name):
    if lv == 'e' and name in CLOSED: return 'X' + name
    if (lv, name) in ALIAS: return ALIAS[(lv, name)]
    hit = [i for i, s in SCH.items() if s['lv'] == lv and s['pub'] == '公立' and s['name'] == '縣立' + name]
    assert len(hit) == 1, (lv, name, hit)
    return hit[0]

# ---------- 讀 PDF 表格 ----------
def rows_of(lv):
    out = []; last = None
    for pg in pymupdf.open(PDF[lv]):
        for t in pg.find_tables():
            for r in t.extract():
                r = [(c or '').replace('\n', '') for c in r]
                no, town, name, rng, shared, exempt, note = r
                if no == '編號' or (not no and not name) or no.startswith('說明'): continue
                if not no:                       # 分校列：歸本校
                    assert name.endswith('分校'), r
                    out.append(dict(no=last['no'] + '/' + name, town=last['town'], name=name, id=last['id'],
                                    rng=rng, shared=shared, exempt=exempt, note=note, label=last['name'] + name))
                    continue
                last = dict(no=no, town=town, name=name, id=sid(lv, name), rng=rng, shared=shared,
                            exempt=exempt, note=note, label=name)
                out.append(last)
    return out
ROWS = {lv: rows_of(lv) for lv in 'ej'}
assert len([r for r in ROWS['e'] if '/' not in r['no']]) == 124 and len(ROWS['j']) == 25, (len(ROWS['e']), len(ROWS['j']))

# ---------- 範圍文字解析 ----------
def norm(s):
    s = s.replace('（', '(').replace('）', ')').replace('~', '-').replace('～', '-').replace('至', '-').replace(' ', '').replace('　', '')
    s = s.replace('；', '、').replace('，', '、').rstrip('。').replace('。', '、')
    s = re.sub(r'及\(([^()]*[村里][^()]*)\)', r'、\1', s)         # 「及(大葛里23至27鄰)」
    return s
def nums(spec, L):
    """'1-9、11鄰' / '(1-8、20鄰)' / '' → set；無法解析 → None"""
    sp = spec.strip('()').replace('鄰', '').replace('(', '').replace(')', '')
    if sp == '': return set(range(1, L + 1))
    out = set()
    for p in sp.split('、'):
        m = re.fullmatch(r'(\d+)(?:-(\d+))?', p)
        if not m: return None
        a, b = int(m.group(1)), int(m.group(2) or m.group(1)); out |= set(range(a, b + 1))
    return out

UNMATCHED = []   # (lv, school, town, name, 原文)
ODD = []         # 條件候選：(lv, id, town, village, set, 原因, 原文)
OVER = []
INFERRED = []    # 共同學區欄未寫鄉鎮、但村名全縣唯一者
def parse_list(lv, row, text, deft, shared=False):
    """回傳 [(town, village, set)]；對不上者記錄。"""
    s = norm(text)
    # 鄉鎮前綴（有冒號或直接接村名）前補分隔
    s = re.sub('(' + '|'.join(TOWNS) + ')：', r'、\1：', s)
    toks = []; depth = 0; cur = ''
    for ch in s:
        if ch == '(': depth += 1
        if ch == ')': depth -= 1
        if ch == '、' and depth == 0: toks.append(cur); cur = ''
        else: cur += ch
    toks.append(cur)
    res = []; town = deft; pend = None   # pend: [town, village, specparts]
    def flush():
        nonlocal pend
        if pend:
            t, v, parts = pend; L = VL[(t, v)]
            spec = '、'.join(parts)
            ns = nums(spec, L) if parts else set(range(1, L + 1))
            if ns is None: ODD.append((lv, row['id'], t, v, None, '原表鄰別截斷或無法解析', v + spec))
            else:
                if max(ns) > L: OVER.append((lv, row['label'], t, v, spec, L)); ns = {n for n in ns if n <= L}
                res.append((t, v, ns))
        pend = None
    queue = [x for x in toks if x]
    while queue:
        tok = queue.pop(0)
        m = re.match('^(' + '|'.join(TOWNS) + ')：?', tok)
        if m and not tok.startswith(m.group(1) + '全'):
            town = m.group(1); tok = tok[m.end():]
            if not tok: continue
        m = re.fullmatch('(' + '|'.join(TOWNS) + ')全(村|部)', tok)
        if m:
            flush(); res += [(t, v, set(range(1, L + 1))) for (t, v), L in VL.items() if t == m.group(1)]; continue
        if re.fullmatch(r'\(?[\d\-、]+鄰?\)?', tok) and pend:      # 「太和村1、2、3…」的後續數字
            pend[2].append(tok); continue
        if re.fullmatch(r'\d+-', tok) and pend:                       # 截斷：「和平村12-」
            pend[2].append(tok); continue
        # 最長前綴對村名
        hit = None
        for k in range(min(5, len(tok)), 1, -1):
            if tok[k - 1] in '村里' and cn(tok[:k]) in VBY[town]: hit = (VBY[town][cn(tok[:k])], tok[k:]); break
        if not hit and shared:
            # 共同學區欄未寫鄉鎮（例：阿里山國中小「觸口村18-19鄰(與民和國中共同)」）：僅在村名全縣唯一時採用並記錄
            for k in range(min(5, len(tok)), 1, -1):
                if tok[k - 1] not in '村里': continue
                tw = [t for t in VBY if cn(tok[:k]) in VBY[t]]
                if len(tw) == 1:
                    INFERRED.append((lv, row['label'], tw[0], tok[:k], text)); town = tw[0]
                    hit = (VBY[town][cn(tok[:k])], tok[k:]); break
        if not hit:
            flush()
            mm = re.match(r'^([一-鿿]+?[村里])(.*)$', tok)
            UNMATCHED.append((lv, row['label'], town, mm.group(1) if mm else tok, text))
            if mm and mm.group(2): queue.insert(0, mm.group(2))
            continue
        flush()
        v, rest = hit
        m2 = re.match(r'^(\((?:[^()]*)\)|[\d\-、]*鄰?)(.*)$', rest)
        spec, tail = m2.group(1), m2.group(2)
        pend = [town, v, [spec] if spec else []]
        if tail: queue.insert(0, tail)
    flush()
    return res

# 朴子國中／東石國中「朴子市全部（除仁和里1鄰、7-13鄰及大葛里23至27鄰屬永慶高中學區外）」
PUZI_ALL = '朴子市全部（除仁和里1鄰、7-13鄰及大葛里23至27鄰屬永慶高中學區外）'
def puzi_all():
    out = []
    for (t, v), L in VL.items():
        if t != '朴子市': continue
        ns = set(range(1, L + 1))
        if v == '仁和里': ns -= {1} | set(range(7, 14))
        if v == '大葛里': ns -= set(range(23, 28))
        out.append((t, v, ns))
    return out

# 原表村名與圖資用字不同，只列條件候選（不改鍵）
VARIANT = {  # (lv, 原表村名) -> (圖資鍵, 說明)
    ('j', '下楫村'): (('東石鄉', '下揖村'), '原表寫「下楫村」，圖資為「下揖村」（同表國小部分寫「下揖村」）；用字不同，僅列待查對應，不定案。'),
    ('j', '頂楫村'): (('東石鄉', '頂揖村'), '原表寫「頂楫村」，圖資為「頂揖村」（同表國小部分寫「頂揖村」）；用字不同，僅列待查對應，不定案。'),
    ('j', '舊卑里'): (('太保市', '舊埤里'), '原表寫「舊卑里」，圖資為「舊埤里」（同表國小部分寫「舊埤里」）；用字不同，僅列待查對應，不定案。'),
}

# 「得免遷戶籍就讀學區」欄：手工結構化，原文逐字斷言在 PDF 中
EXEMPT = [  # (lv, 原文片段, [(town, village, 鄰集合或 None)], 可就讀校)
    ('j', '竹崎鄉灣橋村得免遷戶籍就讀民雄鄉大吉國中', [('竹崎鄉', '灣橋村', None)], '104508j'),
    ('j', '竹崎鄉中和村、光華村得免遷戶籍就讀阿里山國中小', [('竹崎鄉', '中和村', None), ('竹崎鄉', '光華村', None)], '104526j'),
    ('j', '中埔鄉和美村、和睦村得免遷戶籍就讀中埔鄉中埔國中', [('中埔鄉', '和美村', None), ('中埔鄉', '和睦村', None)], '104518j'),
    ('j', '中埔鄉富收村得免遷戶籍就讀水上鄉忠和國中', [('中埔鄉', '富收村', None)], '104517j'),
    ('j', '溪口鄉疊溪村免遷戶籍就讀大林國中', [('溪口鄉', '疊溪村', None)], '104505j'),
    ('j', '梅山鄉太和村得免遷戶籍就讀阿里山國中小', [('梅山鄉', '太和村', None)], '104526j'),
    ('j', '番路鄉公田村1~5鄰、公興村得免遷戶籍就讀阿里山國中小', [('番路鄉', '公田村', set(range(1, 6))), ('番路鄉', '公興村', None)], '104526j'),
    ('j', '阿里山鄉茶山村、新美村得免遷戶籍就讀大埔國中小', [('阿里山鄉', '茶山村', None), ('阿里山鄉', '新美村', None)], '104524j'),
    ('e', '太保市安仁里10-16鄰目前劃分為祥和國小學區，但得就讀安東國小', [('太保市', '安仁里', set(range(10, 17)))], '104670e'),
]
for lv, txt, _, _ in EXEMPT:
    assert any(txt in r['exempt'] for r in ROWS[lv]), txt

# ---------- 建立新表 ----------
# A[lv][(t,v)][n] = {'s':set,'basic':set,'p':set,'t':[],'m':[]}
def cell(): return {'s': set(), 'basic': set(), 'p': set(), 't': [], 'm': [], 'f': None, 'closed': set()}
A = {lv: collections.defaultdict(lambda: collections.defaultdict(cell)) for lv in 'ej'}
SHARED_DECL = collections.defaultdict(set)   # (lv,t,v,n) -> 宣告此鄰為共同學區的學校
for lv in 'ej':
    for r in ROWS[lv]:
        txt_r = f"{TBL[lv]}：{r['label']} 學區範圍：{r['rng']}"
        rng = r['rng']
        items = []
        if '朴子市全部' in rng:
            items += puzi_all()
            rest = rng[rng.index('外）') + 2:].lstrip('。')
            items += parse_list(lv, r, rest, r['town'])
        else:
            items += parse_list(lv, r, rng, r['town'])
        for t, v, ns in items:
            for n in ns:
                c = A[lv][(t, v)][n]; c['t'].append(txt_r)
                if r['id'].startswith('X'): c['closed'].add(r['id'][1:])
                else: c['basic'].add(r['id'])
        if r['shared']:
            sh = norm(r['shared'])
            parts = re.split(r'\(與[^()]*共同\)', sh)
            txt_s = f"{TBL[lv]}：{r['label']} 共同學區：{r['shared']}"
            for part in parts:
                for t, v, ns in parse_list(lv, r, part, r['town'], shared=True):
                    for n in ns:
                        c = A[lv][(t, v)][n]; c['t'].append(txt_s); SHARED_DECL[(lv, t, v, n)].add(r['id'])
                        if r['id'].startswith('X'): c['closed'].add(r['id'][1:])
                        else: c['s'].add(r['id'])

# 用字不同 → 條件候選
for (lv, name), ((t, v), why) in VARIANT.items():
    us = [u for u in UNMATCHED if u[0] == lv and u[3] == name]
    assert us, name
    for u in us:
        ids = [r['id'] for r in ROWS[lv] if r['label'] == u[1]]
        for n in range(1, VL[(t, v)] + 1):
            c = A[lv][(t, v)][n]; c['p'] |= set(ids); c['m'].append('待確認：' + why)
            c['t'].append(f"{TBL[lv]}：{u[1]} 學區範圍：{u[4]}")
    UNMATCHED[:] = [u for u in UNMATCHED if not (u[0] == lv and u[3] == name)]
# 截斷 → 條件候選
for lv, id_, t, v, _, why, raw in ODD:
    m = re.match(r'.*?(\d+)-$', raw)
    a = int(m.group(1)); L = VL[(t, v)]
    label = [r['label'] for r in ROWS[lv] if r['id'] == id_][0]
    for n in range(a, L + 1):
        c = A[lv][(t, v)][n]; c['p'].add(id_)
        c['m'].append(f'待確認：{label}學區範圍原文為「{raw}」（PDF 儲存格截斷，未寫迄鄰），{v}第{a}鄰以後是否全屬{label}無法確定。')
        c['t'].append(f"{TBL[lv]}：{label} 學區範圍：{[r['rng'] for r in ROWS[lv] if r['id']==id_ and raw in r['rng']][0]}")

# 得免遷戶籍 → p
for lv, txt, targets, to in EXEMPT:
    for t, v, ns in targets:
        for n in (ns or range(1, VL[(t, v)] + 1)):
            c = A[lv][(t, v)][n]; c['p'].add(to); c['m'].append('得免遷戶籍就讀（非學區）：' + txt)
            c['t'].append(f"{TBL[lv]} 得免遷戶籍就讀學區：{txt}")

# 合成：學區範圍重疊 → f='bm'＋待確認
OVERLAP = []
for lv in 'ej':
    for key, d in A[lv].items():
        for n, c in d.items():
            for nm in sorted(c['closed']):
                c['m'].append(f'待確認：原表列「{nm}」，但教育部國小名錄已無此校（{CLOSED[nm][1]}，代碼 {CLOSED[nm][0]}），本站不推定現行學區學校，請洽教育處或鄉公所。')
            basic = c['basic']
            if len(basic) > 1 and not basic <= c['s']:
                names = '、'.join(SCH[i]['name'].replace('縣立', '') for i in sorted(basic))
                c['f'] = 'bm'
                c['m'].append(f'待確認：原表{names}的「學區範圍」都列入本鄰，未註明共同學區，入學分配請洽學校或教育處。')
                OVERLAP.append((lv, '|'.join(key), n, sorted(basic)))
            c['s'] |= basic
            c['p'] -= c['s']

# 共同學區不對稱檢查：宣告者 vs 實際 s
ASYM = []
for (lv, t, v, n), decl in SHARED_DECL.items():
    if len(decl) < 2 and not A[lv][(t, v)][n]['closed']: ASYM.append((lv, f'{t}|{v}', n, sorted(decl)))

NEW = copy.deepcopy({lv: {k: dict(d) for k, d in A[lv].items()} for lv in 'ej'})

# ---------- 與既有 13 校單校公告比對 ----------
Z = load(ZP)
OLD = Z['v']
OLD_META = Z['meta']
if OLD_META.get('origin') == 'codex':     # 第一次執行：保存既有資料以便重跑
    prev = {'meta': OLD_META, 'v': OLD, 'sf': Z.get('sf')}
    dump(prev, os.path.join(R, 'raw/10010/prev_codex_13schools_zones_20261029.json'))
prev = load(os.path.join(R, 'raw/10010/prev_codex_13schools_zones_20261029.json'))
CMP = collections.Counter(); CMP_DIFF = []; PROMOTED = []
VARIANT_RAW = {(lv, t, v): n for (lv, n), ((t, v), _) in VARIANT.items()}
for key, lvd in prev['v'].items():
    t, v = key.split('|'); L = VL[(t, v)]
    for lv, segs in lvd.items():
        for x in segs:
            olds = set(x['s']) | set(x.get('p') or [])
            for n in range(x['a'], min(x['b'], L) + 1):
                c = A[lv][(t, v)][n]
                newall = c['s'] | c['p']
                if not newall: CMP['new_empty'] += 1; tag = 'new_empty'
                elif olds <= c['s']: CMP['agree'] += 1; tag = 'agree'
                elif not c['s'] and olds <= c['p'] and any(t + v in tt for tt in x['t']) and any(m.startswith('待確認：原表寫') for m in c['m']):
                    # 全縣表用字與圖資不同（例：舊卑里），但單校 115 學年度公告以圖資同字列入同一校 → 依單校公告列入 s
                    CMP['variant_confirmed_by_school_notice'] += 1; tag = 'promoted'
                    c['s'] |= olds; c['p'] -= olds
                    c['m'] = [m for m in c['m'] if not m.startswith('待確認：原表寫')]
                    c['m'].append('全縣表寫「' + VARIANT_RAW.get((lv, t, v), '?') + '」（與圖資用字不同）；' + '、'.join(SCH[i]['name'].replace('縣立', '') for i in sorted(olds)) + ' 115學年度單校公告寫「' + v + '」，依單校公告列入。')
                    PROMOTED.append((lv, key))
                elif olds <= newall: CMP['agree_as_p'] += 1; tag = 'agree_as_p'
                else: CMP['differ'] += 1; tag = 'differ'
                for tt in x['t']:
                    if tt not in c['t']: c['t'].append('（單校公告）' + tt)
                if tag in ('differ', 'new_empty'):
                    extra = olds - c['s']
                    c['p'] |= extra
                    c['m'].append('待確認：單校115學年度公告（' + '、'.join(SCH[i]['name'].replace('縣立', '') for i in sorted(extra)) + '）列入本鄰，與全縣學區劃分表不一致。')
                    CMP_DIFF.append((lv, key, n, sorted(olds), sorted(c['s']), sorted(c['p'] - extra)))

# ---------- 輸出 segments ----------
def segs(d, L):
    out = []
    for n in range(1, L + 1):
        c = d.get(n)
        if not c or not (c['s'] or c['p'] or c['m']): sig = None
        else:
            x = {'s': sorted(c['s']), 't': sorted(set(c['t']))}
            p = sorted(c['p'] - c['s'])
            if p: x['p'] = p
            if c['m']: x['m'] = sorted(set(c['m']))
            if c['f']: x['f'] = c['f']
            sig = json.dumps(x, ensure_ascii=False, sort_keys=True)
        if out and out[-1][2] == sig: out[-1][1] = n
        else: out.append([n, n, sig])
    res = []
    for a, b, sig in out:
        if sig is None: continue
        x = json.loads(sig); y = {'a': a, 'b': 999 if b == L else b}; y.update(x); res.append(y)
    return res

V = {}
for (t, v), L in sorted(VL.items()):
    e = segs(A['e'].get((t, v), {}), L); j = segs(A['j'].get((t, v), {}), L)
    if e or j:
        V[f'{t}|{v}'] = {k: s for k, s in (('e', e), ('j', j)) if s}

# ---------- 檢查 ----------
assert set(V) <= {f'{t}|{v}' for t, v in VL}
ids_used = {i for d in V.values() for ss in d.values() for x in ss for i in x['s'] + x.get('p', [])}
assert ids_used <= set(SCH), ids_used - set(SCH)
gaps = {'e': [], 'j': []}; cond_only = {'e': [], 'j': []}
for (t, v), L in sorted(VL.items()):
    k = f'{t}|{v}'
    for lv in 'ej':
        cov = set(); sure = set()
        for x in V.get(k, {}).get(lv, []):
            r = set(range(x['a'], (L if x['b'] == 999 else x['b']) + 1)); cov |= r
            if x['s']: sure |= r
        miss = sorted(set(range(1, L + 1)) - cov)
        if miss: gaps[lv].append(k + (':' + ','.join(map(str, miss)) if len(miss) < L else ':全里'))
        co = sorted(cov - sure)
        if co: cond_only[lv].append(k + ':' + ','.join(map(str, co)))

def fmt(ns):
    ns = sorted(ns); out = [];
    for n in ns:
        if out and out[-1][1] == n - 1: out[-1][1] = n
        else: out.append([n, n])
    return ','.join(f'{a}' if a == b else f'{a}-{b}' for a, b in out)

towns_cnt = collections.Counter(t for t, v in VL)
full_v = [k for k in V if all(not g.startswith(k + ':') for lv in 'ej' for g in gaps[lv])]
check = {
    'villages': len(VL), 'zoneVillages': len(V),
    'villages_es_full': len(VL) - len(gaps['e']), 'villages_jh_full': len(VL) - len(gaps['j']),
    'gaps_es': gaps['e'], 'gaps_jh': gaps['j'],
    'conditional_only_es': cond_only['e'], 'conditional_only_jh': cond_only['j'],
    'unmatched_names': [f'{LVN[u[0]]}・{u[1]}：{u[2]}{u[3]}（圖資該鄉鎮無此村里，未寫入）' for u in UNMATCHED],
    'variant_names': [f'{LVN[lv]}・{n}→{t}|{v}（只列條件候選）' for (lv, n), ((t, v), _) in VARIANT.items()],
    'truncated': [f'{LVN[o[0]]}・{o[2]}|{o[3]}：原文「{o[6]}」' for o in ODD],
    'town_inferred': [f'{LVN[i[0]]}・{i[1]} 共同學區欄「{i[3]}」未寫鄉鎮，全縣唯一 → {i[2]}' for i in INFERRED],
    'over_L': [f'{LVN[o[0]]}・{o[1]}：{o[2]}|{o[3]} {o[4]}（圖資 L={o[5]}，超出部分不寫）' for o in OVER],
    'overlap_basic': sorted({f"{LVN[o[0]]}・{o[1]}：{'、'.join(SCH[i]['name'].replace('縣立','') for i in o[3])}" for o in OVERLAP}),
    'shared_asym': sorted({f'{LVN[a[0]]}・{a[1]}第{a[2]}鄰：只有 {SCH[a[3][0]]["name"]} 列為共同學區' for a in ASYM}),
    'prev_compare': dict(CMP),
    'variant_confirmed_by_school_notice': sorted({f'{LVN[lv]}・{k}' for lv, k in PROMOTED}),
    'prev_differ': sorted({f'{LVN[d[0]]}・{d[1]}：單校公告 {"、".join(SCH[i]["name"].replace("縣立","") for i in d[3])}；全縣表 {"、".join(SCH[i]["name"].replace("縣立","") for i in d[4]) or "（無）"}' for d in CMP_DIFF}),
}
# 差集：villages 有村名者 − zones
diff = sorted(f'{t}|{v}' for t, v in VL if f'{t}|{v}' not in V)
check['villages_minus_zones'] = diff

if __name__ == '__main__':
    print(json.dumps({k: (v if not isinstance(v, list) or len(v) < 60 else v[:60] + [f'...共{len(v)}']) for k, v in check.items()}, ensure_ascii=False, indent=1))
    if '--write' in sys.argv:
        meta = {
            'county': '嘉義縣', 'years': '115',
            'title': '嘉義縣115學年度國民中小學學區劃分表（全縣，嘉義縣政府教育處）',
            'source_page': PAGE,
            'source_notice': [NEWS['e'], NEWS['j']],
            'source_files': [SRC_URL['e'], SRC_URL['j'], 'raw/10010/115_cyhg_es_zones_20261126.pdf', 'raw/10010/115_cyhg_jh_zones_20261126.pdf'] + prev['meta']['source_files'],
            'publisher': '嘉義縣政府教育處',
            'method': 'scripts/parse_cyhg_115.py：PyMuPDF 讀取官方 PDF 表格儲存格（文字層，非 OCR）逐校解析「學區範圍／共同學區／得免遷戶籍就讀學區」；既有 13 校單校公告（Codex 匯入，備份於 raw/10010/prev_codex_13schools_zones_20261029.json）逐鄰比對後併入原文，不一致者列候選並標待確認。',
            'notes': [
                '全縣表：嘉義縣政府教育處「115學年度嘉義縣國小學區劃分表」「115學年度嘉義縣國中學區劃分表」（教育處網站上版日期 115-11-04）。PDF 表頭日期分別為 106年8月1日、105年8月1日，教育處以 115 學年度名義公告。',
                '「共同學區」欄所列各校皆列入；「得免遷戶籍就讀學區」不是學區，只列為「另可能」並附原文。',
                '原表兩校「學區範圍」同列一鄰而未註明共同者（例：朴子國中與東石國中範圍文字相同）標「皆列基本學區，依備註分配」並註待確認。',
                '原表國中部分寫「下楫村、頂楫村」「舊卑里」，圖資為「下揖村、頂揖村」「舊埤里」（同表國小部分與圖資相同）；不改鍵。下揖村、頂揖村國中只列條件候選、不定案；舊埤里因太保國中 115 學年度單校公告明寫「太保市舊埤里」，依該公告列入太保國中。',
                '原表水上國中列「建國四村、凌雲二村」、竹崎高中(國中部)列「茄苳村」，圖資該鄉無此村，未寫入。',
                '鹿滿國小原表「和平村12-」儲存格截斷，竹崎鄉和平村12鄰起國小只列條件候選。',
                '番路鄉日安社區（自由學區）、逐鹿社區（番路鄉及阿里山鄉共同學區）以社區名稱公告、未列鄰別，本站不推定其範圍，請看原文備註。',
                '朴子國中普通班有性別限制、藝才班及體育班例外（單校公告）；永慶高中國中部、祥和國小有總量管制與入學資格順位，地址符合學區不保證入學。',
                '大吉國中 2026-05-15 單校公告未明載 115 學年度；其與全縣表不一致處只列候選、待確認。',
            ],
            'auto_parsed': True, 'multi_label': '共同學區',
            'updated': TODAY, 'incomplete': [], 'warnings': [],
            'origin': 'ours', 'partial': False,
            'check': check,
        }
        Z2 = {'meta': meta, 'v': V, 'sf': prev.get('sf') or {}}
        dump(Z2, ZP)
        # registry（只改嘉義縣這一筆；可重跑）
        RG = load(RP)
        rec = [c for c in RG['counties'] if c['code'] == CODE][0]
        unresolved = len(check['gaps_es']) + len(check['gaps_jh'])
        rec.update({
            'origin': 'ours',
            'years': '115',
            'source': f'嘉義縣政府教育處 115學年度國小／國中學區劃分表（全縣）：{PAGE}',
            'official': PAGE,
            'officialNotice': NEWS['e'],
            'verification': 'machine-parsed',
            'updated': TODAY,
            'zoneVillages': len(V),
            'incomplete': [],
            'partialNote': None,
            'warning': ('依嘉義縣政府教育處 115 學年度全縣國小／國中學區劃分表（上版 115-11-04；PDF 表頭為 106/105 年 8 月 1 日版）整理。'
                        '待確認：國中表「下楫村、頂楫村」與圖資「下揖村、頂揖村」用字不同，只列候選（「舊卑里」已由太保國中115單校公告確認為舊埤里）；'
                        '鹿滿國小「和平村12-」原文截斷；朴子國中與東石國中、竹崎高中與大吉國中等學區範圍重疊未註明共同；'
                        '原表國小部分仍列已不在教育部名錄的碧潭、灣潭、太和、大湖國小，相關村鄰（鹿草鄉碧潭村、中埔鄉灣潭村、梅山鄉太和村部分鄰、番路鄉大湖村）國小不推定；'
                        '民雄鄉新山村及部分鄰表列未涵蓋（見 zones meta.check）。得免遷戶籍就讀學區僅列為「另可能」。'),
            'status': 'merged',
        })
        with open(RP, 'w', encoding='utf-8', newline='') as f:
            f.write(json.dumps(RG, ensure_ascii=False, separators=(',', ':')))
        print('written', len(V))
