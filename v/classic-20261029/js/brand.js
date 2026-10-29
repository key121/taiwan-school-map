/* CHAMPION 冠軍商仲 brand layer: hero stats from real data files, CTA scroll, reveal motion. No data is invented here. */
(function(){
  const $=s=>document.querySelector(s);
  const st=$('#heroStats');
  if(st){
    Promise.all(['../../data/registry.json','../../data/stats.json'].map(u=>fetch(u).then(r=>r.json()))).then(([R,S])=>{
      let c=0,v=0,vt=0,n=0;
      for(const r of R){const s=S[r.code]||{};vt+=s.villages||0;n+=s.n_s||0;if(r.status==='covered'){c++;v+=s.villages||0;}}
      const set=(k,h)=>{const e=st.querySelector('[data-s="'+k+'"]');if(e)e.innerHTML=h;};
      set('cty',c+'<small> / '+R.length+'</small>');
      set('vill',v.toLocaleString()+'<small> / '+vt.toLocaleString()+'</small>');
      set('sch',n.toLocaleString()+'<small> 所</small>');
    }).catch(()=>{});
  }
  const toApp=(focus)=>{const a=$('#app');if(!a)return;a.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});if(focus){const q=$('#q');if(q)setTimeout(()=>q.focus({preventScroll:true}),350);}};
  const b=$('#startBtn'); if(b) b.addEventListener('click',e=>{e.preventDefault();toApp(true);});
  // 分享連結開啟時直接捲到結果
  if(/[#&](q|v)=/.test(location.hash)) window.addEventListener('load',()=>setTimeout(()=>toApp(false),300));
  // 手機版：查詢後捲到結果卡
  const f=$('#qform'); if(f) f.addEventListener('submit',()=>{const wait=()=>{const r=$('#result');if(r&&!r.classList.contains('hidden')&&!/計算中/.test(r.innerText)){if(innerWidth<=820)r.scrollIntoView({behavior:'smooth',block:'start'});else toApp(false);}else setTimeout(wait,120);};setTimeout(wait,150);});
  // reveal
  const els=document.querySelectorAll('.reveal');
  if('IntersectionObserver' in window){const io=new IntersectionObserver(es=>es.forEach(x=>{if(x.isIntersecting){x.target.classList.add('in');io.unobserve(x.target);}}),{threshold:.08});els.forEach(e=>io.observe(e));}
  else els.forEach(e=>e.classList.add('in'));
})();
