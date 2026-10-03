import {markerPresentation} from './news_presentation.js';
import * as THREE from 'three';
import {OrbitControls} from '../vendor/three/OrbitControls.js';

/* Single Three.js version. Countries are a rasterized sphere texture, not
   tessellated/extruded polygon meshes: no cap triangles or side walls exist.
   A future day/night layer must be independent of this country texture. */
export async function createGlobe(container, events, onEvent){
 const d3=window.d3;if(!d3)throw new Error('Local geographic library unavailable');
 const response=await fetch('/static/data/countries.geojson');
 if(!response.ok)throw new Error('Local country data unavailable');
 const data=await response.json();
 if(data.type!=='FeatureCollection'||!data.features?.length)throw new Error('Invalid country collection');
 // D3 spherical paths expect small exterior rings clockwise, unlike RFC 7946.
 const countries=data.features.filter(f=>['Polygon','MultiPolygon'].includes(f.geometry?.type)).map(f=>{
  const polygons=f.geometry.type==='Polygon'?[f.geometry.coordinates]:f.geometry.coordinates;
  const normalized=polygons.map(rings=>d3.geoArea({type:'Polygon',coordinates:rings})>2*Math.PI?rings.map(r=>[...r].reverse()):rings);
  return {...f,geometry:{type:'MultiPolygon',coordinates:normalized}};
 });
 const renderer=new THREE.WebGLRenderer({antialias:true,alpha:false});
 renderer.setClearColor('#05090d',1);renderer.setPixelRatio(Math.min(devicePixelRatio||1,2));renderer.outputColorSpace=THREE.SRGBColorSpace;
 container.append(renderer.domElement);renderer.domElement.setAttribute('aria-hidden','true');
 const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(42,1,.1,50);
 const controls=new OrbitControls(camera,renderer.domElement);controls.enablePan=false;controls.enableDamping=true;controls.dampingFactor=.09;controls.rotateSpeed=.65;controls.zoomSpeed=.65;controls.minDistance=1.65;controls.maxDistance=10;
 const globeGroup=new THREE.Group();scene.add(globeGroup);
 // Independent scene group reserved for future terminator/light overlays.
 const environmentLayer=new THREE.Group();environmentLayer.name='future-independent-day-night';scene.add(environmentLayer);
 const canvas=document.createElement('canvas');canvas.width=4096;canvas.height=2048;
 const ctx=canvas.getContext('2d');if(!ctx)throw new Error('Country canvas unavailable');
 const projection=d3.geoEquirectangular().scale(canvas.width/(2*Math.PI)).translate([canvas.width/2,canvas.height/2]).precision(.15);
 const path=d3.geoPath(projection,ctx),texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;texture.anisotropy=Math.min(8,renderer.capabilities.getMaxAnisotropy());
 // MeshBasicMaterial keeps geographic fill stable, independent of lights.
 const sphere=new THREE.Mesh(new THREE.SphereGeometry(1,128,96),new THREE.MeshBasicMaterial({map:texture}));globeGroup.add(sphere);
 let hoverCountry=null,selectedCountry=null,selectedId=null;
 function drawCountries(){
  ctx.fillStyle='#080e14';ctx.fillRect(0,0,canvas.width,canvas.height);
  ctx.beginPath();path(d3.geoGraticule10());ctx.strokeStyle='#10212c';ctx.lineWidth=.65;ctx.stroke();
  for(const country of countries){ctx.beginPath();path(country);ctx.fillStyle=country===selectedCountry?'#204252':country===hoverCountry?'#18333e':'#17232b';ctx.fill();ctx.strokeStyle=country===selectedCountry||country===hoverCountry?'#43d8ff':'#305361';ctx.lineWidth=country===selectedCountry||country===hoverCountry?2.4:1.1;ctx.stroke();}
  texture.needsUpdate=true;
 }
 drawCountries();
 const vector=(lat,lon,r=1)=>{const la=THREE.MathUtils.degToRad(lat),lo=THREE.MathUtils.degToRad(lon);return new THREE.Vector3(r*Math.cos(la)*Math.cos(lo),r*Math.sin(la),-r*Math.cos(la)*Math.sin(lo));};
 const tooltip=document.getElementById('map-tooltip'),stage=document.getElementById('globe-stage');
 function showTooltip(title,detail,x,y){tooltip.replaceChildren();const strong=document.createElement('strong'),span=document.createElement('span');strong.textContent=title;span.textContent=detail;tooltip.append(strong,span);tooltip.hidden=false;tooltip.style.left=`${Math.min(Math.max(8,x+14),Math.max(8,stage.clientWidth-255))}px`;tooltip.style.top=`${Math.min(Math.max(8,y+12),Math.max(8,stage.clientHeight-110))}px`;}
 // Several frozen events share one coarse anchor. Separate their hit targets
 // in screen pixels only; source coordinates and sphere positions stay intact.
 let markers=[];
 function setEvents(next){
 for(const marker of markers){marker.button.remove();globeGroup.remove(marker.mesh);marker.mesh.geometry.dispose();marker.mesh.material.dispose();}
 tooltip.hidden=true;
 const groups=new Map();for(const event of next){const key=`${event.latitude},${event.longitude}`;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(event.id);}
 markers=next.map(event=>{
  const peers=groups.get(`${event.latitude},${event.longitude}`),slot=peers.indexOf(event.id);
  const angle=2*Math.PI*slot/peers.length,offset=peers.length>1?18:0;
  const position=vector(event.latitude,event.longitude,1.013);
  const visual=markerPresentation(event),color=visual.color;
  const mesh=new THREE.Mesh(new THREE.SphereGeometry(.0095,12,8),new THREE.MeshBasicMaterial({color}));mesh.position.copy(position);mesh.visible=!visual.hollow;globeGroup.add(mesh);
  const button=document.createElement('button');button.className='globe-marker';button.type='button';button.setAttribute('aria-label',`Map event: ${event.title}`);button.setAttribute('aria-pressed','false');button.dataset.eventId=event.id;button.dataset.severity=visual.severity.toLowerCase();button.dataset.watchlist=String(visual.linked);button.title=`Severity: ${visual.severity} · Watchlist: ${visual.linked?'Qualified relationship':'No qualified relationship'}`;button.style.setProperty('--marker-color',color);container.append(button);
  button.addEventListener('click',()=>onEvent(event.id));
  button.addEventListener('pointerenter',e=>{const rect=stage.getBoundingClientRect();showTooltip(visual.tooltipTitle,visual.tooltipDetail,e.clientX-rect.left,e.clientY-rect.top);});button.addEventListener('pointerleave',()=>tooltip.hidden=true);
  button.addEventListener('focus',()=>showTooltip(visual.tooltipTitle,visual.tooltipDetail,parseFloat(button.style.left)||10,parseFloat(button.style.top)||10));button.addEventListener('blur',()=>tooltip.hidden=true);
  return {event,position,mesh,button,offsetX:Math.cos(angle)*offset,offsetY:Math.sin(angle)*offset};
 });
 }
 setEvents(events);
 let fitDistance=3.3,width=0,height=0,frame=0,disposed=false;
 function resize(){const w=container.clientWidth,h=container.clientHeight;if(!w||!h||w===width&&h===height)return;
  const previous=fitDistance;const wasReady=width>0;width=w;height=h;camera.aspect=w/h;camera.updateProjectionMatrix();renderer.setSize(w,h,false);
  fitDistance=1.16/Math.sin(Math.atan(Math.tan(THREE.MathUtils.degToRad(21))*Math.min(1,camera.aspect)));
  if(wasReady)camera.position.multiplyScalar(fitDistance/previous);else camera.position.copy(vector(20,90,fitDistance));controls.update();
 }
 const observer=new ResizeObserver(resize);observer.observe(container);resize();
 const raycaster=new THREE.Raycaster(),mouse=new THREE.Vector2();let down=null,moved=false,lastHover=0;
 function countryAt(event){const rect=renderer.domElement.getBoundingClientRect();mouse.set((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(mouse,camera);const hit=raycaster.intersectObject(sphere,false)[0];if(!hit)return null;const p=hit.point.normalize();const coordinate=[THREE.MathUtils.radToDeg(Math.atan2(-p.z,p.x)),THREE.MathUtils.radToDeg(Math.asin(THREE.MathUtils.clamp(p.y,-1,1)))];return countries.find(f=>d3.geoContains(f,coordinate))||null;}
 const countryName=f=>f?.properties?.ADMIN||f?.properties?.NAME||'Country';
 renderer.domElement.addEventListener('pointerdown',e=>{down={x:e.clientX,y:e.clientY};moved=false;tooltip.hidden=true;});
 renderer.domElement.addEventListener('pointermove',e=>{
  if(down&&(Math.hypot(e.clientX-down.x,e.clientY-down.y)>4))moved=true;
  if(e.buttons||performance.now()-lastHover<65)return;lastHover=performance.now();
  const country=countryAt(e);if(country!==hoverCountry){hoverCountry=country;drawCountries();}
  renderer.domElement.style.cursor=country?'pointer':'grab';
  if(country){const rect=stage.getBoundingClientRect();showTooltip(countryName(country),'Click to select country',e.clientX-rect.left,e.clientY-rect.top);}else tooltip.hidden=true;
 });
 renderer.domElement.addEventListener('pointerup',e=>{if(down&&!moved){selectedCountry=countryAt(e);document.getElementById('country-selection').textContent=selectedCountry?countryName(selectedCountry):'No country selected';drawCountries();}down=null;});
 renderer.domElement.addEventListener('pointercancel',()=>down=null);
 renderer.domElement.addEventListener('pointerleave',()=>{tooltip.hidden=true;if(hoverCountry){hoverCountry=null;drawCountries();}});
 controls.addEventListener('start',()=>{tooltip.hidden=true;});
 function zoom(scale){camera.position.multiplyScalar(scale);camera.position.clampLength(controls.minDistance,controls.maxDistance);controls.update();}
 document.getElementById('globe-in').addEventListener('click',()=>zoom(.85));document.getElementById('globe-out').addEventListener('click',()=>zoom(1.18));document.getElementById('globe-reset').addEventListener('click',()=>{camera.position.copy(vector(20,90,fitDistance));controls.target.set(0,0,0);controls.update();});
 container.addEventListener('keydown',e=>{if(e.target!==container)return;const spherical=new THREE.Spherical().setFromVector3(camera.position);if(e.key==='ArrowLeft')spherical.theta-=.12;else if(e.key==='ArrowRight')spherical.theta+=.12;else if(e.key==='ArrowUp')spherical.phi=Math.max(.1,spherical.phi-.12);else if(e.key==='ArrowDown')spherical.phi=Math.min(Math.PI-.1,spherical.phi+.12);else if(e.key==='+'||e.key==='='){zoom(.85);e.preventDefault();return;}else if(e.key==='-'){zoom(1.18);e.preventDefault();return;}else return;e.preventDefault();camera.position.setFromSpherical(spherical);controls.update();});
 function animate(){if(disposed)return;frame=requestAnimationFrame(animate);if(document.hidden)return;controls.update();renderer.render(scene,camera);
  for(const m of markers){const visible=new THREE.Vector3().subVectors(camera.position,m.position).dot(m.position)>0.015;const p=m.position.clone().project(camera);m.button.hidden=!visible||p.z>1||Math.abs(p.x)>1||Math.abs(p.y)>1;m.button.style.left=`${(p.x+1)*width/2+m.offsetX}px`;m.button.style.top=`${(1-p.y)*height/2+m.offsetY}px`;}
 }
 renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();const status=document.getElementById('globe-state');status.hidden=false;status.textContent='Graphics context lost. Reload to restore the globe; the news list remains available.';});
 animate();container.dataset.globeReady='true';container.dataset.countries=String(countries.length);
 window.addEventListener('pagehide',event=>{if(event.persisted)return;disposed=true;cancelAnimationFrame(frame);observer.disconnect();controls.dispose();texture.dispose();globeGroup.traverse(o=>{o.geometry?.dispose();o.material?.dispose();});renderer.dispose();});
 return {setEvents,selectEvent(event,focus){selectedId=event?.id??null;markers.forEach(m=>{m.button.setAttribute('aria-pressed',String(m.event.id===selectedId));m.mesh.scale.setScalar(m.event.id===selectedId?1.3:1);});if(event&&focus){camera.position.copy(vector(event.latitude,event.longitude,camera.position.length()));controls.update();}}};
}
