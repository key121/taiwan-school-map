/* 基隆市學區地圖 — app.js (no build step, no external keys) */
(function(){
'use strict';
const $=s=>document.querySelector(s);
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const LV={elem:'國小',junior:'國中'};
const DISTS=['仁愛區','信義區','中正區','中山區','安樂區','暖暖區','七堵區'];
let D,VG,DG,AI;               // schooldata, villages geojson, districts geojson, address index
let level='elem', map, villLayer, unionLayer, markerLayer, dotLayer, labelLayer, pinLayer, hiLayer;
let schoolBy={elem:{},junior:{}}, selSchool=null, patterns={}, svgDefs=null, flatPts=null;

async function loadData(){
  if(window.__KSM_DATA__){const x=window.__KSM_DATA__;return [x.schooldata,x.villages,x.districts,x.address];}
  const f=u=>fetch(u).then(r=>{if(!r.ok)throw new Error(u+' '+r.status);return r.json();});
  return Promise.all([f('data/schooldata.json'),f('data/villages.geojson'),f('data/districts.geojson'),f('data/address_index.json')]);
}

/* ---------- helpers ---------- */
function ranges(a){ // [1,2,3,5] -> 1-3、5
  a=[...a].sort((x,y)=>x-y); const o=[]; let s=null,p=null;
  for(const v of a){ if(s===null){s=p=v;continue;} if(v===p+1){p=v;continue;} o.push(s===p?s:s+'-'+p); s=p=v; }
  if(s!==null) o.push(s===p?s:s+'-'+p); return o.join('、');
}
function schoolLabel(n){return /高中$/.test(n)? n+'<span class="small">（國中部）</span>':n;}
function plain(n){return /高中$/.test(n)? n+'（國中部）':n;}
function hav(a,b,c,d){const R=6371000,t=Math.PI/180,x=(c-a)*t*Math.cos((b+d)/2*t),y=(d-b)*t;return Math.sqrt(x*x+y*y)*R;}
function fmtDist(m){return m<1000? Math.round(m/10)*10+' 公尺':(m/1000).toFixed(1)+' 公里';}
function toast(t){const e=$('#toast');e.textContent=t;e.classList.add('on');clearTimeout(e._t);e._t=setTimeout(()=>e.classList.remove('on'),2200);}
function statusBadge(st){return st==='single'?'<span class="badge single">全里同一學區</span>':st==='split'?'<span class="badge split">依鄰分屬</span>':'<span class="badge shared">表列多校（共同學區）</span>';}
function flagBadge(s){if(!s||!s.flag)return '';return s.flag==='總量管制學校'?'<span class="badge flag">總量管制</span>':'<span class="badge flag">實驗教育・全市開放學區</span>';}
function colorOf(lvl,n){return (schoolBy[lvl][n]||{}).color||'#888';}
function villColors(v,lvl){const s=[];for(const g of v[lvl].groups)for(const n of g.schools)if(!s.includes(n))s.push(n);return s.map(n=>colorOf(lvl,n));}

/* ---------- SVG stripe patterns for split / shared 里 ---------- */
function patternFor(cols,shared){
  const id='p'+cols.join('').replace(/#/g,'')+(shared?'s':'');
  if(patterns[id]) return id;
  const NS='http://www.w3.org/2000/svg', w=7*cols.length;
  const p=document.createElementNS(NS,'pattern');
  p.setAttribute('id',id);p.setAttribute('patternUnits','userSpaceOnUse');p.setAttribute('width',w);p.setAttribute('height',w);p.setAttribute('patternTransform','rotate(45)');
  cols.forEach((c,i)=>{const r=document.createElementNS(NS,'rect');r.setAttribute('x',i*7);r.setAttribute('y',0);r.setAttribute('width',shared?5:7);r.setAttribute('height',w);r.setAttribute('fill',c);p.appendChild(r);});
  svgDefs.appendChild(p); patterns[id]=1; return id;
}
function villStyle(f){
  const v=D.villages[f.properties.i], L=v[level];
  const dimmed = selSchool && selSchool.level===level && !L.schools.includes(selSchool.name);
  if(L.status==='single') return {color:'#ffffff',weight:1,opacity:.9,fillColor:colorOf(level,L.schools[0]),fillOpacity:dimmed?.08:.42};
  const id=patternFor(villColors(v,level),L.status==='shared');
  return {color:L.status==='shared'?'#b3261e':'#8a4b00',weight:1.6,dashArray:'4 3',opacity:.9,fillColor:'url(#'+id+')',fillOpacity:dimmed?.15:.7};
}

/* ---------- popups ---------- */
function groupsHtml(v,lvl,hiLin){
  const L=v[lvl]; let h='';
  for(const g of L.groups){
    const on = hiLin!=null && g.lins.includes(hiLin);
    const names=g.schools.map(n=>'<span class="sw" style="background:'+colorOf(lvl,n)+'"></span>'+schoolLabel(n)).join(' ／ ');
    h+='<div class="g"'+(on?' style="background:#fff6d8;border-radius:6px;padding:2px 4px"':'')+'><b>'+names+'</b>'+(g.schools.length>1?' <span class="badge shared">表列多校</span>':'')+
       (L.status==='single'?'':'<div class="o">第 '+ranges(g.lins)+' 鄰</div>')+'</div>';
  }
  return h;
}
function officialHtml(v,lvl){return v[lvl].official.map(o=>esc(o.school)+'「'+esc(v.vill)+(o.text==='全里'?'（全里）':'('+esc(o.text)+')')+'」').join('；');}
function villPopup(v){
  let h='<div class="pp"><h3>'+esc(v.dist)+' '+esc(v.vill)+'</h3><div class="o">共 '+v.lins.length+' 鄰（依門牌資料）</div>';
  for(const lvl of [level, level==='elem'?'junior':'elem']){
    h+='<div style="margin-top:8px"><b>'+LV[lvl]+'學區</b> '+statusBadge(v[lvl].status)+groupsHtml(v,lvl)+'<div class="o">表列原文：'+officialHtml(v,lvl)+'</div></div>';
  }
  h+='<div style="margin-top:8px"><button class="btn sm" onclick="KSM.pickVillage('+v.i+')">選此里並指定鄰</button></div></div>';
  return h;
}
function schoolPopup(s){
  const cov={}; for(const c of s.coverage){(cov[c.dist]=cov[c.dist]||[]).push(c.vill+(c.whole?'':'<span class="o">('+esc(c.rule)+')</span>'));}
  let h='<div class="pp"><h3>'+schoolLabel(esc(s.name))+' '+flagBadge(s)+'</h3><div class="o">'+esc(s.addr)+(s.tel?'<br>電話 '+esc(s.tel):'')+(s.url?'<br><a href="'+esc(s.url)+'" target="_blank" rel="noopener">學校網站</a>':'')+'</div>';
  h+='<table>'; for(const d in cov) h+='<tr><td style="white-space:nowrap"><b>'+esc(d)+'</b></td><td>'+cov[d].join('、')+'</td></tr>'; h+='</table>';
  h+='<div style="margin-top:6px"><button class="btn sm" onclick="KSM.selectSchool(\''+s.level+'\',\''+esc(s.name)+'\')">標示學區範圍</button></div></div>';
  return h;
}

/* ---------- map ---------- */
function initMap(){
  map=L.map('map',{zoomControl:true,preferCanvas:false}).setView([25.115,121.725],12);
  const emap=L.tileLayer('https://wmts.nlsc.gov.tw/wmts/EMAP/default/GoogleMapsCompatible/{z}/{y}/{x}',{maxZoom:19,maxNativeZoom:18,attribution:'底圖 &copy; <a href="https://maps.nlsc.gov.tw/" target="_blank">內政部國土測繪中心</a>'});
  const photo=L.tileLayer('https://wmts.nlsc.gov.tw/wmts/PHOTO2/default/GoogleMapsCompatible/{z}/{y}/{x}',{maxZoom:19,maxNativeZoom:19,attribution:'正射影像 &copy; 內政部國土測繪中心'});
  const osm=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>'});
  emap.addTo(map);
  const svg=L.svg({padding:.5}); map.addLayer(svg);
  svgDefs=document.createElementNS('http://www.w3.org/2000/svg','defs'); svg._container.insertBefore(svgDefs,svg._container.firstChild);
  villLayer=L.geoJSON(VG,{renderer:svg,style:villStyle,onEachFeature:(f,l)=>{l.on('click',e=>{L.popup({maxWidth:320}).setLatLng(e.latlng).setContent(villPopup(D.villages[f.properties.i])).openOn(map);});
     l.on('mouseover',()=>l.setStyle({weight:3}));l.on('mouseout',()=>villLayer.resetStyle(l));}}).addTo(map);
  villLayer.setStyle(villStyle);
  L.geoJSON(DG,{interactive:false,style:{color:'#10243D',weight:2.4,opacity:.75,fill:false}}).addTo(map);
  unionLayer=L.layerGroup().addTo(map); hiLayer=L.layerGroup().addTo(map);
  markerLayer=L.layerGroup().addTo(map); pinLayer=L.layerGroup().addTo(map);
  dotLayer=L.layerGroup(); labelLayer=L.layerGroup();
  for(const v of D.villages) if(v.lp) labelLayer.addLayer(L.tooltip({permanent:true,direction:'center',className:'vlabel',interactive:false}).setLatLng([v.lp[1],v.lp[0]]).setContent(v.vill));
  const overlays={'學校標記':markerLayer,'里名標註（放大後）':labelLayer,'分鄰里門牌點（放大至15級）':dotLayer};
  L.control.layers({'國土測繪電子地圖':emap,'正射影像':photo,'OpenStreetMap':osm},overlays,{collapsed:true,position:'topright'}).addTo(map);
  // level toggle control
  const Lc=L.Control.extend({options:{position:'topright'},onAdd:()=>{const d=L.DomUtil.create('div','lvlctl');d.innerHTML='<button data-l="elem" class="on">國小學區</button><button data-l="junior">國中學區</button>';L.DomEvent.disableClickPropagation(d);d.querySelectorAll('button').forEach(b=>b.onclick=()=>setLevel(b.dataset.l));return d;}});
  map.addControl(new Lc());
  const Lg=L.Control.extend({options:{position:'bottomright'},onAdd:()=>{const d=L.DomUtil.create('div','legend');d.id='legend';L.DomEvent.disableClickPropagation(d);return d;}});
  map.addControl(new Lg()); L.control.scale({imperial:false}).addTo(map);
  map.on('zoomend',zoomRules); zoomRules();
  map.on('overlayadd overlayremove',e=>{if(e.layer===dotLayer)dotLayer._user=e.type==='overlayadd'; if(e.layer===labelLayer)labelLayer._user=e.type==='overlayadd';});
  dotLayer._user=true; labelLayer._user=true;
}
function zoomRules(){
  const z=map.getZoom();
  const wantL=z>=15&&labelLayer._user!==false, wantD=z>=15&&dotLayer._user!==false;
  if(wantL&&!map.hasLayer(labelLayer))map.addLayer(labelLayer); if(!wantL&&map.hasLayer(labelLayer)){const u=labelLayer._user;map.removeLayer(labelLayer);labelLayer._user=u;}
  if(wantD&&!map.hasLayer(dotLayer))map.addLayer(dotLayer); if(!wantD&&map.hasLayer(dotLayer)){const u=dotLayer._user;map.removeLayer(dotLayer);dotLayer._user=u;}
}
function drawUnions(){
  unionLayer.clearLayers();
  for(const s of D.schools[level]) L.geoJSON(s.union,{interactive:false,style:{color:'#22313f',weight:1.4,opacity:.55,fill:false}}).addTo(unionLayer);
}
function drawMarkers(){
  markerLayer.clearLayers();
  for(const lvl of ['elem','junior']) for(const s of D.schools[lvl]){
    if(s.lat==null) continue;
    const cur=lvl===level, sz=cur?24:17;
    const ic=L.divIcon({className:'',html:'<div class="smk '+(lvl==='elem'?'e':'j')+(cur?'':' dim')+'" style="width:'+sz+'px;height:'+sz+'px;background:'+s.color+'">'+(lvl==='elem'?'小':'中')+'</div>',iconSize:[sz,sz],iconAnchor:[sz/2,sz/2]});
    L.marker([s.lat,s.lon],{icon:ic,title:plain(s.name),zIndexOffset:cur?1000:0,keyboard:false}).bindPopup(()=>schoolPopup(s),{maxWidth:320}).addTo(markerLayer);
  }
}
const dotRenderer=L.canvas({padding:.3});
function drawDots(){
  dotLayer.clearLayers();
  for(const vi in D.dots){
    const v=D.villages[vi]; if(v[level].status==='single') continue;
    const gl={}; v[level].groups.forEach(g=>g.lins.forEach(l=>gl[l]=g));
    for(const [x,y,lin] of D.dots[vi]){
      const g=gl[lin]; if(!g) continue;
      const c=g.schools.length===1?colorOf(level,g.schools[0]):'#444';
      L.circleMarker([y,x],{renderer:dotRenderer,radius:3.2,weight:1,color:'#fff',fillColor:c,fillOpacity:1}).bindTooltip(v.vill+' 第'+lin+'鄰 → '+g.schools.map(plain).join('／')).addTo(dotLayer);
    }
  }
}
function drawLegend(){
  const st={single:0,split:0,shared:0}; D.villages.forEach(v=>st[v[level].status]++);
  $('#legend').innerHTML='<b>'+LV[level]+'學區圖例</b>'+
   '<div class="row"><span class="sw" style="background:#31a354;opacity:.6"></span>全里同一學區（'+st.single+'里）</div>'+
   '<div class="row"><span class="sw hatch"></span>依鄰分屬（'+st.split+'里）</div>'+
   '<div class="row"><span class="sw hatch2" style="border:1px dashed #b3261e"></span>表列多校（'+st.shared+'里）</div>'+
   '<div class="row"><span class="dot"></span>門牌點：分鄰里的實際歸屬</div>'+
   '<div class="small">斜線里請點選或放大查看鄰別；顏色僅區分相鄰學區。</div>';
}
function setLevel(l){
  level=l; document.querySelectorAll('.lvlctl button').forEach(b=>b.classList.toggle('on',b.dataset.l===l));
  if(selSchool&&selSchool.level!==l) clearSchool(true);
  villLayer.setStyle(villStyle); drawUnions(); drawMarkers(); drawDots(); drawLegend(); renderSchoolList();
  if(lastResult) renderResult(lastResult,false);
  updateHash();
}
function clearSchool(silent){selSchool=null;hiLayer.clearLayers();if(!silent){villLayer.setStyle(villStyle);renderSchoolList();}}
function selectSchool(lvl,name,fly=true){
  if(lvl!==level){level=lvl;setLevel(lvl);}
  const s=schoolBy[lvl][name]; if(!s) return;
  selSchool=s; hiLayer.clearLayers();
  const g=L.geoJSON(s.union,{interactive:false,style:{color:'#B89964',weight:4,opacity:1,fill:false}}).addTo(hiLayer);
  villLayer.setStyle(villStyle); renderSchoolList();
  if(fly) map.fitBounds(g.getBounds(),{padding:[30,30],maxZoom:16});
  map.closePopup(); updateHash();
  const box=$('#result'); box.hidden=false; lastResult=null;
  box.innerHTML='<div class="meta">學校 → 學區範圍（'+LV[lvl]+'）</div>'+schoolPopup(s).replace(/<div style="margin-top:6px">.*?<\/div><\/div>$/,'</div>')+'<div class="small" style="margin-top:6px">地圖金色外框為本校學區；括號內為僅部分鄰屬本校。點選地圖上的里可查看該里完整規定。</div>';
  if(window.innerWidth<=820&&fly) box.scrollIntoView({behavior:'smooth',block:'start'});
}

/* ---------- address parsing & lookup ---------- */
const CN='〇一二三四五六七八九';
function cn2num(s){ // 一百二十三 / 二十 / 十五 → number (only simple forms)
  if(!/^[〇零一二三四五六七八九十百]+$/.test(s)) return null;
  if(!/[十百]/.test(s)) return +[...s].map(ch=>ch==='零'?0:CN.indexOf(ch)).join('');
  let n=0,cur=0; for(const ch of s){ if(ch==='百'){n+=(cur||1)*100;cur=0;} else if(ch==='十'){n+=(cur||1)*10;cur=0;} else cur=ch==='零'?0:CN.indexOf(ch); } return n+cur;
}
function normalize(s){
  s=String(s||'').replace(/[\uFF01-\uFF5E]/g,c=>String.fromCharCode(c.charCodeAt(0)-0xFEE0)).replace(/[\s\u3000,，]/g,'');
  s=s.replace(/褔/g,'福').replace(/台/g,'臺').replace(/○|◯|Ｏ/g,'〇').replace(/－|—|–|~/g,'-');
  s=s.replace(/^\d{3,6}/,'').replace(/^(中華民國)?(臺灣省|臺灣)?/,'').replace(/^\d{3,6}/,'').replace(/^(基隆市|基隆)/,'');
  s=s.replace(/(\d)段/g,(m,d)=>(CN[+d]||d)+'段');
  s=s.replace(/([〇零一二三四五六七八九十百]+)(巷|弄|號|鄰|之)/g,(m,a,b)=>{const n=cn2num(a);return n==null?m:n+b;});
  return s;
}
function parseAddr(raw){
  let s=normalize(raw), r={dist:null,vill:null,lin:null,street:null,lane:'',alley:'',num:null,sub:null,lin_given:null,rest:''};
  const dm=s.match(/^(仁愛|信義|中正|中山|安樂|暖暖|七堵)區/); if(dm){r.dist=dm[1]+'區';s=s.slice(dm[0].length);}
  // 里
  const vills=D.villages.filter(v=>!r.dist||v.dist===r.dist).map(v=>v.vill).sort((a,b)=>b.length-a.length);
  for(const vn of vills){ if(s.startsWith(vn)){ r.vill=vn; s=s.slice(vn.length); break; } }
  const lm=s.match(/^第?(\d+)鄰/); if(lm){r.lin_given=+lm[1]; s=s.slice(lm[0].length);}
  // street
  const cands=[]; for(const d of (r.dist?[r.dist]:DISTS)) for(const st in (AI[d]||{})) if(s.startsWith(st)) cands.push([d,st]);
  if(cands.length){ const mx=Math.max(...cands.map(c=>c[1].length)); r.cands=cands.filter(c=>c[1].length===mx); r.street=r.cands[0][1]; s=s.slice(mx); }
  let m;
  if((m=s.match(/^(\d+)巷/))){r.lane=m[1];s=s.slice(m[0].length);}
  if((m=s.match(/^(\d+)弄/))){r.alley=m[1];s=s.slice(m[0].length);}
  if((m=s.match(/^(臨)?(\d+)(?:[之\-](\d+))?號?(?:之(\d+))?/))&&m[2]){r.lin_pref=m[1]||'';r.num=+m[2];r.sub=m[3]||m[4]||null;r.subAfter=!m[3]&&!!m[4];s=s.slice(m[0].length);}
  r.rest=s; r.norm=normalize(raw); return r;
}
function keyNum(k){const m=k.match(/^(臨)?(\d+)(?:-(.+))?$/);return m?{lin:!!m[1],n:+m[2],sub:m[3]||null}:null;}
function lookupLocal(p){
  if(!p.street||p.num==null) return null;
  const out=[];
  for(const [d,st] of p.cands){
    const lst=(AI[d][st]||{})[p.lane+'|'+p.alley]; if(!lst) continue;
    const want=[ (p.lin_pref||'')+p.num+(p.sub?'-'+p.sub:'') ];
    if(p.sub&&p.subAfter) want.push((p.lin_pref||'')+String(p.num));
    if(!p.lin_pref) want.push('臨'+p.num+(p.sub?'-'+p.sub:''));
    for(const w of want){ const rec=lst.find(x=>x[0]===w); if(rec){ out.push({method:'exact',dist:d,street:st,rec,label:fmtDoor(d,st,p.lane,p.alley,rec[0])}); break; } }
  }
  if(out.length) return out;
  // approximate: same street/lane/alley, nearest house number with same parity
  let best=null;
  for(const [d,st] of p.cands){
    const lst=(AI[d][st]||{})[p.lane+'|'+p.alley]; if(!lst) continue;
    for(const rec of lst){ const k=keyNum(rec[0]); if(!k||k.lin) continue; const diff=Math.abs(k.n-p.num)+((k.n%2)!==(p.num%2)?10000:0)+(k.sub?0.5:0);
      if(!best||diff<best.diff) best={diff,method:'approx',dist:d,street:st,rec,label:fmtDoor(d,st,p.lane,p.alley,rec[0])}; }
  }
  if(best&&best.diff<10000&&Math.abs(keyNum(best.rec[0]).n-p.num)<=40) return [best];
  return null;
}
function fmtDoor(d,st,lane,alley,k){return '基隆市'+d+st+(lane?lane+'巷':'')+(alley?alley+'弄':'')+k.replace(/-(.+)$/,'之$1')+'號';}
function pip(lon,lat){
  const inRing=(r)=>{let c=false;for(let i=0,j=r.length-1;i<r.length;j=i++){const [xi,yi]=r[i],[xj,yj]=r[j];if(((yi>lat)!==(yj>lat))&&(lon<(xj-xi)*(lat-yi)/(yj-yi)+xi))c=!c;}return c;};
  for(const f of VG.features){const g=f.geometry,polys=g.type==='Polygon'?[g.coordinates]:g.coordinates;
    for(const P of polys){ if(inRing(P[0])&&!P.slice(1).some(inRing)) return f.properties.i; } }
  return null;
}
function nearestDoor(lon,lat,vi){
  if(!flatPts){flatPts=[];for(const d in AI)for(const st in AI[d])for(const k in AI[d][st]){const [la,al]=k.split('|');for(const r of AI[d][st][k])flatPts.push([r[3],r[4],r[1],r[2],d,st,la,al,r[0]]);}}
  let b=null,bd=1e18; for(const p of flatPts){ if(vi!=null&&p[2]!==vi) continue; const dd=(p[0]-lon)**2+(p[1]-lat)**2; if(dd<bd){bd=dd;b=p;} }
  return b?{lon:b[0],lat:b[1],vi:b[2],lin:b[3],label:fmtDoor(b[4],b[5],b[6],b[7],b[8]),m:hav(lon,lat,b[0],b[1])}:null;
}
async function geocodeOnline(text){
  const u='https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?f=json&maxLocations=1&countryCode=TWN&outFields=Addr_type,Match_addr&SingleLine='+encodeURIComponent('基隆市'+normalize(text));
  const r=await fetch(u); const j=await r.json(); const c=(j.candidates||[])[0];
  if(!c||c.score<85) return null;
  const x=c.location.x,y=c.location.y; if(x<121.6||x>121.85||y<25.0||y>25.22) return null;
  return {lon:x,lat:y,score:c.score,type:c.attributes.Addr_type,match:c.address};
}

/* ---------- result rendering ---------- */
let lastResult=null;
function resolveLevel(v,lvl,lin){
  const L=v[lvl]; if(L.status==='single') return {groups:[L.groups[0]],exact:true};
  if(lin!=null){const g=L.groups.find(g=>g.lins.includes(lin)); if(g) return {groups:[g],exact:true};}
  return {groups:L.groups,exact:false};
}
function renderResult(R,move=true){
  lastResult=R; const v=D.villages[R.vi]; const box=$('#result'); box.hidden=false;
  let h='';
  if(R.title) h+='<div class="addr">'+esc(R.title)+'</div>';
  h+='<div class="meta">'+esc(v.dist)+' '+esc(v.vill)+(R.lin!=null?' 第'+R.lin+'鄰':'（未指定鄰）')+' · '+R.methodText+'</div>';
  if(R.warn) h+='<div class="note">'+R.warn+'</div>';
  for(const lvl of ['elem','junior']){
    const res=resolveLevel(v,lvl,R.lin);
    h+='<div class="lvl"'+(lvl===level?' style="border-color:#B89964"':'')+'><div class="t">'+LV[lvl]+'學區 '+statusBadge(v[lvl].status)+'</div>';
    if(res.exact){
      const g=res.groups[0];
      h+='<div class="sch">'+g.schools.map(n=>{const s=schoolBy[lvl][n];const dm=(s&&s.lat!=null&&R.lat!=null)?' <span class="dist walk" data-s="'+lvl+'|'+esc(n)+'">直線約'+fmtDist(hav(R.lon,R.lat,s.lon,s.lat))+'・步行計算中…</span>':'';
         return '<span style="cursor:pointer" onclick="KSM.selectSchool(\''+lvl+'\',\''+n+'\')"><span class="sw" style="background:'+colorOf(lvl,n)+'"></span> '+schoolLabel(n)+'</span> '+flagBadge(s)+dm;}).join('<span class="small">／</span>')+'</div>';
      if(g.schools.length>1) h+='<div class="note red">官方劃分表將本'+(v[lvl].status==='shared'?'里':'鄰')+'同時列於 '+g.schools.map(plain).join('、')+'（共同學區），實際分發請洽學校或教育處。</div>';
    }else{
      h+='<div class="small">此里依鄰分屬，請選擇鄰：</div>'+groupsHtml(v,lvl);
    }
    h+='<div class="small" style="margin-top:4px">表列原文：'+officialHtml(v,lvl)+'</div>';
    for(const g of res.groups) for(const n of g.schools){const s=schoolBy[lvl][n]; if(s&&s.flag) h+='<div class="note">'+esc(n)+'為'+esc(s.flag)+'：'+esc(s.flag==='總量管制學校'?D.meta.notes[0]:D.meta.notes[1])+'</div>';}
    if(lvl==='elem'&&v.vill==='東信里'&&(R.lin===32||R.lin==null)) h+='<div class="note">116學年度附註：'+esc(D.meta.notes[3])+'<br>115學年度附註：'+esc((D.meta.notes115||[])[4]||'')+'</div>';
    if(lvl==='elem') for(const g of res.groups) for(const n of g.schools) if(/^(中山|港西|忠孝|復興|尚仁|仙洞|和平)國小$/.test(n)){ h+='<div class="note small">'+esc(n)+'：115學年度表附註——'+esc(D.meta.notes115[3])+'</div>'; break; }
    h+='</div>';
  }
  if(!resolveLevel(v,'elem',R.lin).exact||!resolveLevel(v,'junior',R.lin).exact){
    h+='<div style="margin-top:8px"><select id="resLin" aria-label="選擇鄰"><option value="">— 選擇 '+esc(v.vill)+' 的鄰 —</option>'+v.lins.map(l=>'<option'+(l===R.hintLin?' selected':'')+' value="'+l+'">第'+l+'鄰'+(l===R.hintLin?'（最近門牌推測）':'')+'</option>').join('')+'</select></div>';
  }
  if(R.lat==null) h+='<div class="small">輸入門牌地址即可顯示到學校的步行距離與時間。</div>';
  h+='<div class="acts"><button class="btn sm ghost" id="shareBtn">複製分享連結</button><button class="btn sm ghost" id="copyBtn">複製查詢結果</button><button class="btn sm" id="cardBtn">下載結果圖卡（傳 LINE）</button><button class="btn sm ghost" id="printBtn">列印</button></div>';
  h+='<div class="small" style="margin-top:8px">※ 學區依「戶籍」認定，且有設籍時間等規定；本結果僅供參考，請以學校或基隆市政府教育處公告為準。</div>';
  box.innerHTML=h;
  const rl=$('#resLin'); if(rl) rl.onchange=()=>{ if(rl.value) renderResult(Object.assign({},R,{lin:+rl.value,methodText:R.methodText+'＋手動選鄰'})); };
  $('#shareBtn').onclick=()=>{updateHash();copy(location.href,'已複製分享連結');};
  $('#copyBtn').onclick=()=>copy(resultText(R),'已複製查詢結果');
  $('#cardBtn').onclick=()=>makeCard(R); $('#printBtn').onclick=()=>window.print();
  box.querySelectorAll('.walk').forEach(el=>{const [l,n]=el.dataset.s.split('|');const s=schoolBy[l][n];walkTo(R,s).then(w=>{if(lastResult!==R)return;el.innerHTML=walkHtml(R,s,w);});});
  syncSelects(v,R.lin);
  pinLayer.clearLayers();
  if(R.lat!=null){
    L.marker([R.lat,R.lon],{icon:L.divIcon({className:'',html:'<div class="pinicon">📍</div>',iconSize:[30,30],iconAnchor:[15,28]}),zIndexOffset:2000}).addTo(pinLayer).bindTooltip(R.title||v.vill,{direction:'top',offset:[0,-24]});
    if(move) map.setView([R.lat,R.lon],Math.max(map.getZoom(),16));
  }else if(move){ const f=VG.features.find(f=>f.properties.i===R.vi); if(f) map.fitBounds(L.geoJSON(f).getBounds(),{maxZoom:16}); }
  updateHash();
  if(window.innerWidth<=820&&move) box.scrollIntoView({behavior:'smooth',block:'start'});
}
function resultText(R){
  const v=D.villages[R.vi]; let t=(R.title?R.title+'\n':'')+v.dist+v.vill+(R.lin!=null?'第'+R.lin+'鄰':'')+'\n';
  for(const lvl of ['elem','junior']){const r=resolveLevel(v,lvl,R.lin); t+=LV[lvl]+'學區：'+(r.exact?r.groups[0].schools.map(plain).join('／'):'依鄰分屬：'+r.groups.map(g=>g.schools.map(plain).join('／')+'（第'+ranges(g.lins)+'鄰）').join('；'))+'\n';}
  return t+'資料：基隆市115、116學年度國民中小學學區劃分表（兩版表列相同；116年8月19日修正）。實際以學校／教育處為準。\n'+location.href;
}
function copy(t,msg){(navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).then(()=>toast(msg),()=>{prompt('請複製：',t);});}

/* ---------- walking route (OSRM foot, FOSSGIS demo server) ---------- */
const walkCache={};
async function walkTo(R,s){
  if(!s||s.lat==null||R.lat==null) return null;
  const k=[R.lon,R.lat,s.lon,s.lat].map(x=>x.toFixed(5)).join(',');
  if(k in walkCache) return walkCache[k];
  let out=null;
  try{ const ctl=new AbortController(); const t=setTimeout(()=>ctl.abort(),6000);
    const r=await fetch('https://routing.openstreetmap.de/routed-foot/route/v1/foot/'+R.lon+','+R.lat+';'+s.lon+','+s.lat+'?overview=false',{signal:ctl.signal}); clearTimeout(t);
    const j=await r.json(); if(j.code==='Ok'&&j.routes[0]) out={m:j.routes[0].distance,min:j.routes[0].distance/75,src:'osrm'};
  }catch(e){}
  if(!out){const m=hav(R.lon,R.lat,s.lon,s.lat)*1.35; out={m,min:m/75,src:'est'};}
  return walkCache[k]=out;
}
function walkHtml(R,s,w){
  const line='直線約'+fmtDist(hav(R.lon,R.lat,s.lon,s.lat));
  if(!w) return line;
  return '🚶 步行約 <b>'+Math.max(1,Math.round(w.min))+' 分鐘</b>（'+fmtDist(w.m)+(w.src==='osrm'?'，OSM 步行路線':'，估算＝直線×1.35')+'）・'+line;
}
/* ---------- one-image result card (PNG for LINE) ---------- */
async function makeCard(R){
  const v=D.villages[R.vi], W=1080, pad=64; const cv=document.createElement('canvas'); cv.width=W; cv.height=1350; const c=cv.getContext('2d');
  const F='"Noto Sans TC","PingFang TC","Microsoft JhengHei",sans-serif';
  c.fillStyle='#f6f4ee'; c.fillRect(0,0,W,1350); c.fillStyle='#10243D'; c.fillRect(0,0,W,190);
  c.fillStyle='#B89964'; c.fillRect(0,190,W,8);
  c.fillStyle='#fff'; c.font='bold 54px '+F; c.fillText('基隆市學區查詢結果',pad,95); c.font='30px '+F; c.fillStyle='#e8dcb0'; c.fillText('115、116學年度國民中小學學區劃分表',pad,150);
  const wrap=(t,x,y,max,lh)=>{let line='';for(const ch of t){if(c.measureText(line+ch).width>max){c.fillText(line,x,y);y+=lh;line=ch;}else line+=ch;}if(line){c.fillText(line,x,y);y+=lh;}return y;};
  let y=270; c.fillStyle='#10243D'; c.font='bold 44px '+F; y=wrap(R.title||(v.dist+v.vill),pad,y,W-2*pad,58);
  c.font='34px '+F; c.fillStyle='#555'; c.fillText(v.dist+' '+v.vill+(R.lin!=null?' 第'+R.lin+'鄰':'（未指定鄰）'),pad,y+6); y+=70;
  for(const lvl of ['elem','junior']){
    const res=resolveLevel(v,lvl,R.lin);
    c.fillStyle='#fff'; c.strokeStyle='#d8d2c2'; c.lineWidth=3; const top=y; const h0=230;
    c.fillRect(pad,top,W-2*pad,h0); c.strokeRect(pad,top,W-2*pad,h0);
    c.fillStyle='#B89964'; c.fillRect(pad,top,12,h0);
    c.fillStyle='#10243D'; c.font='bold 36px '+F; c.fillText(LV[lvl]+'學區',pad+40,top+58);
    c.font='bold 50px '+F; c.fillStyle='#111';
    let yy=top+130;
    if(res.exact){ yy=wrap(res.groups[0].schools.map(plain).join('／'),pad+40,yy,W-2*pad-80,60);
      c.font='28px '+F; c.fillStyle='#666';
      const s=schoolBy[lvl][res.groups[0].schools[0]];
      if(R.lat!=null&&s&&s.lat!=null){const w=await walkTo(R,s); c.fillText('步行約 '+Math.max(1,Math.round(w.min))+' 分鐘（'+fmtDist(w.m)+(w.src==='osrm'?'，OSM 步行路線':'，估算')+'）',pad+40,Math.min(yy+4,top+h0-22));}
      else if(res.groups[0].schools.length>1){c.fillText('官方表列為共同學區',pad+40,Math.min(yy+4,top+h0-22));}
    } else { c.font='32px '+F; yy=wrap('依鄰分屬：'+res.groups.map(g=>g.schools.map(plain).join('／')+'（第'+ranges(g.lins)+'鄰）').join('；'),pad+40,top+110,W-2*pad-80,42); }
    y=top+h0+36;
  }
  c.font='26px '+F; c.fillStyle='#666';
  y=wrap('※ 學區依戶籍認定，並有設籍期限、總量管制等規定，實際以學校／基隆市政府教育處公告為準。資料：教育處116學年度學區劃分表（116年8月19日修正）、內政部村里界、基隆市門牌資料（'+D.meta.door_src.replace(/^.*\(|\).*$/g,'')+'）。',pad,y+10,W-2*pad,38);
  const H=Math.min(1350,Math.max(900,y+40+110)); c.fillStyle='#10243D'; c.fillRect(0,H-110,W,110); c.fillStyle='#e8dcb0'; c.font='bold 34px '+F; c.fillText('中信房屋 冠軍商仲 劉展麟　LINE @key1',pad,H-45);
  const out=document.createElement('canvas'); out.width=W; out.height=H; out.getContext('2d').drawImage(cv,0,0);
  out.toBlob(async b=>{
    const name='學區-'+v.dist+v.vill+(R.lin!=null?R.lin+'鄰':'')+'.png'; const file=new File([b],name,{type:'image/png'});
    if(navigator.canShare&&navigator.canShare({files:[file]})){ try{ await navigator.share({files:[file],title:'學區查詢結果'}); return; }catch(e){} }
    const a=document.createElement('a'); a.href=URL.createObjectURL(b); a.download=name; document.body.appendChild(a); a.click(); a.remove(); toast('已下載結果圖卡');
  },'image/png');
  window.__KSM_lastCard=out;
}

async function doSearch(raw){
  raw=(raw||'').trim(); if(!raw) return;
  $('#addr').value=raw; const box=$('#result'); box.hidden=false; box.innerHTML='<span class="spin"></span> 查詢中…';
  const p=parseAddr(raw);
  if(p.vill&&!p.street&&p.num==null&&!p.rest){ // 里／鄰文字查詢，例：安樂區興寮里第26鄰
    const v=D.villages.find(x=>x.vill===p.vill&&(!p.dist||x.dist===p.dist));
    if(v){ if(p.lin_given!=null&&!v.lins.includes(p.lin_given)){ box.innerHTML='<div class="addr">'+esc(v.dist+v.vill)+'查無第'+p.lin_given+'鄰</div><div class="small">門牌資料中'+esc(v.vill)+'的鄰為：第'+ranges(v.lins)+'鄰。請核對戶口名簿，或洽戶政事務所。</div>'; return; }
      renderResult({vi:v.i,lin:p.lin_given,lon:null,lat:null,title:null,q:raw,methodText:p.lin_given!=null?'依里、鄰查詢':'依里查詢'}); return; }
  }
  const hits=lookupLocal(p);
  if(hits&&hits.length>1&&!p._pick){
    const uniq=new Map(); hits.forEach(h=>uniq.set(h.rec[1]+'|'+h.rec[2],h));
    if(uniq.size>1){
      box.innerHTML='<div class="addr">「'+esc(raw)+'」有多筆門牌</div><div class="small">同名路段位於不同行政區，請選擇正確的一筆（不自動猜測）：</div><div class="cands">'+
        [...uniq.values()].map((h,k)=>'<button class="btn sm ghost" data-k="'+k+'">'+esc(h.label)+'（'+esc(D.villages[h.rec[1]].vill)+'第'+h.rec[2]+'鄰）</button>').join('')+'</div>';
      const arr=[...uniq.values()]; box.querySelectorAll('.cands button').forEach(b=>b.onclick=()=>{const h=arr[+b.dataset.k];doSearch(h.label);}); return;
    }
  }
  if(hits&&hits.length){
    const h=hits[0], rec=h.rec;
    let warn=null;
    if(p.lin_given&&p.lin_given!==rec[2]) warn=(warn?warn+'<br>':'')+'您輸入第'+p.lin_given+'鄰，但門牌資料記載為第'+rec[2]+'鄰；以下依門牌資料判定。';
    if(h.method==='approx') warn='門牌資料查無「'+esc(p.norm)+'」，以下以同路段最接近的門牌「'+esc(h.label)+'」推估，鄰別可能不同，請以戶口名簿為準。';
    renderResult({vi:rec[1],lin:rec[2],lon:rec[3],lat:rec[4],q:raw,title:h.method==='exact'?h.label:raw,
      methodText:h.method==='exact'?'門牌資料精確比對':'<span class="badge approx">近似門牌推估</span>',warn});
    return;
  }
  if($('#useOnline').checked){
    try{
      const g=await geocodeOnline(raw);
      if(g){ const vi=pip(g.lon,g.lat);
        if(vi!=null){ const v=D.villages[vi]; const nd=nearestDoor(g.lon,g.lat,vi);
          const single=v.elem.status==='single'&&v.junior.status==='single';
          const want=(p.lane?p.lane+'巷':'')+(p.alley?p.alley+'弄':'')+(p.num!=null?p.num:''), mt=normalize(g.match);
          const partial=!want||!mt.includes(want);
          renderResult({vi,lin:single?null:(p.lin_given||null),hintLin:nd?nd.lin:null,lon:g.lon,lat:g.lat,q:raw,title:raw,
            methodText:'<span class="badge approx">線上定位（ArcGIS '+esc(g.type)+'）＋里界套疊</span>',
            warn:'門牌資料查無此地址，已用線上地圖定位（比對到：'+esc(g.match)+'）。'+(single?'':' 本里依鄰分屬，'+(nd?'最近門牌為「'+esc(nd.label)+'」第'+nd.lin+'鄰（約'+fmtDist(nd.m)+'），':'')+'請確認鄰別。')+(partial?'<br><b style="color:#b3261e">注意：線上定位結果與輸入地址不完全相符，可能只定位到路段，請改用「區→里→鄰」確認。</b>':'')});
          return; }
      }
    }catch(e){ console.warn(e); }
  }
  box.innerHTML='<div class="addr">查無「'+esc(raw)+'」</div><div class="small">請確認地址為基隆市門牌（例：中正區義一路1號、安樂區安樂路二段164號），或改用上方「區→里→鄰」查詢。'+(p.street?'':'<br>無法辨識路名。')+'</div>';
}

/* ---------- selects & lists ---------- */
function fillSelects(){
  const sd=$('#selDist'), sv=$('#selVill'), sl=$('#selLin');
  sd.innerHTML='<option value="">行政區</option>'+DISTS.map(d=>'<option>'+d+'</option>').join('');
  const fv=()=>{const d=sd.value;sv.innerHTML='<option value="">里</option>'+D.villages.filter(v=>v.dist===d).map(v=>'<option value="'+v.i+'">'+v.vill+'</option>').join('');sl.innerHTML='<option value="">鄰</option>';};
  const fl=()=>{const v=D.villages[sv.value];sl.innerHTML='<option value="">鄰</option>'+(v?v.lins.map(l=>'<option>'+l+'</option>').join(''):'');};
  sd.onchange=()=>{fv();}; 
  sv.onchange=()=>{fl(); if(sv.value!=='') renderResult({vi:+sv.value,lin:null,lon:null,lat:null,title:null,methodText:'依里查詢'});};
  sl.onchange=()=>{ if(sv.value!==''&&sl.value) renderResult({vi:+sv.value,lin:+sl.value,lon:null,lat:null,title:null,methodText:'依里、鄰查詢'}); };
  fv(); fillSelects._fv=fv; fillSelects._fl=fl;
}
function syncSelects(v,lin){
  const sd=$('#selDist'),sv=$('#selVill'),sl=$('#selLin');
  if(sd.value!==v.dist){sd.value=v.dist;fillSelects._fv();}
  if(sv.value!==String(v.i)){sv.value=v.i;fillSelects._fl();}
  sl.value=lin!=null?String(lin):'';
}
function pickVillage(i){map.closePopup();renderResult({vi:i,lin:null,lon:null,lat:null,title:null,methodText:'依里查詢'},false);$('#selLin').focus();}
function renderSchoolList(){
  const el=$('#slist'); let h='';
  for(const d of DISTS){
    const ss=D.schools[level].filter(s=>s.addr&&s.addr.includes(d)); if(!ss.length) continue;
    h+='<div class="grp">'+d+'</div>'+ss.map(s=>'<div class="it'+(selSchool&&selSchool.name===s.name?' on':'')+'" data-n="'+esc(s.name)+'"><span class="sw" style="background:'+s.color+'"></span>'+schoolLabel(esc(s.name))+' '+flagBadge(s)+'<span class="small" style="margin-left:auto">'+s.coverage.length+'里</span></div>').join('');
  }
  h+='<div style="margin-top:8px"><button class="btn sm ghost" id="clrSel">清除標示</button></div>';
  el.innerHTML=h;
  el.querySelectorAll('.it').forEach(x=>x.onclick=()=>selectSchool(level,x.dataset.n));
  $('#clrSel').onclick=()=>{clearSchool();updateHash();};
  $('#schoolsBox').querySelector('summary').textContent=LV[level]+'列表（'+D.schools[level].length+'校，點選可標示學區範圍）';
}
function renderFooter(){
  const m=D.meta;
  $('#foot').innerHTML='<b>資料來源與版本</b><br>'+
   '・學區：<a href="'+m.source_page+'" target="_blank" rel="noopener">'+esc(m.title)+'</a>（'+esc(m.revised)+'，'+esc(m.published)+'公告，<a href="'+m.source_pdf+'" target="_blank" rel="noopener">PDF</a>）<br>'+
   (m.prev_page?'・115學年度：<a href="'+m.prev_page+'" target="_blank" rel="noopener">'+esc(m.prev_title)+'</a>（'+esc(m.prev_revised)+'，<a href="'+m.prev_pdf+'" target="_blank" rel="noopener">PDF</a>）——表列內容與116學年度逐列相同，僅附註不同<br>':'')+
   '・里界：<a href="'+m.village_url+'" target="_blank" rel="noopener">'+esc(m.village_src)+'</a><br>'+
   '・門牌／鄰：<a href="'+m.door_url+'" target="_blank" rel="noopener">'+esc(m.door_src)+'</a>，共 '+m.doorplate_count.toLocaleString()+' 筆不重複門牌<br>'+
   '・學校：<a href="'+m.moe_url+'" target="_blank" rel="noopener">'+esc(m.moe_src)+'</a><br>'+
   '・建置時間：'+esc(m.built)+'（臺北時間）<br><br>'+
   '<b>免責聲明</b>：學區以戶籍認定，並有設籍期限、總量管制、實驗教育等規定，本站僅為查詢輔助，<b>實際學區請以學校或基隆市政府教育處公告為準</b>（國民教育科 02-24301505#205）。斜線區域為「依鄰分屬」或「表列多校」，未自行繪製鄰界。'+
   '<div class="brand">中信房屋 冠軍商仲 劉展麟 · LINE @key1<br><b>製作人：劉展麟</b>　冠軍商仲房屋有限公司 ／ 經紀人：蘇郁棠（91）北縣字第723號</div>';
}
function about(){
  const m=D.meta, st=l=>{const c={single:0,split:0,shared:0};D.villages.forEach(v=>c[v[l].status]++);return c;}, e=st('elem'), j=st('junior');
  $('#modalBox').innerHTML='<h2>資料說明</h2><p>本站把 <b>'+esc(m.title)+'</b>（'+esc(m.revised)+'）的文字表逐條轉為資料，套疊內政部村里界，並用基隆市門牌資料（含每個門牌的里、鄰與座標）做地址比對。</p>'+
  '<ul><li>涵蓋：7 區 '+D.villages.length+' 里；國小 '+D.schools.elem.length+' 校、國中 '+D.schools.junior.length+' 校（含附設國中部之高中）。每一里、每一鄰皆有對應學校，無缺漏。</li>'+
  '<li>國小：全里同一學區 '+e.single+' 里、依鄰分屬 '+e.split+' 里、表列多校 '+e.shared+' 里。國中：'+j.single+'／'+j.split+'／'+j.shared+' 里。</li>'+
  '<li>依鄰分屬的里以斜線標示；放大到 15 級可看到每一門牌點的歸屬顏色（官方門牌座標），不自行推測鄰界。</li>'+
  '<li>「表列多校」代表官方表把同一里（或同一鄰）同時列在兩所以上學校，本站如實呈現，不代為判斷。</li>'+
  '<li>地址查詢先比對官方門牌資料（離線、精確到鄰）；查無時才以 ArcGIS 線上定位＋里界套疊，並提示確認鄰別。</li></ul>'+
  '<p><b>官方附註（116學年度）</b></p><ol>'+m.notes.map(n=>'<li>'+esc(n)+'</li>').join('')+'</ol>'+
  (m.notes115?'<p><b>115學年度表附註</b>（表列學區與116相同；附註差異：東信里第32鄰為「二年級以上」，並有七所原開放學區學校之說明）</p><ol>'+m.notes115.map(n=>'<li>'+esc(n)+'</li>').join('')+'</ol>':'')+
  '<p class="small">鄰的清單以門牌資料為準（部分里鄰號不連續，例如信綠里無第14鄰），並與戶政月報鄰數核對一致。</p>'+
  '<div style="text-align:right"><button class="btn" onclick="document.getElementById(\'modal\').classList.remove(\'on\')">關閉</button></div>';
  $('#modal').classList.add('on');
}

/* ---------- URL hash (share links) ---------- */
let hashLock=false;
function updateHash(){
  if(hashLock) return; const q=new URLSearchParams(); q.set('l',level);
  if(lastResult){ if(lastResult.q) q.set('q',lastResult.q); else {const v=D.villages[lastResult.vi];q.set('v',v.dist+'/'+v.vill+(lastResult.lin!=null?'/'+lastResult.lin:''));} if(lastResult.q&&lastResult.lin!=null&&lastResult.methodText.includes('手動'))q.set('n',lastResult.lin); }
  if(selSchool) q.set('s',selSchool.name);
  history.replaceState(null,'','#'+q.toString());
}
async function readHash(){
  const q=new URLSearchParams(location.hash.slice(1)); hashLock=true;
  try{
    if(q.get('l')==='junior') setLevel('junior');
    if(q.get('s')) selectSchool(level,q.get('s'));
    if(q.get('q')){ await doSearch(q.get('q')); if(q.get('n')&&lastResult) renderResult(Object.assign({},lastResult,{lin:+q.get('n'),methodText:lastResult.methodText+'＋手動選鄰'})); }
    else if(q.get('v')){ const [d,vn,ln]=q.get('v').split('/'); const v=D.villages.find(x=>x.dist===d&&x.vill===vn); if(v) renderResult({vi:v.i,lin:ln?+ln:null,lon:null,lat:null,title:null,methodText:'依里、鄰查詢'}); }
  }finally{hashLock=false;}
}

/* ---------- boot ---------- */
async function boot(){
  try{ [D,VG,DG,AI]=await loadData(); }catch(e){ document.body.insertAdjacentHTML('afterbegin','<div style="padding:12px;background:#fdeceb">資料載入失敗：'+esc(e.message)+'（若直接開啟檔案，請改用單一檔案版 keelung-school-map.html 或以本機伺服器開啟）</div>'); return; }
  for(const l of ['elem','junior']) for(const s of D.schools[l]) schoolBy[l][s.name]=s;
  initMap(); drawUnions(); drawMarkers(); drawDots(); drawLegend(); fillSelects(); renderSchoolList(); renderFooter();
  const sts=new Set(); for(const d in AI) for(const st in AI[d]) sts.add(st);
  $('#streetList').innerHTML=[...sts].sort().map(s=>'<option value="'+s+'">').join('');
  const ex=['信義區信二路268號','中正區義一路1號','仁愛區愛四路29號','安樂區安樂路二段164號','暖暖區暖暖街1號','七堵區明德一路1號'];
  $('#examples').innerHTML=ex.map(e=>'<span class="chip">'+e+'</span>').join('');
  $('#examples').querySelectorAll('.chip').forEach(c=>c.onclick=()=>doSearch(c.textContent));
  $('#addrForm').onsubmit=e=>{e.preventDefault();doSearch($('#addr').value);};
  $('#aboutBtn').onclick=about; $('#modal').onclick=e=>{if(e.target.id==='modal')e.target.classList.remove('on');};
  await readHash();
  window.KSM_READY=true;
}
function answer(){if(!lastResult)return null;const v=D.villages[lastResult.vi],o={dist:v.dist,vill:v.vill,lin:lastResult.lin,method:lastResult.methodText};for(const l of ['elem','junior']){const r=resolveLevel(v,l,lastResult.lin);o[l]=r.exact?r.groups[0].schools:null;}return o;}
window.KSM={answer,geocodeOnline,selectSchool,pickVillage,doSearch,setLevel,parseAddr,lookupLocal,get data(){return D;},get last(){return lastResult;}};
boot();
})();
