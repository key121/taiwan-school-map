"""南投縣 115學年度 竹山鎮硘[磘]里 缺里補丁（Issue #1 P2-C）。

來源（兩處 byte 相同，sha256 一致）：
  南投縣政府開放資料平台「南投縣學區劃分表」 https://data.nantou.gov.tw/dataset/doe-02
    國小 resource ba4aa724-… /download/115.pdf  → raw/10008/nantou_115_elementary_rev20260304_dl20261126.pdf
    國中 resource ffb44c93-… /download/115.pdf  → raw/10008/nantou_115_junior_rev20260304_dl20261126.pdf
  光華國小鏡像 https://ghps.ntct.edu.tw/p/406-1039-490646,r2776.php?Lang=zh-tw（同檔）
  前山國小附表「南投縣竹山鎮里鄰調整對照表（前山國小固定學區）」（同鏡像頁）
    → raw/10008/nantou_115_zhushan_qianshan_neighbor_adjust_20260309_dl20261126.pdf
PDF 有 ToUnicode，PyMuPDF get_text() 可抽出中文（pdftotext 只抽得到數字）；已再以 150dpi 圖檔目視核對。

缺因：官方表寫「硘磘里」，圖資鍵為「硘[磘]里」（缺字以方括號標示），Codex 匯入時沒對上。
本腳本以 tools/addrnorm.py 的 canon()／wild_regex() 對上後，寫入**圖資原鍵**「竹山鎮|硘[磘]里」。
可重跑：每次整筆覆寫該鍵，結果相同。
"""
import hashlib, json, os, sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'tools'))
from addrnorm import canon, wild_regex

CODE = '10008'
ZP = os.path.join(R, f'beta/data/c/{CODE}/zones.json')
RP = os.path.join(R, 'beta/data/registry.json')
VP = os.path.join(R, f'data/c/{CODE}/villages.json')
SP = os.path.join(R, f'data/c/{CODE}/schools.json')
TODAY = '2026-11-26'
NOTICE = 'https://data.nantou.gov.tw/dataset/doe-02'
RAW = {  # raw 檔 → sha256（官方平台與光華國小鏡像下載結果 byte 相同）
    'raw/10008/nantou_115_elementary_rev20260304_dl20261126.pdf': 'fa889854b479e83fe934878591f20625efc2c96c453b48e51998b716fc33afa2',
    'raw/10008/nantou_115_junior_rev20260304_dl20261126.pdf': 'cfcca9908a746811daaddc4f391fdea566728d031e75e4db8998c7c55f1b027a',
    'raw/10008/nantou_115_zhushan_qianshan_neighbor_adjust_20260309_dl20261126.pdf': '7a71e4b16acf3cb8af7d20497b541b179dd6809572430aa5c580335b63c1131d',
}
URLS = [
    'https://data.nantou.gov.tw/dataset/31775505-f06e-4550-bb93-9d039b68afdd/resource/ba4aa724-51c8-414a-aae7-9005b8bc3675/download/115.pdf',
    'https://data.nantou.gov.tw/dataset/31775505-f06e-4550-bb93-9d039b68afdd/resource/ffb44c93-5376-4967-874c-be7d67ced34e/download/115.pdf',
]

OFFICIAL_NAME = '硘磘里'   # 官方表寫法
TOWN = '竹山鎮'
# 原文逐字（115學年度南投縣各國民小學／國民中學學區劃分表，修訂 115年3月4日）
T_E = '前山國小：硘磘里（1-11鄰）、中山里(註1)。'
T_J = '竹山國中：竹山鎮：雲林里、竹圍里、中和里、中崎里、硘磘里、秀林里、大鞍里、田子里、德興里、鯉魚里（1-11鄰）、福興里（1-3鄰）、中山里(1-35鄰)、桂林里(24鄰)。'
E_SCHOOL, J_SCHOOL = '084751e', '084511j'   # 縣立前山國小、縣立竹山國中
ADJ_NOTE = ('竹山鎮硘磘里：115學年度國小表列前山國小（1-11鄰）、國中表列竹山國中（全里）；官方表寫「硘磘里」，'
            '圖資鍵為「硘[磘]里」，以 tools/addrnorm.py canon()／wild_regex() 對上後寫入圖資原鍵（2026-11-26 補）。'
            '另前山國小附表「竹山鎮里鄰調整對照表」載調整前硘磘里1鄰部分戶別改編入中山里6鄰（鄰別有異動戶別），115學年度仍屬前山國小固定學區。')

# 抽查：(鍵, 層級, [(a, b, 學校代碼…)]) — 逐列對照上述 PDF 原文
SPOT = [
    ('竹山鎮|中和里', 'e', [(1, 11, ['084653e'])]), ('竹山鎮|中和里', 'j', [(1, 11, ['084511j'])]),
    ('竹山鎮|中崎里', 'e', [(1, 13, ['084653e'])]), ('竹山鎮|中崎里', 'j', [(1, 13, ['084511j'])]),
    ('竹山鎮|田子里', 'e', [(1, 2, ['084645e']), (3, 10, ['084648e'])]), ('竹山鎮|田子里', 'j', [(1, 10, ['084511j'])]),
    ('竹山鎮|鯉魚里', 'e', [(1, 11, ['084650e']), (12, 15, ['084647e'])]),
    ('竹山鎮|鯉魚里', 'j', [(1, 11, ['084511j']), (12, 15, ['xd420f616j'])]),
    ('竹山鎮|福興里', 'e', [(1, 8, ['084645e'])]), ('竹山鎮|福興里', 'j', [(1, 3, ['084511j']), (4, 8, ['xd420f616j'])]),
    ('竹山鎮|桂林里', 'e', [(1, 1, ['084649e']), (2, 22, ['084642e']), (23, 24, ['084649e']), (25, 30, ['084642e'])]),
    ('竹山鎮|桂林里', 'j', [(1, 1, ['084511j', '084512j']), (2, 22, ['084512j']), (23, 23, ['084511j', '084512j']), (24, 24, ['084511j']), (25, 30, ['084512j'])]),
    ('竹山鎮|竹圍里', 'e', [(1, 20, ['084649e'])]), ('竹山鎮|竹圍里', 'j', [(1, 20, ['084511j'])]),
    ('竹山鎮|延和里', 'e', [(1, 25, ['084642e'])]), ('竹山鎮|延和里', 'j', [(1, 25, ['084512j'])]),
    ('竹山鎮|中正里', 'e', [(1, 13, ['084642e'])]), ('竹山鎮|中正里', 'j', [(1, 13, ['084512j'])]),
    ('竹山鎮|秀林里', 'e', [(1, 16, ['084648e'])]), ('竹山鎮|大鞍里', 'e', [(1, 12, ['x33ad1910e'])]),
    ('竹山鎮|桶頭里', 'e', [(1, 17, ['084651e'])]), ('竹山鎮|桶頭里', 'j', [(1, 17, ['xd420f616j'])]),
    ('竹山鎮|坪頂里', 'e', [(1, 10, ['084647e'])]), ('竹山鎮|雲林里', 'e', [(1, 36, ['084649e'])]),
    ('竹山鎮|硘[磘]里', 'e', [(1, 11, ['084751e'])]), ('竹山鎮|硘[磘]里', 'j', [(1, 11, ['084511j'])]),
]

def load(p): return json.load(open(p, encoding='utf-8'))
def dump(o, p):
    with open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(o, ensure_ascii=False, separators=(',', ':')))

for rel, h in RAW.items():
    assert hashlib.sha256(open(os.path.join(R, rel), 'rb').read()).hexdigest() == h, rel

V = {}
for f in load(VP)['features']:
    p = f['properties']
    if p.get('v'): V[p['t'] + '|' + p['v']] = p['L']    # 略過空村名（同 import_codex.geo()）
Z = load(ZP)
S = {s['id'] for s in load(SP)} | {s['id'] for s in Z.get('extra_schools', [])}

# 以 canon()/wild_regex() 在圖資鍵中找官方「竹山鎮 硘磘里」
hits = []
for k in V:
    t, v = k.split('|', 1)
    if t != TOWN: continue
    rx = wild_regex(v)
    if (rx and rx.match(canon(OFFICIAL_NAME))) or canon(v) == canon(OFFICIAL_NAME): hits.append(k)
assert hits == ['竹山鎮|硘[磘]里'], hits
KEY = hits[0]; L = V[KEY]
assert L == 11, L                          # 圖資 L=11 = 官方「1-11鄰」
assert E_SCHOOL in S and J_SCHOOL in S
Z['v'][KEY] = {'e': [{'a': 1, 'b': L, 's': [E_SCHOOL], 't': [T_E]}],
               'j': [{'a': 1, 'b': L, 's': [J_SCHOOL], 't': [T_J]}]}

# 全縣檢查：鍵 ⊆ 圖資、校碼 ⊆ 名錄、逐里逐鄰涵蓋
assert set(Z['v']) <= set(V), set(Z['v']) - set(V)
missing = sorted(set(V) - set(Z['v']))
assert not missing, missing
def fmt(ns):
    out = []
    for n in ns:
        if out and out[-1][1] == n - 1: out[-1][1] = n
        else: out.append([n, n])
    return '、'.join(str(a) if a == b else f'{a}-{b}' for a, b in out)
gaps = []
for k in sorted(V):
    for lv in 'ej':
        c = set()
        for x in Z['v'][k].get(lv, []):
            assert all(s in S for s in x['s'] + x.get('p', [])), (k, x)
            c |= set(range(x['a'], (V[k] if x['b'] == 999 else x['b']) + 1))
        g = sorted(set(range(1, V[k] + 1)) - c)
        if g: gaps.append(f"{k} {'國小' if lv == 'e' else '國中'} 第{fmt(g)}鄰")
print('空鄰（全縣，既有、本 PR 未動）:', len(gaps)); [print('  ', g) for g in gaps]
assert not [g for g in gaps if g.startswith(KEY)], gaps

for k, lv, exp in SPOT:
    got = [(x['a'], x['b'], sorted(x['s'])) for x in Z['v'][k][lv]]
    assert got == [(a, b, sorted(s)) for a, b, s in exp], (k, lv, got)
print('抽查 OK：', len({k for k, _, _ in SPOT}), '里')

M = Z['meta']
for u in [NOTICE] + URLS + list(RAW):
    if u not in M['source_files']: M['source_files'].append(u)
OLDN = '官方資料平台回應503；使用官方光華國小鏡像，兩份PDF均載115學年度與115/3/4修訂。'
NEWN = ('官方資料平台 data.nantou.gov.tw/dataset/doe-02 於 Codex 整理時曾回應503，故改用光華國小鏡像；'
        '2026-11-26 重試：預設 curl 回 403，改用瀏覽器 User-Agent 可正常下載，國小／國中 115 學年度 PDF 與鏡像 sha256 完全相同（修訂 115年3月4日）。')
M['notes'] = [NEWN if n in (OLDN, NEWN) else n for n in M['notes']]
M['notes'] = [n for n in M['notes'] if not n.startswith('竹山鎮硘磘里：')] + [ADJ_NOTE]
M['updated'] = TODAY
M['check'] = {'checked': TODAY, 'scope': '全縣鍵與逐鄰涵蓋檢查；本次只改 竹山鎮|硘[磘]里',
              'village_keys': f'zones.json {len(Z["v"])} 鍵 = data/c/{CODE}/villages.json 有村名者 {len(V)} 鍵（差集 0）',
              'added': {KEY: '國小 前山國小 1-11鄰；國中 竹山國中 1-11鄰（全里）'},
              'empty_neighbors_existing': gaps,
              'spot_check_villages': sorted({k for k, _, _ in SPOT}),
              'source': list(RAW)}
dump(Z, ZP)

REG = load(RP)
r = next(x for x in REG['counties'] if x['code'] == CODE)
r['zoneVillages'] = sum(1 for k in V if k in Z['v'])
r['updated'] = TODAY
r['source'] = ('南投縣政府教育處 115學年度國民中小學學區劃分表（修訂 115年3月4日）PDF：官方開放資料平台與光華國小鏡像同檔；'
               'Codex 整理，2026-11-26 補竹山鎮硘[磘]里')
assert r['villages'] == len(V) == r['zoneVillages'], (r['villages'], len(V), r['zoneVillages'])
dump(REG, RP)
print('ok', r['zoneVillages'], '/', r['villages'])
