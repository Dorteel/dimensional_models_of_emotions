'use strict';
const assert=require('assert'), C=require('./docs/color-space.js');
function near(a,b,tolerance=1e-10){assert(Math.abs(a-b)<tolerance, a+' differs from '+b);}
function vector(a,b){a.forEach((v,i)=>near(v,b[i]));}
const primaries=[[[1,0,0],0],[[1,1,0],60],[[0,1,0],120],[[0,1,1],180],[[0,0,1],240],[[1,0,1],300]];
primaries.forEach(pair=>vector(C.rgbToHsl(pair[0]),[pair[1],1,0.5]));
[0,0.2,0.5,1].forEach(l=>vector(C.rgbToHsl([l,l,l]),[0,0,l]));
C.cubePoints(11).forEach(rgb=>{
  const hsl=C.rgbToHsl(rgb);vector(C.hslToRgb(hsl),rgb);
  const pos=C.hslPosition(hsl);near(pos[2],hsl[2]);
  near(Math.hypot(pos[0],pos[1]),Math.max.apply(null,rgb)-Math.min.apply(null,rgb));
});
[0,0.01,0.2,1/3,0.5,2/3,0.8,0.99,1].forEach(l=>{
  const triangles=C.lightnessSurface(l);assert.strictEqual(triangles.length,6);
  // Vertices AND interior samples must obey the nonlinear lightness equation.
  const points=C.sectionPoints(l,18);
  points.forEach(rgb=>{
    rgb.forEach(v=>assert(v>=-1e-12&&v<=1+1e-12));near(C.rgbToHsl(rgb)[2],l);
  });
  triangles.forEach(triangle=>{
    for(let a=0;a<=4;a++)for(let b=0;b<=4-a;b++){
      const p=triangle[0].map((v,k)=>(1-a/4-b/4)*v+a/4*triangle[1][k]+b/4*triangle[2][k]);
      near(C.rgbToHsl(p)[2],l);
    }
  });
  if(l===0||l===1) assert.strictEqual(points.length,1);
});
assert.strictEqual(C.cubePoints(18).length,18**3);
[-1,2,NaN,Infinity].forEach(l=>assert.throws(()=>C.lightnessSurface(l)));
assert.throws(()=>C.sectionPoints(0.5,1));
const midpoint=C.lightnessSurface(0.5);
assert(midpoint.some(triangle=>Math.abs(triangle[1].reduce((a,b)=>a+b,0)-1.5)>0.1));
console.log('Color conversion, 1,331 round trips, embedding, nine exact sections, endpoints, and validation passed.');
