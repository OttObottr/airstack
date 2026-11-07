// spec: AS-256 AS-257
/* A squarified treemap (Bruls, Huizing and van Wijk), laid out as d3-hierarchy's treemap was configured here: aspect ratio 1.2, 2 px
   between tiles, whole pixels. Values come largest first; it returns [x0, y0, x1, y1] for each, in the same order. Each row runs along
   the shorter side and takes tiles while its worst aspect ratio does not get worse. */
export function squarify(values, W, H, ratio = 1.2, gap = 2) {
  const out = [],
    n = values.length,
    p = gap / 2;
  let x0 = -p,
    y0 = -p,
    x1 = W + p,
    y1 = H + p,
    value = values.reduce((s, v) => s + v, 0),
    i0 = 0,
    i1 = 0;
  while (i0 < n) {
    const dx = x1 - x0,
      dy = y1 - y0;
    let sum, v, min, max;
    do sum = values[i1++];
    while (!sum && i1 < n);
    min = max = sum;
    const alpha = Math.max(dy / dx, dx / dy) / (value * ratio);
    let beta = sum * sum * alpha,
      worst = Math.max(max / beta, beta / min);
    for (; i1 < n; ++i1) {
      sum += v = values[i1];
      if (v < min) min = v;
      if (v > max) max = v;
      beta = sum * sum * alpha;
      const w = Math.max(max / beta, beta / min);
      if (w > worst) {
        sum -= v;
        break;
      }
      worst = w;
    }
    if (dx < dy) {
      /* a row across the top */
      const ya = y0,
        yb = dx ? (y0 += (dy * sum) / value) : y1,
        k = sum && (x1 - x0) / sum;
      for (let i = i0, x = x0; i < i1; i++) out.push([x, ya, (x += values[i] * k), yb]);
    } else {
      /* a column down the left */
      const xa = x0,
        xb = dx ? (x0 += (dx * sum) / value) : x1,
        k = sum && (y1 - y0) / sum;
      for (let i = i0, y = y0; i < i1; i++) out.push([xa, y, xb, (y += values[i] * k)]);
    }
    value -= sum;
    i0 = i1;
  }
  return out.map(([a, b, c, d]) => {
    /* half the gap off each side, never inside out, then whole pixels */
    a += p;
    b += p;
    c -= p;
    d -= p;
    if (c < a) a = c = (a + c) / 2;
    if (d < b) b = d = (b + d) / 2;
    return [Math.round(a), Math.round(b), Math.round(c), Math.round(d)];
  });
}
