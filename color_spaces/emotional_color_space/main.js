/* Independent static application; only the latest control state is rendered. */
(function () {
  'use strict';
  const C=window.EmotionalColors, $=id=>document.getElementById(id);
  const storageKey='emotional-color-space.labels.v1';
  let labels=Object.create(null), busy=false, pending=false, scheduled=false;
  try {
    const saved=localStorage.getItem(storageKey);
    if(saved)labels=C.importLabels(saved);
  } catch(error) {$('storage-status').textContent='Local labels could not load. Session labels and JSON export remain available.';}
  function state() {return {h:Number($('hue').value),s:Number($('saturation').value),v:Number($('value').value)};}
  function xyz(points) {return {x:points.map(p=>p[0]),y:points.map(p=>p[1]),z:points.map(p=>p[2])};}
  function line(points,color,width) {return Object.assign({type:'scatter3d',mode:'lines',line:{color:color,width:width},hoverinfo:'skip',showlegend:false},xyz(points));}
  function closed(points) {return points.concat([points[0]]);}
  function mesh(points,faces,colors,opacity) {
    return Object.assign({type:'mesh3d',i:faces.map(f=>f[0]),j:faces.map(f=>f[1]),k:faces.map(f=>f[2]),
      vertexcolor:colors,opacity:opacity,lighting:{ambient:1,diffuse:0,specular:0},hoverinfo:'skip',showlegend:false},xyz(points));
  }
  function cone() {
    const points=[[0,0,0],[0,0,1]].concat(C.hexagon(1,1)), faces=[];
    for(let i=0;i<6;i++) {const a=i+2,b=(i+1)%6+2;faces.push([0,b,a],[1,a,b]);}
    const trace=mesh(points,faces,['black','white'].concat(Array.from({length:6},(_,i)=>C.cssColor(i*60,1,1))),0.18);
    trace.visible=$('surface').checked;return trace;
  }
  function traces() {
    const {h,s,v}=state(), corners=C.hexagon(1,v), color=C.cssColor(h,s,v);
    const slice=mesh([[0,0,v]].concat(corners),v===0?[]:Array.from({length:6},(_,i)=>[0,i+1,(i+1)%6+1]),
      [C.cssColor(0,0,v)].concat(Array.from({length:6},(_,i)=>C.cssColor(i*60,1,v))),0.3);
    const outline=closed(C.hexagon(1,1));
    for(let i=0;i<6;i++)outline.push([null,null,null],[0,0,0],C.hsvPosition(i*60,1,1));
    const gray=Array.from({length:65},(_,i)=>i/64);
    const axis=line(gray.map(t=>[0,0,t]),gray,8);
    axis.line.colorscale='Greys';axis.line.reversescale=true;axis.line.cmin=0;axis.line.cmax=1;
    const marker=Object.assign({type:'scatter3d',mode:'markers',marker:{size:9,color:color,line:{color:'#14233a',width:3}},
      hovertemplate:'H '+h+'° · S '+s.toFixed(2)+' · V '+v.toFixed(2)+'<extra></extra>',showlegend:false},xyz([C.hsvPosition(h,s,v)]));
    const hueLabels=Object.assign({type:'scatter3d',mode:'markers+text',text:['Red 0°','Yellow 60°','Green 120°','Cyan 180°','Blue 240°','Magenta 300°'],
      marker:{size:4,color:Array.from({length:6},(_,i)=>C.cssColor(i*60,1,1))},textposition:'top center',hoverinfo:'skip',showlegend:false},xyz(C.hexagon(1,1)));
    return [cone(),line(outline,'#a0aec2',2),axis,slice,line(closed(corners),'#58718f',4),
      line(closed(C.hexagon(s,v)),'#192337',6),line([[0,0,v],C.hsvPosition(h,1,v)],C.cssColor(h,1,v),7),marker,hueLabels];
  }
  const axis=(title,range)=>({title:title,range:range,gridcolor:'#e3e9f2',backgroundcolor:'white'});
  const layout={margin:{l:0,r:0,t:15,b:0},showlegend:false,uirevision:'emotional-hsv',
    scene:{uirevision:'emotional-hsv-camera',dragmode:'orbit',aspectmode:'manual',aspectratio:{x:1,y:1,z:1},
      xaxis:axis('Hexagonal hue coordinate x',[-1.2,1.2]),yaxis:axis('Hexagonal hue coordinate y',[-1.2,1.2]),zaxis:axis('Value',[0,1.1])}};
  function panel() {
    const {h,s,v}=state(),rgb=C.hsvToRgb(h,s,v);
    $('hue-output').textContent=h+'°';$('saturation-output').textContent=s.toFixed(2);$('value-output').textContent=v.toFixed(2);
    $('hue-number').textContent=h+'°';$('saturation-number').textContent=s.toFixed(2);$('value-number').textContent=v.toFixed(2);
    $('emotion').textContent=labels[h]||'Unassigned';$('energy').textContent=Math.round(s*100)+'%';$('orientation').textContent=Math.round(v*100)+'%';
    $('swatch').style.backgroundColor=C.cssColor(h,s,v);
    $('rgb-readout').textContent='RGB ('+rgb.map(c=>c.toFixed(4)).join(', ')+') · '+C.cssColor(h,s,v);
    $('degenerate').textContent=v===0?'Black: hue and saturation are not visible.':s===0?'Grayscale: hue is not visible.':'';
  }
  async function render() {
    scheduled=false;if(busy){pending=true;return;}busy=true;
    try {
      await Plotly.react($('plot'),traces(),layout,{responsive:true,displaylogo:false,scrollZoom:true});
      $('render-status').textContent='';
    } catch(error) {$('render-status').textContent='Could not render: '+error.message;}
    finally {busy=false;if(pending){pending=false;schedule();}}
  }
  function schedule() {if(!scheduled){scheduled=true;requestAnimationFrame(render);}}
  function save() {
    try {localStorage.setItem(storageKey,C.exportLabels(labels));$('storage-status').textContent='Labels saved in this browser.';}
    catch(error) {$('storage-status').textContent='Saved for this session only. Export JSON to keep your labels.';}
    panel();
  }
  ['hue','saturation','value'].forEach(id=>$(id).addEventListener('input',()=>{
    panel();if(id==='hue')$('label').value=labels[state().h]||'';schedule();
  }));
  $('surface').addEventListener('change',schedule);
  $('label-form').addEventListener('submit',event=>{
    event.preventDefault();const name=$('label').value.trim();
    if(!name || name.length>120){$('storage-status').textContent='Enter an emotion name of 1–120 characters.';return;}
    labels[state().h]=name;save();
  });
  $('remove').addEventListener('click',()=>{delete labels[state().h];$('label').value='';save();});
  $('export').addEventListener('click',()=>{
    const url=URL.createObjectURL(new Blob([C.exportLabels(labels)],{type:'application/json'}));
    const link=document.createElement('a');link.href=url;link.download='emotional-hues.json';link.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  $('import').addEventListener('change',async event=>{
    const file=event.target.files[0];if(!file)return;
    try {
      if(file.size>100000)throw new Error('Label files must be smaller than 100 KB.');
      const imported=C.importLabels(await file.text()); // Validate before replacing.
      labels=imported;$('label').value=labels[state().h]||'';save();
    } catch(error) {$('storage-status').textContent='Import failed: '+error.message;}
    finally {event.target.value='';}
  });
  panel();$('label').value=labels[state().h]||'';
  if(window.Plotly)schedule();else $('render-status').textContent='Plotly could not load. Keep plotly.min.js beside this page.';
})();
