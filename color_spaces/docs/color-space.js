/* Pure geometry shared by the browser and Node tests. */
(function (root) {
  'use strict';
  function rgbToHsl(rgb) {
    const max = Math.max.apply(null, rgb), min = Math.min.apply(null, rgb);
    const c = max - min, l = (max + min) / 2;
    if (c === 0) return [0, 0, l]; // Achromatic hue is undefined; convention: 0.
    let h;
    if (max === rgb[0]) h = ((rgb[1] - rgb[2]) / c) % 6;
    else if (max === rgb[1]) h = (rgb[2] - rgb[0]) / c + 2;
    else h = (rgb[0] - rgb[1]) / c + 4;
    return [(h * 60 + 360) % 360, c / (1 - Math.abs(2 * l - 1)), l];
  }
  function hslToRgb(hsl) {
    const h = hsl[0] / 60, l = hsl[2];
    const c = hsl[1] * (1 - Math.abs(2 * l - 1));
    const x = c * (1 - Math.abs(h % 2 - 1)), m = l - c / 2;
    const sectors = [[c,x,0], [x,c,0], [0,c,x], [0,x,c], [x,0,c], [c,0,x]];
    return sectors[((Math.floor(h) % 6) + 6) % 6].map(v => v + m);
  }
  function hslPosition(hsl) {
    const angle = hsl[0] * Math.PI / 180;
    const radius = hsl[1] * (1 - Math.abs(2 * hsl[2] - 1));
    return [radius * Math.cos(angle), radius * Math.sin(angle), hsl[2]];
  }
  function cubePoints(n) {
    if (!Number.isInteger(n) || n < 2) throw Error('Resolution must be at least 2');
    const points = [];
    for (let r = 0; r < n; r++) for (let g = 0; g < n; g++) for (let b = 0; b < n; b++)
      points.push([r, g, b].map(v => v / (n - 1)));
    return points;
  }
  // Each ordered-channel region is a triangle: min=L-C/2, max=L+C/2.
  const orders = [[0,1,2],[0,2,1],[1,0,2],[1,2,0],[2,0,1],[2,1,0]];
  function lightnessSurface(l) {
    if (!Number.isFinite(l) || l < 0 || l > 1) throw Error('Lightness must be in [0,1]');
    const extent = Math.min(l, 1-l), low = l-extent, high = l+extent;
    return orders.map(order => {
      function ordered(values) {
        const rgb = [0,0,0]; order.forEach((axis,i) => {rgb[axis] = values[i];}); return rgb;
      }
      return [[l,l,l], ordered([low,low,high]), ordered([low,high,high])];
    });
  }
  function sectionPoints(l, n) {
    if (!Number.isInteger(n) || n < 2) throw Error('Resolution must be at least 2');
    const points = [], seen = new Set();
    lightnessSurface(l).forEach(triangle => {
      for (let i=0; i<n; i++) for (let j=0; j<n-i; j++) {
        const a=i/(n-1), b=j/(n-1);
        const rgb=triangle[0].map((v,k) => (1-a-b)*v+a*triangle[1][k]+b*triangle[2][k]);
        const key=rgb.map(v => v.toFixed(12)).join(',');
        if (!seen.has(key)) {seen.add(key); points.push(rgb);}
      }
    });
    return points;
  }
  const api={rgbToHsl,hslToRgb,hslPosition,cubePoints,lightnessSurface,sectionPoints};
  if (typeof module !== 'undefined') module.exports=api;
  root.ColorSpace=api;
})(typeof window !== 'undefined' ? window : global);
