"""桃園市 115學年度 八德區／大溪區 缺口核對與補丁（Issue #1 P1-A）。

來源：桃園市政府教育局「八德區／大溪區115學年度國民中小學學區一覽表」PDF（上版日期 114-12-31）
  raw/68000/tyc_115_bade_20251231.pdf  ← https://www.tyc.edu.tw/News_Content.aspx?n=5208&s=1601250
  raw/68000/tyc_115_daxi_20251231.pdf  ← https://www.tyc.edu.tw/News_Content.aspx?n=5208&s=1601252
兩份 PDF 的中文字型沒有 ToUnicode 對照（pdftotext 抽不出中文），故以 PyMuPDF 轉 150dpi 圖檔後逐頁人工判讀；
下方 SRC 為原文逐字抄錄（只抄與缺口相關的列）。

結論（逐鄰核對 villages.json 的 L）：
  官方表確實未列 → 不補，前端自動顯示「表列未涵蓋」：
    八德區|瑞興里 第22鄰（國小、國中）、八德區|瑞豐里 第31鄰（國小）、八德區|大興里 第28鄰（國小）
  原文有歧義（只列某鄰的門牌除外，其餘鄰未見於任何學校）→ 只列「條件候選」（s 為空、p 列候選校、m 寫明待確認），不定案：
    八德區|大智里 國小／國中 第1–23、25–32鄰（候選：大成國小／大成國中）
    大溪區|仁美里 國中 第1–3、5–19鄰（候選：仁和國中）
    大溪區|仁善里 國中 第2–5、7–8、10–19鄰（候選：仁和國中）
可重跑：每次先移除目標鄰段再寫入，結果相同。
"""
import json, os
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZP = os.path.join(R, 'beta/data/c/68000/zones.json')
RP = os.path.join(R, 'beta/data/registry.json')
VP = os.path.join(R, 'data/c/68000/villages.json')
TODAY = '2026-11-26'

BADE = 'https://ws.tycg.gov.tw/Download.ashx?u=LzAwMS9VcGxvYWQvNjYvcmVsZmlsZS8xMTI4Ni8xNjAxMjUwLzUyNGQzZDM2LTM4ZTctNDNkMy05ZTAxLTA0MDM1YTIzMTZkNS5wZGY%3d&n=5YWr5b635Y2AMTE15a245bm05bqm5ZyL5rCR5Lit5bCP5a245a245Y2A5LiA6Ka96KGoLnBkZg%3d%3d'
DAXI = 'https://ws.tycg.gov.tw/Download.ashx?u=LzAwMS9VcGxvYWQvNjYvcmVsZmlsZS8xMTI4Ni8xNjAxMjUyL2FkMjM3NDAxLWM0ZDctNGU2YS04ODFjLTBhNTQ3MTdlMTFhZC5wZGY%3d&n=5aSn5rqq5Y2AMTE15a245bm05bqm5ZyL5rCR5Lit5bCP5a245a245Y2A5LiA6Ka96KGoLnBkZg%3d%3d'

# 原文逐字（八德區／大溪區 115學年度 PDF）
SRC = {
    'dazhi_e': '大成國小：大智（24【桃德路8巷26弄1~3號 、5~8號、10號，桃德路8巷32號除外】）',
    'dazhi_j': '大成國中：大智(24鄰桃德路8巷26弄1~3號 、5~8號、10號，桃德路8巷32號除外)',
    'renmei_j': '仁和國中：仁美(4【仁美街172巷180號及仁美街172巷180之1號除外】)',
    'renshan_j': '仁和國中：仁善（9【新光東路76巷29號】除外、6【埔頂路二段474巷23號、474巷31號、527號、575巷118號】除外）',
}
NOTE = {
    'dazhi': '待確認：八德區115學年度表中「大智」只見於大成國小「大智（24【…除外】）」、大成國中「大智(24鄰…除外)」及大勇國小／建國國中的24鄰指定門牌；本里第1–23、25–32鄰未見於任何學校。若原意為「全里，惟24鄰指定門牌除外」則屬大成國小／大成國中，但原文未明寫，本站不定案，請洽桃園市政府教育局。',
    'renmei': '待確認：大溪區115學年度國中表中「仁美」只見於仁和國中「仁美(4【…除外】)」及仁美4鄰指定門牌之仁和／八德國中自由學區；本里第1–3、5–19鄰未見於任何國中。若原意為「全里，惟4鄰指定門牌除外」則屬仁和國中，但原文未明寫，本站不定案，請洽桃園市政府教育局。',
    'renshan': '待確認：大溪區115學年度國中表中仁和國中列「仁善（9【…】除外、6【…】除外）」，括號內只列除外門牌、未列鄰別範圍；另「◎仁善（1、9【…】、6【…】）」為仁和、八德國中自由學區。本里第2–5、7–8、10–19鄰可能屬仁和國中，但原文未逐鄰列出，本站不定案，請洽桃園市政府教育局。',
}
# (key, level, 鄰段, 候選校, 原文鍵, 註記鍵)
PATCH = [
    ('八德區|大智里', 'e', [(1, 23), (25, 32)], ['034646e'], 'dazhi_e', 'dazhi'),
    ('八德區|大智里', 'j', [(1, 23), (25, 32)], ['034517j'], 'dazhi_j', 'dazhi'),
    ('大溪區|仁美里', 'j', [(1, 3), (5, 19)], ['034513j'], 'renmei_j', 'renmei'),
    ('大溪區|仁善里', 'j', [(2, 5), (7, 8), (10, 19)], ['034513j'], 'renshan_j', 'renshan'),
]
UNLISTED = [  # 官方表確實未列（不補）
    ('八德區|瑞興里', 'e', 22), ('八德區|瑞興里', 'j', 22),
    ('八德區|瑞豐里', 'e', 31), ('八德區|大興里', 'e', 28),
]

def load(p): return json.load(open(p, encoding='utf-8'))
def dump(o, p):
    with open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(o, ensure_ascii=False, separators=(',', ':')))

V = {}
for f in load(VP)['features']:
    p = f['properties']
    if p.get('v'): V[p['t'] + '|' + p['v']] = p['L']
Z = load(ZP)
S = {s['id'] for s in load(os.path.join(R, 'data/c/68000/schools.json'))}

for key, lv, ranges, cand, src, note in PATCH:
    assert key in V and key in Z['v'], key            # 鍵名必須與圖資完全一致
    assert all(c in S for c in cand), cand
    L = V[key]; tgt = {n for a, b in ranges for n in range(a, b + 1)}
    assert max(tgt) <= L, (key, L)
    segs = Z['v'][key].setdefault(lv, [])
    # 移除先前寫入的同鄰段（可重跑），不動其他鄰
    segs[:] = [x for x in segs if not set(range(x['a'], (L if x['b'] == 999 else x['b']) + 1)) <= tgt]
    for x in segs:
        assert not set(range(x['a'], (L if x['b'] == 999 else x['b']) + 1)) & tgt, (key, lv, x)
    for a, b in ranges:
        segs.append({'a': a, 'b': b, 's': [], 't': [SRC[src]], 'm': [NOTE[note]], 'p': cand})
    segs.sort(key=lambda x: x['a'])

# 涵蓋檢查（八德區、大溪區全部村里）
def cover(key, lv, strict):
    L = V[key]; c = set()
    for x in Z['v'][key].get(lv, []):
        if strict and not x['s']: continue
        c |= set(range(x['a'], (L if x['b'] == 999 else x['b']) + 1))
    return sorted(set(range(1, L + 1)) - c)
def fmt(ns):
    out = [];
    for n in ns:
        if out and out[-1][1] == n - 1: out[-1][1] = n
        else: out.append([n, n])
    return '、'.join(str(a) if a == b else f'{a}-{b}' for a, b in out)
gaps, cond = [], []
for key in sorted(V):
    if not key.startswith(('八德區|', '大溪區|')): continue
    for lv in 'ej':
        g = cover(key, lv, False); d = cover(key, lv, True)
        if g: gaps.append(f"{key} {'國小' if lv=='e' else '國中'} 第{fmt(g)}鄰")
        only = sorted(set(d) - set(g))
        if only: cond.append(f"{key} {'國小' if lv=='e' else '國中'} 第{fmt(only)}鄰")
exp = sorted(f"{k} {'國小' if lv=='e' else '國中'} 第{n}鄰" for k, lv, n in UNLISTED)
assert sorted(gaps) == exp, gaps
print('表列未涵蓋', gaps); print('僅條件候選（含原有門牌條件鄰）', cond)

M = Z['meta']
for u in (BADE, DAXI):
    if u not in M['source_files']: M['source_files'].append(u)
OLD = '八德區瑞興里22鄰、瑞豐里31鄰、大興里28鄰及大智里部分鄰，另大溪區仁善／仁美里部分國中範圍未能從115表確定；不把鄰號括號中的門牌除外泛化為全里。'
NEW = ('八德區、大溪區已於2026-11-26對照115學年度官方PDF（上版日期114-12-31）逐鄰核對：'
       '八德區瑞興里第22鄰（國小、國中）、瑞豐里第31鄰（國小）、大興里第28鄰（國小）官方表確實未列，顯示「表列未涵蓋，請洽教育局」；'
       '八德區大智里（第24鄰以外）、大溪區仁美里（第4鄰以外）及仁善里（第1、6、9鄰以外）之國中，原文只列某鄰指定門牌「除外」而未逐鄰列出，'
       '僅列大成國小／大成國中、仁和國中為「條件候選（待確認）」，不定案、不泛化為全里。')
M['warnings'] = [NEW if w in (OLD,) or w.startswith('八德區、大溪區已於') else w for w in M['warnings']]
M['notes'] = [n.replace(OLD, NEW) for n in M['notes']]
M['incomplete'] = []
M['updated'] = TODAY
M['check'] = {'checked': TODAY, 'scope': '八德區、大溪區（其他11區未重跑）',
              'source': ['raw/68000/tyc_115_bade_20251231.pdf', 'raw/68000/tyc_115_daxi_20251231.pdf'],
              'unlisted_by_official_table': gaps, 'conditional_candidates_only': cond,
              'village_keys': 'zones.json 529 鍵 = data/c/68000/villages.json 有村名者 529 鍵（差集 0）'}
assert set(Z['v']) == set(V)
dump(Z, ZP)

REG = load(RP)
r = next(x for x in REG['counties'] if x['code'] == '68000')
r['incomplete'] = []
r['updated'] = TODAY
r['zoneVillages'] = sum(1 for k in V if k in Z['v'])
r['warning'] = ('八德區瑞興里第22鄰、瑞豐里第31鄰國小、大興里第28鄰國小，115學年度官方表未列（表列未涵蓋）；'
                '八德區大智里、大溪區仁美里／仁善里部分鄰之國中（大智里含國小）原文只列門牌除外、未逐鄰列出，僅列條件候選待確認，請洽桃園市政府教育局。')
dump(REG, RP)
print('ok', r['zoneVillages'], '/', r['villages'])
