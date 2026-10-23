/* 全臺國中小學區地圖 — app.js（無建置步驟、無金鑰；各縣市資料按需載入） */
(function(){
'use strict';
const $=s=>document.querySelector(s);
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const LVN={e:'國小',j:'國中'};
const PAL=['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b','#e377c2','#17becf','#bcbd22','#3f51b5','#009688','#f44336','#795548','#607d8b','#ff9800','#4caf50','#673ab7','#00bcd4','#cddc39','#e91e63'];
let REG=[], REGBY={}, CTY=null, map, ctyLayer, villLayer, schLayer, pinLayer;
let cur=null;            // {code, reg, vill:FC, schools:[], zones|null, cross|null, byKey, sBy}
let lv='e', svgDefs=null, patterns={}, selSchool=null, lastR=null;
const cache={};
const fj=u=>fetch(u).then(r=>{if(!r.ok)throw new Error(u+' '+r.status);return r.json();});
function toast(t){const e=$('#toast');e.textContent=t;e.classList.add('on');clearTimeout(e._t);e._t=setTimeout(()=>e.classList.remove('on'),2400);}
function hav(lat1,lon1,lat2,lon2){const R=6371000,t=Math.PI/180,x=(lon2-lon1)*t*Math.cos((lat1+lat2)/2*t),y=(lat2-lat1)*t;return Math.sqrt(x*x+y*y)*R;}
function fmtD(m){return m<1000?Math.round(m/10)*10+' 公尺':(m/1000).toFixed(1)+' 公里';}
function linTxt(a,b,L){if(a===1&&(b>=999||(L&&b>=L)))return '全里';if(b>=999)return '第'+a+'鄰起至末鄰';return a===b?'第'+a+'鄰':'第'+a+'-'+b+'鄰';}
function hashStr(s){let h=0;for(const c of s)h=(h*31+c.charCodeAt(0))|0;return Math.abs(h);}
function normTxt(s){return String(s||'').trim().replace(/台/g,'臺').replace(/[０-９]/g,c=>String.fromCharCode(c.charCodeAt(0)-65248)).replace(/\s+/g,'');}

/* ---------- 幾何 ---------- */
function inRing(x,y,r){let ins=false;for(let i=0,j=r.length-1;i<r.length;j=i++){const xi=r[i][0],yi=r[i][1],xj=r[j][0],yj=r[j][1];if(((yi>y)!==(yj>y))&&(x<(xj-xi)*(y-yi)/(yj-yi)+xi))ins=!ins;}return ins;}
function inPoly(x,y,g){const P=g.type==='Polygon'?[g.coordinates]:g.coordinates;for(const p of P){if(inRing(x,y,p[0])){let hole=false;for(let k=1;k<p.length;k++)if(inRing(x,y,p[k]))hole=true;if(!hole)return true;}}return false;}
// 高雄市含東沙、南沙（太平島），縮放時只框本島範圍
const FITBOX={'64000':[120.17,22.47,121.05,23.47]};
function bboxOf(g){let a=[1e9,1e9,-1e9,-1e9];const P=g.type==='Polygon'?[g.coordinates]:g.coordinates;for(const p of P)for(const q of p[0]){if(q[0]<a[0])a[0]=q[0];if(q[1]<a[1])a[1]=q[1];if(q[0]>a[2])a[2]=q[0];if(q[1]>a[3])a[3]=q[1];}return a;}
function centroid(g){const b=bboxOf(g);return [(b[1]+b[3])/2,(b[0]+b[2])/2];}
function countyAt(lat,lon){for(const f of CTY.features){const b=f.properties.bbox;if(lon<b[0]-.01||lon>b[2]+.01||lat<b[1]-.01||lat>b[3]+.01)continue;if(inPoly(lon,lat,f.geometry))return f.properties.code;}
  // 外框為簡化版，近海岸點以最近縣市框判斷
  let best=null,bd=1e9;for(const f of CTY.features){const b=f.properties.bbox;if(lon>=b[0]&&lon<=b[2]&&lat>=b[1]&&lat<=b[3]){const d=Math.abs((b[0]+b[2])/2-lon)+Math.abs((b[1]+b[3])/2-lat);if(d<bd){bd=d;best=f.properties.code;}}}return best;}
function villageAt(lat,lon){for(const f of cur.vill.features){const p=f.properties;if(!p.v)continue;if(!p._b)p._b=bboxOf(f.geometry);const b=p._b;if(lon<b[0]||lon>b[2]||lat<b[1]||lat>b[3])continue;if(inPoly(lon,lat,f.geometry))return f;}return null;}

/* ---------- 學區規則 ---------- */
function rulesOf(key,l){return cur.zones&&cur.zones.v[key]?cur.zones.v[key][l]||[]:[];}
function villStatus(key,l){const r=rulesOf(key,l);if(!r.length)return 'none';const multi=r.some(x=>x.s.length>1);const diff=new Set(r.map(x=>x.s.join())).size>1;return diff?'split':(multi?'shared':'single');}
function schoolsInRules(r){const s=[];for(const x of r)for(const id of x.s)if(!s.includes(id))s.push(id);return s;}
function sName(id){const s=cur.sBy[id];return s?s.name.replace(/^(市立|縣立)/,''):id;}
function sColor(id){const s=cur.sBy[id];if(!s)return '#888';if(!s._c)s._c=PAL[hashStr(id)%PAL.length];return s._c;}
function patternFor(cols,shared){const id='p'+cols.join('').replace(/#/g,'')+(shared?'s':'');if(patterns[id])return id;const NS='http://www.w3.org/2000/svg',w=7*cols.length;const p=document.createElementNS(NS,'pattern');p.setAttribute('id',id);p.setAttribute('patternUnits','userSpaceOnUse');p.setAttribute('width',w);p.setAttribute('height',w);p.setAttribute('patternTransform','rotate(45)');cols.forEach((c,i)=>{const r=document.createElementNS(NS,'rect');r.setAttribute('x',i*7);r.setAttribute('y',0);r.setAttribute('width',shared?5:7);r.setAttribute('height',w);r.setAttribute('fill',c);p.appendChild(r);});svgDefs.appendChild(p);patterns[id]=1;return id;}
function villStyle(f){
  const p=f.properties; if(!p.v) return {color:'#999',weight:.5,fillOpacity:0};
  const key=p.t+'|'+p.v;
  if(!cur.zones) return {color:'#6b6b6b',weight:.8,opacity:.7,fillColor:'#bdbdbd',fillOpacity:.12};
  const r=rulesOf(key,lv), st=villStatus(key,lv);
  if(st==='none') return {color:'#b3261e',weight:1,fillColor:'#fff',fillOpacity:.1,dashArray:'2 3'};
  const ids=schoolsInRules(r);
  const dim=selSchool&&selSchool.lv===lv&&!ids.includes(selSchool.id);
  if(st==='single') return {color:'#fff',weight:1,opacity:.9,fillColor:sColor(ids[0]),fillOpacity:dim?.07:.45};
  const pid=patternFor(ids.slice(0,4).map(sColor),st==='shared');
  return {color:st==='shared'?'#b3261e':'#8a4b00',weight:1.5,dashArray:'4 3',opacity:.9,fillColor:'url(#'+pid+')',fillOpacity:dim?.15:.7};
}
function ML(){const m=cur.zones&&cur.zones.meta;return m&&m.multi_label||(m&&m.auto_parsed?'自由學區':'共同學區');}
function gName(x,id){if(x.f!=='g'||!x.g)return sName(id);const t=['男','女'].filter(k=>(x.g[k]||[]).includes(id));return sName(id)+(t.length===1?'（'+t[0]+'生）':'');}
function segBadge(x){let b='';if(x.f==='g')b+=' <span class="badge b-warn">依性別分校</span>';if(x.m&&x.m.length)return b+' <span class="badge b-bad">依門牌或條件分屬・請看原文</span>';if(x.f==='g'){const sh=['男','女'].some(k=>(x.g[k]||[]).length>1);return b+(sh?' <span class="badge b-warn">'+ML()+'・擇一</span>':'');}if(x.s.length>1)return x.f==='bm'?' <span class="badge b-bad">皆列基本學區・依備註分配</span>':' <span class="badge b-warn">'+ML()+'・擇一</span>';return '';}
function notesHtml(ids){const N=cur.zones&&cur.zones.school_notes;if(!N)return '';const h=ids.filter(id=>N[id]).map(id=>'<div class="o"><b>'+esc(sName(id))+' 備註</b>：'+esc(N[id])+'</div>').join('');return h;}
function rulesHtml(key,l,L,hiLin){
  const r=rulesOf(key,l); if(!r.length) return '<div class="o">表列未涵蓋此里，請洽教育局（處）。</div>';
  const st=villStatus(key,l);
  return r.map(x=>{const on=hiLin!=null&&hiLin>=x.a&&hiLin<=x.b;return '<div class="opt"'+(on?' style="background:#fff6d8"':'')+'>'+(st==='single'&&r.length===1?'':'<b>'+linTxt(x.a,x.b,L)+'</b>：')+x.s.map(id=>'<span class="sw" style="background:'+sColor(id)+'"></span>'+esc(gName(x,id))).join(' ／ ')+segBadge(x)+(cur.zones.meta.auto_parsed?'<div class="o">原文：'+x.t.map(esc).join('；')+'</div>':'')+'</div>';}).join('');
}

/* ---------- 地圖 ---------- */
function initMap(){
  map=L.map('map',{zoomControl:true,preferCanvas:false}).setView([23.7,120.95],7);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap 貢獻者'}).addTo(map);
  const svg=L.svg().addTo(map); svgDefs=document.createElementNS('http://www.w3.org/2000/svg','defs'); svg._container.insertBefore(svgDefs,svg._container.firstChild);
  ctyLayer=L.geoJSON(CTY,{renderer:svg,style:f=>{const r=REGBY[f.properties.code];return {color:'#10243D',weight:1,fillColor:r.status==='covered'?'#1b7f4b':'#9e9e9e',fillOpacity:r.status==='covered'?.28:.12};},
    onEachFeature:(f,l)=>{const r=REGBY[f.properties.code];l.bindTooltip(r.name+'：'+(r.status==='covered'?'已收錄 '+r.years+'學年度':'尚未收錄'),{sticky:true});l.on('click',()=>selectCounty(f.properties.code,true));}}).addTo(map);
  pinLayer=L.layerGroup().addTo(map);
}
function legend(){
  const el=$('#legend'); if(!cur){el.innerHTML='<b>收錄狀態</b><br><span class="sw" style="background:#1b7f4b;opacity:.6"></span>已收錄官方學區<br><span class="sw" style="background:#9e9e9e;opacity:.5"></span>尚未收錄（僅附近學校）';return;}
  if(!cur.zones){el.innerHTML='<b>'+esc(cur.reg.name)+'：尚未收錄官方學區</b><br>灰色＝村里界（內政部）<br><span class="sw" style="background:#1f5fbf;border-radius:50%"></span>國小　<span class="sw" style="background:#c0392b;border-radius:50%"></span>國中<br><span class="small">學校點位不代表學區範圍。</span>';return;}
  let n={single:0,split:0,shared:0,none:0};for(const k in cur.zones.v)n[villStatus(k,lv)]++;
  el.innerHTML='<b>'+esc(cur.reg.name)+' '+LVN[lv]+'學區</b><br><span class="sw" style="background:#4c8fd6"></span>全里同一學區（'+n.single+'）<br><span class="sw" style="background:repeating-linear-gradient(45deg,#d68a00 0 4px,#4c8fd6 4px 8px)"></span>依鄰分屬（'+n.split+'）<br><span class="sw" style="background:repeating-linear-gradient(45deg,#d62728 0 3px,#fff 3px 5px,#2ca02c 5px 8px)"></span>'+ML()+(Object.values(cur.zones.v).some(v=>(v[lv]||[]).some(x=>x.f==='g'))?'／依性別分校':'')+'（'+n.shared+'）'+(n.none?'<br><span class="sw" style="border:1px dashed #b3261e"></span>表列未涵蓋（'+n.none+'）':'')+'<br><span class="small">斜線里請點選查看各鄰歸屬；顏色僅區分相鄰學區。</span>';
}
function drawCounty(fit){
  if(villLayer){map.removeLayer(villLayer);villLayer=null;} if(schLayer){map.removeLayer(schLayer);schLayer=null;}
  villLayer=L.geoJSON(cur.vill,{style:villStyle,onEachFeature:(f,l)=>{if(!f.properties.v)return;l.on('click',e=>{L.popup({maxWidth:310}).setLatLng(e.latlng).setContent(villPopup(f)).openOn(map);});}}).addTo(map);
  schLayer=L.layerGroup();
  for(const s of cur.schools){ if(s.lat==null) continue; if(s.lv!==lv&&cur.zones) continue;
    const m=L.circleMarker([s.lat,s.lon],{radius:s.lv==='e'?5:6,color:'#fff',weight:1.5,fillColor:s.lv==='e'?'#1f5fbf':'#c0392b',fillOpacity:.95});
    m.bindTooltip(s.name.replace(/^(市立|縣立)/,''),{direction:'top'}); m.on('click',()=>{m.bindPopup(schoolPopup(s),{maxWidth:310}).openPopup();}); schLayer.addLayer(m);}
  schLayer.addTo(map);
  ctyLayer.setStyle(f=>{const r=REGBY[f.properties.code];const me=f.properties.code===cur.code;return {color:'#10243D',weight:me?2.5:1,fillColor:r.status==='covered'?'#1b7f4b':'#9e9e9e',fillOpacity:me?0:(r.status==='covered'?.2:.08)};});
  if(fit){const b=FITBOX[cur.code]||CTY.features.find(f=>f.properties.code===cur.code).properties.bbox;map.fitBounds([[b[1],b[0]],[b[3],b[2]]],{padding:[10,10],animate:false});}
  legend();
}
function villPopup(f){
  const p=f.properties,key=p.t+'|'+p.v;
  let h='<div class="pp"><h3>'+esc(cur.reg.name+p.t+' '+p.v)+'</h3><div class="o">共 '+(p.L||'?')+' 鄰（戶政司115年7月）</div>';
  if(cur.zones){for(const l of [lv,lv==='e'?'j':'e'])h+='<div style="margin-top:6px"><b>'+LVN[l]+'學區</b>'+rulesHtml(key,l,p.L)+'</div>';}
  else h+='<div class="warn">本縣市尚未收錄官方學區資料。<br><a href="'+esc(cur.reg.official)+'" target="_blank" rel="noopener">查看官方學區公告</a></div>'+crossHtml(key);
  h+='<div style="margin-top:6px"><button class="btn sm" onclick="TSM.pick(\''+esc(p.t)+'\',\''+esc(p.v)+'\')">選此'+(p.v.endsWith('村')?'村':'里')+'並指定鄰</button></div></div>';return h;
}
function crossHtml(key){
  if(!cur.cross||!cur.cross.v[key])return '';const c=cur.cross.v[key];let h='<div class="opt"><b>跨縣市資訊</b>：'+esc(cur.cross.meta.title)+'<br>';
  for(const l in c)for(const x of c[l])h+=linTxt(x.a,x.b)+'：'+x.s.map(id=>esc((cur.crossS[id]||{}).name||id)).join(' ／ ')+'（'+LVN[l]+'）<br>';
  return h+'<span class="o">僅臺北市學校之表列；新北市本身學區尚未收錄。</span></div>';
}
function schoolPopup(s){
  let h='<div class="pp"><h3>'+esc(s.name)+'</h3><div class="o">'+esc(s.addr)+(s.tel?'<br>電話 '+esc(s.tel):'')+(s.url?'<br><a href="'+esc(s.url)+'" target="_blank" rel="noopener">學校網站</a>':'')+'<br>座標來源：'+esc(s.src||'')+'</div>';
  if(cur.zones){const vs=coverageOf(s.id);h+='<div style="margin-top:6px"><b>學區涵蓋 '+vs.length+' 個里</b><div class="o">'+vs.slice(0,40).map(x=>esc(x.t+x.v)+(x.part?'('+x.part+')':'')).join('、')+(vs.length>40?'…':'')+'</div><button class="btn sm" onclick="TSM.selSchool(\''+s.id+'\')">標示學區範圍</button></div>';}
  else h+='<div class="warn">本縣市尚未收錄官方學區，學校位置不代表學區範圍。</div>';
  return h+'</div>';
}
function coverageOf(id){const out=[];for(const key in cur.zones.v){const r=rulesOf(key,id.slice(-1));const hit=r.filter(x=>x.s.includes(id));if(!hit.length)continue;const [t,v]=key.split('|');const Lc=(cur.villBy[key]||{}).L;const whole=hit.length===r.length;out.push({t,v,part:whole&&hit.every(x=>x.s.length===1)?'':hit.map(x=>linTxt(x.a,x.b,Lc)+(x.s.length>1?'共同':'')).join('、')});}return out;}

/* ---------- 縣市載入 ---------- */
async function loadCounty(code){
  if(cache[code]) return cache[code];
  const reg=REGBY[code]; $('#loading').classList.remove('hidden');
  try{
    const base='data/c/'+code+'/';
    const [vill,schools,zones]=await Promise.all([fj(base+'villages.json'),fj(base+'schools.json'),reg.status==='covered'?fj(base+'zones.json'):Promise.resolve(null)]);
    let cross=null,crossS={};
    if(reg.cross){try{cross=await fj(base+reg.cross.file);const cs=await fj('data/c/'+reg.cross.from+'/schools.json');for(const s of cs)crossS[s.id]=s;}catch(e){}}
    const sBy={};for(const s of schools)sBy[s.id]=s;
    const villBy={};for(const f of vill.features)if(f.properties.v)villBy[f.properties.t+'|'+f.properties.v]=f.properties;
    return cache[code]={code,reg,vill,schools,zones,cross,crossS,sBy,villBy};
  } finally { $('#loading').classList.add('hidden'); }
}
async function selectCounty(code,fit){
  if(cur&&cur.code===code){ if(fit)drawCounty(true); return cur; }
  cur=await loadCounty(code); selSchool=null; patterns={}; while(svgDefs.firstChild)svgDefs.removeChild(svgDefs.firstChild);
  $('#county').value=code; covBadge(); fillTowns(); fillSchools(); drawCounty(fit); return cur;
}
function covBadge(){
  const r=cur.reg;
  $('#covBadge').innerHTML=r.status==='covered'
   ? '<span class="badge b-ok">已收錄</span> <b>'+esc(r.years)+'學年度</b><br><span class="small">資料來源：'+esc(r.source)+'　<a href="'+esc(r.official)+'" target="_blank" rel="noopener">官方連結</a></span>'+(r.special?'<br><a class="small" href="'+esc(r.special)+'">→ 基隆專版：門牌號碼精確比對里鄰</a>':'')
   : '<span class="badge b-none">尚未收錄</span> 本站尚未收錄此縣市官方學區資料，查詢時僅列<b>附近學校，非官方學區</b>。<br><span class="small">官方來源：'+esc(r.source)+'　<a href="'+esc(r.official)+'" target="_blank" rel="noopener">開啟官方學區公告</a></span>';
}
function fillTowns(){
  const ts=[...new Set(cur.vill.features.filter(f=>f.properties.v).map(f=>f.properties.t))].sort((a,b)=>a.localeCompare(b,'zh-Hant'));
  $('#selT').innerHTML='<option value="">鄉鎮市區</option>'+ts.map(t=>'<option>'+esc(t)+'</option>').join('');
  $('#selV').innerHTML='<option value="">村里</option>';$('#selL').innerHTML='<option value="">鄰</option>';
}
function fillVills(t){const vs=cur.vill.features.filter(f=>f.properties.t===t&&f.properties.v).map(f=>f.properties.v).sort((a,b)=>a.localeCompare(b,'zh-Hant'));$('#selV').innerHTML='<option value="">村里</option>'+vs.map(v=>'<option>'+esc(v)+'</option>').join('');$('#selL').innerHTML='<option value="">鄰</option>';}
function fillLins(t,v){const p=cur.villBy[t+'|'+v];const n=p&&p.L||0;let h='<option value="">鄰（不確定可不選）</option>';for(let i=1;i<=n;i++)h+='<option value="'+i+'">第'+i+'鄰</option>';$('#selL').innerHTML=h;}
function fillSchools(){
  const list=cur.schools.filter(s=>s.lv==='e').concat(cur.schools.filter(s=>s.lv==='j'));
  $('#selS').innerHTML='<option value="">選擇學校（'+list.length+'所）</option>'+['e','j'].map(l=>'<optgroup label="'+LVN[l]+'">'+cur.schools.filter(s=>s.lv===l).map(s=>'<option value="'+s.id+'">'+esc(s.town+' '+s.name.replace(/^(市立|縣立)/,''))+'</option>').join('')+'</optgroup>').join('');
  $('#schoolNote').textContent=cur.zones?'選擇學校可在地圖上標示其學區涵蓋之里鄰。':'本縣市尚未收錄官方學區，僅能顯示學校位置與資訊。';
}

/* ---------- 查詢 ---------- */
function parseText(q){
  q=normTxt(q).replace(/^(中華民國|臺灣省|臺灣)/,'').replace(/^\d{3,6}/,'');
  const c=REG.find(r=>q.startsWith(r.name)); const rest=c?q.slice(c.name.length):q;
  const m=rest.match(/^(.{1,4}?[區鄉鎮市])?(.{1,5}?[里村])?(?:第?(\d{1,3})鄰)?(.*)$/);
  return {code:c?c.code:null,raw:q,rest,town:m&&m[1]||null,vill:m&&m[2]||null,lin:m&&m[3]?+m[3]:null,tail:m?m[4]:rest};
}
async function geocode(q){
  const u='https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?f=json&countryCode=TWN&maxLocations=1&outFields=Score,Addr_type,Match_addr&SingleLine='+encodeURIComponent(q);
  const ctl=new AbortController();const t=setTimeout(()=>ctl.abort(),8000);
  try{const j=await fetch(u,{signal:ctl.signal}).then(r=>r.json());const c=(j.candidates||[])[0];if(!c||c.score<85)return null;return {lat:c.location.y,lon:c.location.x,score:c.score,type:c.attributes.Addr_type,match:c.attributes.Match_addr||c.address};}
  catch(e){return null;} finally{clearTimeout(t);}
}
async function doSearch(q,fromHash){
  q=(q||'').trim(); if(!q) return;
  const P=parseText(q);
  let code=P.code||(cur&&cur.code);
  // 文字直接指定 區＋里（＋鄰）
  if(code){await selectCounty(code,false);
    let town=P.town, vill=P.vill;
    if(!town&&vill){const c=Object.keys(cur.villBy).filter(k=>k.split('|')[1]===vill);if(c.length===1)town=c[0].split('|')[0];}
    if(town&&vill&&cur.villBy[town+'|'+vill]&&!/\d+號/.test(P.tail)){return showResult({code,town,vill,lin:P.lin,method:'依'+(vill.endsWith('村')?'村':'里')+'、鄰查詢',q},fromHash);}
  }
  // 線上定位
  $('#loading').classList.remove('hidden'); const g=await geocode((P.code?'':((cur&&cur.reg.name)||''))+P.raw); $('#loading').classList.add('hidden');
  if(!g){ renderMsg('查無可靠定位結果','請確認地址是否完整（含縣市、區），或改用下方「鄉鎮市區 → 村里 → 鄰」選擇。'); return; }
  const c2=countyAt(g.lat,g.lon); if(!c2){renderMsg('定位結果不在臺灣村里界內','請改用下拉選單。');return;}
  await selectCounty(c2,false);
  const f=villageAt(g.lat,g.lon);
  if(!f){renderMsg('定位點未落在任何村里界內','可能位於海岸或界線附近，請改用下拉選單。');return;}
  return showResult({code:c2,town:f.properties.t,vill:f.properties.v,lin:P.lin,method:'線上定位（ArcGIS '+g.type+'，'+Math.round(g.score)+'分）＋村里界套疊',geo:g,q},fromHash);
}
function renderMsg(t,m){const e=$('#result');e.classList.remove('hidden');e.innerHTML='<div class="res"><h2>'+esc(t)+'</h2><div class="small">'+esc(m)+'</div></div>';}
function nearest(lat,lon,l,n){return cur.schools.filter(s=>s.lv===l&&s.lat!=null).map(s=>({s,d:hav(lat,lon,s.lat,s.lon)})).sort((a,b)=>a.d-b.d).slice(0,n);}
async function showResult(R,fromHash){
  lastR=R; const key=R.town+'|'+R.vill, vp=cur.villBy[key]; const Lc=vp&&vp.L;
  const f=cur.vill.features.find(x=>x.properties.t===R.town&&x.properties.v===R.vill);
  const pt=R.geo?[R.geo.lat,R.geo.lon]:centroid(f.geometry);
  if(R.lin!=null&&Lc&&(R.lin<1||R.lin>Lc)){renderMsg(R.town+R.vill+'查無第'+R.lin+'鄰','依戶政司資料，'+R.vill+'共 '+Lc+' 鄰（第1-'+Lc+'鄰）。請核對戶口名簿。');return;}
  $('#selT').value=R.town; fillVills(R.town); $('#selV').value=R.vill; fillLins(R.town,R.vill); if(R.lin)$('#selL').value=R.lin;
  let h='<div class="res"><h2>'+esc(R.q||'')+'</h2><div class="loc">'+esc(cur.reg.name+' '+R.town+' '+R.vill)+(R.lin?' 第'+R.lin+'鄰':'（未指定鄰）')+' · '+esc(R.method)+'</div>';
  if(R.geo){h+='<div class="warn">線上定位比對到「'+esc(R.geo.match)+'」。里別由定位點套疊村里界推得，靠近里界時可能有誤；<b>請以戶口名簿之里鄰為準</b>，必要時用下拉選單修正'+(cur.code==='10017'?'，或改用<a href="keelung/index.html#q='+encodeURIComponent(R.q)+'">基隆專版門牌精確比對</a>':'')+'。</div>';}
  const walkTargets=[];
  if(cur.zones){
    for(const l of ['e','j']){
      const r=rulesOf(key,l); h+='<div class="lvbox"><h3>'+LVN[l]+'學區</h3>';
      if(!r.length){h+='<div class="o">官方表列未涵蓋此里（可能為里鄰整編後新編之里），請洽教育局（處）。</div></div>';continue;}
      let hit=R.lin!=null?r.filter(x=>R.lin>=x.a&&R.lin<=x.b):r;
      const covAll=r.length&&r[0].a===1&&r.every((x,i)=>i===0||x.a===r[i-1].b+1)&&(r[r.length-1].b>=999||(Lc&&r[r.length-1].b>=Lc));
      if(R.lin==null&&!covAll){h+='<div class="o"><span class="badge b-bad">部分鄰表列未涵蓋</span> 請指定鄰別：</div>'+rulesHtml(key,l,Lc)+'</div>';continue;}
      const sets=new Set(hit.map(x=>x.s.join()));
      if(R.lin!=null&&!hit.length){h+='<div class="o"><span class="badge b-bad">表列未涵蓋</span> 官方表未列第'+R.lin+'鄰（可能為里鄰整編後新編之鄰），請洽教育局（處）。不推測。</div>'+rulesHtml(key,l,Lc)+'</div>';continue;}
      if(sets.size===1){const ids=hit[0].s;h+=ids.map(id=>{walkTargets.push(id);return '<div class="sch"><span class="sw" style="background:'+sColor(id)+'"></span>'+esc(gName(hit[0],id))+'</div><div class="walk" data-id="'+id+'"></div>';}).join('')+(ids.length>1||(hit[0].m&&hit[0].m.length)?'<div class="o">'+segBadge(hit[0])+' '+(hit[0].m&&hit[0].m.length?'原文另有鄰別以外的條件（如路段、門牌或分發順序），請核對下方原文。':hit[0].f==='bm'?'官方表兩校皆列為基本學區，實際分配依備註（如身分證字號尾數）辦理。':hit[0].f==='g'?'官方表依性別分列學區：男生、女生分別就讀上列標示之學校'+(['男','女'].some(k=>(hit[0].g[k]||[]).length>1)?'（同性別列兩校者可擇一）':'')+'。':'表列上述學校，可擇一就讀（仍依各校分發規定）。')+'</div>':'')+(R.lin==null&&r.length>1&&!(hit[0].m&&hit[0].m.length)?'<div class="o">此里各鄰皆同。</div>':'')+(cur.zones.meta.auto_parsed?'<div class="o">原文：'+[...new Set(hit.flatMap(x=>x.t))].map(esc).join('；')+'</div>':'')+notesHtml(ids);}
      else{h+='<div class="o"><span class="badge b-warn">依鄰分屬</span> 此里不同鄰分屬不同學區，請指定鄰別（不猜測）：</div>'+rulesHtml(key,l,Lc)+notesHtml(schoolsInRules(hit));}
      h+='</div>';
    }
    h+='<div class="o">依據：'+esc(cur.zones.meta.title)+'。'+(cur.zones.meta.notes||[]).slice(0,3).map(esc).join(' ')+'</div>';
  }else{
    h+='<div class="near"><h3>附近學校，非官方學區</h3><div class="o">本站尚未收錄'+esc(cur.reg.name)+'官方學區資料。以下僅為與'+(R.geo?'定位點':'該村里中心')+'直線距離最近之學校，<b>不代表學區</b>。</div>';
    for(const l of ['e','j']){h+='<div style="margin-top:6px"><b>'+LVN[l]+'</b></div>'+nearest(pt[0],pt[1],l,3).map(x=>'<div class="opt">'+esc(x.s.name)+' <span class="o">直線約'+fmtD(x.d)+'</span></div>').join('');}
    h+='<div style="margin-top:6px"><a class="btn sm" href="'+esc(cur.reg.official)+'" target="_blank" rel="noopener">查看官方學區公告</a></div><div class="o">'+esc(cur.reg.source)+'</div></div>'+crossHtml(key);
  }
  h+='<div class="acts"><button class="btn sm" id="shareBtn">複製分享連結</button><button class="btn sm ghost" onclick="window.print()">列印</button></div><div class="brand">中信房屋 冠軍商仲 劉展麟　LINE @key1</div></div>';
  const e=$('#result'); e.classList.remove('hidden'); e.innerHTML=h;
  $('#shareBtn').onclick=()=>{const u=location.href.split('#')[0]+'#'+shareHash(R);(navigator.clipboard?navigator.clipboard.writeText(u):Promise.reject()).then(()=>toast('已複製分享連結'),()=>prompt('複製此連結',u));};
  if(!fromHash) history.replaceState(null,'','#'+shareHash(R));
  pinLayer.clearLayers(); L.marker(pt,{icon:L.divIcon({className:'',html:'<div class="pinicon">📍</div>',iconSize:[30,30],iconAnchor:[15,28]}),zIndexOffset:2000}).addTo(pinLayer).bindTooltip(R.geo?'定位點':'村里中心（示意）');
  if(f){const gl=L.geoJSON(f,{style:{color:'#10243D',weight:3,fill:false}}).addTo(pinLayer);const doFit=()=>map.fitBounds(gl.getBounds(),{maxZoom:16,padding:[30,30],animate:!fromHash}); if(map._animatingZoom)map.once('zoomend',doFit); else doFit();}
  // 步行（只在有定位點時計算，避免以村里中心誤導）
  for(const id of walkTargets){const s=cur.sBy[id],el=document.querySelector('.walk[data-id="'+id+'"]');if(!el||!s)continue;
    if(s.lat==null){el.textContent='（此校無可靠座標）';continue;}
    if(!R.geo){el.textContent='學校地址：'+s.addr;continue;}
    const d=hav(pt[0],pt[1],s.lat,s.lon); el.textContent='直線約'+fmtD(d)+'・步行計算中…';
    walk(pt,[s.lat,s.lon]).then(w=>{el.innerHTML='🚶 步行約 <b>'+Math.max(1,Math.round(w.m/75))+'</b> 分鐘（'+fmtD(w.m)+'，'+w.src+'）・直線約'+fmtD(d);});}
}
const wcache={};
async function walk(a,b){const k=a.join()+';'+b.join();if(wcache[k])return wcache[k];
  const ctl=new AbortController();const t=setTimeout(()=>ctl.abort(),6000);
  try{const j=await fetch('https://routing.openstreetmap.de/routed-foot/route/v1/foot/'+a[1]+','+a[0]+';'+b[1]+','+b[0]+'?overview=false',{signal:ctl.signal}).then(r=>r.json());if(j.code==='Ok'&&j.routes[0])return wcache[k]={m:j.routes[0].distance,src:'OSM 步行路線'};}catch(e){}finally{clearTimeout(t);}
  return wcache[k]={m:hav(a[0],a[1],b[0],b[1])*1.35,src:'估算＝直線×1.35'};}
function shareHash(R){const p=new URLSearchParams();p.set('c',cur.code);p.set('l',lv);if(R.geo&&R.q)p.set('q',R.q);else{p.set('t',R.town);p.set('v',R.vill);if(R.lin)p.set('n',R.lin);}return p.toString();}
function selSchoolFn(id){
  const s=cur.sBy[id]; if(!s)return; if(s.lv!==lv){lv=s.lv;syncLv();}
  selSchool={id,lv:s.lv}; drawCounty(false); $('#selS').value=id;
  if(cur.zones){const vs=coverageOf(id);const e=$('#result');e.classList.remove('hidden');
    e.innerHTML='<div class="res"><h2>'+esc(s.name)+' → 學區範圍</h2><div class="loc">'+esc(s.addr)+'</div><div class="lvbox"><h3>涵蓋 '+vs.length+' 個村里</h3>'+vs.map(x=>'<div class="opt">'+esc(x.t+' '+x.v)+(x.part?' <span class="o">'+esc(x.part)+'</span>':' <span class="o">全里</span>')+'</div>').join('')+'</div><div class="o">依據：'+esc(cur.zones.meta.title)+'</div><div class="brand">中信房屋 冠軍商仲 劉展麟　LINE @key1</div></div>';
    const fs=cur.vill.features.filter(f=>f.properties.v&&vs.some(x=>x.t===f.properties.t&&x.v===f.properties.v)); if(fs.length)map.fitBounds(L.geoJSON({type:'FeatureCollection',features:fs}).getBounds(),{padding:[20,20]});}
  else if(s.lat!=null) map.setView([s.lat,s.lon],15);
  if(s.lat!=null){L.popup({maxWidth:310}).setLatLng([s.lat,s.lon]).setContent(schoolPopup(s)).openOn(map);}
}
function syncLv(){document.querySelectorAll('.lvtoggle button').forEach(b=>b.classList.toggle('on',b.dataset.lv===lv));}
async function fromHash(){
  const p=new URLSearchParams(location.hash.slice(1)); if(!p.get('c'))return false;
  if(p.get('l'))lv=p.get('l')==='j'?'j':'e'; syncLv();
  await selectCounty(p.get('c'),!(p.get('q')||(p.get('t')&&p.get('v'))));
  if(p.get('q')){$('#q').value=p.get('q');await doSearch(p.get('q'),true);}
  else if(p.get('t')&&p.get('v')){await showResult({code:cur.code,town:p.get('t'),vill:p.get('v'),lin:p.get('n')?+p.get('n'):null,method:'分享連結（區、里、鄰）',q:cur.reg.name+p.get('t')+p.get('v')+(p.get('n')?p.get('n')+'鄰':'')},true);}
  return true;
}

/* ---------- 啟動 ---------- */
async function main(){
  [REG,CTY]=await Promise.all([fj('data/registry.json'),fj('data/counties.geojson')]);
  for(const r of REG)REGBY[r.code]=r;
  $('#county').innerHTML='<option value="">選擇縣市</option>'+REG.map(r=>'<option value="'+r.code+'">'+esc(r.name)+(r.status==='covered'?'　✓ 已收錄 '+r.years:'　（尚未收錄）')+'</option>').join('');
  initMap(); legend();
  $('#county').onchange=e=>{if(e.target.value)selectCounty(e.target.value,true);};
  $('#qform').onsubmit=e=>{e.preventDefault();doSearch($('#q').value);};
  $('#selT').onchange=e=>fillVills(e.target.value);
  $('#selV').onchange=e=>{const t=$('#selT').value,v=e.target.value;fillLins(t,v);if(v)showResult({code:cur.code,town:t,vill:v,lin:null,method:'下拉選擇',q:cur.reg.name+t+v});};
  $('#selL').onchange=e=>{const t=$('#selT').value,v=$('#selV').value;if(v)showResult({code:cur.code,town:t,vill:v,lin:e.target.value?+e.target.value:null,method:'下拉選擇',q:cur.reg.name+t+v+(e.target.value?e.target.value+'鄰':'')});};
  $('#selS').onchange=e=>{if(e.target.value)selSchoolFn(e.target.value);};
  document.querySelectorAll('.lvtoggle button').forEach(b=>b.onclick=()=>{lv=b.dataset.lv;syncLv();if(cur)drawCounty(false);});
  if(!(await fromHash())){ await selectCounty('63000',true); }
  window.TSM._ready=true;
}
window.TSM={pick:(t,v)=>{map.closePopup();$('#selT').value=t;fillVills(t);$('#selV').value=v;fillLins(t,v);showResult({code:cur.code,town:t,vill:v,lin:null,method:'地圖點選',q:cur.reg.name+t+v});},selSchool:selSchoolFn,search:doSearch,selectCounty,get map(){return map;},get cur(){return cur;},get last(){return lastR;}};
main().catch(e=>{console.error(e);renderMsg('載入失敗',String(e));});
})();
