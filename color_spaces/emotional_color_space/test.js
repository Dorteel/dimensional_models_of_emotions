/* Dependency-free math and controller tests. No WebGL rendering is simulated. */
'use strict';
const assert=require('assert'),fs=require('fs'),vm=require('vm'),path=require('path');
const C=require('./color_spaces.js');
function near(a,b){assert(Math.abs(a-b)<1e-10,a+' != '+b);}
function vector(a,b){a.forEach((v,i)=>near(v,b[i]));}
const colors=[[1,0,0],[1,1,0],[0,1,0],[0,1,1],[0,0,1],[1,0,1]];
colors.forEach((rgb,i)=>vector(C.hsvToRgb(i*60,1,1),rgb));
vector(C.hsvToRgb(30,0.5,0.8),[0.8,0.6,0.4]);
vector(C.hsvToRgb(360,1,1),colors[0]);vector(C.hsvToRgb(-60,1,1),colors[5]);
for(let h=0;h<360;h++) {
  vector(C.hsvPosition(h,1,0),[0,0,0]);vector(C.hsvPosition(h,0,0.8),[0,0,0.8]);
  vector(C.hsvToRgb(h,0,0.8),[0.8,0.8,0.8]);
  for(const v of [0.2,0.6,1]) {
    const a=C.hsvPosition(Math.floor(h/60)*60,1,v),b=C.hsvPosition((Math.floor(h/60)+1)*60,1,v),p=C.hsvPosition(h,1,v);
    near((p[0]-a[0])*(b[1]-a[1])-(p[1]-a[1])*(b[0]-a[0]),0); // On a straight edge.
    vector(C.hsvPosition(h,0.4,v),[p[0]*0.4,p[1]*0.4,v]);
    const rgb=C.hsvToRgb(h,0.4,v);near(Math.max.apply(null,rgb),v);near(Math.min.apply(null,rgb),v*0.6);
  }
}
for(const v of [0.1,0.6,1]) {
  const corners=C.hexagon(1,v);assert.strictEqual(corners.length,6);
  corners.forEach((p,i)=>{near(p[2],v);near(Math.hypot(p[0],p[1]),v);const q=corners[(i+1)%6];near(Math.hypot(p[0]-q[0],p[1]-q[1]),v);});
}
const labels={'0':'Curiosity','120':'Connection','359':'<b>Personal</b>'};
assert.strictEqual(C.exportLabels(C.importLabels(C.exportLabels(labels))),C.exportLabels(labels));
['{}','{"version":1,"labels":{"360":"Bad"}}','{"version":1,"labels":{"1":""}}','{"version":1,"labels":{"__proto__":"bad"}}','{"version":1,"labels":[]}'].forEach(json=>assert.throws(()=>C.importLabels(json)));
assert.throws(()=>C.hsvPosition(0,-1,1));
console.log('Geometry: canonical RGB, 360 hue directions, apex, grayscale, boundary, regular hexagons, saturation scaling, JSON validation passed.');
const ids=['hue','saturation','value','surface','plot','hue-output','saturation-output','value-output','hue-number','saturation-number','value-number','emotion','energy','orientation','swatch','rgb-readout','degenerate','label','label-form','remove','export','import','storage-status','render-status'];
const elements={};ids.forEach(id=>{elements[id]={value:({hue:'120',saturation:'0.8',value:'0.6',label:''})[id]||'',checked:true,style:{},events:{},addEventListener(name,fn){this.events[name]=fn;}};});
let saved=null,blob=null,downloads=0,camera={eye:{x:2,y:1,z:1}};
const plotly={react(view,data,layout){
  if(view.layout)assert.strictEqual(layout.scene.uirevision,view.layout.scene.uirevision);
  // Emulate Plotly retaining a user camera with unchanged uirevision.
  view.camera=camera;view.data=data;view.layout=layout;return Promise.resolve();
}};
const context={window:{EmotionalColors:C,Plotly:plotly},Plotly:plotly,
  document:{getElementById:id=>elements[id],createElement:()=>({click(){downloads++;}})},
  localStorage:{getItem:()=>saved,setItem:(key,value)=>{saved=value;}},
  URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},Blob:function(parts){blob=parts[0];},
  requestAnimationFrame:fn=>setTimeout(fn,0),setTimeout,console};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'main.js'),'utf8'),context);
const wait=()=>new Promise(resolve=>setTimeout(resolve,25));
(async()=>{
  await wait();const plot=elements.plot;
  vector([plot.data[7].x[0],plot.data[7].y[0],plot.data[7].z[0]],C.hsvPosition(120,0.8,0.6));
  assert.strictEqual(plot.data[7].marker.color,C.cssColor(120,0.8,0.6));
  assert.strictEqual(elements.emotion.textContent,'Unassigned');
  elements.label.value='Connection';elements['label-form'].events.submit({preventDefault(){}});
  assert.strictEqual(C.importLabels(saved)['120'],'Connection');
  elements.export.events.click();assert.strictEqual(downloads,1);assert.strictEqual(C.importLabels(blob)['120'],'Connection');
  elements.import.events.change({target:{files:[{size:40,text:async()=>C.exportLabels({'30':'Wonder'})}],value:'x'}});await wait();
  assert.strictEqual(C.importLabels(saved)['30'],'Wonder');
  const previous=saved;
  await elements.import.events.change({target:{files:[{size:2,text:async()=>'{}'}],value:'x'}});
  assert.strictEqual(saved,previous);assert(elements['storage-status'].textContent.includes('Import failed'));
  for(const update of [['hue','30'],['saturation','0.5'],['value','0.8']]) {
    elements[update[0]].value=update[1];elements[update[0]].events.input();await wait();
    assert.strictEqual(plot.camera,camera);assert.strictEqual(plot.layout.scene.uirevision,'emotional-hsv-camera');
  }
  vector([plot.data[7].x[0],plot.data[7].y[0],plot.data[7].z[0]],C.hsvPosition(30,0.5,0.8));
  assert.strictEqual(elements.swatch.style.backgroundColor,'rgb(204,153,102)');
  assert.strictEqual(elements.emotion.textContent,'Wonder');
  assert.strictEqual(elements.energy.textContent,'50%');assert.strictEqual(elements.orientation.textContent,'80%');
  elements.surface.checked=false;elements.surface.events.change();await wait();assert.strictEqual(plot.data[0].visible,false);
  elements.value.value='0';elements.value.events.input();await wait();
  vector([plot.data[7].x[0],plot.data[7].y[0],plot.data[7].z[0]],[0,0,0]);assert.strictEqual(plot.data[3].i.length,0);
  elements.remove.events.click();assert.strictEqual(elements.emotion.textContent,'Unassigned');
  console.log('Controller: marker, swatch, sliders, revision stability, surface toggle, label save/remove/export/import, invalid import preservation passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
