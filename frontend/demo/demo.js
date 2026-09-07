import './home-digital-card.js';
customElements.define('ha-card',class extends HTMLElement{constructor(){super();this.attachShadow({mode:'open'}).innerHTML='<style>:host{display:block;background:var(--ha-card-background,#fff);border:1px solid #e1e7de;border-radius:18px;overflow:hidden}h2{font:500 18px system-ui;padding:18px;margin:0}</style><h2 hidden></h2><slot></slot>';}set header(v){this.shadowRoot.querySelector('h2').textContent=v;this.shadowRoot.querySelector('h2').hidden=!v;}});
const state=(id,value,attributes={})=>({entity_id:id,state:value,attributes,last_changed:new Date().toISOString(),last_updated:new Date().toISOString()});
const hass={connected:true,states:{},config:{time_zone:'Asia/Shanghai',unit_system:{temperature:'°C'},version:'2026.9.1'},locale:{language:'zh-Hans',number_format:'language',time_format:'24',date_format:'language'},themes:{darkMode:false,themes:{}},language:'zh-Hans',localize:x=>x,connection:{subscribeMessage:async()=>()=>{}},callApi:async()=>[],callWS:async()=>[]};
const values={'light.demo_living':'on','media_player.demo_tv':'on','vacuum.demo_robot':'docked','climate.demo_vrf':'cool','light.demo_bedroom':'off','cover.demo_curtain':'open','switch.demo_supply':'on'};
for(const [id,value]of Object.entries(values))hass.states[id]=state(id,value,{current_temperature:24,current_position:65,supported_features:0,brightness:180,source:'HDMI 1',volume_level:.2});
const card=document.querySelector('home-digital-card');card.setConfig({asset_base:'.',version:'demo-v1',demo:true});card.hass=hass;
hass.callService=async(domain,action,{entity_id})=>{const old=hass.states[entity_id];if(!old)return;hass.states={...hass.states,[entity_id]:{...old,state:action==='turn_on'?'on':action==='turn_off'?'off':old.state}};card.hass=hass;};
card.addEventListener('hass-more-info',()=>alert('演示详情：真实使用时由 Home Assistant 打开对应设备控制面板。'));
let loaded=false;
document.querySelector('#show-home').onclick=()=>show('home');
document.querySelector('#show-energy').onclick=async()=>{show('energy');if(loaded)return;loaded=true;
 try{
  await import('./apexcharts-card.js');await import('./flex-table-card.js');
  const view=(await(await fetch('electricity.json')).json()).views[0];
  const daily=Array.from({length:31},(_,i)=>{const d=new Date();d.setDate(d.getDate()-31+i);return{date:d.toISOString().slice(0,10),total_usage:+(12+Math.sin(i*.83)*6+i%4).toFixed(2),valley_usage:+(4+Math.cos(i)*2).toFixed(2),flat_usage:+((12+Math.sin(i*.83)*6+i%4)-(4+Math.cos(i)*2)).toFixed(2)}});
  const year=new Date().getFullYear();const months=Array.from({length:8},(_,i)=>({month:`${year}-${String(i+1).padStart(2,'0')}`,total_usage:210+i*18+(i%3)*22,total_charge:105+i*9+(i%3)*11}));
  hass.states['sensor.sgcc_status']=state('sensor.sgcc_status','ok',{daily,months});
  document.querySelector('#metrics').innerHTML=[['最近日用电',daily.at(-1).total_usage+' 度'],['最近月账单',months.at(-1).total_charge+' 元'],['示例累计电量',months.reduce((sum,m)=>sum+m.total_usage,0).toLocaleString()+' 度'],['数据粒度','日 / 月']].map(([a,b])=>`<div class="metric"><label>${a}</label><strong>${b}</strong></div>`).join('');
  for(const section of view.sections.slice(1,3)){const col=document.createElement('div');col.className='column';document.querySelector('.columns').append(col);for(const config of section.cards){const el=document.createElement(config.type.replace('custom:',''));el.setConfig(config);el.hass=hass;col.append(el)}}
 }catch(e){document.querySelector('.columns').textContent='先执行 npm run demo:assets，并生成 electricity.json。'+e.message;loaded=false;}
};
function show(id){for(const name of ['home','energy']){document.querySelector('#'+name).hidden=name!==id;document.querySelector('#show-'+name).setAttribute('aria-pressed',String(name===id));}window.dispatchEvent(new Event('resize'));}
