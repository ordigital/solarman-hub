'use strict';
window.DevicesUI={render(status,profiles){
  const root=document.getElementById('device-cards');if(!root)return;root.replaceChildren();
  const {t}=I18n;
  function node(tag,text,cls){const value=document.createElement(tag);value.textContent=text;if(cls)value.className=cls;return value;}
  for(const logger of status.loggers){
    const card=node('article','','card');card.append(node('h3',logger.name));
    const table=node('dl','','device-details');
    const names={logger_serial:'Logger serial number',peer_ip:'Observed peer IP',logger_firmware:'Logger firmware',inverter_serial:'Inverter serial number'};
    for(const [key,label]of Object.entries(names)){
      table.append(node('dt',t(label)));
      const value=logger.identity?.[key],description=node('dd',value?value.value:t('Not observed'));
      if(value)description.append(node('small',value.source+' · '+new Date(value.observed_at*1000).toLocaleString(I18n.locale),'muted'));
      table.append(description);
    }
    const profile=profiles.find(item=>item.id===logger.profile);
    table.append(node('dt',t('Configured manufacturer / model')),node('dd',profile?[profile.manufacturer,profile.model].filter(Boolean).join(' / '):'—'));
    table.append(node('dt',t('Protocol')),node('dd','Solarman V5 / TCP'));
    table.append(node('dt',t('Observed frame formats')),node('dd',Object.entries(logger.frame_types||{}).map(([format,count])=>format+' × '+count).join(', ')||t('Not observed')));
    card.append(table,node('p',t('Configured model is a profile declaration, not an automatic hardware identification.'),'hint'));root.append(card);
  }
  if(!status.loggers.length)root.append(node('p',t('Add your first logger in Configuration.'),'empty-note'));
}};
