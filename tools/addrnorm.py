"""Address normalization shared by tools/import_codex.py and mirrored 1:1 in beta/js/norm.js.
Keep both in sync; the doorplate keys in beta/data/a/ are built with this function."""
import re, unicodedata
CN = {'零':0,'〇':0,'一':1,'二':2,'兩':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
def cnum(s):
    if s.isdigit(): return int(s)
    if not re.search('[十百千]', s): return int(''.join(str(CN[c]) for c in s))
    n=t=0
    for c in s:
        if c in CN: t=CN[c]
        else: n+=(t or 1)*{'十':10,'百':100,'千':1000}[c]; t=0
    return n+t
def norm(s):
    s=unicodedata.normalize('NFKC', s or '')
    s=re.sub(r'(\d)\s+(?=\d)',r'\1,',s)   # '之3 5F' must not become '之35F'
    s=re.sub(r'\s+','',s).replace('台','臺')
    s=re.sub(r'[\-‐‑–—―−－~～]','之',s)
    s=re.sub(r'(\d+)[Ff](?![A-Za-z])',r'\1樓',s)
    s=re.sub(r'[零〇一二兩三四五六七八九十百千]+(?=[段巷弄衖號鄰樓之])',lambda m:str(cnum(m.group(0))),s)
    s=re.sub(r'號之(\d+)',r'之\1號',s)
    s=re.sub(r'第(\d+)鄰',r'\1鄰',s)
    return s
def door_key(rest):
    """rest = normalized address after county+district (+village/鄰). Returns key up to 號 or None."""
    i=rest.find('號')
    if i<0: return None
    k=rest[:i+1]
    if not re.search(r'\d+(之\d+)?(附\d+)?號$',k): return None
    return k
TAIL=re.compile(r'(\d+巷)?(\d+弄)?(\d+衖)?臨?\d+(之\d+)?(附\d+)?號$')
def road_of(key):
    return TAIL.sub('',key)
# rare-character / variant folding for 里/村 and school names (display keeps the official form)
VAR={'舘':'館','壳':'殼','磘':'窯','塩':'鹽','峯':'峰','双':'雙','脚':'腳','鷄':'雞','坑':'坑','崁':'崁','廍':'廍','塭':'塭','塍':'塍','嶺':'嶺','鄉':'鄉','着':'著','裡':'里','邨':'村','臺':'臺','台':'臺','灣':'灣','温':'溫','爲':'為','濓':'濂','褔':'福','嗂':'窯','巿':'市','综':'綜','𦰡':'那','焰':'燄','塭':'溫','舊':'舊','峯':'峰','羣':'群','啓':'啟','綫':'線','麪':'麵','闗':'關','祕':'秘','銹':'鏽','厦':'廈','响':'響','凉':'涼'}
def canon(name):
    s=unicodedata.normalize('NFKC',name or '')
    s=re.sub(r'\[([^\]|]*)\|[^\]]*\]',r'\1',s)   # [木|日] -> 木
    s=re.sub(r'[\[\]［］【】()（）]','',s)
    return ''.join(VAR.get(c,c) for c in s)

WILD=re.compile(r'\[[^\]]*\]|[?？■□○\ue000-\uf8ff]')
def wild_regex(name):
    """'瓦■里' / '石[石曹]里' / '上\ue397里' -> regex matching canon() of the real name, or None if no wildcard"""
    s=unicodedata.normalize('NFKC',name or '')
    if not WILD.search(s): return None
    parts=WILD.split(s)
    return re.compile('^'+'.'.join(re.escape(canon(x)) for x in parts)+'$')
