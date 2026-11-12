
(() => {
  const M = (window.RS_DATA || {}).model;
  if (!M) return;
  const { model, base } = M;
  const F = base.features;
  const N = base.ids.length;
  const fi = Object.fromEntries(F.map((f, i) => [f, i]));

  function predictRow(x) {
    let raw = model.base;
    for (const t of model.trees) {
      let k = 0;
      while (!t.leaf[k]) {
        const v = x[t.f[k]];
        const left = Number.isNaN(v) ? t.m[k] === 1 : v <= t.t[k];
        k = left ? t.l[k] : t.r[k];
      }
      raw += t.v[k];
    }
    return 1 / (1 + Math.exp(-raw));
  }
  const toAlarm = (r) => 1 / (1 + Math.exp(-(Math.log(r + 1e-9) - Math.log(base.threshold)) * 1.6));
  const riverRisk = (h, e) => (e > 0 ? e / (1 + Math.exp(-(h - 2.0) / 0.25)) : 0);

  function hav(a, b, c, d) {
    const r = Math.PI / 180, p1 = a * r, p2 = c * r;
    const x = Math.sin((p2 - p1) / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin((d - b) * r / 2) ** 2;
    return 2 * 6371 * Math.asin(Math.sqrt(x));
  }

  function compute(p, centers) {
    const t0 = performance.now();
    const out = { total: [], flood: [], flash: [], river: [], heat: [], wind: [], ice: [], p1: [], p3: [], gust: [], trail: [], why: [], h3: [] };
    const x = new Array(F.length).fill(0);
    for (let i = 0; i < N; i++) {
      const c = centers[i];
      const d = p.lat == null ? 1e9 : hav(p.lat, p.lon, c[0], c[1]);
      const r3 = p.rain * Math.exp(-((d / p.radius) ** 2)) * (1 + p.climate / 100) + 3;
      const v = { p1: r3 * 0.45, p3: r3, p7: r3 + 6, p_ante30: p.soil, p3_extreme: r3 / base.q99[i] };
      for (const f of F) x[fi[f]] = f in v ? v[f] : base.static[f][i];
      const sA = toAlarm(predictRow(x));

      const hLoc = p.scope === "odra" ? (base.hriver[i] === "ODRA" ? p.river : 0)
        : (p.lat == null ? 0 : p.river * Math.exp(-((d / (2 * p.radius)) ** 2)));
      const sB = riverRisk(hLoc, base.exposure[i]);
      const w = 1 - (1 - sA) * (1 - sB);
      out.total.push(w); out.flood.push(w); out.flash.push(sA); out.river.push(sB);
      out.heat.push(0); out.wind.push(0); out.ice.push(0);
      out.p1.push(+(r3 * 0.45).toFixed(1)); out.p3.push(+r3.toFixed(1));
      out.gust.push(0); out.trail.push(0); out.h3.push(base.exposure[i] > 0 ? +hLoc.toFixed(2) : -9);
      const why = [];
      if (sB > 0.3) why.push(["stan wody w rzece (IMGW) – fala wezbraniowa", +sB.toFixed(3)]);
      if (sA > 0.3) why.push(["opad 3-dniowy (symulacja)", +Math.min(1, r3 / 300).toFixed(3)],
                             ["uwilgotnienie gruntu", +Math.min(1, p.soil / 200).toFixed(3)]);
      out.why.push(why);
    }
    out.ms = performance.now() - t0;
    return out;
  }

  window.RS_SIM = { compute, trees: model.trees.length, n: N };
})();
