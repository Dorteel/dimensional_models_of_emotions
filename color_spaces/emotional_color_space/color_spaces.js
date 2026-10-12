/* Pure HSV geometry and label serialization; usable in browsers and Node. */
(function (root) {
  'use strict';
  function validate(h, s, v) {
    if (![h,s,v].every(Number.isFinite) || s<0 || s>1 || v<0 || v>1)
      throw new Error('HSV requires finite hue and saturation/value in [0,1].');
  }
  const normalizeHue = h => ((h % 360) + 360) % 360;
  function hsvToRgb(h, s, v) {
    validate(h,s,v);
    const sector=normalizeHue(h)/60, c=v*s;
    const x=c*(1-Math.abs(sector%2-1)), m=v-c;
    return [[c,x,0],[x,c,0],[0,c,x],[0,x,c],[x,0,c],[c,0,x]][Math.floor(sector)].map(channel=>channel+m);
  }
  function hsvPosition(h, s, v) {
    validate(h,s,v);
    const sector=normalizeHue(h)/60, index=Math.floor(sector), fraction=sector-index;
    const a=index*Math.PI/3, b=(index+1)*Math.PI/3;
    // Linear interpolation on a regular hexagon edge, not on a circular arc.
    // Hue is the sector parameter; its Euclidean polar angle is not exactly H.
    return [s*v*((1-fraction)*Math.cos(a)+fraction*Math.cos(b)),
            s*v*((1-fraction)*Math.sin(a)+fraction*Math.sin(b)),v];
  }
  function hexagon(s,v) {
    return Array.from({length:6},(_,i)=>hsvPosition(i*60,s,v));
  }
  function cssColor(h,s,v) {
    return 'rgb('+hsvToRgb(h,s,v).map(c=>Math.round(255*c)).join(',')+')';
  }
  function validateLabels(data) {
    if (!data || data.version!==1 || !data.labels || typeof data.labels!=='object' || Array.isArray(data.labels))
      throw new Error('Expected {"version":1,"labels":{"120":"your emotion"}}.');
    const labels=Object.create(null);
    Object.keys(data.labels).forEach(key=>{
      const hue=Number(key), value=data.labels[key];
      if (!/^\d+$/.test(key) || !Number.isInteger(hue) || hue<0 || hue>=360 || String(hue)!==key ||
          typeof value!=='string' || !value.trim() || value.length>120)
        throw new Error('Labels require integer hues 0–359 and names of 1–120 characters.');
      labels[key]=value.trim();
    });
    return labels;
  }
  function importLabels(json) {return validateLabels(JSON.parse(json));}
  function exportLabels(labels) {
    const data={version:1,labels:labels};validateLabels(data);return JSON.stringify(data,null,2);
  }
  const api={normalizeHue,hsvToRgb,hsvPosition,hexagon,cssColor,importLabels,exportLabels};
  if(typeof module!=='undefined')module.exports=api;
  root.EmotionalColors=api;
})(typeof window!=='undefined'?window:global);
