import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const ICON={switch:'◉',power_switch:'⏻',led_strip:'━',aircon:'❄',thermostat:'▣',sensor:'◌',motion_sensor:'◎',curtain:'▥',vacuum:'●',dock:'▤',television:'▣'};
const WORD={on:'开启',off:'关闭',open:'已打开',closed:'已关闭',opening:'正在打开',closing:'正在关闭',cool:'制冷',heat:'制热',dry:'除湿',fan_only:'送风',auto:'自动',docked:'已停靠',cleaning:'清洁中',returning:'回充中',paused:'已暂停',idle:'待机',playing:'播放中',buffering:'缓冲中',standby:'待机',unavailable:'暂不可用',unknown:'未知'};
const DOCK_NAMES={empty_dustbin:'集尘',wash_mop:'清洗拖布',dry_mop:'烘干拖布',dry_and_disinfect_dust_bin:'尘盒烘干消毒',dry_and_disinfect_dock_bag:'尘袋烘干消毒'};
const esc=(s)=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const stateText=(s)=>{if(!s)return '连接中';if(s.entity_id?.endsWith('_dock_dry_mop')&&s.state==='on')return '正在烘干拖布';let text=(WORD[s.state]??s.state)+(s.attributes?.unit_of_measurement?' '+s.attributes.unit_of_measurement:'');if(s.entity_id?.startsWith('climate.')&&typeof s.attributes?.current_temperature==='number')text+=` · ${s.attributes.current_temperature} °C`;if(s.entity_id?.startsWith('media_player.')&&!['off','standby','unavailable','unknown'].includes(s.state)){if(s.attributes?.source)text+=` · ${s.attributes.source}`;if(s.attributes?.is_volume_muted)text+=' · 已静音';else if(Number.isFinite(s.attributes?.volume_level))text+=` · 音量 ${Math.round(s.attributes.volume_level*100)}`;}return text;};
const active=s=>s&&!s.entity_id?.startsWith('sensor.')&&!(s.entity_id?.startsWith('media_player.')?['off','standby','unavailable','unknown']:['off','closed','docked','idle','unavailable','unknown']).includes(s.state);
const CSS=`
 :host{display:block;font-family:var(--primary-font-family,Inter,"Microsoft YaHei",sans-serif);color:#293c35;--green:#356956;--muted:#75837b}
 *{box-sizing:border-box}button{font:inherit;cursor:pointer}button:focus-visible{outline:3px solid #d19d47;outline-offset:3px}button:disabled{cursor:default;opacity:.45}
 ha-card{display:block;overflow:hidden;background:#f4f5ef;border:1px solid #dce2d8;border-radius:22px;box-shadow:0 4px 20px #203b2310;color:#293c35}
 .top{padding:24px 28px 14px;display:flex;align-items:flex-start;justify-content:space-between;gap:14px}.eyebrow{font-size:10px;letter-spacing:2px;color:#728378;font-weight:700;margin-bottom:7px}.title{font-size:27px;letter-spacing:1px;font-weight:600;line-height:1.4}.sub{font-size:12px;color:var(--muted);margin-top:6px;line-height:1.7}.live{display:flex;align-items:center;gap:7px;white-space:nowrap;font-size:11px;background:#e6ede2;padding:8px 11px;border-radius:18px}.live i{width:6px;height:6px;background:#5e9576;border-radius:50%}
 .rooms{display:flex;gap:7px;overflow-x:auto;padding:0 28px 16px;scrollbar-width:thin}.chip{white-space:nowrap;background:transparent;border:1px solid #d9e0d5;border-radius:16px;padding:6px 12px;color:#6a7b70;font-size:12px}.chip[aria-pressed=true]{background:var(--green);color:white;border-color:var(--green)}
 .main{display:grid;grid-template-columns:minmax(0,1fr) 245px;min-height:590px}.stage{position:relative;min-width:0;height:590px;background:radial-gradient(ellipse at 50% 48%,#eef1e6 0,#e5ecdf 85%);overflow:hidden}.stage canvas{display:block;width:100%;height:100%;touch-action:none}.labels{position:absolute;inset:0;pointer-events:none;overflow:hidden}.label{position:absolute;left:0;top:0;pointer-events:auto;white-space:nowrap;transform:translate(-50%,-50%)}
 .room-label{background:#ffffffd9;border:1px solid #ffffffe8;box-shadow:0 3px 12px #23371d0d;color:#486153;padding:5px 9px;border-radius:6px;font-size:11px;backdrop-filter:blur(5px);z-index:1}.leader-lines{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;overflow:hidden}.leader-lines line{stroke:#789078;stroke-width:1;opacity:.5}.pin{z-index:2}
 .pin{width:23px;height:23px;border-radius:50%;border:2px solid #fff;background:#859c92;color:white;padding:0;font-size:13px;box-shadow:0 2px 7px #183b252e}.pin.on{background:#be9042}.pin.selected{outline:3px solid #d8aa5c;outline-offset:3px}.pin.unavailable{background:#aab0ac}.pin:hover{z-index:9;scale:1.12}
 .tools{position:absolute;top:15px;left:15px;display:flex;gap:5px;z-index:3}.tool{border:1px solid #d2dccd;background:#f9fbf4ed;color:#486153;padding:7px 10px;border-radius:8px;font-size:11px}.tool[aria-pressed=true]{color:white;background:#4f7561;border-color:#4f7561}.hint{position:absolute;bottom:16px;left:18px;right:18px;display:flex;justify-content:space-between;gap:10px;color:#728271;font-size:10px;pointer-events:none}.loading{position:absolute;inset:0;display:grid;place-content:center;background:#e8eee2;color:#647a67;font-size:13px;z-index:5}.loading[hidden]{display:none}.loader-dot{height:5px;background:#65816e;margin-bottom:15px;border-radius:3px;animation:load 1s ease-in-out infinite alternate}@keyframes load{to{opacity:.25;transform:scaleX(.55)}}
 .side{background:#fafbf6;border-left:1px solid #e0e5da;padding:20px 17px;min-width:0;max-height:590px;overflow:auto;scrollbar-width:thin}.side-kicker{font-size:10px;letter-spacing:1.5px;color:#839183}.side-title{font-size:18px;font-weight:600;margin:10px 0 6px;line-height:1.5}.side-state{font-size:12px;color:#5c7666;margin-bottom:14px}.side-note{font-size:11px;line-height:1.8;color:#899488;margin-top:14px}.device-list{display:flex;flex-direction:column;gap:5px;margin-top:15px}.device-row{border:0;border-bottom:1px solid #e7ebdf;background:transparent;padding:10px 0;display:flex;align-items:center;text-align:left;gap:9px;color:#3e5147;width:100%}.device-row .symbol{display:grid;place-items:center;width:28px;height:28px;background:#edf0e6;border-radius:8px;font-size:14px;flex:none}.device-row .copy{min-width:0}.device-row .name{font-size:11px;line-height:1.5}.device-row .value{font-size:10px;color:#879381;margin-top:3px}.device-row.selected .symbol{background:#d8e6d3}
 .actions{display:flex;flex-wrap:wrap;gap:7px;margin-top:14px}.action{border:1px solid #d7e0d1;background:#eff3e9;color:#48644f;border-radius:8px;padding:9px 11px;font-size:12px}.action.primary{background:#356956;color:white;border-color:#356956}.action.wide{width:100%}.status-bar{padding:12px 28px;border-top:1px solid #dfe5d8;display:flex;align-items:center;gap:17px;flex-wrap:wrap;font-size:11px;color:#778674;background:#f7f9f2}.legend-dot{display:inline-block;border-radius:50%;width:6px;height:6px;background:#be9042;margin-right:5px}.legend-dot.off{background:#859c92}.foot-note{margin-left:auto;font-size:10px;color:#94a08d}.toast{position:absolute;bottom:45px;left:50%;transform:translateX(-50%);background:#294a3f;color:white;padding:9px 15px;border-radius:8px;font-size:12px;max-width:90%;z-index:7;box-shadow:0 5px 18px #233c3326}.toast[hidden]{display:none}.range{width:100%;accent-color:#527f60;margin-top:12px}.percent{font-size:12px;color:#7b8a78}.badge{display:inline-block;font-size:10px;background:#edf0e6;border-radius:4px;padding:3px 6px;color:#829079;margin-top:5px}
 @media(max-width:750px){.top{padding:18px 16px 12px}.title{font-size:22px}.eyebrow{font-size:9px}.rooms{padding:0 16px 13px}.main{grid-template-columns:1fr;min-height:0}.stage{height:360px}.side{border-left:0;border-top:1px solid #e0e5da;max-height:300px;padding:16px}.device-list{display:grid;grid-template-columns:1fr 1fr;gap:0 14px}.status-bar{padding:12px 16px;gap:10px}.foot-note{width:100%;margin-left:0}.live{font-size:10px;padding:7px 8px}.sub{font-size:11px}.room-label{font-size:10px;padding:4px 6px}.pin{width:22px;height:22px}}
 @media(prefers-reduced-motion:reduce){.loader-dot{animation:none}}
`;

export class HomeDigitalCard extends HTMLElement {
  constructor(){super();this.attachShadow({mode:'open'});this._area='all';this._selected=null;this._topView=false;this._fullHeight=false;this._labels=false;this._busy=false;this._visible=true;this._states={};this._frame=0;}
  setConfig(config){this.config={asset_base:'/local/digital-home',...config};if(this.isConnected&&!this._started)this._init();}
  getCardSize(){return 13;}
  getGridOptions(){return{columns:'full',min_columns:12,rows:'auto'};}
  set hass(hass){this._hass=hass;this._states=hass?.states??{};this._updateStates();}
  get hass(){return this._hass;}
  connectedCallback(){if(this.config&&!this._started)this._init();}
  disconnectedCallback(){this._dispose();}
  async _init(){
    this._started=true;this._generation=(this._generation??0)+1;const generation=this._generation;
    this.shadowRoot.innerHTML=`<style>${CSS}</style><ha-card><div class="top"><div><div class="eyebrow">HOME / DIGITAL TWIN</div><div class="title">家 · 立体概览</div><div class="sub">房间与设备 · 状态来自 Home Assistant</div></div><div class="live"><i></i><span class="live-text">正在连接 HA</span></div></div><nav class="rooms" aria-label="选择房间"></nav><div class="main"><div class="stage"><div class="labels"></div><div class="tools"><button class="tool" data-view="3d" aria-pressed="true">立体</button><button class="tool" data-view="top" aria-pressed="false">俯视</button><button class="tool" data-view="reset">复位</button><button class="tool" data-view="walls" aria-pressed="false">完整墙体</button><button class="tool" data-view="labels" aria-pressed="true">标记</button></div><div class="hint"><span>拖动旋转 · 滚轮 / 双指缩放</span><span>点击设备查看控制</span></div><div class="loading"><div class="loader-dot"></div><div class="loading-text">正在载入 Blender 家居模型…</div></div><div class="toast" role="status" hidden></div></div><aside class="side" aria-label="设备控制"></aside></div><div class="status-bar"><span><i class="legend-dot"></i>开启 / 活动</span><span><i class="legend-dot off"></i>关闭 / 待机</span><span class="device-count"></span><span class="foot-note">尺寸为估算 · 设备点可校准 · 无机器人实时定位</span></div></ha-card>`;
    try{
      const res=await fetch(`${this.config.asset_base}/layout.json?v=${this.config.version??1}`);if(!res.ok)throw Error(`布局加载失败 (${res.status})`);this.layout=await res.json();this._validateLayout(this.layout);
      if(!this.isConnected||generation!==this._generation)return;
      this._byEntity=new Map(this.layout.models.map(m=>[m.entity_id,m]));
      this._bindUI();this._buildScene();
      const gltf=await new GLTFLoader().loadAsync(`${this.config.asset_base}/home.glb?v=${this.config.version??1}`);
      if(!this.isConnected||generation!==this._generation){this._freeObject(gltf.scene);return;}
      this._model=gltf.scene;this._scene.add(this._model);this._entityMeshes=new Map();this._entityRoots=new Map();this._curtains=[];this._upperObjects=[];
      this._model.traverse(o=>{
        if(o.userData.cutaway_upper){o.visible=this._fullHeight;this._upperObjects.push(o);}
        if(o.userData.entity_id){if(!this._entityMeshes.has(o.userData.entity_id))this._entityMeshes.set(o.userData.entity_id,[]);if(o.isMesh)this._entityMeshes.get(o.userData.entity_id).push(o);if(o.userData.label)this._entityRoots.set(o.userData.entity_id,o);}
        if(o.userData.curtain_entity){this._curtains.push(o);o.userData.originalZScale=o.scale.z;}
        if(o.isMesh){o.castShadow=true;o.receiveShadow=true;if(o.userData.entity_id){o.material=o.material.clone();o.userData.originalColor=o.material.color.clone();o.userData.originalEmission=o.material.emissive?.clone();}}
      });
      this._createLabels();this._updateStates();this._renderSide();this._resize();
      this.shadowRoot.querySelector('.loading').hidden=true;this.dataset.loaded='true';this.dataset.models=String(this.layout.models.length);
      this._tick();
    }catch(error){if(generation!==this._generation)return;this.shadowRoot.querySelector('.loading-text').textContent=`3D 加载失败：${error.message}。原房间卡片仍可使用。`;this.dataset.error=error.message;console.error('Digital home',error);}
  }
  _validateLayout(layout){
    const entity=/^[a-z_]+\.[a-z0-9_]+$/, room=/^[a-z][a-z0-9_-]*$/;
    const point=p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite);
    if(!Array.isArray(layout.rooms)||!Array.isArray(layout.models)||!Array.isArray(layout.outline)||layout.outline.length<3||!layout.outline.every(point))throw Error('Invalid layout geometry');
    const rooms=new Set(),ids=new Set();
    for(const r of layout.rooms){if(!room.test(r.id)||rooms.has(r.id)||!point(r.center)||typeof r.name!=='string')throw Error('Invalid room');rooms.add(r.id);}
    for(const m of layout.models){if(!entity.test(m.entity_id)||ids.has(m.entity_id)||!rooms.has(m.area_id)||!point(m.position)||typeof m.name!=='string'||!Object.hasOwn(ICON,m.kind))throw Error('Invalid model binding');ids.add(m.entity_id);if(m.related_entities&&!m.related_entities.every(e=>entity.test(e)))throw Error('Invalid related entity');}
  }
  _bindUI(){
    this.shadowRoot.querySelector('.rooms').innerHTML=[{id:'all',name:'全屋'},...this.layout.rooms].map(r=>`<button class="chip" data-room="${esc(r.id)}" aria-pressed="${r.id===this._area}">${esc(r.name.replace('（模拟分区）',''))}</button>`).join('');
    this.shadowRoot.querySelectorAll('[data-room]').forEach(b=>b.addEventListener('click',()=>this._setArea(b.dataset.room)));
    const markerButton=this.shadowRoot.querySelector('[data-view=labels]');markerButton.textContent='设备点';markerButton.setAttribute('aria-pressed',this._labels);
    this.shadowRoot.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>{
      if(b.dataset.view==='walls'){this._fullHeight=!this._fullHeight;for(const o of this._upperObjects??[])o.visible=this._fullHeight;b.setAttribute('aria-pressed',this._fullHeight);this.dataset.fullHeight=String(this._fullHeight);return;}
      if(b.dataset.view==='labels'){this._labels=!this._labels;b.setAttribute('aria-pressed',this._labels);this._positionLabels();return;}
      if(b.dataset.view==='reset'){this._area='all';this._selected=null;this._setArea('all');}
      else this._topView=b.dataset.view==='top';
      this.shadowRoot.querySelector('[data-view="3d"]').setAttribute('aria-pressed',!this._topView);this.shadowRoot.querySelector('[data-view="top"]').setAttribute('aria-pressed',this._topView);this._resetCamera();
    }));
    this.shadowRoot.querySelector('.side').addEventListener('click',e=>{const b=e.target.closest('button');if(!b||b.disabled)return;if(b.dataset.entity)this._select(b.dataset.entity);if(b.dataset.action)this._action(b.dataset.action,b.dataset.target);});
    this.shadowRoot.querySelector('.side').addEventListener('change',e=>{if(e.target.matches('[data-range]'))this._action(e.target.dataset.range,null,Number(e.target.value));});
    this.shadowRoot.querySelector('.device-count').textContent=`${this.layout.models.length} 个设备模型`;
  }
  _buildScene(){
    const stage=this.shadowRoot.querySelector('.stage');this._scene=new THREE.Scene();
    this._renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'low-power'});this._renderer.setPixelRatio(Math.min(devicePixelRatio,1.6));this._renderer.outputColorSpace=THREE.SRGBColorSpace;this._renderer.toneMapping=THREE.ACESFilmicToneMapping;this._renderer.toneMappingExposure=1.0;this._renderer.shadowMap.enabled=true;this._renderer.shadowMap.type=THREE.PCFSoftShadowMap;
    this._renderer.domElement.setAttribute('aria-label','由布局文件加载的交互三维家居模型');stage.prepend(this._renderer.domElement);
    this._scene.add(new THREE.HemisphereLight(0xf8fff2,0x879b83,2.0));
    const sun=new THREE.DirectionalLight(0xfff0d7,2.8);sun.position.set(-6,14,6);sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);sun.shadow.camera.left=-10;sun.shadow.camera.right=10;sun.shadow.camera.top=10;sun.shadow.camera.bottom=-10;sun.shadow.normalBias=.045;sun.shadow.bias=-.0001;this._scene.add(sun);
    const fill=new THREE.DirectionalLight(0xe3f0ff,1.0);fill.position.set(8,6,-9);this._scene.add(fill);
    const ground=new THREE.Mesh(new THREE.PlaneGeometry(80,80),new THREE.ShadowMaterial({color:0x73806a,opacity:.17}));ground.rotation.x=-Math.PI/2;ground.position.y=-.31;ground.receiveShadow=true;this._scene.add(ground);
    this._camera=new THREE.OrthographicCamera(-10,10,10,-10,.1,100);this._camera.position.set(12,19,15);
    this._controls=new OrbitControls(this._camera,this._renderer.domElement);this._controls.enableDamping=true;this._controls.dampingFactor=.12;this._controls.maxPolarAngle=Math.PI*.47;this._controls.minZoom=.65;this._controls.maxZoom=4;this._controls.target.set(0,.2,-.1);
    this._raycaster=new THREE.Raycaster();this._pointer=new THREE.Vector2();
    let start=null;
    this._renderer.domElement.addEventListener('pointerdown',e=>{start=[e.clientX,e.clientY];});
    this._renderer.domElement.addEventListener('pointerup',e=>{
      if(!start||Math.hypot(e.clientX-start[0],e.clientY-start[1])>5)return;start=null;
      const rect=this._renderer.domElement.getBoundingClientRect();this._pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);this._raycaster.setFromCamera(this._pointer,this._camera);
      const hit=this._raycaster.intersectObject(this._model,true).find(x=>x.object.userData.entity_id);if(hit)this._select(hit.object.userData.entity_id);
    });
    this._resizeObserver=new ResizeObserver(()=>this._resize());this._resizeObserver.observe(stage);
    this._intersection=new IntersectionObserver(es=>{this._visible=es[0].isIntersecting;});this._intersection.observe(this);
    this._resetCamera();
  }
  _resetCamera(){if(!this._camera)return;this._camera.position.set(...(this._topView?[0,26,.001]:(this.layout.camera?.isometric??[12,19,15])));this._camera.zoom=1;this._controls.target.set(...(this.layout.camera?.target??[0,.2,-.1]));this._controls.update();this._resize();}
  _resize(){
    if(!this._renderer)return;const s=this.shadowRoot.querySelector('.stage'),w=s.clientWidth,h=s.clientHeight;if(!w||!h)return;
    this._renderer.setSize(w,h);const aspect=w/h;this._camera.updateMatrixWorld();
    const target=this._controls.target,right=new THREE.Vector3().setFromMatrixColumn(this._camera.matrixWorld,0),up=new THREE.Vector3().setFromMatrixColumn(this._camera.matrixWorld,1);
    let rx=0,ry=0;for(const p of this.layout.outline){for(const height of [0,2.65]){const v=new THREE.Vector3(p[0],height,-p[1]).sub(target);rx=Math.max(rx,Math.abs(v.dot(right)));ry=Math.max(ry,Math.abs(v.dot(up)));}}
    const span=Math.max(ry*2.2,rx*2.2/aspect);this._camera.left=-span*aspect/2;this._camera.right=span*aspect/2;this._camera.top=span/2;this._camera.bottom=-span/2;this._camera.updateProjectionMatrix();
  }
  _createLabels(){
    const layer=this.shadowRoot.querySelector('.labels');this._labelObjects=[];
    this._leaderSvg=document.createElementNS('http://www.w3.org/2000/svg','svg');this._leaderSvg.classList.add('leader-lines');this._leaderSvg.setAttribute('aria-hidden','true');layer.append(this._leaderSvg);
    for(const r of this.layout.rooms){const b=document.createElement('button');b.className='label room-label';b.textContent=r.name.replace('（模拟分区）','');b.title=r.mapping==='simulated_subzone'?'厨房尚未独立分区，此处为模拟位置':r.name;b.addEventListener('click',()=>this._setArea(r.id));layer.append(b);this._labelObjects.push({element:b,point:new THREE.Vector3(r.center[0],.08,-r.center[1]),area:r.id,room:true});}
    for(const m of this.layout.models){const b=document.createElement('button');b.className='label pin';b.textContent=ICON[m.kind];b.setAttribute('aria-label',`选择 ${m.name}`);b.title=m.name;b.dataset.entity=m.entity_id;b.addEventListener('click',()=>this._select(m.entity_id));layer.append(b);const line=document.createElementNS('http://www.w3.org/2000/svg','line');this._leaderSvg.append(line);this._labelObjects.push({element:b,line,point:new THREE.Vector3(m.position[0],m.marker_height??(m.kind==='vacuum'?.42:1.2),-m.position[1]),entity:m.entity_id,area:m.area_id});}
  }
  _positionLabels(){
    if(!this._labelObjects)return;const w=this._renderer.domElement.clientWidth,h=this._renderer.domElement.clientHeight,placed=[];
    for(const l of this._labelObjects){
      const v=l.point.clone().project(this._camera),showDevice=(this._labels||this._area!=='all'||l.entity===this._selected||l.entity?.startsWith('vacuum.'))&&(this._area==='all'||l.area===this._area);
      const visible=(l.room||showDevice)&&Math.abs(v.x)<1&&Math.abs(v.y)<1&&v.z<1;l.element.hidden=!visible;if(l.line)l.line.style.display=visible?'':'none';if(!visible)continue;
      const ox=(v.x+1)*w/2,oy=(1-v.y)*h/2;let x=ox,y=oy;
      if(!l.room){
        let found=false;
        for(const radius of [0,26,39,52,65,78]){
          for(let i=0;i<(radius?12:1);i++){
            const a=i*Math.PI/6,tx=ox+Math.cos(a)*radius,ty=oy+Math.sin(a)*radius;
            if(tx<16||tx>w-16||ty<60||ty>h-35)continue;
            if(placed.every(p=>Math.abs(tx-p.x)>p.hw+14||Math.abs(ty-p.y)>p.hh+14)){x=tx;y=ty;found=true;break;}
          }if(found)break;
        }
      }
      l.element.style.left=`${x}px`;l.element.style.top=`${y}px`;placed.push({x,y,hw:l.room?l.element.offsetWidth/2:12,hh:l.room?l.element.offsetHeight/2:12});
      if(l.line){l.line.setAttribute('x1',ox);l.line.setAttribute('y1',oy);l.line.setAttribute('x2',x);l.line.setAttribute('y2',y);l.line.style.display=Math.hypot(x-ox,y-oy)>8?'':'none';}
    }
  }
  _tick(){if(!this._started)return;this._frame=requestAnimationFrame(()=>this._tick());if(!this._visible||document.hidden)return;const now=performance.now();if(now-(this._lastFrame??0)<32)return;this._lastFrame=now;this._controls.update();this._renderer.render(this._scene,this._camera);this._positionLabels();}
  _setArea(id){this._area=id;this._selected=null;this.shadowRoot.querySelectorAll('[data-room]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.room===id));this._renderSide();this._updateStates();this._positionLabels();}
  _select(eid){if(!this._byEntity?.has(eid))return;this._selected=eid;this._renderSide();this._updateStates();}
  _updateStates(){
    if(!this.layout)return;const online=Boolean(this._hass?.connected??this._hass?.connection?.connected??this._hass);const label=this.shadowRoot.querySelector('.live-text');if(label)label.textContent=this.config.demo?'合成演示状态':online?'HA 实时状态':'等待 HA 连接';
    this.dataset.connected=String(online);
    for(const l of this._labelObjects??[]){if(!l.entity)continue;const s=this._states[l.entity];l.element.classList.toggle('on',Boolean(active(s)));l.element.classList.toggle('selected',l.entity===this._selected);l.element.classList.toggle('unavailable',!s||['unavailable','unknown'].includes(s.state));l.element.title=`${this._byEntity.get(l.entity)?.name} · ${stateText(s)}`;l.element.dataset.state=s?.state??'unknown';}
    for(const [eid,meshes] of this._entityMeshes??[]){const s=this._states[eid],isOn=active(s),selected=eid===this._selected;for(const o of meshes){if(!o.material.emissive)continue;const indicator=o.material.name.startsWith('Status_');if(o.userData.screen_entity){const known=s&&!['unavailable','unknown'].includes(s.state)&&online;const lit=known&&isOn;o.material.color.set(!known?0x50565b:lit?0x315966:0x101419);o.material.emissive.set(lit?0x72bed6:0x000000);o.material.emissiveIntensity=lit?.48:0;}else if(indicator){o.material.color.set(isOn?0xcba458:0x6f9087);o.material.emissive.set(isOn?0xa4732e:0x000000);o.material.emissiveIntensity=isOn?.30:0;}else if(o.userData.emissive_entity){o.material.emissive.set(isOn?0xffbd61:0x000000);o.material.emissiveIntensity=isOn?.85:0;}else{if(selected){o.material.emissive.set(0x987338);o.material.emissiveIntensity=.16;}else if(o.userData.originalEmission){o.material.emissive.copy(o.userData.originalEmission);o.material.emissiveIntensity=0;}}}}
    for(const c of this._curtains??[]){const s=this._states[c.userData.curtain_entity],pos=s?.attributes?.current_position??(s?.state==='open'?100:0);c.scale.z=c.userData.originalZScale*(1-Number(pos)/100*.72);}
    const state=this._selected?this._states[this._selected]:null;const stateEl=this.shadowRoot.querySelector('.selected-state');if(stateEl)stateEl.textContent=stateText(state);
    for(const b of this.shadowRoot.querySelectorAll('.device-row')){const s=this._states[b.dataset.entity];b.querySelector('.value').textContent=stateText(s);}
    if(this._selected&&!this._busy){const signature=JSON.stringify([state?.state,state?.attributes?.supported_features,state?.attributes?.current_position,state?.attributes?.brightness,this._hass?.connected]);if(signature!==this._actionSignature){this._actionSignature=signature;this._renderSide();}}
  }
  _renderSide(){
    if(!this.layout)return;const el=this.shadowRoot.querySelector('.side');const m=this._selected?this._byEntity.get(this._selected):null;const room=this.layout.rooms.find(r=>r.id===this._area);
    const priority={television:-1,vacuum:0,dock:1,switch:2,led_strip:2,power_switch:3,curtain:4,aircon:5,thermostat:6,motion_sensor:7,sensor:8};
    const devices=this.layout.models.filter(x=>this._area==='all'||x.area_id===this._area).sort((a,b)=>priority[a.kind]-priority[b.kind]);
    if(!m){el.innerHTML=`<div class="side-kicker">${this._area==='all'?'AT A GLANCE':'ROOM DEVICES'}</div><div class="side-title">${esc(room?.name??'此刻的家')}</div><div class="side-state">${devices.length} 个设备模型 · 点击查看</div><div class="side-note">${this._area==='all'?'选择地图中的设备，或从下方列表打开控制。':room?.mapping==='simulated_subzone'?'厨房暂未被云鲸独立分区，此处采用模拟位置。':'设备位置来自布局配置，可按实际安装位置校准。'}</div>`;}
    else{
      const s=this._states[m.entity_id],domain=m.entity_id.split('.')[0],unavailable=!s||['unavailable','unknown'].includes(s.state)||this._hass?.connected===false;
      const button=(action,text,primary=false,disabled=false)=>`<button class="action ${primary?'primary':''}" data-action="${action}" ${unavailable||disabled||this._busy?'disabled':''}>${text}</button>`;
      let actions='';
      if(['switch','light'].includes(domain)&&m.kind!=='dock')actions=button(s?.state==='on'?'turn_off':'turn_on',s?.state==='on'?'关闭':'开启',true,m.protected);
      if(domain==='cover')actions=button('open_cover','打开')+button('stop_cover','停止')+button('close_cover','关闭');
      if(domain==='vacuum'){
        const f=s?.attributes?.supported_features??0;
        if(f&8192)actions+=button('start',s?.state==='paused'?'继续清洁':'开始清洁',true,s?.state==='cleaning');
        if(f&4)actions+=button('pause','暂停',false,s?.state!=='cleaning');
        if(f&8)actions+=button('stop','停止',false,['docked','idle'].includes(s?.state));
        if(f&16)actions+=button('return_to_base','回充',false,s?.state==='docked');
      }
      let range='';if(domain==='light'&&s?.state==='on'&&'brightness'in(s.attributes??{}))range=`<label class="percent">亮度 ${Math.round(s.attributes.brightness/255*100)}%<input class="range" type="range" min="1" max="100" value="${Math.round(s.attributes.brightness/255*100)}" data-range="brightness" aria-label="灯带亮度" ${unavailable?'disabled':''}></label>`;
      if(domain==='cover'&&'current_position'in(s?.attributes??{}))range=`<label class="percent">开启程度 ${s.attributes.current_position}%<input class="range" type="range" min="0" max="100" value="${s.attributes.current_position}" data-range="position" aria-label="窗帘开启程度" ${unavailable?'disabled':''}></label>`;
      const note=m.protected?'此开关名称标注“勿关”，3D 看板保留状态显示，不提供快捷断电。':domain==='vacuum'?'模型使用配置的静态位置，没有实时定位时不会模拟移动轨迹。':m.kind==='dock'?'基站任务受机器人当前状态限制，请在 HA 详情中查看可用操作。':(m.position_note??'设备安装点来自布局文件，可继续校准。');
      el.innerHTML=`<div class="side-kicker">${esc(ICON[m.kind])} / DEVICE</div><div class="side-title">${esc(m.name)}</div><div class="side-state selected-state">${esc(stateText(s))}</div><div class="actions">${actions}<button class="action wide" data-action="more-info">${domain==='climate'?'温度与空调控制':domain==='media_player'?'打开电视遥控':'打开 HA 设备详情'}</button></div>${range}<div class="side-note">${esc(note)}</div><div class="badge">${m.position_source==='user_confirmed'?'位置已由你确认':'安装点为估计位置'}</div>`;
      if(m.kind==='dock'){
        const related=m.related_entities.filter(e=>e.startsWith('switch.'));
        el.innerHTML+=`<div class="actions">${related.map(e=>`<button class="action wide" data-action="related-info" data-target="${e}">${esc(DOCK_NAMES[e.split('_dock_').pop()]??this._states[e]?.attributes?.friendly_name??e.split('_dock_').pop())} · ${esc(stateText(this._states[e]))}</button>`).join('')}</div>`;
      }
    }
    el.innerHTML+=`<div class="device-list">${devices.map(d=>`<button class="device-row ${d.entity_id===this._selected?'selected':''}" data-entity="${d.entity_id}"><span class="symbol">${ICON[d.kind]}</span><span class="copy"><span class="name">${esc(d.name)}</span><span class="value" style="display:block">${esc(stateText(this._states[d.entity_id]))}</span></span></button>`).join('')}</div>`;
  }
  async _action(action,target,value){
    const m=this._byEntity.get(this._selected);if(!m)return;
    if(action==='more-info'||action==='related-info'){this.dispatchEvent(new CustomEvent('hass-more-info',{detail:{entityId:target??m.entity_id},bubbles:true,composed:true}));return;}
    const s=this._states[m.entity_id];if(this._busy||!s||['unavailable','unknown'].includes(s.state)||this._hass?.connected===false||m.protected)return;
    const domain=m.entity_id.split('.')[0];let service=action,data={entity_id:m.entity_id};
    const allowed={switch:['turn_on','turn_off'],light:['turn_on','turn_off','brightness'],cover:['open_cover','close_cover','stop_cover','position'],vacuum:['start','pause','stop','return_to_base']};if(!allowed[domain]?.includes(action))return;
    if(action==='brightness'){service='turn_on';data.brightness_pct=Math.max(1,Math.min(100,value));}if(action==='position'){service='set_cover_position';data.position=Math.max(0,Math.min(100,value));}
    this._busy=true;this._renderSide();
    try{await this._hass.callService(domain,service,data);this._toast('指令已提交，等待设备状态更新');}catch(err){this._toast(`操作未完成：${err.message??err}`);}finally{this._busy=false;this._renderSide();}
  }
  _toast(text){const el=this.shadowRoot.querySelector('.toast');el.textContent=text;el.hidden=false;clearTimeout(this._toastTimer);this._toastTimer=setTimeout(()=>{el.hidden=true;},4500);}
  _freeObject(root){root.traverse(o=>{if(o.geometry)o.geometry.dispose();if(o.material){const ms=Array.isArray(o.material)?o.material:[o.material];ms.forEach(m=>{for(const v of Object.values(m))if(v?.isTexture)v.dispose();m.dispose();});}});}
  _dispose(){this._started=false;this._generation=(this._generation??0)+1;cancelAnimationFrame(this._frame);clearTimeout(this._toastTimer);this._resizeObserver?.disconnect();this._intersection?.disconnect();this._controls?.dispose();if(this._scene)this._freeObject(this._scene);this._renderer?.dispose();this._renderer?.forceContextLoss();this._renderer=null;this._model=null;this._labelObjects=[];}
}
if(!customElements.get('home-digital-card'))customElements.define('home-digital-card',HomeDigitalCard);
window.customCards=window.customCards??[];window.customCards.push({type:'home-digital-card',name:'家 · 立体概览',description:'Blender 家居模型与 HA 实时设备控制',preview:false});
