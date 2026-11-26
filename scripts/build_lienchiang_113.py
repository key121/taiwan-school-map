"""連江縣 113學年度 國民中小學學區（Issue #1 P3-C）。

來源：連江縣政府教育處「法令規章」→ 國教科法令「連江縣113學年度國民小學、國民中學學區劃分表」（發布 113-07-10）
  公告頁 https://www.matsu.edu.tw/Rule.aspx?cnid=44&p=254
  國小 https://www.matsu.edu.tw/Download_File.ashx?id=24549 → raw/09007/lienchiang_113_elem_zones_20240710.pdf
  國中 https://www.matsu.edu.tw/Download_File.ashx?id=24550 → raw/09007/lienchiang_113_jhs_zones_20240710.pdf
PDF 標題為「連江縣113學年度國民小學／國民中學學區劃分表(113年7月1日更新)」。
中文字型沒有 ToUnicode（pdftotext 只抽得出數字），以 PyMuPDF 轉 150dpi 圖檔人工判讀，下方 SRC 為逐字抄錄
（只去掉排版用空白）。2026-11-26 查教育處網站（法令規章、行政公告、下載專區）未見 114／115 學年度新表，
故 years 照實寫 113，不標成 115。

原表為「學校 → 村名」，全部以整村列出（無鄰別、無門牌條件），故每村寫一段 a=1,b=999（至末鄰）。
南竿鄉國小三校（介壽、中正、仁愛）、國中兩校（介壽、中正）列出完全相同的 9 村，原文未說明如何分配，
本站照原文同列，不推定「哪一校為主」。
可重跑：每次整檔重建 zones.json，並只改 registry 的 09007 那一筆。
"""
import json, os
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE = '09007'
ZP = os.path.join(R, f'beta/data/c/{CODE}/zones.json')
RP = os.path.join(R, 'beta/data/registry.json')
VP = os.path.join(R, f'data/c/{CODE}/villages.json')
SP = os.path.join(R, f'data/c/{CODE}/schools.json')
TODAY = '2026-11-26'
PAGE = 'https://www.matsu.edu.tw/Rule.aspx?cnid=44&p=254'
FILES = ['https://www.matsu.edu.tw/Download_File.ashx?id=24549', 'https://www.matsu.edu.tw/Download_File.ashx?id=24550',
         'raw/09007/lienchiang_113_elem_zones_20240710.pdf', 'raw/09007/lienchiang_113_jhs_zones_20240710.pdf']

NANGAN = '介壽村、復興村、福沃村、清水村、馬祖村、珠螺村、四維村、仁愛村、津沙村'
BEIGAN = '塘岐村、后沃村、橋仔村、芹壁村、坂里村、白沙村'
# (學校原文, 學區範圍原文, 鄉鎮原文, 校碼)
SRC = {
    'e': [
        ('介壽國中小(國小部)', NANGAN, '南竿鄉', '724601e'),
        ('中正國中小(國小部)', NANGAN, '南竿鄉', '724602e'),
        ('仁愛國小', NANGAN, '南竿鄉', '724603e'),
        ('塘岐國小', BEIGAN, '北竿鄉', '724604e'),
        ('敬恆國中小(國小部)', '青帆村、田沃村、西坵村', '莒光鄉', '724606e'),
        ('東莒國小', '大坪村、福正村', '莒光鄉', '724607e'),
        ('東引國中小(國小部)', '中柳村、樂華村', '東引鄉', '724608e'),
    ],
    'j': [
        ('介壽國中小(國中部)', NANGAN, '南竿鄉', '724501j'),
        ('中正國中小(國中部)', NANGAN, '南竿鄉', '724502j'),
        ('中山國中', BEIGAN, '北竿鄉', '724503j'),
        ('敬恆國中小(國中部)', '青帆村、田沃村、西坵村、大坪村、福正村', '莒光鄉', '724504j'),
        ('東引國中小(國中部)', '中柳村、樂華村', '東引鄉', '724505j'),
    ],
}
TITLE = {'e': '連江縣113學年度國民小學學區劃分表(113年7月1日更新)', 'j': '連江縣113學年度國民中學學區劃分表(113年7月1日更新)'}

def load(p): return json.load(open(p, encoding='utf-8'))
def dump(o, p):
    with open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(o, ensure_ascii=False, separators=(',', ':')))

V = {}
for f in load(VP)['features']:
    p = f['properties']
    if p.get('v'): V[p['t'] + '|' + p['v']] = p['L']
S = {s['id']: s for s in load(SP)}
assert len(V) == 22, len(V)

Z = {'v': {}}
for lv, rows in SRC.items():
    for school, scope, town, sid in rows:
        assert sid in S and S[sid]['town'] == town, (sid, town)
        t = f'{school}：{scope}（{town}）'
        for vill in scope.split('、'):
            key = f'{town}|{vill}'
            assert key in V, key                      # 村里鍵必須與圖資完全一致
            segs = Z['v'].setdefault(key, {'e': [], 'j': []})[lv]
            if not segs: segs.append({'a': 1, 'b': 999, 's': [], 't': []})
            segs[0]['s'].append(sid); segs[0]['t'].append(t)

# 逐村逐鄰涵蓋：每村國小、國中都要有一段 1–999
gaps = [f'{k} {lv}' for k in V for lv in 'ej' if not (Z['v'].get(k, {}).get(lv))]
assert not gaps, gaps
assert set(Z['v']) == set(V)
multi = sorted(f"{k} {'國小' if lv == 'e' else '國中'}：{'、'.join(S[i]['name'] for i in x[0]['s'])}"
               for k, d in Z['v'].items() for lv, x in d.items() if len(x[0]['s']) > 1)

Z['meta'] = {
    'county': '連江縣', 'years': '113',
    'title': '連江縣113學年度國民小學、國民中學學區劃分表（連江縣政府教育處，113年7月1日更新）',
    'source_page': PAGE, 'source_files': FILES, 'publisher': '連江縣政府教育處（國民教育科）',
    'method': 'PDF 無 ToUnicode，轉圖人工逐字判讀；原表以整村列出，每村寫 a=1,b=999。scripts/build_lienchiang_113.py 可重跑。',
    'notes': ['官方公開最新為113學年度表（教育處法令規章 113-07-10 發布），2026-11-26 查無114／115學年度新表；115學年度是否變動請洽教育處國民教育科 0836-25614。',
              '南竿鄉國小三校（介壽、中正、仁愛）、國中兩校（介壽、中正）原表列出相同9村，原文未說明分配方式，本站照原文同列。'],
    'multi_label': '原表各校同列此村', 'auto_parsed': False, 'updated': TODAY, 'incomplete': [], 'warnings': [],
    'origin': 'ours',
    'check': {'checked': TODAY, 'source': FILES[2:],
              'village_keys': f'zones.json {len(Z["v"])} 鍵 = data/c/09007/villages.json 有村名者 {len(V)} 鍵（差集 0；未編定村里圖斑略過）',
              'coverage': '22村 × 國小／國中 皆有 1–999 整村段，無空鄰', 'unlisted_by_official_table': [],
              'school_ids': '全部校碼 ⊆ data/c/09007/schools.json', 'same_scope_multi_school': multi},
}
Z = {'meta': Z['meta'], 'v': {k: Z['v'][k] for k in sorted(Z['v'])}}
os.makedirs(os.path.dirname(ZP), exist_ok=True)
dump(Z, ZP)

REG = load(RP)
r = next(x for x in REG['counties'] if x['code'] == CODE)
r.update({
    'origin': 'ours', 'hasZones': True, 'years': '113',
    'source': '連江縣政府教育處「連江縣113學年度國民小學、國民中學學區劃分表」（113年7月1日更新，113-07-10 發布；公開最新年度，非115）',
    'official': PAGE, 'officialNotice': PAGE, 'verification': 'manual-transcribed', 'updated': TODAY,
    'incomplete': [], 'zoneVillages': sum(1 for k in V if k in Z['v']),
    'warning': '本縣資料為113學年度（官方公開最新），115學年度是否變動請洽連江縣政府教育處國民教育科 0836-25614。',
    'partialNote': '依連江縣政府教育處公開最新之113學年度學區表收錄全縣22村（整村列出）；尚未見115學年度新表，本縣亦無可公開再散布的門牌資料，最新學區請洽教育處。',
})
assert r['status'] == 'partial' and r['addr'] is None
dump(REG, RP)
print('ok', r['zoneVillages'], '/', r['villages']); print('\n'.join(multi))
