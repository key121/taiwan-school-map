"""澎湖縣 湖西／白沙／西嶼／望安／七美 五鄉＋馬公市桶盤里 學區補丁（Issue #1 P3-A）。

來源：澎湖縣政府教育處「澎湖縣各國中小學學區劃分表」（表頭日期 114年2月06日；本縣自114學年度起實施大學區制）
  raw/10016/phc_114up_zone_table_1140206_edu_sidebar_dl20261126.pdf
      ← 教育處網站側欄「澎湖縣國中小學各區之學區劃分表」（2026-11-26 仍為現行連結）
        https://www.penghu.gov.tw/websitedowndoc?file=edu/202506041056250.pdf&filedisplay=澎湖縣各國中小學區劃分表1140206.pdf
  raw/10016/phc_114up_zone_table_1140206_edu_notice_att1140603_dl20261126.pdf
      ← 公告頁（dataserno=202412170006）附件「1140603-附件-澎湖縣各國中小學區劃分表」（內容同上，僅字體粗細不同）
        https://www.penghu.gov.tw/uploaddowndoc?file=msg/202506030844010.pdf&flag=doc
學年度：表頭只寫 114年2月06日，未寫學年度；教育處 2026-04-17「115學年度國中小新生入學」公告引用「大學區制學區劃分表」，
  但教育處網站未另公告 115 學年度全縣版。故五鄉標「114學年度起（114.2.6 表）」，不寫成 115。
  馬公市原有資料（115學年度馬公市戶政表，114-12-23 府教國字第11409159932號）不覆蓋；本腳本只做比對、列出差異。
PDF 中文字型無 ToUnicode（pdftotext 抽不出中文），以 PyMuPDF 轉 150dpi 圖檔逐頁人工判讀，下方 ROWS 為原文逐字。

寫入規則：
  - 原學區國小／國中 → s；同鄉「共同自由學區」其他學校 → p（條件式），m 寫原文條件。
  - 原文只寫「自由學區」而未列學校者 → s 空、p 只列原文明確範圍的學校（無則空）、m 寫「待確認」，t 放原文。
  - 不從馬公市表外推，不用距離猜。
可重跑：五鄉及桶盤里整里覆寫；馬公市其他 32 里不動。
"""
import json, os
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE = '10016'
ZP = os.path.join(R, f'beta/data/c/{CODE}/zones.json')
RP = os.path.join(R, 'beta/data/registry.json')
VP = os.path.join(R, f'data/c/{CODE}/villages.json')
SP = os.path.join(R, f'data/c/{CODE}/schools.json')
TODAY = '2026-11-26'
TBL = '澎湖縣各國中小學學區劃分表（114年2月06日）'
EDU_PAGE = 'https://www.penghu.gov.tw/edu/home.jsp?act=view&dataserno=202412170006&id=93'
SRC_FILES = [
    'raw/10016/phc_114up_zone_table_1140206_edu_sidebar_dl20261126.pdf',
    'https://www.penghu.gov.tw/websitedowndoc?file=edu/202506041056250.pdf&filedisplay=%E6%BE%8E%E6%B9%96%E7%B8%A3%E5%90%84%E5%9C%8B%E4%B8%AD%E5%B0%8F%E5%AD%B8%E5%8D%80%E5%8A%83%E5%88%86%E8%A1%A81140206.pdf',
    'raw/10016/phc_114up_zone_table_1140206_edu_notice_att1140603_dl20261126.pdf',
    'https://www.penghu.gov.tw/uploaddowndoc?file=msg/202506030844010.pdf&filedisplay=1140603-%E9%99%84%E4%BB%B6-%E6%BE%8E%E6%B9%96%E7%B8%A3%E5%90%84%E5%9C%8B%E4%B8%AD%E5%B0%8F%E5%AD%B8%E5%8D%80%E5%8A%83%E5%88%86%E8%A1%A8.pdf&flag=doc',
]

CL = '以上各國中、國小為共同自由學區，以上各校以原學區之學生優先入學，在學校現有可容納的班級數量下，開放其他共同學區的學生就學。'
CLM = '共同自由學區：原學區學生優先入學；在學校現有可容納班級數量下，開放同鄉其他共同學區學生就學（另可能之學校依此條件）。'
FREE = '國中、國小自由學區：馬公市桶盤里；白沙鄉員貝村、大倉村；望安鄉東嶼坪、西嶼坪、東吉村。'
FREE_M = '待確認：官方表僅列為「國中、國小自由學區」，未列原學區或可就讀之學校，本站不指定；請洽澎湖縣政府教育處。'

# 學校代碼（data/c/10016/schools.json）
E = {'湖西': '164616e', '西溪': '164615e', '龍門': '164618e', '隘門': '164619e', '成功': '164614e', '沙港': '164620e',
     '中屯': '164621e', '講美': '164623e', '赤崁': '164625e', '後寮': '164629e', '鳥嶼': '164627e', '吉貝': '164628e',
     '合橫': '164630e', '大池': '164633e', '池東': '164634e', '內垵': '164636e', '外垵': '164637e',
     '望安': '164638e', '將軍': '164639e', '花嶼': '164641e', '七美': '164643e', '雙湖': '164644e'}
J = {'湖西國中': '164504j', '白沙國中': '164507j', '鳥嶼國中': '164514j', '吉貝國中': '164508j', '西嶼國中': '164509j',
     '望安國中': '164510j', '將澳國中': '164511j', '七美國中': '164512j'}
# 各鄉「以上各國中、國小」範圍（共同自由學區）
GRP = {
    '湖西鄉': (['湖西', '西溪', '龍門', '隘門', '成功', '沙港'], ['湖西國中']),
    '白沙鄉': (['中屯', '講美', '赤崁', '後寮', '鳥嶼', '吉貝'], ['白沙國中', '鳥嶼國中', '吉貝國中']),
    '西嶼鄉': (['合橫', '大池', '池東', '內垵', '外垵'], ['西嶼國中']),
    '望安鄉': (['望安', '將軍', '花嶼'], ['望安國中', '將澳國中']),
    '七美鄉': (['七美', '雙湖'], ['七美國中']),
}
# (鄉, 國中欄原文, 國小欄原文, 里鄰欄原文逐字, 村名清單)
ROWS = [
    ('湖西鄉', '湖西國中', '湖西', '湖西村、湖東村、南寮村、北寮村、青螺村、白坑村、菓葉村。', '湖西 湖東 南寮 北寮 青螺 白坑 菓葉'),
    ('湖西鄉', '湖西國中', '西溪', '西溪村、紅羅村。', '西溪 紅羅'),
    ('湖西鄉', '湖西國中', '龍門', '龍門村、尖山村。', '龍門 尖山'),
    ('湖西鄉', '湖西國中', '隘門', '隘門村、林投村、太武村。', '隘門 林投 太武'),
    ('湖西鄉', '湖西國中', '成功', '成功村、城北村。', '成功 城北'),
    ('湖西鄉', '湖西國中志清分班', '沙港', '沙港村、鼎灣村、潭邊村、中西村、許家村、東石村。', '沙港 鼎灣 潭邊 中西 許家 東石'),
    ('白沙鄉', '白沙國中', '中屯', '中屯村。', '中屯'),
    ('白沙鄉', '白沙國中', '講美', '講美村、城前村。', '講美 城前'),
    ('白沙鄉', '白沙國中', '赤崁', '赤崁村、小赤村、瓦硐村、港子村、岐頭村、鎮海村。', '赤崁 小赤 瓦硐 港子 岐頭 鎮海'),
    ('白沙鄉', '白沙國中', '後寮', '後寮村、通梁村。', '後寮 通梁'),
    ('白沙鄉', '鳥嶼國中', '鳥嶼', '鳥嶼村。', '鳥嶼'),
    ('白沙鄉', '吉貝國中', '吉貝', '吉貝村。', '吉貝'),
    ('西嶼鄉', '西嶼國中', '合橫', '112-115學年度辦理實驗教育期間，招收對象應為本縣之學生，得不受本縣學區限制，但應優先招生原學區(合界村、橫礁村)內學生。報名入學學生過多時，依該校學生入學辦法辦理。', '合界 橫礁'),
    ('西嶼鄉', '西嶼國中', '大池', '大池村。', '大池'),
    ('西嶼鄉', '西嶼國中', '池東', '池東村、池西村、二崁村、赤馬村。', '池東 池西 二崁 赤馬'),
    ('西嶼鄉', '西嶼國中', '內垵', '內垵村。', '內垵'),
    ('西嶼鄉', '西嶼國中', '外垵', '外垵村。', '外垵'),
    ('望安鄉', '望安國中', '望安', '東安村、西安村、中社村、水垵村。', '東安 西安 中社 水垵'),
    ('望安鄉', '將澳國中', '將軍', '將軍村。', '將軍'),
    ('望安鄉', '全縣國中自由學區', '花嶼', '花嶼村。', '花嶼'),
    ('七美鄉', '七美國中', '七美', '南港村、海豐村、中和村、平和村。', '南港 海豐 中和 平和'),
    ('七美鄉', '七美國中', '雙湖', '東湖村、西湖村。', '東湖 西湖'),
]
HUXI_FREE_J = '全縣國中自由學區：沙港村、鼎灣村、潭邊村、中西村、許家村、東石村'
XIYU_NOTE = '註：西嶼鄉合界村、橫礁村、竹灣村、小門村，國小為西嶼鄉自由學區。'
FREE_KEYS = {  # 自由學區（未列學校）：圖資鍵 → 額外註記
    '馬公市|桶盤里': None, '白沙鄉|員貝村': None, '白沙鄉|大倉村': None, '望安鄉|東吉村': None,
    '望安鄉|東坪村': '原文寫「東嶼坪」，對應圖資「望安鄉|東坪村」（東嶼坪嶼屬東坪村；名稱不同，請核對）。',
    '望安鄉|西坪村': '原文寫「西嶼坪」，對應圖資「望安鄉|西坪村」（西嶼坪嶼屬西坪村；名稱不同，請核對）。',
}
TARGET_TOWNS = ('湖西鄉', '白沙鄉', '西嶼鄉', '望安鄉', '七美鄉')


def load(p): return json.load(open(p, encoding='utf-8'))
def dump(o, p):
    with open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(json.dumps(o, ensure_ascii=False, separators=(',', ':')))
def seg(s, p, t, m=None):
    x = {'a': 1, 'b': 999, 's': s, 't': t}
    if m: x['m'] = m
    if p: x['p'] = p
    return x


V = {}
for f in load(VP)['features']:
    pr = f['properties']
    if pr.get('v'): V[pr['t'] + '|' + pr['v']] = pr['L']
SCH = {s['id']: s for s in load(SP)}
Z = load(ZP)
for t, (es, js) in GRP.items():  # 每鄉學校清單必須等於 schools.json 該鄉全部學校（確保 p 沒漏沒多）
    assert {E[x] for x in es} == {i for i, s in SCH.items() if s['town'] == t and i.endswith('e')}, t
    assert {J[x] for x in js} == {i for i, s in SCH.items() if s['town'] == t and i.endswith('j')}, t

new = {}
for town, jcol, ecol, txt, vills in ROWS:
    es, js = GRP[town]
    eid = E[ecol]
    for vn in vills.split():
        key = f'{town}|{vn}村'
        assert key in V, key
        te = [f'{ecol}國小：{txt}', CL]
        ep = [E[x] for x in es if E[x] != eid]
        em = [CLM]
        if ecol == '合橫':
            te = [f'合橫國小：{txt}', XIYU_NOTE, CL]
            em = ['合橫國小為實驗教育學校（112-115學年度），得不受學區限制，但優先招收原學區合界村、橫礁村學生；註明合界村、橫礁村國小為西嶼鄉自由學區。', CLM]
        if jcol == '全縣國中自由學區':
            ent_j = seg([], [], [f'全縣國中自由學區（國小：{ecol}）：{txt}', CL],
                        ['待確認：國中欄原文為「全縣國中自由學區」，未指定原學區國中，可選讀全縣國中（原文未逐校列出），請洽澎湖縣政府教育處。'])
        else:
            jid = J['湖西國中' if jcol == '湖西國中志清分班' else jcol]
            tj = [f'{jcol}（國小：{ecol}）：{txt}', CL]
            jm = [CLM] if len(js) > 1 else None
            jp = [J[x] for x in js if J[x] != jid]
            if jcol == '湖西國中志清分班':
                tj = [f'湖西國中志清分班（國小：沙港）：{txt}', HUXI_FREE_J, CL]
                jm = ['原文國中欄為「湖西國中志清分班」（屬湖西國中）；另列「全縣國中自由學區」，可選讀全縣國中（原文未逐校列出）。']
            ent_j = seg([jid], jp, tj, jm)
        new[key] = {'e': [seg([eid], ep, te, em)], 'j': [ent_j]}

# 西嶼鄉竹灣村、小門村：只出現在「註」列（位於西嶼國中合併儲存格內）
xi_es = [E[x] for x in GRP['西嶼鄉'][0]]
for vn in ('竹灣', '小門'):
    key = f'西嶼鄉|{vn}村'; assert key in V, key
    new[key] = {
        'e': [seg([], xi_es, [XIYU_NOTE, CL], ['待確認：原文僅寫「國小為西嶼鄉自由學區」，未指定原學區國小；另可能為西嶼鄉各國小，請洽澎湖縣政府教育處。'])],
        'j': [seg([J['西嶼國中']], [], [f'西嶼國中：{XIYU_NOTE}（此註列位於西嶼國中欄內；西嶼鄉僅西嶼國中一校）', CL])],
    }
for key, extra in FREE_KEYS.items():
    assert key in V, key
    m = [FREE_M] + ([extra] if extra else [])
    t = [FREE] + (['馬公市115學年度戶政表（114-12-23 府教國字第11409159932號）：國中、國小自由學區｜馬公市桶盤里。'] if key == '馬公市|桶盤里' else [])
    new[key] = {'e': [seg([], [], t, m)], 'j': [seg([], [], t, m)]}

# 斷言：五鄉全部村里都有、鍵 ⊆ 圖資、校碼 ⊆ schools.json
want = {k for k in V if k.split('|')[0] in TARGET_TOWNS} | {'馬公市|桶盤里'}
assert set(new) == want, (sorted(want - set(new)), sorted(set(new) - want))
for k, v in new.items():
    for lv in 'ej':
        for x in v[lv]:
            for i in x['s'] + x.get('p', []):
                assert i in SCH and i.endswith(lv), (k, i)
# 不覆蓋馬公市其他里
old_mk = {k: v for k, v in Z['v'].items() if k.startswith('馬公市|') and k != '馬公市|桶盤里'}
assert len(old_mk) == 32
for k in list(Z['v']):
    if k in new: del Z['v'][k]
Z['v'].update(new)
assert all(Z['v'][k] == v for k, v in old_mk.items())
assert set(Z['v']) == set(V), sorted(set(V) - set(Z['v']))

# 逐里逐鄰涵蓋（整里 a=1,b=999）；確定指派／僅條件
def cov(k, lv):
    L = V[k]; c = set()
    for x in Z['v'][k].get(lv, []): c |= set(range(x['a'], (L if x['b'] == 999 else x['b']) + 1))
    return sorted(set(range(1, L + 1)) - c)
gaps = [f'{k} {lv}' for k in V for lv in 'ej' if cov(k, lv)]
assert not gaps, gaps
nos = sorted(f"{k} {'國小' if lv == 'e' else '國中'}" for k in new for lv in 'ej' if not new[k][lv][0]['s'])
print('無確定學校（僅原文／條件）', len(nos), nos)

# 馬公市比對：114.2.6 全縣表 vs 既有（115 戶政表）— 原學區（s−p）
MK = {  # 原學區（114.2.6 表）；鄰段差異只比集合
    '陽明里': ({'164601e'}, {'164501j'}), '光復里': ({'164601e', '164602e'}, {'164501j'}), '朝陽里': ({'164603e'}, {'164501j'}),
    '西衛里': ({'164603e'}, {'164501j'}), '東文里': ({'164645e', '164605e', '164604e'}, {'164501j'}),
    '西文里': ({'164645e', '164603e', '164605e'}, {'164501j'}), '光明里': ({'164601e'}, {'164513j'}),
    '中興里': ({'164601e', '164602e'}, {'164513j'}), '啟明里': ({'164602e'}, {'164513j'}), '重慶里': ({'164602e'}, {'164513j'}),
    '復興里': ({'164602e'}, {'164513j'}), '中央里': ({'164602e'}, {'164513j'}), '長安里': ({'164602e'}, {'164513j'}),
    '光榮里': ({'164603e', '164646e'}, {'164513j'}), '重光里': ({'164646e'}, {'164513j'}),
    '石泉里': ({'164605e'}, {'164502j'}), '菜園里': ({'164605e'}, {'164502j'}), '光華里': ({'164605e'}, {'164502j'}),
    '案山里': ({'164604e', '164645e'}, {'164502j'}), '前寮里': ({'164605e', '164604e'}, {'164502j'}),
    '興仁里': ({'164607e'}, {'164502j'}), '烏崁里': ({'164607e'}, {'164502j'}), '東衛里': ({'164606e'}, {'164502j'}),
    '安宅里': ({'164606e'}, {'164502j'}), '虎井里': ({'164601e'}, {'164502j'}),
    '山水里': ({'164608e'}, {'164503j'}), '風櫃里': ({'164611e'}, {'164503j'}),
    '五德里': ({'164609e'}, {'164503j'}), '鎖港里': ({'164609e'}, {'164503j'}), '鐵線里': ({'164609e'}, {'164503j'}),
    '井垵里': ({'164609e', '164610e'}, {'164503j'}), '[嵵]裡里': ({'164610e'}, {'164503j'}),
}
assert set(f'馬公市|{k}' for k in MK) == set(old_mk)
diff = []
for vn, (we, wj) in MK.items():
    v = Z['v'][f'馬公市|{vn}']
    for lv, w in (('e', we), ('j', wj)):
        core = set()
        for x in v.get(lv, []): core |= {i for i in x['s'] if i not in (x.get('p') or [])}
        if core != w: diff.append(f"馬公市|{vn} {'國小' if lv == 'e' else '國中'}：既有原學區 {sorted(core)}；114.2.6 表 {sorted(w)}")
print('馬公市差異（不覆蓋）', diff)

M = Z['meta']
M['years'] = '114、115'
M['title'] = '澎湖縣國民中小學學區（馬公市：115學年度戶政表；五鄉與桶盤里：教育處114.2.6全縣學區劃分表）'
M['source_page'] = EDU_PAGE
M['publisher'] = '澎湖縣政府教育處'
for u in ['https://www.penghu.gov.tw/makun/home.jsp?id=142'] + SRC_FILES:
    if u not in M['source_files']: M['source_files'].append(u)
NOTE = ('2026-11-26 補湖西、白沙、西嶼、望安、七美五鄉與馬公市桶盤里：依教育處「' + TBL + '」（自114學年度起實施大學區制；'
        '教育處網站未另公告115學年度全縣版，2026-04-17 115學年度新生入學公告仍引用大學區制學區劃分表）。原學區學校列為確定，'
        '同鄉共同自由學區其他學校列為條件（另可能）。桶盤里、白沙鄉員貝村／大倉村、望安鄉東坪村（原文東嶼坪）／西坪村（原文西嶼坪）／東吉村'
        '原文僅稱「國中、國小自由學區」未列學校；西嶼鄉竹灣村、小門村國小、望安鄉花嶼村國中亦未指定原學區學校，均不產生確定指派。')
M['notes'] = [n for n in M['notes'] if not n.startswith('2026-11-26 補湖西')] + [NOTE]
M['notes'] = [n.replace('本檔只覆蓋馬公市，其他5鄉不推定。', '本段只指馬公市。').replace('桶盤里僅稱國中小自由學區未完整列學校，故不產生確定指派。', '') for n in M['notes']]
M['incomplete'] = []
M['updated'] = TODAY
M['check'] = {'checked': TODAY, 'scope': '五鄉63村＋馬公市桶盤里（馬公市其他32里未改，只比對）',
              'source': SRC_FILES[0::2],
              'village_keys': f'zones.json {len(Z["v"])} 鍵 = data/c/10016/villages.json 有村名者 {len(V)} 鍵（差集 0）',
              'neighbour_gaps': gaps, 'no_definite_school': nos, 'makung_diff_vs_1140206': diff}
dump(Z, ZP)

REG = load(RP)
r = next(x for x in REG['counties'] if x['code'] == CODE)
r['incomplete'] = []
r['years'] = '114、115'
r['source'] = ('澎湖縣政府教育處「' + TBL + '」（五鄉、桶盤里）：' + SRC_FILES[1] +
               '；馬公市115學年度戶政表（Codex 整理）：https://www.penghu.gov.tw/makun/home.jsp?id=142')
r['updated'] = TODAY
r['zoneVillages'] = sum(1 for k in V if k in Z['v'])
r['warning'] = ('湖西、白沙、西嶼、望安、七美五鄉依教育處114年2月6日全縣學區劃分表（自114學年度起大學區制；未見115學年度全縣版），'
                '馬公市依115學年度表。桶盤里、員貝村、大倉村、東坪村、西坪村、東吉村原文僅稱國中小自由學區、未列學校，'
                '竹灣村、小門村國小與花嶼村國中亦未指定學校，請洽澎湖縣政府教育處。')
dump(REG, RP)
print('ok', r['zoneVillages'], '/', r['villages'])
