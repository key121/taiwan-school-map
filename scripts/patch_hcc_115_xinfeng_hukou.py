"""新竹縣 115學年度 新豐鄉／湖口鄉 缺口核對與補丁（Issue #1 P1-B）。

來源：新竹縣政府「新竹縣115學年度各鄉鎮(市)國民中小學學區劃分表」
  （依新竹縣政府115年2月2日府授教國字第1150651170C號函；附件檔名「115學年度學區劃分表(正確版)1150202.pdf」，
   由竹北市仁愛國中轉公告：https://jajh.hcc.edu.tw/p/406-1006-528106,r1490.php?Lang=zh-tw）
  raw/10004/hcc_115_school_zones_20260202.pdf（16頁：PDF第1–7頁國中、第8–16頁國小）
PDF 中文字型沒有 ToUnicode（pdftotext 抽不出中文），以 PyMuPDF 轉 150dpi 圖檔逐頁人工判讀；
下方 SRC 為原文逐字抄錄（只抄與本次修改相關的列）。

結論（逐鄰對照 data/c/10004/villages.json 的 L）：
  官方表確實未列 → 不補，前端自動顯示「表列未涵蓋」：
    新豐鄉|上坑村 國中 第4–12鄰（國中表只有新豐國中、忠孝國中「上坑村1-3鄰【共同學區】」）
    湖口鄉|湖南村 國小 第1–6、11–18鄰（國小表只有「湖南村7-10鄰【湖口、中興、華興三校共同學區】」）
    湖口鄉|東興村 國小 第1–10、12–14、17–18、24–26鄰（國小表只有「東興村11鄰、15-16鄰、19-23鄰【新湖、和興共同學區】」）
  門牌條件 → 寫入預設學校 s，另以 p／m 保留門牌條件（不拆成確定指派）：
    新豐鄉|崎頂村 第15、20鄰（國小：新豐國小，另可能山崎國小；國中：新豐國中，另可能忠孝國中）
  修正 Codex 解析錯誤（原文本來就有、但被錯貼到其他鄰或誤當共同學區）：
    湖口鄉|鳳山村 國小：「1鄰部份區域」門牌條件被貼到6–23鄰、並把山崎／華興誤列為12–23鄰共同學區 → 依原文重建 1／2／3／4–5／6–11／12–20／21–23鄰
    湖口鄉|仁勢村 國中：依街道單雙號分屬湖口／新湖國中，原檔把兩校都放在 s（前端會顯示「可擇一」）→ s 改為空、兩校留在 p、m 寫明條件
可重跑：每次整段覆寫目標村里／學制，結果相同。
"""
import json, os
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE = '10004'
ZP = os.path.join(R, f'beta/data/c/{CODE}/zones.json')
RP = os.path.join(R, 'beta/data/registry.json')
VP = os.path.join(R, f'data/c/{CODE}/villages.json')
SP = os.path.join(R, f'data/c/{CODE}/schools.json')
TODAY = '2026-11-26'
PAGE = 'https://jajh.hcc.edu.tw/p/406-1006-528106,r1490.php?Lang=zh-tw'
RAW = 'raw/10004/hcc_115_school_zones_20260202.pdf'
FILE = ('https://jajh.hcc.edu.tw/app/index.php?Action=downloadfile&file=dGp4eXJqUTFMTWhjZXQzZHhyc2lHNEpHa3RnVllqOHhzamJxRzQrZGZNRGhWK0RCTVptd1lJK2RTYlJ5S3JCc0F4VFhiTG9JTWlXSnpac3A1ckZHYmZPekc2K3FSOCtGUzBhUXowdUIvUVE9'
        '&fname=cjhYS2pxUldORnNUaWYrSTk2eStMbWVITWpkOGI0WXdpaGUyTUw1c0I0Q2pjQk93b2xvcjg0ODhyTFdOWFVlc1VUZnk4Z2piK1hxbjhOUm4xbHdtd3IwK1JVTVFBaXQ0Sm8vRE91eDRnYWlnYVYrSGoxS0FMQXM1RmJGYU9najJLVlFmNGhOaGNEcGs4bkVBY2ZWa0dRPT0=')

# 校碼（data/c/10004/schools.json）
XF_E, SQ_E, SL_E = '044651e', '044641e', '044681e'          # 新豐國小、山崎國小、松林國小
HX_E, ZX_E = '044644e', '044643e'                          # 華興國小、中興國小
XF_J, ZXIAO_J, HK_J, XH_J = '044513j', '044525j', '044534j', '044521j'  # 新豐國中、忠孝國中、湖口國中、新湖國中

# 原文逐字（115學年度學區劃分表 PDF；括號內為 PDF 頁碼）
SRC = {
    'qd_e_xf': '新豐國小：崎頂村（1-14鄰、15鄰新庄子45號、20鄰新庄子23-27號、22-23鄰屬山崎國小）。',   # p13
    'qd_e_sq': '山崎國小：崎頂村1-14鄰、15鄰新庄子45號、20鄰新庄子23-27號、22-23鄰。',               # p13
    'qd_j_xf': '新豐國中：崎頂村（1-14鄰、15鄰新庄子45號、20鄰新庄子23-27號、22-23鄰屬忠孝國中）。',   # p5
    'qd_j_zx': '忠孝國中：崎頂村1-14鄰、15鄰新庄子45號、20鄰新庄子23-27號、22-23鄰。',               # p5
    'fs_hx_1_11': '華興國小：鳳山村1-11鄰',                                                          # p15
    'fs_hx_1p': '華興國小：鳳山村1鄰部份區域【三民二路全部；榮光一路全部；三民南路110、142、226、228、236(臨)號；榮光路545、593、605、613、617號為華興國小及山崎國小共同學區】。',
    'fs_sq_1p': '山崎國小：湖口鄉鳳山村1鄰部份區域【三民二路全部；榮光一路全部；三民南路110、142、226、228、236(臨)號；榮光路545、593、605、613、617號為華興國小及山崎國小共同學區】',  # p13
    'fs_hx_245': '華興國小：鳳山村2鄰、4-5鄰【華興國小及山崎國小共同學區】',
    'fs_sq_245': '山崎國小：湖口鄉鳳山村2鄰、4-5鄰【華興國小及山崎國小共同學區】。',
    'fs_hx_3': '華興國小：鳳山村3鄰【華興國小、山崎國小、松林國小三校共同學區】。',
    'fs_sq_3': '山崎國小：湖口鄉鳳山村3鄰【華興國小、山崎國小、松林國小三校共同學區】。',
    'fs_sl_3': '松林國小：湖口鄉鳳山村3鄰【華興國小、山崎國小、松林國小三校共同學區】。',
    'fs_zx': '中興國小：鳳山村12-20鄰。',                                                            # p16
    'fs_sq_21': '山崎國小：湖口鄉鳳山村21-23鄰。',                                                  # p13
    'rs_hk': '湖口國中：仁勢村（民權街、民生街全部。民族街雙號以東）。',                              # p7
    'rs_xh': '新湖國中：仁勢村（民族街單號以西）。',                                                  # p7
}
NOTE = {
    'qd15e': '依門牌分屬：崎頂村15鄰「新庄子45號」屬山崎國小；本鄰其餘門牌屬新豐國小（新豐國小列「崎頂村（…15鄰新庄子45號…屬山崎國小）」）。請以戶籍門牌核對。',
    'qd20e': '依門牌分屬：崎頂村20鄰「新庄子23-27號」屬山崎國小；本鄰其餘門牌屬新豐國小（新豐國小列「崎頂村（…20鄰新庄子23-27號…屬山崎國小）」）。請以戶籍門牌核對。',
    'qd15j': '依門牌分屬：崎頂村15鄰「新庄子45號」屬忠孝國中（總量管制）；本鄰其餘門牌屬新豐國中（新豐國中列「崎頂村（…15鄰新庄子45號…屬忠孝國中）」）。請以戶籍門牌核對。',
    'qd20j': '依門牌分屬：崎頂村20鄰「新庄子23-27號」屬忠孝國中（總量管制）；本鄰其餘門牌屬新豐國中（新豐國中列「崎頂村（…20鄰新庄子23-27號…屬忠孝國中）」）。請以戶籍門牌核對。',
    'fs1': '依門牌分屬：鳳山村1鄰屬華興國小；其中三民二路全部、榮光一路全部、三民南路110、142、226、228、236(臨)號、榮光路545、593、605、613、617號為華興國小及山崎國小共同學區。請以戶籍門牌核對。',
    'rs': '依街道門牌分屬：民權街、民生街全部及民族街雙號以東屬湖口國中；民族街單號以西屬新湖國中。原文未逐鄰列出，本站不以鄰別定案，請以戶籍門牌核對。',
}

def seg(a, b, s, t, m=None, p=None):
    x = {'a': a, 'b': b, 's': s, 't': [SRC[k] for k in t]}
    if m: x['m'] = [NOTE[m]]
    if p: x['p'] = p
    return x

# (村里鍵, 學制, 只覆寫這些鄰, 新鄰段)
PATCH = [
    ('新豐鄉|崎頂村', 'e', {15, 20}, [
        seg(15, 15, [XF_E], ['qd_e_xf', 'qd_e_sq'], 'qd15e', [SQ_E]),
        seg(20, 20, [XF_E], ['qd_e_xf', 'qd_e_sq'], 'qd20e', [SQ_E])]),
    ('新豐鄉|崎頂村', 'j', {15, 20}, [
        seg(15, 15, [XF_J], ['qd_j_xf', 'qd_j_zx'], 'qd15j', [ZXIAO_J]),
        seg(20, 20, [XF_J], ['qd_j_xf', 'qd_j_zx'], 'qd20j', [ZXIAO_J])]),
    ('湖口鄉|鳳山村', 'e', set(range(1, 24)), [
        seg(1, 1, [HX_E], ['fs_hx_1_11', 'fs_hx_1p', 'fs_sq_1p'], 'fs1', [SQ_E]),
        seg(2, 2, [HX_E, SQ_E], ['fs_hx_1_11', 'fs_hx_245', 'fs_sq_245']),
        seg(3, 3, [HX_E, SQ_E, SL_E], ['fs_hx_1_11', 'fs_hx_3', 'fs_sq_3', 'fs_sl_3']),
        seg(4, 5, [HX_E, SQ_E], ['fs_hx_1_11', 'fs_hx_245', 'fs_sq_245']),
        seg(6, 11, [HX_E], ['fs_hx_1_11']),
        seg(12, 20, [ZX_E], ['fs_zx']),
        seg(21, 23, [SQ_E], ['fs_sq_21'])]),
    ('湖口鄉|仁勢村', 'j', set(range(1, 13)), [
        seg(1, 12, [], ['rs_hk', 'rs_xh'], 'rs', [HK_J, XH_J])]),
]
# 官方表確實未列（不補）
UNLISTED = {
    ('新豐鄉|上坑村', 'j'): list(range(4, 13)),
    ('湖口鄉|湖南村', 'e'): list(range(1, 7)) + list(range(11, 19)),
    ('湖口鄉|東興村', 'e'): list(range(1, 11)) + [12, 13, 14, 17, 18, 24, 25, 26],
}

def load(p): return json.load(open(p, encoding='utf-8'))
def dump(o, p):
    with open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(o, ensure_ascii=False, separators=(',', ':')))

V = {}
for f in load(VP)['features']:
    p = f['properties']
    if p.get('v'): V[p['t'] + '|' + p['v']] = p['L']
Z = load(ZP)
S = {s['id'] for s in load(SP)} | {s['id'] for s in Z.get('extra_schools', [])}
assert set(Z['v']) == set(V), set(Z['v']) ^ set(V)           # 村里鍵與圖資完全一致

def nums(x, L): return set(range(x['a'], (L if x['b'] == 999 else x['b']) + 1))

for key, lv, tgt, new in PATCH:
    assert key in V and key in Z['v'], key
    L = V[key]
    assert max(tgt) <= L, (key, L)
    for x in new:
        assert nums(x, L) <= tgt, (key, x)
        assert all(c in S for c in x['s'] + x.get('p', [])), x
    segs = Z['v'][key].setdefault(lv, [])
    keep = []
    for x in segs:
        n = nums(x, L)
        if n <= tgt: continue                                 # 整段在目標鄰內 → 由新段取代
        assert not n & tgt, (key, lv, x)                       # 不可切到其他既有段
        keep.append(x)
    segs[:] = sorted(keep + new, key=lambda x: x['a'])

# 涵蓋檢查（新豐鄉、湖口鄉全部村里）
def fmt(ns):
    out = []
    for n in ns:
        if out and out[-1][1] == n - 1: out[-1][1] = n
        else: out.append([n, n])
    return '、'.join(str(a) if a == b else f'{a}-{b}' for a, b in out)
LVN = {'e': '國小', 'j': '國中'}
gaps, cond = {}, []
for key in sorted(V):
    if not key.startswith(('新豐鄉|', '湖口鄉|')): continue
    L = V[key]
    for lv in 'ej':
        segs = Z['v'][key].get(lv, [])
        c = set()
        for x in segs: c |= nums(x, L)
        g = sorted(set(range(1, L + 1)) - c)
        if g: gaps[(key, lv)] = g
        cn = sorted(set().union(*[nums(x, L) for x in segs if x.get('m') or x.get('p')]) if segs else set())
        if cn: cond.append(f'{key} {LVN[lv]} 第{fmt(cn)}鄰')
        # 同鄰不可重複出現在兩段
        tot = sum(len(nums(x, L)) for x in segs)
        assert tot == len(c), (key, lv, '重疊')
assert gaps == UNLISTED, gaps
unlisted = [f'{k} {LVN[lv]} 第{fmt(g)}鄰' for (k, lv), g in sorted(gaps.items())]
print('表列未涵蓋', unlisted)
print('門牌／條件', cond)

M = Z['meta']
for u in (FILE, RAW):
    if u not in M['source_files']: M['source_files'].append(u)
NEW = ('新豐鄉、湖口鄉已於2026-11-26對照115學年度官方學區劃分表（府授教國字第1150651170C號，1150202正確版）逐鄰核對：'
       '新豐鄉上坑村第4–12鄰（國中）、湖口鄉湖南村第1–6、11–18鄰（國小）、東興村第1–10、12–14、17–18、24–26鄰（國小）官方表確實未列，顯示「表列未涵蓋，請洽教育處」；'
       '崎頂村第15、20鄰依「新庄子」門牌分屬，以預設學校加「另可能」條件呈現；湖口鄉仁勢村國中依街道單雙號分屬湖口／新湖國中，只列條件，不定案。')
M['warnings'] = [w for w in M.get('warnings', []) if not w.startswith('新豐鄉、湖口鄉已於')] + [NEW]
M['incomplete'] = []
M['updated'] = TODAY
M['check'] = {
    'checked': TODAY, 'scope': '新豐鄉、湖口鄉（其他11鄉鎮市未重跑）', 'source': [RAW],
    'unlisted_by_official_table': unlisted,
    'conditional_by_doorplate': cond,
    'fixed_parse_errors': ['湖口鄉|鳳山村 國小：1鄰部份區域門牌條件曾誤貼至6–23鄰、12–23鄰誤列華興／山崎共同學區，已依原文重建',
                           '湖口鄉|仁勢村 國中：街道單雙號分屬原誤列為兩校皆可（s），改為僅列條件（p＋m）'],
    'village_keys': f'zones.json {len(Z["v"])} 鍵 = data/c/{CODE}/villages.json 有村名者 {len(V)} 鍵（差集 0）',
}
dump(Z, ZP)

REG = load(RP)
r = next(x for x in REG['counties'] if x['code'] == CODE)
r['incomplete'] = []
r['updated'] = TODAY
r['zoneVillages'] = sum(1 for k in V if k in Z['v'])
r['warning'] = ('新豐鄉上坑村第4–12鄰國中、湖口鄉湖南村第1–6、11–18鄰國小、東興村第1–10、12–14、17–18、24–26鄰國小，115學年度官方表未列（表列未涵蓋）；'
                '新豐鄉崎頂村第15、20鄰、湖口鄉鳳山村第1鄰（國小）、仁勢村（國中）依門牌或街道分屬，請以戶籍門牌核對並洽新竹縣政府教育處。')
dump(REG, RP)
print('ok', r['zoneVillages'], '/', r['villages'])
