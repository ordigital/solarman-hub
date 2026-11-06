'use strict';
window.HistoryUI = (() => {
  let context, samples=[],nextBefore=null, selected=null, request=0, chart=null, chartRequest=0, series=[];
  const $=id=>document.getElementById(id);
  const {t}=I18n;
  function element(tag,text){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;}
  function bounds(prefix){
    const duration=Number($(prefix+'-range').value);
    const end=duration?Date.now()/1000:new Date($(prefix+'-to').value).getTime()/1000;
    const start=duration?end-duration:new Date($(prefix+'-from').value).getTime()/1000;
    if(!Number.isFinite(start)||!Number.isFinite(end)||end<start)throw Error(t('Choose a valid time range.'));
    return {from:start,to:end};
  }
  function custom(prefix){$(prefix+'-custom').hidden=$(prefix+'-range').value!=='0';}
  function localInput(time){const value=new Date(time);return new Date(value.getTime()-value.getTimezoneOffset()*60000).toISOString().slice(0,16);}
  function sample(){return $('data-mode').value==='history'?selected:context.latest();}
  function current(){return $('data-mode').value==='history';}
  async function load(append=false){
    if(!current())return;
    const serial=context.serial();if(!serial)return;
    const identifier=++request;
    $('history-state').textContent=t('Loading history…');
    try{
      const params=new URLSearchParams({...bounds('history'),limit:50});
      if(append&&nextBefore)params.set('before',nextBefore);
      const result=await context.api('history/'+serial+'?'+params);
      if(identifier!==request||serial!==context.serial())return;
      samples=append?[...samples,...result.samples]:result.samples;nextBefore=result.next_before;
      const previous=append?selected?.history_id:null;
      selected=samples.find(item=>item.history_id===previous)||samples[0]||null;
      render();context.render();
    }catch(error){if(identifier===request)$('history-state').textContent=error.message;}
  }
  function render(){
    $('history-controls').hidden=!current();
    $('history-sample').replaceChildren(...samples.map(item=>new Option(context.date(item.sample_time||item.received_at)+' · '+item.profile,item.history_id)));
    if(selected)$('history-sample').value=selected.history_id;
    $('history-older').disabled=!nextBefore;
    $('history-state').textContent=samples.length?t('Loaded samples: {count}',{count:samples.length}):t('No history in this range.');
  }
  function changed(){request++;samples=[];selected=null;nextBefore=null;render();if(current())load();}
  function svg(tag,attributes,text){const node=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [key,value]of Object.entries(attributes))node.setAttribute(key,value);if(text!==undefined)node.textContent=text;return node;}
  function draw(result){
    series=result.points;$('chart-title').textContent=result.name+(result.unit?' · '+result.unit:'');
    $('chart-note').textContent=result.truncated?t('Query limit reached. Choose a shorter range.'):t('Source profile: {profile} · revision: {revision}',{profile:result.profile,revision:result.profile_revision});
    const root=$('chart-svg');root.replaceChildren();
    $('chart-point').disabled=!series.length;$('chart-point').max=Math.max(0,series.length-1);$('chart-point').value=0;
    if(!series.length){$('chart-hover').textContent=t('No history in this range.');return;}
    const minimum=Math.min(...series.map(point=>point.value)),maximum=Math.max(...series.map(point=>point.value));
    const pad=(maximum-minimum)*.08||Math.max(Math.abs(maximum)*.05,1);
    const low=minimum-pad,high=maximum+pad;
    chart.scale={x:time=>70+(time-result.from)/Math.max(1,result.to-result.from)*880,y:value=>260-(value-low)/(high-low)*230};
    for(let i=0;i<5;i++){
      const value=low+(high-low)*i/4,y=chart.scale.y(value);
      root.append(svg('line',{x1:70,x2:950,y1:y,y2:y,class:'chart-grid'}),svg('text',{x:62,y:y+4,'text-anchor':'end',class:'chart-label'},new Intl.NumberFormat(I18n.locale,{maximumFractionDigits:2,notation:'compact'}).format(value)));
      const time=result.from+(result.to-result.from)*i/4;
      root.append(svg('text',{x:chart.scale.x(time),y:295,'text-anchor':'middle',class:'chart-label'},new Date(time*1000).toLocaleString(I18n.locale,{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'})));
    }
    let path='',segment=null;
    for(const point of series){path+=(segment===point.segment?'L':'M')+chart.scale.x(point.time)+' '+chart.scale.y(point.value)+' ';segment=point.segment;}
    root.append(svg('path',{d:path,class:'chart-line'}),svg('line',{id:'chart-crosshair',x1:0,x2:0,y1:25,y2:260,class:'chart-crosshair'}),svg('circle',{id:'chart-marker',r:5,class:'chart-marker'}));
    showPoint(0);
  }
  function showPoint(index){
    const point=series[index];if(!point||!chart?.scale)return;
    const x=chart.scale.x(point.time),y=chart.scale.y(point.value);
    $('chart-crosshair').setAttribute('x1',x);$('chart-crosshair').setAttribute('x2',x);
    $('chart-marker').setAttribute('cx',x);$('chart-marker').setAttribute('cy',y);
    $('chart-point').value=index;
    $('chart-hover').textContent=context.date(point.time)+' · '+new Intl.NumberFormat(I18n.locale,{maximumFractionDigits:6}).format(point.value)+' '+(chart.unit||'');
  }
  async function loadChart(){
    if(!chart)return;
    const identifier=++chartRequest, selection=chart;
    series=[];chart.scale=null;
    $('chart-svg').replaceChildren();$('chart-point').disabled=true;
    $('chart-hover').textContent=t('Loading history…');
    try{
      const result=await context.api('history/'+chart.serial+'/series?'+new URLSearchParams({...bounds('chart'),field:chart.field,profile:chart.profile,revision:chart.revision,points:600}));
      if(identifier!==chartRequest||selection!==chart||!$('chart-dialog').open)return;
      chart.unit=result.unit;draw(result);
    }catch(error){if(identifier===chartRequest&&selection===chart)$('chart-hover').textContent=error.message;}
  }
  async function open(field){
    const data=sample();if(!data)return;
    chart={serial:context.serial(),field,profile:data.profile,revision:data.profile_revision};
    $('chart-title').textContent=data.values[field].name;
    $('chart-range').value=$('history-range').value;custom('chart');
    $('chart-from').value=$('history-from').value;$('chart-to').value=$('history-to').value;
    $('chart-dialog').showModal();await loadChart();
  }
  function init(options){
    context=options;
    for(const prefix of ['history','chart']){
      $(prefix+'-from').value=localInput(Date.now()-86400000);$(prefix+'-to').value=localInput(Date.now());
      $(prefix+'-range').onchange=()=>{custom(prefix);if($(prefix+'-range').value!=='0')(prefix==='history'?load():loadChart());};
    }
    $('data-mode').onchange=()=>{render();context.render();if(current())load();};
    $('history-load').onclick=()=>load();$('history-older').onclick=()=>load(true);
    $('history-sample').onchange=()=>{selected=samples.find(item=>String(item.history_id)===$('history-sample').value);context.render();};
    $('chart-load').onclick=loadChart;$('chart-close').onclick=()=>$('chart-dialog').close();
    $('chart-dialog').addEventListener('close',()=>{chart=null;chartRequest++;series=[];});
    $('chart-point').oninput=()=>showPoint(Number($('chart-point').value));
    $('chart-svg').onpointermove=event=>{
      if(!series.length||!chart?.scale)return;
      const rect=$('chart-svg').getBoundingClientRect(),x=(event.clientX-rect.left)/rect.width*1000;
      let best=0,distance=Infinity;
      series.forEach((point,index)=>{const current=Math.abs(chart.scale.x(point.time)-x);if(current<distance){distance=current;best=index;}});showPoint(best);
    };
    window.addEventListener('hub-language-change',()=>{render();if(chart&&$('chart-dialog').open)loadChart();});
  }
  return {init,sample,current,changed,open};
})();
