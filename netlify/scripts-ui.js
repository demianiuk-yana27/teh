(function(){
  let activeCategory=0;
  const e=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function renderCategory(i){
    const data=window.SCRIPT_DATA||[]; const c=data[i]; if(!c)return; activeCategory=i;
    document.querySelectorAll('#scriptFolders .script-folder').forEach((x,n)=>x.classList.toggle('selected',n===i));
    const title=document.getElementById('scriptCategoryTitle'), meta=document.getElementById('scriptCategoryMeta'), cards=document.getElementById('scriptCards');
    if(title) title.textContent=c.category;
    if(meta) meta.textContent=c.items.length+' готових відповідей';
    if(cards) cards.innerHTML=c.items.map((x,n)=>`<article class="script-card"><div class="script-card-head"><span class="script-num">${String(n+1).padStart(2,'0')}</span><strong>${e(x.title)}</strong><button class="copy script-copy" data-cat="${i}" data-item="${n}">▣ Скопіювати</button></div><div class="script-text">${e(x.text).replace(/\n/g,'<br>')}</div></article>`).join('');
  }
  function init(){
    const data=window.SCRIPT_DATA||[], folders=document.getElementById('scriptFolders'), count=document.getElementById('scriptTotal');
    if(!folders)return;
    if(count) count.textContent=data.reduce((n,c)=>n+c.items.length,0);
    folders.innerHTML=data.map((c,i)=>`<button class="script-folder ${i===0?'selected':''}" data-index="${i}"><span>▱ ${e(c.category.replace(/^\d+\.\s*/,''))}</span><b>${c.items.length}</b></button>`).join('');
    folders.addEventListener('click',ev=>{const b=ev.target.closest('.script-folder');if(b)renderCategory(Number(b.dataset.index));});
    document.getElementById('scriptCards')?.addEventListener('click',ev=>{const b=ev.target.closest('.script-copy');if(!b)return;const x=data[Number(b.dataset.cat)]?.items[Number(b.dataset.item)];if(!x)return;navigator.clipboard.writeText(x.text);const old=b.textContent;b.textContent='✓ Скопійовано';setTimeout(()=>b.textContent=old,1200);});
    const search=document.getElementById('scriptSearch');
    search?.addEventListener('input',()=>{const q=search.value.toLowerCase().trim();if(!q)return renderCategory(activeCategory);const found=[];data.forEach((c,ci)=>c.items.forEach((x,ii)=>{if((x.title+' '+x.text).toLowerCase().includes(q))found.push({...x,ci,ii,category:c.category})}));document.getElementById('scriptCategoryTitle').textContent='Результати пошуку';document.getElementById('scriptCategoryMeta').textContent=found.length+' знайдено';document.getElementById('scriptCards').innerHTML=found.map((x,n)=>`<article class="script-card"><div class="script-card-head"><span class="script-num">${String(n+1).padStart(2,'0')}</span><strong>${e(x.title)}</strong><button class="copy script-copy" data-cat="${x.ci}" data-item="${x.ii}">▣ Скопіювати</button></div><div class="script-category-label">${e(x.category)}</div><div class="script-text">${e(x.text).replace(/\n/g,'<br>')}</div></article>`).join('')||'<div class="empty">Нічого не знайдено.</div>';});
    renderCategory(0);
  }
  document.addEventListener('DOMContentLoaded',init);
})();
