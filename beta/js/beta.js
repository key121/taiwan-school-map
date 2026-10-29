/* 台灣學區查詢 測試版：門牌 → 里鄰 → 學區。資料：beta/data（本測試版）＋ ../data（正式版之村里界、學校名錄，唯讀）。 */
(function(){
'use strict';
const N=window.AddrNorm;
const $=s=>document.querySelector(s);
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const LVN={e:'國小',j:'國中'};
const STN={verified:'本站核對',merged:'整理資料',partial:'部分收錄',none:'未收錄'};
const ALIAS={'臺北縣':'65000','桃園縣':'68000','臺中縣':'66000','臺南縣':'67000','高雄縣':'64000'};
const STATS={bytes:0,files:[],mapBytes:0,mapFiles:[]};let MAPCTX=false;             // 每次查詢下載量（QA 用）
let REG=null,REGBY={},TOWNS=null,CTY=null;
const cache={},addrMeta={},shardC={},roadsC={};
let map=null,ctyLayer=null,villLayer=null,schLayer=null,pinLayer=null,lv='e',cur=null,last=null;

/* ---------- 下載（含 .gz 解壓與流量統計） ---------- */
async function getBuf(u,forMap){const r=await fetch(u);if(!r.ok)throw new Error(u+' '+r.status);const b=await r.arrayBuffer();if(forMap){STATS.mapBytes+=b.byteLength;STATS.mapFiles.push([u,b.byteLength]);}else{STATS.bytes+=b.byteLength;STATS.files.push([u,b.byteLength]);}return b;}
async function fj(u,forMap){const b=await getBuf(u,forMap);return JSON.parse(new TextDecoder().decode(b));}
async function fgz(u){
  const b=await getBuf(u);const v=new Uint8Array(b);
  if(v[0]===0x1f&&v[1]===0x8b){const s=new Blob([b]).stream().pipeThrough(new DecompressionStream('gzip'));return JSON.parse(await new Response(s).text());}
  return JSON.parse(new TextDecoder().decode(b));   // 伺服器已自動解壓
}
function loading(on){$('#loading').classList.toggle('hidden',!on);}

/* ---------- 啟動 ---------- */
async function boot(){
  [REG,TOWNS]=await Promise.all([fj('data/registry.json'),fj('data/towns.json')]);
  for(const r of REG.counties)REGBY[r.code]=r;
  const sel=$('#county');
  for(const r of REG.counties){const o=document.createElement('option');o.value=r.code;o.textContent=r.name+'（'+STN[r.status]+'）';sel.appendChild(o);}
  covTable();
  $('#qform').addEventListener('submit',e=>{e.preventDefault();run($('#q').value,$('#county').value||null);});
  document.querySelectorAll('.lvtoggle button').forEach(b=>b.addEventListener('click',()=>{lv=b.dataset.lv;document.querySelectorAll('.lvtoggle button').forEach(x=>x.classList.toggle('on',x===b));if(cur&&villLayer)drawCounty(false);legend();}));
  lazyMap();
  // 社區名稱自動完成：輸入兩個字以上、且沒有門牌號碼時才下載社區索引（約 30KB）
  const q=$('#q'),box=$('#qSug');let tmr=null,seq=0;
  const hide=()=>{box.classList.add('hidden');box.innerHTML='';};
  q.addEventListener('input',()=>{clearTimeout(tmr);const v=q.value.trim();if(v.length<2||/\d/.test(v)){hide();return;}
    tmr=setTimeout(async()=>{const my=++seq;const L=await commFind(v,8).catch(()=>[]);if(my!==seq)return;if(!L.length||q.value.trim()!==v){hide();return;}
      box.innerHTML=L.map(([,c])=>'<button type="button" role="option" data-n="'+esc(c.n)+'">'+esc(c.n)+'<small>'+esc(REGBY[c.code].name+c.d)+'・社區</small></button>').join('');box.classList.remove('hidden');
      box.querySelectorAll('button').forEach(b=>b.addEventListener('mousedown',e=>e.preventDefault()));
      box.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{q.value=b.dataset.n;hide();run(b.dataset.n,$('#county').value||null);}));},150);});
  q.addEventListener('blur',()=>setTimeout(hide,150));
  $('#qform').addEventListener('submit',hide);
  const h=new URLSearchParams(location.hash.slice(1));
  if(h.get('q')){$('#q').value=h.get('q');if(h.get('c'))$('#county').value=h.get('c');run(h.get('q'),h.get('c')||null,h.get('n')?+h.get('n'):null);}
}

/* ---------- 解析地址 ---------- */
function parse(raw,forced){
  let a=N.norm(raw).replace(/^\d{3}(\d{2,3})?(?=\D)/,'').replace(/^臺灣省?/,'');
  const P={raw,norm:a,code:null,dist:null,vill:null,lin:null,key:null,rest:''};
  let code=null;
  for(const [k,c] of Object.entries(ALIAS))if(a.startsWith(k)){code=c;a=a.slice(k.length);break;}
  if(!code)for(const r of REG.counties)if(a.startsWith(r.name)){code=r.code;a=a.slice(r.name.length);break;}
  if(!code){const short=REG.counties.filter(r=>a.startsWith(r.name.slice(0,2)));if(short.length===1&&!/^(市|縣)/.test(a.slice(2))){const s2=a.slice(2);const t=distAt(s2,short[0].code);if(t){code=short[0].code;a=s2;}}}
  P.typedCode=code;P.forced=forced||null;
  if(forced){P.override=code&&code!==forced?code:null;code=forced;}
  P.code=code;
  // 鄉鎮市區
  const cands=Object.keys(TOWNS).filter(t=>!code||TOWNS[t].includes(code)).sort((x,y)=>y.length-x.length);
  let d=null;
  for(const t of cands)if(a.startsWith(t)){d=t;a=a.slice(t.length);break;}
  if(!d)for(const t of cands){if(t.length<3)continue;const s=t.slice(0,-1);if(a.startsWith(s)&&!/^(路|街|大道|巷|弄|段|里|村)/.test(a.slice(s.length))&&!/^\d/.test(a.slice(s.length))){d=t;a=a.slice(s.length);break;}}
  P.dist=d;
  if(d&&!code){const cs=TOWNS[d];if(cs.length===1)P.code=cs[0];else P.needCounty=cs;}
  // 里／村＋鄰
  let m=a.match(/^([^\d路街道巷弄號段]{1,6}?[里村])(\d+)鄰/);
  if(m){P.vill=m[1];P.lin=+m[2];a=a.slice(m[0].length);}
  else{m=a.match(/^([^\d路街道巷弄號段]{1,6}?[里村])(?=[^\d]|$)/);if(m&&!/[路街]/.test(m[1])){P.villMaybe=m[1];}}
  if(!P.lin){const ml=a.match(/^(\d+)鄰/);if(ml){P.lin=+ml[1];a=a.slice(ml[0].length);}}
  P.rest=a;
  return P;
}
function distAt(s,code){return Object.keys(TOWNS).some(t=>TOWNS[t].includes(code)&&s.startsWith(t));}

/* ---------- 縣市資料 ---------- */
async function loadCounty(code){
  if(cache[code])return cache[code];
  const reg=REGBY[code];
  const [schools,zones]=await Promise.all([fj('../data/c/'+code+'/schools.json').catch(()=>[]),reg.hasZones?fj('data/c/'+code+'/zones.json'):Promise.resolve(null)]);
  const sBy={};for(const s of schools)sBy[s.id]=s;
  if(zones&&zones.extra_schools)for(const s of zones.extra_schools)sBy[s.id]=Object.assign({extra:true},s);
  let cross=null,crossS={};
  if(reg.cross){try{cross=await fj('../data/c/'+code+'/'+reg.cross.file);const cs=await fj('../data/c/'+reg.cross.from+'/schools.json');for(const s of cs)crossS[s.id]=s;}catch(e){}}
  return cache[code]={code,reg,schools,sBy,zones,cross,crossS,vill:null,villBy:null};
}
async function loadVill(C){
  if(C.vill)return C;
  C.vill=await fj('../data/c/'+C.code+'/villages.json',!C._needPip);
  C.villBy={};for(const f of C.vill.features)if(f.properties.v)C.villBy[f.properties.t+'|'+f.properties.v]=f.properties;
  return C;
}
async function aMeta(code){if(!(code in addrMeta)){const r=REGBY[code];addrMeta[code]=r.addr?await fj('data/a/'+code+'/meta.json'):null;}return addrMeta[code];}
async function shard(code,dist,road){
  const M=await aMeta(code);if(!M||!M.f[dist])return null;
  const f=M.f[dist];const b=f.nb>1?N.rhash(road,f.nb):0;const u='data/a/'+code+'/'+f.i+'_'+b+'.json.gz';
  if(!shardC[u])shardC[u]=fgz(u);
  return shardC[u];
}
async function roads(code){if(!roadsC[code])roadsC[code]=fgz('data/a/'+code+'/roads.json.gz');return roadsC[code];}

/* ---------- 全台路名索引（沒寫縣市、區時用；每次只下載一個約 24KB 的分片） ---------- */
const rbC={};let NAMES=null,COMM=null;
async function roadBucket(road){const b=N.rhash(road,8);if(!rbC[b])rbC[b]=fgz('data/r/'+b+'.json.gz');return rbC[b];}
async function roadLocs(road){const B=await roadBucket(road);return {locs:(B[road]||[]).map(x=>{const [code,i]=x.split('.');return {code,i:+i};}),sug:B['~'+road]||[]};}
async function roadNames(){if(!NAMES)NAMES=fgz('data/r/names.json.gz');return NAMES;}
const noAddr=()=>REG.counties.filter(r=>!r.addr).map(r=>r.name);

/* ---------- 社區名稱索引（目前：基隆市） ---------- */
const COMM_CODES=['10017'];
async function comm(){
  if(!COMM)COMM=Promise.all(COMM_CODES.map(c=>fj('data/comm/'+c+'.json').then(j=>(j.code=c,j)))).then(L=>{const all=[];for(const j of L)for(const c of j.c){c.code=j.code;c.keys=[c.n].concat(c.a||[]).map(cnorm).filter(Boolean);all.push(c);}return {list:all,src:L};});
  return COMM;
}
const SUFX=/(管理委員會|管委會|社區|大樓|大廈|華廈|公寓|住宅|新城)$/;
function cnorm(s){
  s=String(s||'').normalize('NFKC').replace(/台/g,'臺').replace(/[\s‧·・．.,，、\-－_~～()（）「」『』"']/g,'');
  s=s.replace(/^(臺灣省?)?/,'');
  for(const r of (REG?REG.counties:[]))if(s.startsWith(r.name)&&s.length>r.name.length+1){s=s.slice(r.name.length);break;}
  if(TOWNS)for(const t of Object.keys(TOWNS))if(t.length>=2&&s.startsWith(t)&&s.length>t.length+1){s=s.slice(t.length);break;}
  for(let i=0;i<2;i++){const t=s.replace(SUFX,'');if(t.length>=2)s=t;}
  return s;
}
async function commFind(q,max){
  const qn=cnorm(q);if(qn.length<2)return [];
  const {list}=await comm();const out=[];
  for(const c of list){let sc=0;for(const k of c.keys){const v=k===qn?3:k.startsWith(qn)?2:k.includes(qn)?1:(qn.length>=3&&qn.includes(k)&&k.length>=2)?0.5:0;if(v>sc)sc=v;}if(sc)out.push([sc,c]);}
  out.sort((a,b)=>b[0]-a[0]||a[1].n.length-b[1].n.length);
  return out.slice(0,max||50);
}

/* ---------- 門牌查找 ---------- */
function recs(x){return Array.isArray(x[0])?x:[x];}
async function lookupIn(code,dist,key){
  const road=N.roadOf(key);const S=await shard(code,dist,road);if(!S)return null;
  const tries=[[key,null]];
  if(key.includes('臨'))tries.push([key.replace(/臨(?=\d+(之\d+)?(附\d+)?號$)/,''),null]);
  if(/附\d+號$/.test(key))tries.push([key.replace(/附\d+號$/,'號'),'無「附號」門牌，以主號比對']);
  const mm=key.match(/^(.*?\d+)之\d+(附\d+)?號$/);if(mm)tries.push([mm[1]+'號','無此「之號」門牌，以主號 '+mm[1].match(/\d+$/)[0]+' 號比對']);
  for(const [k,note] of tries){const x=S.k[k];if(x)return {dist,key:k,note,hits:recs(x).map(r=>({vill:S.v[r[0]],lin:r[1],lat:r[2],lng:r[3],orig:r[4]||null}))};}
  return {dist,miss:true};
}
async function lookup(code,dist,key){
  const M=await aMeta(code);if(!M)return {noIndex:true};
  if(dist){const r=await lookupIn(code,dist,key);return r&&!r.miss?{found:[r]}:{found:[]};}
  const R=await roads(code);const road=N.roadOf(key);
  const ds=(R[road]||[]).map(i=>M.d[i]);
  if(ds.length>6)return {found:[],many:ds,roadKnown:true};   // 同縣市太多區有此路：請選區，避免一次下載大量分片
  const found=[];for(const d of ds){const r=await lookupIn(code,d,key);if(r&&!r.miss)found.push(r);}
  return {found,roadKnown:ds.length>0};
}

/* ---------- ArcGIS 後援 ---------- */
async function geocode(q){
  const u='https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?f=json&countryCode=TWN&maxLocations=1&outFields=Score,Addr_type,Match_addr&SingleLine='+encodeURIComponent(q);
  const ctl=new AbortController();const t=setTimeout(()=>ctl.abort(),8000);
  try{const j=await fetch(u,{signal:ctl.signal}).then(r=>r.json());const c=(j.candidates||[])[0];if(!c||c.score<85)return null;return {lat:c.location.y,lon:c.location.x,score:c.score,type:c.attributes.Addr_type,match:c.attributes.Match_addr||c.address};}
  catch(e){return null;}finally{clearTimeout(t);}
}
function inRing(x,y,r){let c=false;for(let i=0,j=r.length-1;i<r.length;j=i++){const xi=r[i][0],yi=r[i][1],xj=r[j][0],yj=r[j][1];if(((yi>y)!==(yj>y))&&(x<(xj-xi)*(y-yi)/(yj-yi)+xi))c=!c;}return c;}
function inPoly(x,y,g){const P=g.type==='Polygon'?[g.coordinates]:g.coordinates;for(const p of P){if(inRing(x,y,p[0])){let h=false;for(let k=1;k<p.length;k++)if(inRing(x,y,p[k]))h=true;if(!h)return true;}}return false;}
async function counties(forMap){if(!CTY)CTY=fj('../data/counties.geojson',forMap);return CTY;}
async function countyAt(lat,lon){const G=await counties();for(const f of G.features){const b=f.properties.bbox;if(lon<b[0]-.01||lon>b[2]+.01||lat<b[1]-.01||lat>b[3]+.01)continue;if(inPoly(lon,lat,f.geometry))return f.properties.code;}return null;}
function villAt(C,lat,lon){for(const f of C.vill.features){if(!f.properties.v)continue;if(inPoly(lon,lat,f.geometry))return f.properties;}return null;}

/* ---------- 主流程 ---------- */
async function run(q,forced,presetLin){
  q=(q||'').trim();if(!q)return;
  STATS.bytes=0;STATS.files=[];STATS.mapBytes=0;STATS.mapFiles=[];
  const P=parse(q,forced);
  show('<div class="small">查詢中…</div>');
  try{await resolve(P,presetLin);}catch(e){console.error(e);show('<div class="flag bad">查詢時發生錯誤：'+esc(e.message)+'</div>');}
  window.__betaStats=STATS;
}
async function resolve(P,presetLin){
  const key=N.doorKey(P.rest);
  // 社區名稱（沒有門牌、沒有鄰時先試；例如「微笑台北」「信義城」）
  if(!key&&!P.lin&&(!(P.forced||P.typedCode)||COMM_CODES.includes(P.forced||P.typedCode))){const r=await commSearch(P);if(r)return;}
  if(P.needCounty){
    // 同名區（如大安區、東區）：先用里名或路名自動判斷，仍無法判斷才請使用者選
    let cs=P.needCounty;const v=P.vill||P.villMaybe;
    if(v){const ok=[];for(const c of cs){const C=await loadCounty(c);if(C.zones&&Object.keys(C.zones.v).some(k=>k===P.dist+'|'+v||(k.split('|')[0]===P.dist&&N.canon(k.split('|')[1])===N.canon(v))))ok.push(c);}if(ok.length)cs=ok;}
    else if(key){const ok=[];for(const c of cs){const M=await aMeta(c);if(!M)continue;const R=await roads(c);const i=M.d.indexOf(P.dist);if((R[N.roadOf(key)]||[]).includes(i))ok.push(c);}if(ok.length)cs=ok;}
    if(cs.length===1){P.code=cs[0];P.needCounty=null;}
    else return choose('「'+P.dist+'」在多個縣市都有，請選縣市：',cs.map(c=>[REGBY[c].name,()=>run(P.raw,c)]));
  }
  // 1) 只給 區＋里＋鄰（沒有門牌）
  if(P.code&&P.vill&&!key){const C=await loadCounty(P.code);return answer(C,{dist:P.dist||guessDist(C,P.vill),vill:P.vill,lin:P.lin,how:'user',P});}
  // 2) 門牌比對
  if(key&&P.code){
    const C=await loadCounty(P.code);
    const L=await lookup(P.code,P.dist,key);
    if(L.many)return choose('「'+N.roadOf(key)+'」在'+REGBY[P.code].name+'的 '+L.many.length+' 個區都有，請選區：',L.many.map(d=>[d,()=>run(REGBY[P.code].name+d+P.rest,P.code)]));
    if(L.found&&L.found.length){
      if(L.found.length>1)return choose('這個門牌在 '+REGBY[P.code].name+' 的多個區都有，請選區：',L.found.map(f=>[f.dist,()=>run(REGBY[P.code].name+f.dist+P.rest,P.code)]));
      const f=L.found[0];
      const uniq=[...new Map(f.hits.map(h=>[h.vill+'|'+h.lin,h])).values()];
      if(uniq.length>1&&presetLin==null)return choose('此門牌在門牌資料中對應多個里鄰（常見於同號多戶），請選擇：',uniq.map(h=>[h.vill+h.lin+'鄰',()=>answer(C,{dist:f.dist,vill:h.vill,lin:h.lin,how:'door',hit:h,lk:f,P})]));
      const h=uniq[0];
      return answer(C,{dist:f.dist,vill:h.vill,lin:h.lin,how:'door',hit:h,lk:f,P,userVill:P.vill,userLin:P.lin});
    }
    return geoFallback(P,key,L.noIndex?'本縣市尚無門牌索引':'門牌資料查無此門牌',presetLin);
  }
  if(key&&!P.code)return roadOnly(P,key,presetLin);

  if(P.code&&P.villMaybe){const C=await loadCounty(P.code);return answer(C,{dist:P.dist||guessDist(C,P.villMaybe),vill:P.villMaybe,lin:P.lin,how:'user',P});}
  show('<div class="flag">'+(P.commMiss?'找不到名為「'+esc(P.raw)+'」的社區（社區名稱目前只收錄基隆市）。<br>':'')+'請輸入下列任一種：<br>・門牌地址，例如「<b>基隆市信義區孝東路108號</b>」<br>・社區名稱，例如「<b>微笑台北</b>」<br>・戶口名簿上的「區＋里＋鄰」，例如「<b>信義區孝深里24鄰</b>」</div>');
}
/* 沒寫縣市也沒寫區：全台路名索引 → 精確門牌；同名路列候選，不自動猜 */
async function roadOnly(P,key,presetLin){
  const road=N.roadOf(key);const R=await roadLocs(road);
  const tail=key.slice(road.length);           // 例如「108號」
  // 建議（非原輸入路名）：較長的同尾路名（孝東路→忠孝東路），或未寫「段」時的各段
  let sug=R.sug.filter(x=>R.locs.length?!x.startsWith(road):true);
  if(!R.locs.length&&!sug.length){const NM=await roadNames();if(road.length>=2)sug=NM.filter(x=>x!==road&&(x.endsWith(road)||x.includes(road))).sort((a,b)=>a.length-b.length).slice(0,8);}
  const rest=P.rest.slice(P.rest.indexOf(key)+key.length);
  const sugBtns=sug.map(x=>['建議：'+x+tail,()=>{$('#q').value=x+tail+rest;run(x+tail+rest,null);}]);
  P.sugHtml=sug.length?'<div class="flag"><b>你是不是要找</b>（建議，非原輸入路名）：'+sug.map(x=>'<button type="button" class="btn sm ghost sugBtn" data-q="'+esc(x+tail+rest)+'">'+esc(x+tail)+'</button>').join(' ')+'</div>':'';
  const unindexed=noAddr();
  const note='沒寫縣市和區：已在有門牌資料的縣市中比對「'+key+'」'+(unindexed.length?'（'+unindexed.join('、')+'尚無門牌資料，未比對）':'')+'。';
  if(!R.locs.length){
    if(sug.length)return choose('門牌資料裡沒有「'+road+'」這條路。你是不是要找下列路名？（建議，非原輸入路名）',sugBtns);
    return geoFallback(P,key,'各縣市門牌資料都沒有「'+road+'」這條路',presetLin);
  }
  const byC={};for(const l of R.locs)(byC[l.code]=byC[l.code]||[]).push(l.i);
  if(R.locs.length>6){
    const cs=Object.keys(byC).sort((a,b)=>byC[b].length-byC[a].length);
    return choose('「'+road+'」在 '+cs.length+' 個縣市、'+R.locs.length+' 個區都有，請選縣市（下次可直接在地址前加上縣市和區）：',cs.map(c=>[REGBY[c].name+'（'+byC[c].length+' 區）',()=>run(REGBY[c].name+P.rest,c)]).concat(sugBtns));
  }
  const found=[];
  for(const l of R.locs){const M=await aMeta(l.code);if(!M)continue;const d=M.d[l.i];const r=await lookupIn(l.code,d,key);if(r&&!r.miss)found.push(Object.assign(r,{code:l.code}));}
  if(found.length===1){
    const f=found[0];const C=await loadCounty(f.code);
    const uniq=[...new Map(f.hits.map(h=>[h.vill+'|'+h.lin,h])).values()];
    const P2=Object.assign({},P,{code:f.code,roadOnlyNote:note,extraHtml:P.sugHtml});
    if(uniq.length>1&&presetLin==null)return choose(REGBY[f.code].name+f.dist+f.key+'：門牌資料中對應多個里鄰（常見於同號多戶），請選擇：',uniq.map(h=>[h.vill+h.lin+'鄰',()=>answer(C,{dist:f.dist,vill:h.vill,lin:h.lin,how:'door',hit:h,lk:f,P:P2})]));
    const h=uniq[0];return answer(C,{dist:f.dist,vill:h.vill,lin:h.lin,how:'door',hit:h,lk:f,P:P2});
  }
  if(found.length>1)return choose('「'+key+'」在多個地方都有，請選一個：',found.map(f=>[REGBY[f.code].name+f.dist+f.key,()=>{const q=REGBY[f.code].name+f.dist+P.rest;$('#q').value=q;run(q,f.code);}]).concat(sugBtns));
  // 路名存在但門牌號碼不在資料中：列出這條路所在，交給使用者選（不換路名）
  const opts=[];for(const l of R.locs){const M=await aMeta(l.code);if(M)opts.push([REGBY[l.code].name+M.d[l.i]+P.rest,l.code]);}
  return choose('門牌資料有「'+road+'」這條路，但沒有「'+key+'」這個門牌。請確認號碼，或選地點改用線上定位：',opts.map(([q,c])=>[q,()=>{$('#q').value=q;run(q,c);}]).concat(sugBtns));
}
/* 社區名稱 → 門牌 → 里鄰 → 學區；不同棟分屬不同學區時逐一列出 */
async function commSearch(P){
  const q=P.raw;let hits=await commFind(q);
  if(/[里村]$/.test(cnorm(q)))hits=hits.filter(h=>h[0]===3);   // 像里名的輸入只接受完全相同的社區名
  if(!hits.length){P.commMiss=!P.villMaybe&&!/\d/.test(q);return false;}
  const exact=hits.filter(h=>h[0]===3);
  if(exact.length===1)return commAnswer(exact[0][1],P,hits.filter(h=>h[0]<3).slice(0,6).map(h=>h[1])),true;
  const L=(exact.length?exact:hits).slice(0,12);
  if(L.length===1)return commAnswer(L[0][1],P,[]),true;
  choose('有 '+(exact.length||hits.length)+' 個社區名稱符合「'+q+'」，請選：',L.map(([,c])=>[c.n+'（'+REGBY[c.code].name+c.d+'）',()=>{$('#q').value=c.n;commAnswer(c,Object.assign({},P,{raw:c.n}),[]);}]));
  return true;
}
async function commAnswer(c,P,others){
  const C=await loadCounty(c.code);const name=REGBY[c.code].name;
  const groups=[];const bySig=new Map();
  for(const g of c.g){
    const [d,v,lin,lab,k,n]=g;let K=d+'|'+v;
    if(C.zones&&!C.zones.v[K]){const alt=Object.keys(C.zones.v).find(x=>x.split('|')[0]===d&&N.canon(x.split('|')[1])===N.canon(v));if(alt)K=alt;}
    const be=lvBlock(C,K,'e',lin),bj=lvBlock(C,K,'j',lin);const sg=be.html+bj.html;
    if(!bySig.has(sg)){const o={html:sg,ids:be.ids.concat(bj.ids),parts:[],key:k,d,v,lin};bySig.set(sg,o);groups.push(o);}
    bySig.get(sg).parts.push({d,v,lin,lab,n});
  }
  const otherHtml=others&&others.length?'<div class="small">其他名稱相近的社區：'+others.map(o=>'<button type="button" class="btn sm ghost commBtn" data-n="'+esc(o.n)+'">'+esc(o.n)+'</button>').join(' ')+'</div>':'';
  const head='<div class="ans-addr">'+esc(c.n)+'<span class="o">（'+esc(name+c.d)+'）</span></div><div class="small">社區門牌：'+esc(c.t)+'</div>';
  const vl=ps=>{const by={};for(const p of ps)(by[p.v]=by[p.v]||[]).push(p.lin);return Object.entries(by).map(([v,ls])=>v+[...new Set(ls)].sort((a,b)=>a-b).join('、')+'鄰').join('；');};
  let h='<div class="res">'+head;
  if(groups.length===1){
    const G=groups[0];
    h+='<div class="ans-top"><div class="ans-vl">'+esc(vl(G.parts))+'</div><span class="src door">社區門牌比對</span></div>';
    h+='<div class="flag ok">此社區 '+G.parts.length+' 個里鄰的學區<b>都相同</b>。</div>'+G.html;
  }else{
    h+='<div class="flag"><b>此社區的門牌分屬 '+groups.length+' 種學區結果</b>，請依你家的門牌號碼看：</div>';
    for(const G of groups){
      const byLab=new Map();for(const p of G.parts){if(!byLab.has(p.lab))byLab.set(p.lab,[]);byLab.get(p.lab).push(p);}
      h+='<div class="commGrp"><div class="cg-lab">'+[...byLab].map(([lab,ps])=>esc(lab)+'<span class="o">（'+esc(vl(ps))+'）</span>').join('<br>')+'</div>'+G.html+'<button type="button" class="btn sm ghost cgBtn" data-q="'+esc(name+G.d+G.key)+'">用門牌「'+esc(G.key)+'」看詳細</button></div>';
    }
  }
  h+='<div class="flag">社區門牌範圍來自管委會報備資料，可能不含全部棟別；請以你家實際門牌或戶口名簿的里鄰為準。</div>'+otherHtml;
  h+='<div class="meta-src"><b>社區資料</b>：'+esc(((await comm()).src.find(x=>x.code===c.code)||{}).source||'')+'（'+esc((((await comm()).src.find(x=>x.code===c.code)||{}).updated||'').slice(0,10))+'）</div>'+sourceHtml(C);
  h+='<div class="acts"><button class="btn sm ghost" id="shareBtn">複製分享連結</button></div></div>';
  show(h);
  document.querySelectorAll('#result .cgBtn').forEach(b=>b.addEventListener('click',()=>{$('#q').value=b.dataset.q;run(b.dataset.q,c.code);}));
  document.querySelectorAll('#result .commBtn').forEach(b=>b.addEventListener('click',()=>{$('#q').value=b.dataset.n;run(b.dataset.n,null);}));
  const u=location.origin+location.pathname+'#q='+encodeURIComponent(c.n);
  $('#shareBtn').addEventListener('click',()=>{navigator.clipboard&&navigator.clipboard.writeText(u).then(()=>toast('已複製連結'),()=>toast(u));});
  history.replaceState(null,'','#q='+encodeURIComponent(c.n));
  const G=groups[0];const S=await lookupIn(c.code,G.d,G.key).catch(()=>null);const hit=S&&!S.miss?S.hits[0]:null;
  mapShow(C,{dist:G.d,K:G.d+'|'+G.v,hit,ids:groups.flatMap(x=>x.ids)});
}
function guessDist(C,vill){if(!C.zones)return null;const ks=Object.keys(C.zones.v).filter(k=>k.split('|')[1]===vill);return ks.length===1?ks[0].split('|')[0]:null;}
async function geoFallback(P,key,why,presetLin){
  loading(true);
  const g=await geocode((P.code&&!P.typedCode?REGBY[P.code].name:'')+P.norm);
  loading(false);
  if(!g)return show('<div class="flag bad"><b>找不到這個地址。</b>'+esc(why)+'，線上地圖也定位不到。</div>'+(P.sugHtml||'')+'<div class="flag">可以這樣試：<br>・檢查路名、門牌號碼，並加上縣市和區，例如「<b>基隆市信義區孝東路108號</b>」<br>・或輸入戶口名簿上的「區＋里＋鄰」，例如「<b>信義區孝深里24鄰</b>」<br>・或輸入社區名稱，例如「<b>微笑台北</b>」（目前限基隆市）</div>'+officialLinks(P.code));
  const code=await countyAt(g.lat,g.lon);
  if(!code)return show('<div class="flag bad">線上定位結果不在臺灣縣市範圍內。</div>');
  if(P.code&&code!==P.code)return show('<div class="flag bad">線上定位結果落在'+esc(REGBY[code].name)+'，與輸入的'+esc(REGBY[P.code].name)+'不符，無法判定。請確認地址。</div>');
  // 定位後若知道區，再試一次門牌（使用者未寫區時）
  const C0=await loadCounty(code);C0._needPip=true;const C=await loadVill(C0);
  const vp=villAt(C,g.lat,g.lon);
  if(vp&&key&&REGBY[code].addr){const L=await lookup(code,vp.t,key);if(L.found&&L.found.length){const f=L.found[0];const h=f.hits[0];return answer(C,{dist:f.dist,vill:h.vill,lin:h.lin,how:'door',hit:h,lk:f,P});}}
  if(!vp)return show('<div class="flag bad">定位點不在任何村里界內，無法判定。</div>');
  return answer(C,{dist:vp.t,vill:vp.v,lin:presetLin!=null?presetLin:P.lin,how:'geo',geo:g,why,P});
}

/* ---------- 學區計算 ---------- */
function segsOf(C,K,l){return C.zones&&C.zones.v[K]?C.zones.v[K][l]||[]:[];}
function sig(x){return [x.s.join(','),(x.p||[]).join(','),x.m&&x.m.length?'m':'',x.f||''].join('/');}
function sName(C,id){const s=C.sBy[id];return s?s.name.replace(/^(市立|縣立|國立|私立)/,''):id;}
function gName(C,x,id){if(x.f!=='g'||!x.g)return sName(C,id);const t=['男','女'].filter(k=>(x.g[k]||[]).includes(id));return sName(C,id)+(t.length===1?'（'+t[0]+'生）':'');}
function ML(C){const m=C.zones&&C.zones.meta;return m&&m.multi_label||(m&&m.auto_parsed?'自由學區':'共同學區');}
function linTxt(a,b,L){if(a===1&&b>=999)return '全里';if(b>=999)return '第'+a+'鄰起';return a===b?'第'+a+'鄰':'第'+a+'–'+b+'鄰';}
function maxLin(C,K){let m=0;for(const l of ['e','j'])for(const x of segsOf(C,K,l))if(x.b<999)m=Math.max(m,x.b);const vb=C.villBy&&C.villBy[K];return Math.max(m,vb&&vb.L||0)||30;}
function sfHtml(C,ids){const F=C.zones&&C.zones.sf;if(!F)return '';const out=[];for(const id of ids)for(const f of (F[id]||[]))out.push('<span class="badge b-warn">'+esc(sName(C,id))+'・'+esc(f)+'</span>');return out.length?'<div class="o">'+out.join(' ')+'</div>':'';}
function notesHtml(C,ids){const Nn=C.zones&&C.zones.school_notes;if(!Nn)return '';return ids.filter(id=>Nn[id]).map(id=>'<div class="o"><b>'+esc(sName(C,id))+' 備註</b>：'+esc(Nn[id])+'</div>').join('');}
function lvBlock(C,K,l,lin){
  const segs=segsOf(C,K,l);
  if(!segs.length)return {html:'<div class="lvans"><div class="k">'+LVN[l]+'</div><div class="v"><span class="alt">表列未涵蓋此里</span></div></div>',need:false,ids:[]};
  let use=segs;
  if(lin!=null){use=segs.filter(x=>lin>=x.a&&lin<=x.b);if(!use.length)return {html:'<div class="lvans"><div class="k">'+LVN[l]+'</div><div class="v"><span class="alt">第'+lin+'鄰不在表列範圍</span></div><div class="o">'+rangesHtml(C,K,l)+'</div></div>',need:false,ids:[]};}
  const sigs=new Set(use.map(sig));
  if(sigs.size>1)return {html:'<div class="lvans"><div class="k">'+LVN[l]+'</div><div class="v"><span class="alt">依鄰別而不同</span></div><div class="o">'+rangesHtml(C,K,l)+'</div></div>',need:true,ids:[]};
  const x=use[0];const ids=x.s.slice();const pids=(x.p||[]).filter(id=>!ids.includes(id));
  let v=ids.map(id=>esc(gName(C,x,id))).join('<span class="alt">　或　</span>')||'<span class="alt">（僅列條件式學校）</span>';
  if(ids.length>1&&x.f!=='g')v+='<span class="cond">'+(x.f==='bm'?'皆列基本學區，依備註分配':esc(ML(C))+'：可擇一')+'</span>';
  if(x.f==='g')v+='<span class="cond">依性別分校</span>';
  if(pids.length)v+='<span class="cond">另可能：'+pids.map(id=>esc(sName(C,id))).join('、')+'（依條件，請看原文）</span>';
  if(x.m&&x.m.length)v+='<span class="cond">依門牌或條件分屬，請看原文</span>';
  const raw=(x.t||[]).length?'<details class="raw o"><summary>官方原文</summary><div class="o">'+x.t.map(esc).join('<br>')+'</div></details>':'';
  return {html:'<div class="lvans"><div class="k">'+LVN[l]+'</div><div class="v">'+v+'</div>'+(sfHtml(C,ids.concat(pids))||'')+(notesHtml(C,ids)?'<div class="o">'+notesHtml(C,ids)+'</div>':'')+(raw?'<div class="o">'+raw+'</div>':'')+'</div>',need:false,ids:ids.concat(pids)};
}
function rangesHtml(C,K,l){const L=maxLin(C,K);return '<div class="ranges">'+segsOf(C,K,l).map(x=>'<div><b>'+linTxt(x.a,x.b,L)+'</b>：'+x.s.map(id=>esc(gName(C,x,id))).join(' ／ ')+((x.p||[]).length?' <span class="o">（另可能 '+x.p.map(id=>esc(sName(C,id))).join('、')+'）</span>':'')+'</div>').join('')+'</div>';}
function crossHtml(C,K){if(!C.cross||!C.cross.v[K])return '';const c=C.cross.v[K];let h='<div class="flag"><b>跨縣市資訊</b>：'+esc(C.cross.meta.title)+'<br>';for(const l in c)for(const x of c[l])h+=linTxt(x.a,x.b)+'：'+x.s.map(id=>esc((C.crossS[id]||{}).name||id)).join(' ／ ')+'（'+LVN[l]+'）<br>';return h+'</div>';}
function officialLinks(code){if(!code)return '';const r=REGBY[code];const u=r.officialNotice||r.official;return u?'<div class="small" style="margin-top:6px"><a href="'+esc(u)+'" target="_blank" rel="noopener">'+esc(r.name)+' 官方學區公告</a></div>':'';}

/* ---------- 答案卡 ---------- */
async function answer(C,A){
  last={C,A};
  const r=C.reg;const Z=C.zones;
  let K=A.dist?A.dist+'|'+A.vill:null;
  const flags=[];
  // 里名對不到：試標準化、舊名
  if(Z&&K&&!Z.v[K]){
    const alt=Object.keys(Z.v).find(k=>k.split('|')[0]===A.dist&&N.canon(k.split('|')[1])===N.canon(A.vill));
    if(alt)K=alt;
    else if(Z.meta.old2new&&Z.meta.old2new[K]){flags.push('「'+A.vill+'」已於 115.7.1 調整為 '+Z.meta.old2new[K].map(k=>k.split('|')[1]).join('、')+'，請以新里名與新鄰別查詢（見戶口名簿）。');}
    else flags.push('學區表中找不到「'+A.dist+A.vill+'」。里名可能已調整或門牌資料用字不同，請以戶口名簿核對並看官方公告。');
  }
  if(!A.dist&&A.vill)flags.push('同名的里不只一個，請在里名前加上區名。');
  const lin=A.lin!=null?A.lin:null;
  // 旗標
  if(A.hit&&A.hit.orig)flags.push('門牌資料原寫「'+esc(A.hit.orig)+'」，已依座標判定為「'+esc(A.vill)+'」，請以戶口名簿核對。');
  if(Z&&Z.meta.renamed&&K&&Z.meta.renamed[K])flags.push('此里為 '+esc(Z.meta.renamed[K])+'，學區表仍使用調整前里名，鄰別已重編；'+(A.how==='geo'?'線上定位無法判定新鄰別，':'')+'請以戶口名簿之新里鄰並核對官方公告。');
  if(A.lk&&A.lk.note)flags.push(A.lk.note+'，里鄰可能不同，請核對門牌。');
  if(A.how==='door'&&A.userVill&&A.userVill!==A.vill)flags.push('你輸入的是「'+esc(A.userVill)+'」，門牌資料為「'+esc(A.vill)+'」，以門牌資料為準。');
  if(A.how==='door'&&A.userLin!=null&&A.userLin!==A.lin)flags.push('你輸入第'+A.userLin+'鄰，門牌資料為第'+A.lin+'鄰，以門牌資料為準。');
  if(A.P&&A.P.roadOnlyNote)flags.push(esc(A.P.roadOnlyNote)+'若不是這裡，請加上縣市和區再查。');
  if(A.P&&A.P.override)flags.push('地址寫的是'+esc(REGBY[A.P.override].name)+'，但已依你選的縣市「'+esc(r.name)+'」查詢。');
  if(r.status==='partial')flags.push('<b>部分收錄</b>：'+esc(r.partialNote||'本縣市只收錄部分學校或部分鄉鎮。')+' <a href="'+esc(r.officialNotice||r.official||'')+'" target="_blank" rel="noopener">看官方公告</a>');
  if((r.incomplete||[]).includes(A.dist))flags.push('<b>'+esc(A.dist)+'資料不完整</b>（整理時原表未全部收錄），請以 <a href="'+esc(r.officialNotice||r.official)+'" target="_blank" rel="noopener">官方公告</a> 核對。');
  if(r.warning)flags.push(esc(r.warning));
  // 主答案
  let body='';let need=false;
  if(!Z){body='<div class="flag bad">'+esc(r.name)+'尚未收錄官方學區資料，無法判定學區。'+officialLinks(C.code)+'</div>';}
  else if(K){
    const be=lvBlock(C,K,'e',lin),bj=lvBlock(C,K,'j',lin);need=be.need||bj.need;
    body=be.html+bj.html+crossHtml(C,K);
    A.ids=be.ids.concat(bj.ids);
  }
  const vlab=A.vill?(A.vill.endsWith('村')?'村':'里'):'里';
  let linShow=lin!=null?lin+'<small>鄰</small>':(need?'<small>鄰別待確認</small>':(Z&&K?'<small>（全里同一學區，不需鄰別）</small>':''));
  const src=A.how==='door'?'<span class="src door">門牌比對・'+esc((r.addr||{}).name||'門牌資料')+'</span>'
    :A.how==='geo'?'<span class="src geo">線上定位推估（非門牌比對）</span>':'<span class="src user">依輸入之里鄰</span>';
  let h='<div class="res">';
  h+='<div class="ans-addr">'+esc(r.name+(A.dist||'')+(A.lk?A.lk.key:(A.P?A.P.rest:'')))+'</div>';
  h+='<div class="ans-top"><div class="ans-vl">'+esc(A.vill||'')+(lin!=null||need?' ':'')+linShow+'</div>'+src+'</div>';
  if(A.how==='geo')h+='<div class="flag">'+esc(A.why)+'，改用 ArcGIS 線上定位（'+esc(A.geo.match||'')+'，分數 '+Math.round(A.geo.score)+'）＋內政部村里界推估里別。<b>此方式無法判定鄰別</b>，落點靠近里界時可能誤判。</div>';
  if(need){
    // 依各級學區分界組出鄰別區間按鈕，另可直接輸入鄰
    const cut=new Set([1]);for(const l of ['e','j'])for(const x of segsOf(C,K,l)){cut.add(x.a);if(x.b<999)cut.add(x.b+1);}
    const cs=[...cut].sort((a,b)=>a-b);let bt='';
    for(let i=0;i<cs.length;i++){const a=cs[i],b=i+1<cs.length?cs[i+1]-1:999;bt+='<button type="button" class="btn sm ghost linBtn" data-n="'+a+'">'+(b>=999?'第'+a+'鄰以後':a===b?'第'+a+'鄰':'第'+a+'–'+b+'鄰')+'</button> ';}
    h+='<div class="needlin"><b>這個里依鄰別分屬不同學校</b>，請選鄰別（見戶口名簿或門牌上的「鄰」）：<div class="row">'+bt+'</div><div class="row"><input id="linIn" type="number" min="1" max="999" inputmode="numeric" placeholder="或輸入鄰" style="width:7em"> <button type="button" class="btn sm" id="linGo">查詢</button></div></div>';
  }
  h+=body;
  for(const f of flags)h+='<div class="flag">'+f+'</div>';
  if(A.P&&A.P.extraHtml)h+=A.P.extraHtml;
  h+=sourceHtml(C);
  h+='<div class="acts"><button class="btn sm ghost" id="shareBtn">複製分享連結</button></div></div>';
  show(h);
  document.querySelectorAll('.linBtn').forEach(b=>b.addEventListener('click',()=>answer(C,Object.assign({},A,{lin:+b.dataset.n}))));
  const li=$('#linIn'),lg=$('#linGo');if(lg)lg.addEventListener('click',()=>{const n=parseInt(li.value,10);if(n>0)answer(C,Object.assign({},A,{lin:n}));});
  $('#shareBtn').addEventListener('click',()=>{const u=location.origin+location.pathname+'#q='+encodeURIComponent(A.P?A.P.raw:'')+(C.code?'&c='+C.code:'')+(lin!=null&&A.how!=='door'?'&n='+lin:'');navigator.clipboard&&navigator.clipboard.writeText(u).then(()=>toast('已複製連結'),()=>toast(u));});
  history.replaceState(null,'','#q='+encodeURIComponent(A.P?A.P.raw:'')+'&c='+C.code);
  A.K=K;mapShow(C,A);
}
function sourceHtml(C){
  const r=C.reg;const m=(C.zones&&C.zones.meta)||{};
  let h='<div class="meta-src"><b>學區資料</b>：'+esc(m.title||r.source||'')+(r.years?'（'+esc(r.years)+'學年度）':'')+'・<span class="badge st-'+r.status+'">'+STN[r.status]+'</span>';
  if(r.official)h+='<br><a href="'+esc(r.officialNotice||r.official)+'" target="_blank" rel="noopener">官方公告</a>'+(m.publisher?'（'+esc(m.publisher)+'）':'');
  if(r.origin==='codex')h+='<br>由 Codex 自官方公告整理'+(r.updated?'，'+esc(r.updated)+' 更新':'')+'；本站轉換格式，未逐列人工核對。';
  if(r.addr)h+='<br><b>門牌資料</b>：'+esc(r.addr.name)+(r.addr.version?'（版本 '+esc(r.addr.version)+'）':'')+(r.addr.url?' <a href="'+esc(r.addr.url)+'" target="_blank" rel="noopener">來源</a>':'');
  return h+'<br>政府資料開放授權條款－第1版</div>';
}
function choose(msg,opts){
  show('<div class="flag">'+esc(msg)+'</div><div class="choices"></div>');
  const box=$('#result .choices');for(const [lab,fn] of opts){const b=document.createElement('button');b.className='btn sm'+(lab.startsWith('建議：')?' ghost':'');b.textContent=lab;b.addEventListener('click',fn);box.appendChild(b);}
}
function show(h){const r=$('#result');r.innerHTML=h;r.querySelectorAll('.sugBtn').forEach(b=>b.addEventListener('click',()=>{$('#q').value=b.dataset.q;run(b.dataset.q,null);}));r.classList.remove('hidden');$('#emptyCard').classList.add('hidden');if(innerWidth<=820)r.scrollIntoView({block:'start',behavior:'smooth'});}
function toast(t){const e=$('#toast');e.textContent=t;e.classList.add('on');setTimeout(()=>e.classList.remove('on'),2200);}

/* ---------- 收錄表 ---------- */
function covTable(){
  const tb=$('#covTable tbody');let h='';
  for(const r of REG.counties){
    const zs=r.hasZones?(r.years||'')+'學年度・'+r.zoneVillages+'/'+r.villages+' 里':'—';
    const ad=r.addr?(r.addr.keys||0).toLocaleString()+' 筆':'<span class="o">無（改用線上定位）</span>';
    let note=r.origin==='codex'?'Codex 整理'+(r.updated?'（'+esc(r.updated)+'）':''):(r.origin==='ours'?'本站核對':'');
    if(r.incomplete&&r.incomplete.length)note+='；不完整：'+r.incomplete.map(esc).join('、');
    if(r.partialNote)note+='；'+esc(r.partialNote);
    if(r.warning)note+='；'+esc(r.warning);
    h+='<tr><td>'+esc(r.name)+'</td><td><span class="badge st-'+r.status+'">'+STN[r.status]+'</span> '+zs+'</td><td>'+ad+'</td><td>'+note+(r.officialNotice||r.official?' <a href="'+esc(r.officialNotice||r.official)+'" target="_blank" rel="noopener">官方</a>':'')+'</td></tr>';
  }
  tb.innerHTML=h;$('#covBuilt').textContent='資料建置：'+REG.built+'；Codex 資料檢查日：'+REG.codexCheckedAt;
}

/* ---------- 地圖（看得到才載入） ---------- */
function lazyMap(){
  const el=$('#mapwrap');
  const go=()=>{if(map)return;initMap();};
  if('IntersectionObserver' in window){const io=new IntersectionObserver(es=>{if(es.some(e=>e.isIntersecting)){io.disconnect();go();}},{rootMargin:'100px'});io.observe(el);}else go();
}
async function initMap(){
  map=L.map('map',{zoomControl:true}).setView([23.7,120.95],7);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap 貢獻者'}).addTo(map);
  pinLayer=L.layerGroup().addTo(map);
  const G=await counties(true);
  const col={verified:'#1b7f4b',merged:'#1f5fbf',partial:'#d68a00',none:'#9e9e9e'};
  ctyLayer=L.geoJSON(G,{style:f=>{const r=REGBY[f.properties.code];return {color:'#10243D',weight:1,fillColor:col[r.status],fillOpacity:.22};},onEachFeature:(f,l)=>{const r=REGBY[f.properties.code];l.bindTooltip(r.name+'：'+STN[r.status],{sticky:true});}}).addTo(map);
  legend();
  if(pending){const p=pending;pending=null;mapShow(p.C,p.A);}
}
let pending=null;
async function mapShow(C,A){
  if(!map){pending={C,A};return;}
  cur=C;await loadVill(C);drawCounty(false);
  pinLayer.clearLayers();
  const vf=C.vill.features.find(f=>f.properties.t===A.dist&&f.properties.v===(A.K||'').split('|')[1]);
  if(A.hit&&A.hit.lat)L.marker([A.hit.lat,A.hit.lng]).addTo(pinLayer).bindTooltip('門牌位置');
  else if(A.geo)L.marker([A.geo.lat,A.geo.lon]).addTo(pinLayer).bindTooltip('線上定位位置');
  for(const id of (A.ids||[])){const s=C.sBy[id];if(s&&s.lat!=null)L.circleMarker([s.lat,s.lon],{radius:8,color:'#fff',weight:2,fillColor:'#F36B21',fillOpacity:1}).addTo(pinLayer).bindTooltip(sName(C,id),{permanent:true,direction:'top',offset:[0,-6]});}
  if(vf){const g=L.geoJSON(vf,{style:{color:'#F36B21',weight:3,fill:false}}).addTo(pinLayer);const b=g.getBounds();for(const l of pinLayer.getLayers())if(l.getLatLng)b.extend(l.getLatLng());map.fitBounds(b,{padding:[30,30],maxZoom:16});}
  else if(A.geo)map.setView([A.geo.lat,A.geo.lon],15);
}
const PAL=['#4c8fd6','#e07b39','#3aa676','#b0558f','#c9a227','#5b6bd6','#d65b5b','#2f9fb3','#8a6d3b','#7a9e2f','#a05cc8','#c0712f'];
function hashStr(s){let h=0;for(const c of s)h=(h*31+c.codePointAt(0))>>>0;return h;}
function sColor(id){return PAL[hashStr(id)%PAL.length];}
function drawCounty(){
  const C=cur;if(villLayer)map.removeLayer(villLayer);if(schLayer)map.removeLayer(schLayer);
  villLayer=L.geoJSON(C.vill,{style:f=>{const p=f.properties;if(!p.v||!C.zones)return {color:'#888',weight:.6,fillOpacity:.05};const s=segsOf(C,p.t+'|'+p.v,lv);if(!s.length)return {color:'#b3261e',weight:1,fillColor:'#fff',fillOpacity:.1,dashArray:'2 3'};const sigs=new Set(s.map(sig));if(sigs.size>1||s[0].s.length>1)return {color:'#8a4b00',weight:1,dashArray:'4 3',fillColor:'#d68a00',fillOpacity:.25};return {color:'#fff',weight:1,fillColor:sColor(s[0].s[0]),fillOpacity:.4};},
    onEachFeature:(f,l)=>{const p=f.properties;if(p.v)l.bindTooltip(p.t+p.v,{sticky:true});}}).addTo(map);
  villLayer.bringToBack();
  schLayer=L.layerGroup();for(const s of C.schools){if(s.lat==null||s.lv!==lv)continue;schLayer.addLayer(L.circleMarker([s.lat,s.lon],{radius:4,color:'#fff',weight:1,fillColor:lv==='e'?'#1f5fbf':'#c0392b',fillOpacity:.9}).bindTooltip(s.name.replace(/^(市立|縣立)/,'')));}
  schLayer.addTo(map);if(ctyLayer)ctyLayer.setStyle({fillOpacity:.04});
  legend();
}
function legend(){
  const el=$('#legend');
  if(!cur||!cur.vill){el.innerHTML='<b>收錄狀態</b><br><span class="sw" style="background:#1b7f4b;opacity:.6"></span>本站核對<br><span class="sw" style="background:#1f5fbf;opacity:.6"></span>整理資料<br><span class="sw" style="background:#d68a00;opacity:.6"></span>部分收錄<br><span class="sw" style="background:#9e9e9e;opacity:.6"></span>未收錄';return;}
  el.innerHTML='<b>'+esc(cur.reg.name)+' '+LVN[lv]+'學區</b><br><span class="sw" style="background:#4c8fd6"></span>全里同一學區<br><span class="sw" style="background:#d68a00;opacity:.6"></span>依鄰分屬或'+esc(ML(cur))+'<br><span class="sw" style="border:1px dashed #b3261e"></span>表列未涵蓋<br><span class="sw" style="background:#F36B21;border-radius:50%"></span>查詢結果學校';
}

window.TSMB={run,parse:q=>parse(q,null),stats:()=>window.__betaStats,ready:null};
window.TSMB.ready=boot().catch(e=>{console.error(e);show('<div class="flag bad">資料載入失敗：'+esc(e.message)+'</div>');});
})();
