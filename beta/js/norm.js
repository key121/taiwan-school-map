/* 地址正規化：與 tools/addrnorm.py 逐條對應（門牌索引的 key 由 Python 版產生，兩邊必須一致）。 */
(function(g){
const CN={'零':0,'〇':0,'一':1,'二':2,'兩':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9};
function cnum(s){
  if(/^\d+$/.test(s))return parseInt(s,10);
  if(!/[十百千]/.test(s))return parseInt([...s].map(c=>CN[c]).join(''),10);
  let n=0,t=0;for(const c of s){if(c in CN)t=CN[c];else{n+=(t||1)*({'十':10,'百':100,'千':1000}[c]);t=0;}}return n+t;
}
function norm(s){
  s=(s||'').normalize('NFKC');
  s=s.replace(/(\d)\s+(?=\d)/g,'$1,');   // '之3 5F' must not become '之35F'
  s=s.replace(/\s+/g,'').replace(/台/g,'臺');
  s=s.replace(/[\-‐‑–—―−－~～]/g,'之');
  s=s.replace(/(\d+)[Ff](?![A-Za-z])/g,'$1樓');
  s=s.replace(/[零〇一二兩三四五六七八九十百千]+(?=[段巷弄衖號鄰樓之])/g,m=>String(cnum(m)));
  s=s.replace(/號之(\d+)/g,'之$1號');
  s=s.replace(/第(\d+)鄰/g,'$1鄰');
  return s;
}
function doorKey(rest){
  const i=rest.indexOf('號');if(i<0)return null;
  const k=rest.slice(0,i+1);
  return /\d+(之\d+)?(附\d+)?號$/.test(k)?k:null;
}
const TAIL=/(\d+巷)?(\d+弄)?(\d+衖)?臨?\d+(之\d+)?(附\d+)?號$/;
function roadOf(key){return key.replace(TAIL,'');}
function rhash(road,nb){let h=0;for(const ch of road)h+=ch.codePointAt(0);return h%nb;}
const VAR={'舘':'館','壳':'殼','磘':'窯','塩':'鹽','峯':'峰','双':'雙','脚':'腳','鷄':'雞','着':'著','裡':'里','邨':'村','台':'臺','温':'溫','爲':'為','濓':'濂','褔':'福','嗂':'窯','巿':'市','综':'綜','𦰡':'那','焰':'燄','塭':'溫','羣':'群','啓':'啟','綫':'線','麪':'麵','闗':'關','祕':'秘','銹':'鏽','厦':'廈','响':'響','凉':'涼'};
function canon(name){
  let s=(name||'').normalize('NFKC');
  s=s.replace(/\[([^\]|]*)\|[^\]]*\]/g,'$1').replace(/[\[\]［］【】()（）]/g,'');
  return [...s].map(c=>VAR[c]||c).join('');
}
g.AddrNorm={norm,doorKey,roadOf,rhash,canon,cnum};
})(typeof window!=='undefined'?window:globalThis);
if(typeof module!=='undefined')module.exports=globalThis.AddrNorm;
