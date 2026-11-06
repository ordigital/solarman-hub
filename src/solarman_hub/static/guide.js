'use strict';
window.GuideUI=(()=>{
  let chapter='hub',observer=null,request=0;
  async function load(api){
    const current=++request;
    const guide=await api('docs?lang='+I18n.language);
    if(current!==request)return;
    observer?.disconnect();
    document.getElementById('manual').innerHTML=guide.html;
    const menu=document.getElementById('guide-toc');menu.replaceChildren();
    const title=document.createElement('h3');title.textContent=I18n.t('Contents');menu.append(title);
    function active(value){chapter=value;menu.querySelectorAll('button').forEach(button=>button.classList.toggle('active',button.dataset.chapter===value));}
    for(const item of guide.toc){
      const button=document.createElement('button');button.type='button';button.className='nav-item';button.dataset.chapter=item.id;button.textContent=item.title;
      button.onclick=()=>{active(item.id);document.getElementById('guide-'+item.id).scrollIntoView({block:'start'});};menu.append(button);
    }
    active(chapter);
    observer=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting)active(entry.target.id.slice(6));},{rootMargin:'-5% 0px -75% 0px'});
    for(const item of guide.toc)observer.observe(document.getElementById('guide-'+item.id));
    if(chapter!=='hub')document.getElementById('guide-'+chapter)?.scrollIntoView({block:'start'});
  }
  let firmwareRequest=0;
  async function loadFirmware(api){
    const current=++firmwareRequest;
    const guide=await api('docs?lang='+I18n.language);
    if(current!==firmwareRequest)return;
    const documentCopy=new DOMParser().parseFromString(guide.html,'text/html');
    const content=document.createDocumentFragment();
    let include=false;
    for(const child of documentCopy.body.children){
      if(child.tagName==='H2')include=['guide-esp32','guide-ota'].includes(child.id);
      if(include){
        const copy=child.cloneNode(true);
        if(copy.id)copy.id='firmware-'+copy.id;
        content.append(copy);
      }
    }
    document.getElementById('firmware-instructions').replaceChildren(content);
  }
  return {load,loadFirmware};
})();
