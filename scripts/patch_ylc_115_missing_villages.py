"""雲林縣 115學年度 缺漏村里核對與補丁（Issue #1 P1-C）。

來源：雲林縣政府「修正雲林縣115學年度國民中小學學區劃分表」附件一（表頭 115.1.19，公告 1150128）
  公告頁 https://huwei.yunlin.gov.tw/News_Content.aspx?n=20380&s=579611
  原檔 474,894 bytes，SHA-256 2f509fed3ded76ffab91a8012a5c1c5bd04e2b5b2de917809499ff829ca1010a
  來源紀錄與逐字摘錄：raw/10009/ylc_115_zoning_20260128_SOURCE.txt；原檔 raw/10009/ylc_115_zoning_20260128.pdf（ws.yunlin.gov.tw 有 Cloudflare，CLI 抓不到，由 Key 2026-11-26 手動存檔）

結論（data/c/10009/villages.json 392 鍵 vs zones.json 375 鍵，差 17）：
  寫入 5 里（縣內唯一村里名，只是官方表字形與圖資鍵不同；鍵名照抄圖資）：
    四湖鄉|[萡]子村、四湖鄉|[萡]東村 ← 原文「萡子村、萡東村」（建陽國小／飛沙國中）
    斗六市|崙峯里 ← 原文「崙峰里」（canon 折合 峯/峰）；斗六市|溝埧里 ← 原文「溝壩里」（埧為壩之異體；縣內無其他溝壩／溝埧）
    水林鄉|[欍]埔村 ← 原文「瓊埔村」（wild_regex 於水林鄉命中 [欍]埔／海埔／春埔，後二者已有獨立鍵；
                       門牌資料 beta/data/a/10009 此村 219 筆門牌皆標 [木|日]埔村、路名為「瓊埔路」）
  保持未列 12 里（縣內同名、原文只寫村里名未寫鄉鎮，不依學校所在地推定）：見 UNLISTED_VILLAGES
  另列出已在 zones 但國小鄰覆蓋為 0 的 14 里（同樣不臆補）：見 ZERO_E
可重跑：每次先刪除 PATCH 內的鍵再寫入，結果相同；registry 只改雲林縣那一筆，rebase 後重跑本腳本即可。
"""
import json, os, re, sys
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'tools'))
from addrnorm import canon, wild_regex  # noqa: E402

ZP = os.path.join(R, 'beta/data/c/10009/zones.json')
RP = os.path.join(R, 'beta/data/registry.json')
VP = os.path.join(R, 'data/c/10009/villages.json')
SP = os.path.join(R, 'data/c/10009/schools.json')
TODAY = '2026-11-26'
PAGE = 'https://huwei.yunlin.gov.tw/News_Content.aspx?n=20380&s=579611'
RAW = 'raw/10009/ylc_115_zoning_20260128_SOURCE.txt'
PDF = 'raw/10009/ylc_115_zoning_20260128.pdf'  # Key 2026-11-26 手動存檔，SHA-256 與 SOURCE.txt 紀錄相同

# 原文逐字（pdf.js 抽字，空白依原排版去除）
SRC = {
    'goba_e': '溝壩國小：崙峰里、溝壩里、三光里1至5鄰、江厝里1至12鄰、古坑鄉田心村1至9鄰。',
    'ylin_j': '雲林國中：虎溪里、正心里、長平里、保庄里、久安里、龍潭里、江厝里、三光里、溝壩里、崙峰里、嘉東里、光興里、中和里、鎮西里、鎮南里、社口里、太平里、古坑鄉田心村1至9鄰。',
    'jy_e': '建陽國小：萡子村、萡東村。',
    'fs_j': '飛沙國中：飛東村、飛沙村、三姓村、崙北村、崙南村、萡子村、萡東村、林厝村、林東村、溪尾村4鄰、廣溝村。',
    'cx_e': '中興國小：瓊埔村、塭底村。',
    'ns_j': '蔦松藝術高中(國中部)：瓊埔村、塭底村、松中村、松西村、松北村、山腳村、蕃薯村。',
}
# (圖資鍵, 原文村里名, 鄉鎮, 國小[校碼], 國小原文, 國中[校碼], 國中原文)
PATCH = [
    ('四湖鄉|[萡]子村', '萡子村', '四湖鄉', ['094729e'], 'jy_e', ['094504j'], 'fs_j'),
    ('四湖鄉|[萡]東村', '萡東村', '四湖鄉', ['094729e'], 'jy_e', ['094504j'], 'fs_j'),
    ('斗六市|崙峯里', '崙峰里', '斗六市', ['094603e'], 'goba_e', ['094516j'], 'ylin_j'),
    ('斗六市|溝埧里', '溝壩里', '斗六市', ['094603e'], 'goba_e', ['094516j'], 'ylin_j'),
    ('水林鄉|[欍]埔村', '瓊埔村', '水林鄉', ['094751e'], 'cx_e', ['094326j'], 'ns_j'),
]
UNLISTED_VILLAGES = [  # 官方表未明示鄉鎮之同名村里 → 不寫，前端顯示「表列未涵蓋」
    '北港鎮|中和里', '北港鎮|公舘里', '北港鎮|大同里', '口湖鄉|崙東村', '古坑鄉|新庄村', '古坑鄉|湳仔村',
    '古坑鄉|麻園村', '四湖鄉|新庄村', '斗六市|中和里', '斗南鎮|大同里', '斗南鎮|東仁里', '虎尾鎮|東仁里',
]
ZERO_E = [  # 已在 zones（國中由「全鄉／全鎮」等明示鄉鎮之列得出），但國小鄰覆蓋為 0
    '古坑鄉|樟湖村', '西螺鎮|中和里', '西螺鎮|公舘里', '莿桐鄉|麻園村', '二崙鄉|湳仔村', '二崙鄉|復興村',
    '二崙鄉|崙東村', '麥寮鄉|瓦[磘]村', '麥寮鄉|新吉村', '元長鄉|新吉村', '褒忠鄉|龍岩村', '東勢鄉|復興村',
    '元長鄉|龍岩村', '元長鄉|瓦[磘]村',
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
S = {s['id'] for s in load(SP)} | {s['id'] for s in Z.get('extra_schools', [])}
NAMES = {}
for k in V: NAMES.setdefault(k.split('|')[1], []).append(k)

for key in [p[0] for p in PATCH]: Z['v'].pop(key, None)          # 可重跑
before = sorted(set(V) - set(Z['v']))
assert len(before) == 17, before

for key, orig, town, es, esrc, js, jsrc in PATCH:
    assert key in V, key                                               # 鍵名必須與圖資完全一致
    assert key.split('|')[0] == town
    assert all(s in S for s in es + js), (es, js)
    assert orig in SRC[esrc] and orig in SRC[jsrc], (orig, esrc, jsrc)  # 原文確有此村里名
    vname = key.split('|')[1]
    rx = wild_regex(vname)
    if rx:                                                             # 方括號鍵：同鄉鎮內只剩此鍵未對到
        hits = [k for k in V if k.startswith(town + '|') and rx.match(canon(k.split('|')[1]))]
        assert key in hits and rx.match(canon(orig)), (key, hits)
        assert all(k in Z['v'] for k in hits if k != key), hits
    elif canon(vname) != canon(orig):                                  # 異體字：僅 溝埧/溝壩
        assert (vname, orig) == ('溝埧里', '溝壩里'), (vname, orig)
    # 縣內唯一：圖資沒有其他同名（canon 後）村里，原文也沒有其他鄉鎮的同名村里
    same = [k for k in V if canon(k.split('|')[1]) in (canon(vname), canon(orig))]
    assert same == [key], same
    L = V[key]
    Z['v'][key] = {
        'e': [{'a': 1, 'b': L, 's': es, 't': [SRC[esrc]]}],
        'j': [{'a': 1, 'b': L, 's': js, 't': [SRC[jsrc]]}],
    }

# 逐里逐鄰涵蓋（全縣）
def gaps(key, lv):
    L = V[key]; c = set()
    for x in Z['v'].get(key, {}).get(lv, []):
        c |= set(range(x['a'], (L if x['b'] == 999 else min(x['b'], L)) + 1))
    return sorted(set(range(1, L + 1)) - c)
def fmt(ns):
    out = []
    for n in ns:
        if out and out[-1][1] == n - 1: out[-1][1] = n
        else: out.append([n, n])
    return '、'.join(str(a) if a == b else f'{a}-{b}' for a, b in out)

missing = sorted(set(V) - set(Z['v']))
assert missing == sorted(UNLISTED_VILLAGES), missing
assert set(Z['v']) <= set(V)
zero_e = sorted(k for k in Z['v'] if not Z['v'][k].get('e'))
zero_j = sorted(k for k in Z['v'] if not Z['v'][k].get('j'))
assert zero_e == sorted(ZERO_E) and zero_j == [], (zero_e, zero_j)
partial = []
for k in sorted(Z['v']):
    for lv in 'ej':
        g = gaps(k, lv)
        if g and len(g) < V[k]: partial.append(f"{k} {'國小' if lv == 'e' else '國中'} 第{fmt(g)}鄰")
for key, *_ in PATCH:
    assert not gaps(key, 'e') and not gaps(key, 'j'), key
for k in UNLISTED_VILLAGES:  # 這些名稱在原文確實沒有寫鄉鎮（只出現裸名）
    assert len(NAMES[k.split('|')[1]]) >= 2, k
print('寫入', [p[0] for p in PATCH])
print('官方未明示鄉鎮（未列）', missing)
print('國小鄰覆蓋為0', zero_e)
print('既有部分鄰缺口（本 PR 未動）', partial)

M = Z['meta']
for u in (PDF, RAW):
    if u not in M['source_files']: M['source_files'].append(u)
NOTE = ('2026-11-26 對照115學年度修正版學區劃分表（115.1.19）補入5個縣內唯一但字形與圖資不同的村里：'
        '四湖鄉[萡]子村／[萡]東村（原文萡子村／萡東村）、斗六市崙峯里（原文崙峰里）、斗六市溝埧里（原文溝壩里）、水林鄉[欍]埔村（原文瓊埔村）。')
NOTE2 = ('北港鎮中和里／公舘里／大同里、斗六市中和里、斗南鎮大同里／東仁里、虎尾鎮東仁里、口湖鄉崙東村、古坑鄉新庄村／湳仔村／麻園村、'
         '四湖鄉新庄村等12里，縣內有同名村里且原文只寫村里名未寫鄉鎮，未依學校所在地推定，維持「表列未涵蓋」；'
         '另古坑鄉樟湖村等14里國小未能確定（樟湖村國小表未列，其餘為同名未分鄉），國小顯示「表列未涵蓋」。')
M['notes'] = [n for n in M['notes'] if not n.startswith(('2026-11-26 對照115學年度修正版', '北港鎮中和里／公舘里'))] + [NOTE, NOTE2]
M['updated'] = TODAY
M['check'] = {
    'checked': TODAY, 'scope': '缺漏17里＋國小／國中鄰覆蓋為0之里（其他里未重跑）', 'source': [PAGE, PDF, RAW],
    'added_villages': [p[0] for p in PATCH],
    'unlisted_same_name_no_town': missing,
    'zero_elementary_coverage': zero_e,
    'pre_existing_partial_gaps_untouched': partial,
    'village_keys': f'zones.json {len(Z["v"])} 鍵 ⊆ data/c/10009/villages.json 有村名者 {len(V)} 鍵；差集 {len(missing)} 鍵皆為同名未分鄉',
}
dump(Z, ZP)

REG = load(RP)
r = next(x for x in REG['counties'] if x['code'] == '10009')
r['zoneVillages'] = sum(1 for k in V if k in Z['v'])
r['incomplete'] = []
r['updated'] = TODAY
r['source'] = ('Codex 整理＋2026-11-26 對照115學年度修正版學區劃分表（115.1.19）補5里：' + PAGE)
r['warning'] = ('北港鎮中和里／公舘里／大同里、斗六市中和里、斗南鎮大同里／東仁里、虎尾鎮東仁里、口湖鄉崙東村、古坑鄉新庄村／湳仔村／麻園村、四湖鄉新庄村，'
                '縣內有同名村里而115學年度學區表未寫鄉鎮，本站不推定（表列未涵蓋）；另西螺鎮中和里、二崙鄉崙東村、古坑鄉樟湖村等14里國小未能確定。請洽雲林縣政府教育處。')
dump(REG, RP)
print('ok', r['zoneVillages'], '/', r['villages'])
