/* Static browser application: no Python or network service at runtime. */
(function () {
  'use strict';
  const C = window.ColorSpace, $ = id => document.getElementById(id);
  const views = [$('rgb'), $('hsl')];
  let selected = [1,0,0], points = [], cacheKey = '', busy = false, pending = false;
  const cssColor = rgb => 'rgb(' + rgb.map(v => Math.round(v*255)).join(',') + ')';
  const format = values => values.map(v => v.toFixed(4)).join(', ');
  function coordinates(rgb, hslView) {return hslView ? C.hslPosition(C.rgbToHsl(rgb)) : rgb;}
  function xyz(points) {return {x:points.map(p=>p[0]), y:points.map(p=>p[1]), z:points.map(p=>p[2])};}
  function scatter(points, options) {return Object.assign({type:'scatter3d', showlegend:false}, xyz(points), options);}
  function cloud(hslView) {
    return scatter(points.map(p=>coordinates(p,hslView)), {
      mode:'markers', marker:{size:3, color:points.map(cssColor), opacity:0.72},
      customdata:points, text:points.map(p=>'RGB ('+format(p)+')<br>HSL ('+format(C.rgbToHsl(p))+')'),
      hovertemplate:'%{text}<extra></extra>', name:'Color samples'
    });
  }
  function surface(l, hslView) {
    let vertices=[], faces=[];
    if (hslView) {
      // The circular embedding bends hue edges; subdivide the disk in hue.
      vertices=[[l,l,l]];
      for(let i=0;i<120;i++) vertices.push(C.hslToRgb([i*3,1,l]));
      if(l>0 && l<1) for(let i=0;i<120;i++) faces.push([0,i+1,(i+1)%120+1]);
    } else {
      C.lightnessSurface(l).forEach(triangle=>{
        const offset=vertices.length; vertices.push.apply(vertices,triangle);
        if(l>0 && l<1) faces.push([offset,offset+1,offset+2]);
      });
    }
    return Object.assign({type:'mesh3d', i:faces.map(f=>f[0]), j:faces.map(f=>f[1]), k:faces.map(f=>f[2]),
      vertexcolor:vertices.map(cssColor), opacity:0.2, lighting:{ambient:1,diffuse:0,specular:0},
      hoverinfo:'skip', showlegend:false}, xyz(vertices.map(p=>coordinates(p,hslView))));
  }
  function sectionBoundary(l,hslView) {
    let boundary=[];
    if(hslView) {
      for(let i=0;i<=120;i++) boundary.push(C.hslPosition([i*3,1,l]));
    } else {
      const seen=new Set();
      C.lightnessSurface(l).forEach(triangle=>triangle.slice(1).forEach(p=>{
        const key=p.join(','); if(!seen.has(key)){seen.add(key);boundary.push(p);}
      }));
      // Sort the six outer corners around the grayscale direction.
      const u=[1/Math.sqrt(2),-1/Math.sqrt(2),0], v=[1/Math.sqrt(6),1/Math.sqrt(6),-2/Math.sqrt(6)];
      const angle=p=>Math.atan2(p.reduce((s,x,i)=>s+(x-l)*v[i],0),p.reduce((s,x,i)=>s+(x-l)*u[i],0));
      boundary.sort((a,b)=>angle(a)-angle(b)); boundary.push(boundary[0]);
    }
    return scatter(boundary,{mode:'lines',line:{color:'#36527d',width:5},hoverinfo:'skip'});
  }
  function grayAxis(hslView) {
    const values=Array.from({length:65},(_,i)=>i/64);
    return scatter(values.map(t=>hslView?[0,0,t]:[t,t,t]),{
      mode:'lines',line:{color:values,colorscale:'Greys',reversescale:true,cmin:0,cmax:1,width:9},
      visible:$('axes').checked,hoverinfo:'skip'
    });
  }
  function frame(hslView) {
    const lines=[];
    if(hslView) {
      for(let i=0;i<=120;i++) {const a=i*2*Math.PI/120;lines.push([Math.cos(a),Math.sin(a),0.5]);}
      lines.push([null,null,null]);
      for(let i=0;i<6;i++) {const a=i*Math.PI/3;lines.push([0,0,0],[Math.cos(a),Math.sin(a),0.5],[0,0,1],[null,null,null]);}
    } else {
      for(let axis=0;axis<3;axis++) for(let a=0;a<2;a++) for(let b=0;b<2;b++) {
        const start=[0,0,0],end=[0,0,0],fixed=[0,1,2].filter(i=>i!==axis);
        start[fixed[0]]=end[fixed[0]]=a;start[fixed[1]]=end[fixed[1]]=b;end[axis]=1;
        lines.push(start,end,[null,null,null]);
      }
    }
    return scatter(lines,{mode:'lines',line:{color:'#a0aec2',width:2},hoverinfo:'skip'});
  }
  function highlight(hslView) {
    return scatter([coordinates(selected,hslView)],{
      mode:'markers', marker:{size:10,color:cssColor(selected),line:{color:'#101c30',width:4}},
      customdata:[selected], hovertemplate:'Selected color<extra></extra>'
    });
  }
  function selectionInfo() {
    const hsl=C.rgbToHsl(selected);
    $('swatch').style.backgroundColor=cssColor(selected);
    $('selected-rgb').textContent='RGB ('+format(selected)+') · '+cssColor(selected);
    $('selected-hsl').textContent='HSL: H '+hsl[0].toFixed(2)+'° · S '+hsl[1].toFixed(4)+' · L '+hsl[2].toFixed(4);
    $('selection-note').textContent=hsl[1]===0 ? 'Hue is undefined for grayscale; shown as 0° by convention.' : 'The highlighted color remains selected when controls change.';
  }
  function layout(hslView) {
    const axis=(title,range)=>({title:title,range:range,backgroundcolor:'#fff',gridcolor:'#e3e9f2',zerolinecolor:'#a0aec2'});
    return {margin:{l:0,r:0,t:10,b:0},paper_bgcolor:'#fff',showlegend:false,uirevision:'lab',
      scene:{uirevision:'lab-camera',dragmode:'orbit',aspectmode:'manual',aspectratio:{x:1,y:1,z:1},
        xaxis:axis(hslView?'Chroma × cos(H)':'Red',hslView?[-1.1,1.1]:[0,1]),
        yaxis:axis(hslView?'Chroma × sin(H)':'Green',hslView?[-1.1,1.1]:[0,1]),
        zaxis:axis(hslView?'Lightness':'Blue',[0,1])}};
  }
  async function render() {
    if(busy) {pending=true;return;}
    busy=true;
    try {
      const n=Number($('resolution').value), l=Number($('lightness').value), section=$('section').checked;
      $('resolution-value').textContent=n; $('lightness-value').textContent=l.toFixed(2);
      const key=n+':'+(section?l:'cube');
      if(key!==cacheKey) {points=section?C.sectionPoints(l,n):C.cubePoints(n);cacheKey=key;}
      await Promise.all(views.map((view,index)=>{
        const hslView=index===1;
        return Plotly.react(view,[cloud(hslView),surface(l,hslView),sectionBoundary(l,hslView),grayAxis(hslView),frame(hslView),highlight(hslView)],layout(hslView),{responsive:true,displaylogo:false,scrollZoom:true});
      }));
      $('status').textContent=points.length.toLocaleString()+' linked samples · '+(section?'exact constant-lightness surface':'all RGB colors sampled')+' · L = '+l.toFixed(2);
      selectionInfo();
    } catch(error) {$('status').textContent='Could not render the laboratory: '+error.message;}
    finally {busy=false;if(pending){pending=false;render();}}
  }
  async function updateSelection() {
    // Serialize selection redraws with slider redraws, retaining the latest state.
    if(busy) {pending=true;return;}
    busy=true;
    try {
      await Promise.all(views.map((plot,index)=>{
        const position=coordinates(selected,index===1);
        return Plotly.restyle(plot,{
          x:[[position[0]]],y:[[position[1]]],z:[[position[2]]],
          'marker.color':cssColor(selected),'customdata':[[selected]]
        },[5]);
      }));
    } catch(error) {$('status').textContent='Could not update selection: '+error.message;}
    finally {busy=false;if(pending){pending=false;render();}}
  }
  async function initialize() {
    if(!window.Plotly) {$('status').textContent='Plotly could not load. Regenerate the laboratory assets using the Python script.';return;}
    await render();
    views.forEach(view=>view.on('plotly_click',event=>{
      const point=event.points && event.points[0];
      const rgb=point && point.customdata;
      if(!Array.isArray(rgb) || rgb.length!==3 || !rgb.every(Number.isFinite)) return;
      // A WebGL redraw can replay the picked point. Repeated selection is a no-op.
      if(rgb.every((value,index)=>value===selected[index])) return;
      selected=rgb.slice(); selectionInfo();
      // Leave Plotly's picking callback before changing either WebGL scene.
      clearTimeout(initialize.selectionTimer);
      initialize.selectionTimer=setTimeout(updateSelection,0);
    }));
    ['resolution','lightness'].forEach(id=>$(id).addEventListener('input',()=>{
      // Coalesce fast slider changes; limit costly WebGL cloud rebuilds.
      clearTimeout(initialize.timer);initialize.timer=setTimeout(render,100);
      $('resolution-value').textContent=$('resolution').value;
      $('lightness-value').textContent=Number($('lightness').value).toFixed(2);
    }));
    ['axes','section'].forEach(id=>$(id).addEventListener('change',render));
  }
  initialize();
})();
