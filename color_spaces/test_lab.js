/* Controller integration checks with a Plotly/DOM stub; not a rendering test. */
'use strict';
const assert=require('assert'),fs=require('fs'),vm=require('vm'),path=require('path'),C=require('./docs/color-space.js');
const elements={};
['rgb','hsl','resolution','lightness','axes','section','status','swatch','selected-rgb','selected-hsl','selection-note','resolution-value','lightness-value'].forEach(id=>{
  elements[id]={value:id==='resolution'?'18':'0.5',checked:id==='axes',style:{},events:{},
    addEventListener(name,callback){this.events[name]=callback;},on(name,callback){this.events[name]=callback;}};
});
let selectionRedraws=0;
const plotly={
  react(view,data,layout){view.data=data;view.layout=layout;return Promise.resolve();},
  restyle(view,update,indices){
    selectionRedraws++;
    // Emulate a picked point replayed by a redraw: this must not recurse.
    view.events.plotly_click({points:[{customdata:update.customdata[0][0]}]});
    indices.forEach(i=>{
    ['x','y','z','customdata'].forEach(k=>{if(update[k])view.data[i][k]=update[k][0];});
    view.data[i].marker.color=update['marker.color'];
  });return Promise.resolve();}
};
const context={window:{ColorSpace:C,Plotly:plotly},Plotly:plotly,document:{getElementById:id=>elements[id]},setTimeout,clearTimeout,console};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'docs/lab.js'),'utf8'),context);
const wait=()=>new Promise(resolve=>setTimeout(resolve,150));
(async()=>{
  await wait();
  assert.strictEqual(elements.rgb.data[0].x.length,18**3);
  assert.strictEqual(elements.hsl.data[0].x.length,18**3);
  assert.deepStrictEqual(elements.rgb.data[0].customdata,elements.hsl.data[0].customdata);
  assert.strictEqual(elements.rgb.layout.scene.uirevision,'lab-camera');
  elements.hsl.events.plotly_click({points:[{customdata:[0.2,0.4,0.8]}]});
  await wait();
  assert.strictEqual(selectionRedraws,2);
  elements.hsl.events.plotly_click({points:[{customdata:[0.2,0.4,0.8]}]});
  await wait();
  assert.strictEqual(selectionRedraws,2);
  assert.strictEqual(elements.rgb.data[5].x[0],0.2);
  assert.strictEqual(elements.hsl.data[5].z[0],0.5);
  assert(elements['selected-hsl'].textContent.includes('L 0.5000'));
  elements.section.checked=true;elements.section.events.change();await wait();
  elements.lightness.value='0.2';elements.lightness.events.input();await wait();
  elements.rgb.data[0].customdata.forEach(rgb=>assert(Math.abs(C.rgbToHsl(rgb)[2]-0.2)<1e-10));
  assert.strictEqual(elements.rgb.data[5].x[0],0.2); // Selection persists.
  elements.axes.checked=false;elements.axes.events.change();await wait();
  assert.strictEqual(elements.rgb.data[3].visible,false);
  assert.strictEqual(elements.hsl.data[3].visible,false);
  elements.lightness.value='1';elements.lightness.events.input();await wait();
  assert.strictEqual(elements.rgb.data[0].x.length,1);
  assert.strictEqual(elements.rgb.data[1].i.length,0);
  elements.section.checked=false;elements.resolution.value='3';elements.section.events.change();await wait();
  assert.strictEqual(elements.rgb.data[0].x.length,27);
  assert.strictEqual(elements.hsl.data[0].x.length,27);
  console.log('Controller checks passed: paired samples, linked selection, filters, lightness, axes, resolution, endpoint, camera configuration.');
})().catch(error=>{console.error(error);process.exitCode=1;});
