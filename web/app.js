
(() => {
  const D = window.RS_DATA || {};
  const SEG = D.segments || [];
  const HZ = { flood: "Woda: podmycie lub fala", heat: "Wyboczenie toru (upał)", wind: "Wiatr: drzewa na torze", ice: "Oblodzenie sieci" };
  const HZS = { flood: "woda", heat: "upał", wind: "wiatr", ice: "oblodzenie" };
  const ACTION = {
    flood: "obchód toru i kontrola przepustów, mostów i nasypów przed pierwszym pociągiem; gotowość pociągu sieciowego i sprzętu do zabezpieczenia skarp; przy fali wezbraniowej – obserwacja filarów mostów i usuwanie spływającego drewna",
    heat: "kontrola geometrii toru w godz. 13–19, szczególnie na odcinkach po robotach torowych",
    wind: "gotowość brygad do usuwania powalonych drzew; objazd linii po przejściu frontu przed wznowieniem ruchu",
    ice: "kursy pociągów odladzających sieć trakcyjną; rozważenie trakcji spalinowej na odcinkach krytycznych",
  };
  const ALARM = 0.5, WARN = 0.3;

  const kmf = (k) => k.toFixed(1).replace(".", ",");
  const kmTxt = (sg) => (sg.km ? `km ${kmf(sg.km[0])}–${kmf(sg.km[1])}` : "");
  const odDo = (sg) => (sg.od && sg.do && sg.od !== sg.do ? `${sg.od} – ${sg.do}` : sg.od || sg.place || "");
  const segTitle = (sg) => `Linia ${sg.line}${sg.km ? " · " + kmTxt(sg) : sg.place ? " · " + sg.place : ""}`;
  const VIEWS = { live: [[52.0, 19.3], 6], line: [[52.0, 19.3], 6], heat: [[52.0, 19.3], 6],
    replay2024: [[50.55, 16.95], 8], y1997: [[50.85, 17.45], 8], sim: [[50.45, 16.9], 9] };

  const st = { mode: "live", hz: "total", day: 0, issue: 3, rain: false,
    sim: { lat: null, lon: null, rain: 180, radius: 35, soil: 80, river: 0.5, climate: 0 } };
  let simRisk = null, simBase = null;
  const $ = (s) => document.querySelector(s);
  const pct = (v) => Math.round(v * 100) + "%";
  const isDark = () => document.documentElement.dataset.theme === "dark";
  const mobile = () => matchMedia("(max-width: 860px)").matches;

  const map = L.map("map", { zoomControl: false, zoomSnap: 0.25, preferCanvas: true, attributionControl: true }).setView([52.0, 19.3], 6);
  map.attributionControl.setPrefix('<a href="https://leafletjs.com" target="_blank" rel="noopener">Leaflet</a>');
  window.RS_MAP = map;
  let tiles;
  function setTiles() {
    if (tiles) map.removeLayer(tiles);
    const base = isDark() ? "World_Dark_Gray_Base" : "World_Light_Gray_Base";
    tiles = L.tileLayer(`https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/${base}/MapServer/tile/{z}/{y}/{x}`, {
      attribution: "Podkład: Esri, HERE, Garmin, © OpenStreetMap · Linie: © OpenStreetMap (ODbL)", maxZoom: 16,
    }).addTo(map);
  }
  setTiles();

  const side = $("#side"), app = $("#app");
  let sheet = "half";
  const sheetPx = () => (mobile() ? sheetHeights()[sheet] : 0);
  const pad = () => (mobile() ? { paddingTopLeft: [10, 110], paddingBottomRight: [10, sheetPx() + 10] }
    : { paddingTopLeft: [400, 90], paddingBottomRight: [30, 30] });
  const PL = [[49.0, 14.1], [54.85, 24.15]];
  const NATIONAL = ["live", "line", "heat"];
  function goView(mode) {
    if (NATIONAL.includes(mode)) { map.flyToBounds(PL, { ...pad(), duration: 0.9 }); return; }
    const v = VIEWS[mode]; if (!v) return;
    const off = mobile() ? [0, (sheetPx() - 70) / 2] : [-190, -20];
    const c = map.project(L.latLng(v[0]), v[1]).add(L.point(off));
    map.flyTo(map.unproject(c, v[1]), v[1], { duration: 0.9 });
  }

  const color = (v) => {
    const stops = [[0, [43, 182, 115]], [0.3, [255, 210, 63]], [0.5, [255, 138, 0]], [0.75, [229, 72, 77]], [1, [163, 19, 58]]];
    for (let i = 1; i < stops.length; i++) {
      if (v <= stops[i][0]) {
        const [a, ca] = stops[i - 1], [b, cb] = stops[i], t = (v - a) / (b - a);
        return `rgb(${ca.map((c, k) => Math.round(c + t * (cb[k] - c))).join(",")})`;
      }
    }
    return "rgb(163,19,58)";
  };
  const lowCol = () => (isDark() ? "#4f6680" : "#8d9bb0");

  const layers = SEG.map((s, i) => {
    const pl = L.polyline(s.g, { weight: 2, opacity: 0.9, color: "#888" }).addTo(map);
    pl.on("click", (e) => openPopup(i, e.latlng));
    return pl;
  });
  const dmgLayer = L.layerGroup().addTo(map);
  map.createPane("rainPane"); map.getPane("rainPane").style.zIndex = 350;
  const rainLayer = L.layerGroup().addTo(map);
  const simLayer = L.layerGroup().addTo(map);
  const lineLayer = L.layerGroup().addTo(map);
  const centers = SEG.map((s) => { const b = L.polyline(s.g).getBounds().getCenter(); return [b.lat, b.lng]; });

  function view() {
    if (st.mode === "sim") return simRisk ? { days: ["sim"], risk: { sim: simRisk }, meta: { title: "Symulator" } } : null;
    const m = st.mode === "line" ? D.live : D[st.mode];
    if (!m) return null;
    if (st.mode === "replay2024") {
      const iss = m.issues[Math.min(st.issue, m.issues.length - 1)];
      return { days: iss.days, risk: iss.risk, issued: iss.issued, meta: m.meta };
    }
    return { days: m.days, risk: m.risk, meta: m.meta };
  }
  const cur = () => {
    if (st.mode === "sim") return simRisk;
    const v = view(); return v && v.risk[v.days[Math.min(st.day, v.days.length - 1)]];
  };

  const today = () => new Date().toLocaleDateString("sv-SE");
  const isLive = () => st.mode === "live" || st.mode === "line";
  const ageH = (v) => {
    const g = v && v.meta && (v.meta.generated || (v.meta.issued && v.meta.issued + " 12:00"));
    return g ? (Date.now() - new Date(g.replace(" ", "T")).getTime()) / 36e5 : 0;
  };
  const stale = (v) => isLive() && v && v.meta && ageH(v) > 30;
  const qOf = (r, i) => (r && r.q ? r.q[i] : 0);
  function confidence(r, i) {
    if (qOf(r, i) === 2) return { lvl: "brak", txt: "ocena niedostępna – brak danych pogodowych" };
    if (st.mode === "sim") return { lvl: "symulacja", txt: "scenariusz symulacji, nie prognoza" };
    if (st.mode === "y1997" || st.mode === "heat") return { lvl: "test historyczny", txt: "reanaliza – pogoda znana po fakcie" };
    if (stale(view())) return { lvl: "niska", txt: "prognoza nieaktualna – nie opieraj się na niej" };
    const L = ["wysoka", "średnia", "niższa"];
    let k = Math.min(st.day, 2);
    let txt = ["prognoza na dziś", "prognoza na jutro", "prognoza na pojutrze"][k];
    if (qOf(r, i) === 1) { k = Math.min(k + 1, 2); txt += "; brak aktualnego stanu wody z wodowskazu"; }
    return { lvl: L[k], txt };
  }
  const DECIDE = "Decyzję o działaniach podejmuje uprawniony pracownik zgodnie z obowiązującymi procedurami. RailSentinel wspiera ocenę zagrożenia i nie zastępuje procedur ani ostrzeżeń IMGW.";
  const STALE_TXT = "Dane nieaktualne: brak alarmu NIE oznacza braku zagrożenia. Postępuj według standardowych procedur i ostrzeżeń IMGW.";
  let RANK = {}, NWARN = 0;

  const domHz = (r, i) => ["flood", "heat", "wind", "ice"].reduce((a, h) => (r[h][i] > r[a][i] ? h : a), "flood");

  function render() {
    $("#simCtrl").hidden = st.mode !== "sim";
    $("#lineCtrl").hidden = st.mode !== "line";
    $("#daysCtrl").hidden = st.mode === "sim";
    $("#statusCard").hidden = st.mode === "line";
    $("#hzCtrl").hidden = st.mode === "sim" || st.mode === "line";
    $("#topBox").hidden = st.mode === "line";
    $("#issueCtrl").hidden = st.mode !== "replay2024";
    if (st.mode === "sim") runSim();
    const v = view(), r = cur();
    renderStory(v);
    if (!r) { $("#top").innerHTML = "<li class='empty'>Brak danych dla tego widoku.</li>"; return; }
    renderView(v, r);
  }

  function renderView(v, r) {
    $("#days").innerHTML = v.days.length > 1 ? v.days.map((d, k) =>
      `<button data-d="${k}" class="${k === st.day ? "on" : ""}">${dayLbl(d, k)}</button>`).join("") : "";
    if (st.mode === "replay2024") renderTimeline(v, r);

    const vals = r[st.hz];
    const low = lowCol();
    layers.forEach((pl, i) => {
      const x = vals[i] || 0;
      if (qOf(r, i) === 2) { pl.setStyle({ color: "#8a94a3", weight: 2, opacity: 0.6, dashArray: "2 6" }); return; }
      pl.setStyle({ dashArray: null });
      pl.setStyle(x >= WARN ? { color: color(x), weight: x >= ALARM ? 5 : 3.5, opacity: 1 }
        : x >= 0.12 ? { color: color(x), weight: 2.2, opacity: 0.8 } : { color: low, weight: 1.6, opacity: 0.7 });
    });
    layers.forEach((pl, i) => { if ((vals[i] || 0) >= WARN) pl.bringToFront(); });

    dmgLayer.clearLayers();
    const dmg = st.mode === "replay2024" ? new Set(D.replay2024.damaged) : new Set();
    $("#lgDmg").style.display = dmg.size ? "flex" : "none";
    const ink = getComputedStyle(document.documentElement).getPropertyValue("--ink");
    SEG.forEach((s) => { if (dmg.has(s.id)) L.polyline(s.g, { color: ink, weight: 9, opacity: 0.5, dashArray: "4 7", interactive: false }).addTo(dmgLayer); });

    const idx = vals.map((x, i) => [x, i]).sort((a, b) => b[0] - a[0]);
    const alarm = idx.filter(([x]) => x >= ALARM), warn = idx.filter(([x]) => x >= WARN && x < ALARM);
    RANK = {}; idx.forEach(([x, i], k) => { if (x >= WARN) RANK[i] = k + 1; }); NWARN = alarm.length + warn.length;
    $("#kAlarm").textContent = alarm.length.toLocaleString("pl-PL");
    $("#kAlarmLbl").textContent = alarm.length === 1 ? "odcinek w alarmie" : "odcinków w alarmie";
    $("#kWarn").textContent = warn.length.toLocaleString("pl-PL");
    $("#kKm").textContent = Math.round(alarm.reduce((a, [, i]) => a + SEG[i].len, 0)).toLocaleString("pl-PL");
    $("#statusCard").className = "status " + (alarm.length ? "" : warn.length ? "warn" : "ok");

    const list = idx.filter(([x]) => x >= 0.15).slice(0, 8);
    $("#top").innerHTML = list.length ? list.map(([x, i]) => {
      const s = SEG[i], h = st.hz === "total" ? domHz(r, i) : st.hz;
      return `<li data-i="${i}"><span class="pill" style="background:${color(x)}">${Math.round(x * 100)}</span>
        <span class="t"><b>${segTitle(s)}${dmg.has(s.id) ? " <span class='tag r'>zniszczony</span>" : ""}</b>
        <small>${s.km ? odDo(s) + " · " : ""}${HZS[h]}${detail(h, r, i)}${s.river ? " · dolina " + s.river : ""}</small></span></li>`;
    }).join("") : `<li class="empty">Brak odcinków z podwyższonym ryzykiem w tym dniu. ✓</li>`;

    renderBrief(v, r, alarm.map(([, i]) => i), warn.map(([, i]) => i));
    renderRain(r);
    if (st.mode === "line") renderLine();
    const stt = v.meta && v.meta.status;
    const nq2 = r.q ? r.q.filter((q) => q === 2).length : 0;
    $("#updChip").classList.toggle("stale", !!stale(v));
    $("#updChip").innerHTML = isLive()
      ? (stale(v) ? `⚠ <b>Prognoza nieaktualna</b> (z ${fmtDay(v.meta.issued, 0, true)}). ${STALE_TXT}`
        : `Prognoza wydana <b>${fmtDay(v.meta.issued || v.days[0], 0, true)}</b>${v.meta.generated ? " " + v.meta.generated.slice(11) : ""}` +
          `<span class="hm">${stt ? ` · IMGW: ${stt.gauges ? stt.gauges + " wodowskazów" : "<b>brak danych</b>"}` : ""}` +
          `${nq2 ? ` · ${nq2} odc. bez oceny` : ""}</span>`) : "";
    $("#statusCard").classList.toggle("stale", !!stale(v));
  }
  function detail(h, r, i) {
    if (h === "flood") return r.river && r.flash && r.river[i] > r.flash[i] ? " · fala na rzece" : ` · opad 3 doby ${Math.round(r.p3[i])} mm`;
    if (h === "heat") return ` · szyna ${Math.round(r.trail[i])} °C`;
    if (h === "wind") return ` · porywy ${Math.round(r.gust[i])} km/h`;
    if (h === "ice") return " · marznący opad";
    return "";
  }

  function renderTimeline(v, r) {
    $("#issueLbl").textContent = fmtDay(v.issued, -1, true) + " wieczorem";
    const dmg = D.replay2024.damaged.map((id) => SEG.findIndex((s) => s.id === id)).filter((i) => i >= 0);

    const n = dmg.filter((i) => v.days.some((d) => v.risk[d].total[i] >= ALARM)).length;
    $("#tlStat").innerHTML = `zniszczone odcinki z alarmem: <b>${n}/${dmg.length}</b>`;
  }

  const LS = { get: (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } },
               set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {  } } };
  const byLine = {};
  SEG.forEach((s, i) => { (byLine[s.line] = byLine[s.line] || []).push(i); });
  const lineNames = Object.keys(byLine).filter((l) => l !== "bn").sort((a, b) => (+a || 9999) - (+b || 9999));
  $("#lineList").innerHTML = lineNames.map((l) => {
    const pl = [...new Set(byLine[l].map((i) => SEG[i].place).filter(Boolean))];
    return `<option value="${l}">${pl.slice(0, 1).join("")}${pl.length > 1 ? " – " + pl[pl.length - 1] : ""}</option>`;
  }).join("");
  st.line = LS.get("rs_line") || "";
  $("#lineInput").value = st.line;
  function lineOrder(ii) {
    if (ii.filter((i) => SEG[i].km).length >= ii.length * 0.8)
      return [...ii].sort((a, b) => (SEG[a].km ? SEG[a].km[0] : 1e9) - (SEG[b].km ? SEG[b].km[0] : 1e9));
    const c = ii.map((i) => centers[i]);
    const mx = c.reduce((a, p) => a + p[1], 0) / c.length, my = c.reduce((a, p) => a + p[0], 0) / c.length;
    let sxx = 0, syy = 0, sxy = 0;
    c.forEach(([y, x]) => { sxx += (x - mx) ** 2; syy += (y - my) ** 2; sxy += (x - mx) * (y - my); });
    const ang = 0.5 * Math.atan2(2 * sxy, sxx - syy);
    return ii.map((i, k) => [i, (c[k][1] - mx) * Math.cos(ang) + (c[k][0] - my) * Math.sin(ang)]).sort((a, b) => a[1] - b[1]).map((x) => x[0]);
  }
  function renderLine(fit) {
    const v = view();
    lineLayer.clearLayers();
    if (!v) { $("#lineStatus").innerHTML = "Brak prognozy."; return; }
    const ii = byLine[st.line];
    if (!ii) {
      $("#lineStatus").className = "linestatus";
      $("#lineStatus").innerHTML = st.line ? `Nie znam linii „${st.line}”. Wybierz numer z listy albo użyj 📍.` :
        "Wpisz numer swojej linii albo kliknij <b>📍 Gdzie jestem</b>. Pokażę zagrożenia dla każdego jej odcinka na 3 dni.";
      $("#lineTable").innerHTML = ""; return;
    }
    const ord = lineOrder(ii);
    let worst = { x: -1 };
    v.days.forEach((d) => ord.forEach((i) => { const r = v.risk[d]; if (r.total[i] > worst.x) worst = { x: r.total[i], d, i, h: domHz(r, i) }; }));
    const lvl = worst.x >= ALARM ? "alarm" : worst.x >= WARN ? "warn" : "ok";
    const km = Math.round(ord.reduce((a, i) => a + SEG[i].len, 0));
    const places = [...new Set(ord.map((i) => SEG[i].place).filter(Boolean))];
    $("#lineStatus").className = "linestatus " + lvl;
    $("#lineStatus").innerHTML = `<b class="big">Linia ${st.line}: ${lvl === "alarm" ? "ALARM" : lvl === "warn" ? "UWAGA" : "bez zagrożeń"}</b>
      <span class="muted">${places[0] || ""}${places.length > 1 ? " – " + places[places.length - 1] : ""} · ${km} km toru</span><br>
      ${lvl === "ok" ? "W ciągu 72 h brak zagrożeń pogodowych powyżej progu uwagi." :
        `Najwyższe ryzyko <b>${pct(worst.x)}</b>: ${HZ[worst.h].toLowerCase()}, ${fmtDay(worst.d)}, ${kmTxt(SEG[worst.i]) ? kmTxt(SEG[worst.i]) + " (" + odDo(SEG[worst.i]) + ")" : "rejon " + (SEG[worst.i].place || "?")}.<br><i>Do rozważenia (decyzja: uprawniony pracownik):</i> ${ACTION[worst.h]}.`}`;
    $("#lineTable").innerHTML = `<table class="ltab"><tr><th>Odcinek</th>${v.days.map((d, k) => `<th class="c">${dayLbl(d, k)}</th>`).join("")}</tr>` +
      ord.map((i) => `<tr data-i="${i}"><td>${odDo(SEG[i]) || "–"}${SEG[i].km ? ` <span class="muted small">· ${kmTxt(SEG[i])}</span>` : ""}${SEG[i].river ? ` <span class="muted small">· ${SEG[i].river}</span>` : ""}</td>` +
        v.days.map((d) => { const x = v.risk[d].total[i]; return `<td class="c"><span class="chip" style="background:${color(x)}">${Math.round(x * 100)}</span></td>`; }).join("") + "</tr>").join("") + "</table>";
    $("#lineUpd").textContent = `prognoza z ${fmtDay(v.meta.issued || v.days[0])}`;
    ord.forEach((i) => L.polyline(SEG[i].g, { color: "#3b82f6", weight: 12, opacity: 0.3, interactive: false }).addTo(lineLayer));
    if (fit) map.fitBounds(L.featureGroup(ord.map((i) => layers[i])).getBounds(), { ...pad(), maxZoom: 11 });
    st.lineText = $("#lineStatus").innerText;
  }
  function setLine(l, fit = true) { st.line = String(l).trim(); LS.set("rs_line", st.line); $("#lineInput").value = st.line; render(); renderLine(fit); }
  $("#lineInput").addEventListener("change", (e) => setLine(e.target.value));
  $("#lineTable").addEventListener("click", (e) => { const tr = e.target.closest("tr[data-i]"); if (tr) focusSeg(+tr.dataset.i); });
  $("#geoBtn").addEventListener("click", () => {
    if (!navigator.geolocation) { alert("Ta przeglądarka nie udostępnia lokalizacji."); return; }
    $("#geoBtn").textContent = "⏳ Szukam…";
    navigator.geolocation.getCurrentPosition((pos) => {
      $("#geoBtn").textContent = "📍 Gdzie jestem";
      const { latitude: la, longitude: lo } = pos.coords;
      let best = [1e9, 0];
      centers.forEach((c, i) => { const d = (c[0] - la) ** 2 + ((c[1] - lo) * Math.cos(la * Math.PI / 180)) ** 2; if (d < best[0]) best = [d, i]; });
      setLine(SEG[best[1]].line);
      L.circleMarker([la, lo], { radius: 7, color: "#fff", weight: 2, fillColor: "#3b82f6", fillOpacity: 1 }).addTo(lineLayer);
    }, () => { $("#geoBtn").textContent = "📍 Gdzie jestem"; alert("Brak dostępu do lokalizacji – wpisz numer linii."); }, { enableHighAccuracy: true, timeout: 10000 });
  });
  $("#shareBtn").addEventListener("click", async () => {
    const txt = `RailSentinel – ${st.lineText || ""}\n${location.origin + location.pathname}#mode=line&line=${st.line}`;
    try { if (navigator.share) await navigator.share({ title: "RailSentinel", text: txt }); else { await navigator.clipboard.writeText(txt); $("#shareBtn").textContent = "✓ Skopiowano"; } } catch (e) {  }
  });
  let deferred = null;
  window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); deferred = e; $("#installBtn").hidden = false; });
  $("#installBtn").addEventListener("click", async () => { if (!deferred) return; deferred.prompt(); await deferred.userChoice; deferred = null; $("#installBtn").hidden = true; });

  function renderRain(r) {
    rainLayer.clearLayers();
    if (!st.rain || !r || !r.p1) return;
    const cells = {};
    SEG.forEach((s, i) => { const c = s.cell || ""; (cells[c] = cells[c] || []).push(r.p1[i]); });
    for (const [c, arr] of Object.entries(cells)) {
      if (!c) continue;
      const [la, lo] = c.split(",").map(Number);
      const p = arr.reduce((a, b) => a + b, 0) / arr.length;
      if (p < 2) continue;
      L.rectangle([[la - 0.125, lo - 0.125], [la + 0.125, lo + 0.125]], {
        stroke: false, fillColor: "#3b82f6", fillOpacity: Math.min(0.5, p / 120), interactive: false, pane: "rainPane",
      }).addTo(rainLayer);
    }
  }

  function runSim() {
    if (!window.RS_SIM) return;
    const p = st.sim;
    simRisk = window.RS_SIM.compute(p, centers);
    simBase = p.climate > 0 ? window.RS_SIM.compute({ ...p, climate: 0 }, centers) : null;
    $("#vRain").textContent = p.rain + " mm"; $("#vRad").textContent = p.radius + " km";
    $("#vSoil").textContent = p.soil + " mm"; $("#vRiver").textContent = p.river.toFixed(1) + " × próg";
    $("#vClim").textContent = p.climate + "%";
    const cnt = (rr) => rr.total.filter((x) => x >= ALARM).length;
    const km = (rr) => Math.round(rr.total.reduce((a, x, i) => a + (x >= ALARM ? SEG[i].len : 0), 0));
    $("#climDelta").innerHTML = simBase
      ? `Przy opadach mocniejszych o ${p.climate}%: <b>${cnt(simRisk)}</b> odcinków w alarmie zamiast ${cnt(simBase)} – <b>+${km(simRisk) - km(simBase)} km</b> toru do sprawdzenia.` : "";
    $("#simHint").innerHTML = (p.lat == null ? "Kliknij na mapie, aby postawić ulewę. " : "") +
      `<span class="mlbadge">model ML liczy w przeglądarce · ${simRisk.ms.toFixed(0)} ms</span>`;
    simLayer.clearLayers();
    if (p.lat != null) {
      L.circle([p.lat, p.lon], { radius: p.radius * 1000, color: "#3b82f6", weight: 1, fillOpacity: 0.08, interactive: false }).addTo(simLayer);
      L.circle([p.lat, p.lon], { radius: p.radius * 450, color: "#3b82f6", weight: 1, dashArray: "3 4", fillOpacity: 0.12, interactive: false }).addTo(simLayer);
    }
  }
  const PRESETS = {
    "2024": { lat: 50.33, lon: 16.85, rain: 260, radius: 45, soil: 120, river: 3.0, climate: 0, scope: "storm", view: [50.45, 16.9, 9] },
    storm: { lat: 50.86, lon: 15.62, rain: 190, radius: 22, soil: 90, river: 0.8, climate: 0, scope: "storm", view: [50.88, 15.7, 10] },
    odra: { lat: null, lon: null, rain: 20, radius: 30, soil: 60, river: 3.2, climate: 0, scope: "odra", view: [51.0, 17.2, 8] },
    clear: { lat: null, lon: null, rain: 180, radius: 35, soil: 80, river: 0.5, climate: 0, scope: "storm" },
  };
  function syncSliders() {
    const p = st.sim;
    $("#sRain").value = p.rain; $("#sRad").value = p.radius; $("#sSoil").value = p.soil;
    $("#sRiver").value = Math.round(p.river * 10); $("#sClim").value = p.climate;
  }
  function presetView(vw) {
    if (!vw) return;
    const off = mobile() ? [0, (sheetPx() - 70) / 2] : [-190, -20];
    map.setView(map.unproject(map.project(L.latLng(vw[0], vw[1]), vw[2]).add(L.point(off)), vw[2]), vw[2]);
  }

  function renderStory(v) {
    const T = {
      live: ["Prognoza na żywo", v ? `Cała Polska, najbliższe 72 h · pogoda ECMWF/ICON i bieżące stany rzek IMGW` : ""],
      line: ["Moja linia", "Status Twojej linii na 3 dni. Działa też bez zasięgu."],
      replay2024: ["Powódź 2024 – czy system by ostrzegł?", "System widzi tylko prognozy wydane w tamtych dniach. Naciśnij ▶ i obserwuj."],
      sim: ["Symulator: co jeśli?", "Postaw ulewę, podnieś rzeki albo wzmocnij opady. Model ML przelicza ryzyko na żywo."],
      heat: [v ? v.meta.title.split("–")[0].trim() : "Upał", "Szacowana temperatura szyny. Powyżej ok. 50 °C rośnie ryzyko wyboczenia toru."],
      y1997: ["Powódź 1997 – test na nieznanych danych", "Model nie widział tej powodzi. Fala na Odrze – zobacz, gdzie zapala alarm."],
    }[st.mode];
    $("#story").innerHTML = `<h2>${T[0]}</h2><p>${T[1]}</p>`;
  }

  function renderBrief(v, r, alarm, warn) {
    const day = v.days[st.day];
    if (!alarm.length && !warn.length) {
      $("#brief").innerHTML = `<p><b>${fmtDay(day)}:</b> brak odcinków powyżej progu uwagi. Standardowy tryb utrzymania.</p>`;
      return;
    }
    const byHz = {};
    alarm.forEach((i) => { const h = st.hz === "total" ? domHz(r, i) : st.hz; (byHz[h] = byHz[h] || []).push(i); });
    const stt = v.meta && v.meta.status;
    let html = `<div class="proc"><b>Stan danych:</b> ${v.meta && v.meta.issued ? "prognoza wydana " + fmtDay(v.meta.issued) + (v.meta.generated ? ", " + v.meta.generated.slice(11) : "") : (v.meta && v.meta.title) || ""}` +
      `${stt ? `; IMGW: ${stt.gauges ? stt.gauges + " wodowskazów" : "brak danych – moduł fali nieaktywny"}; prognoza pogody: ${stt.cells_ok}/${stt.cells} punktów` : ""}.` +
      `${stale(v) ? `<br><b class="warnTxt">⚠ ${STALE_TXT}</b>` : ""}` +
      `<br><b>Jak czytać:</b> pozycje uszeregowane według priorytetu weryfikacji (1 = najpierw). Pewność oceny maleje z wyprzedzeniem prognozy.` +
      `<br><b>Kto decyduje:</b> ${DECIDE}</div>`;
    html += `<p><b>${fmtDay(day)}</b> – <span class="tag r">ALARM</span> ${alarm.length} odc. · <span class="tag o">UWAGA</span> ${warn.length} odc. · pewność oceny: ${confidence(r, alarm[0] ?? warn[0]).lvl}</p>`;
    for (const [h, list] of Object.entries(byHz)) {
      const lines = {};
      list.forEach((i) => { (lines[SEG[i].line] = lines[SEG[i].line] || []).push(i); });
      const items = Object.entries(lines).sort((a, b) => Math.min(...a[1].map((i) => RANK[i] || 1e9)) - Math.min(...b[1].map((i) => RANK[i] || 1e9))).slice(0, 8).map(([ln, ii]) => {
        const rivers = [...new Set(ii.map((i) => SEG[i].river).filter(Boolean))].slice(0, 2).join(", ");
        const places = [...new Set(ii.map((i) => SEG[i].place).filter(Boolean))].slice(0, 3).join(", ");
        const mx = Math.max(...ii.map((i) => r[h][i]));
        let det = "";
        if (h === "flood") {
          const riv = ii.filter((i) => r.river && r.river[i] > (r.flash ? r.flash[i] : 0));
          det = riv.length > ii.length / 2
            ? `fala wezbraniowa – stan wody ${Math.max(...riv.map((i) => r.h3[i])).toFixed(1)}× ponad poziom 1% najwyższych dni`
            : `opad 3-dobowy do ${Math.max(...ii.map((i) => r.p3[i])).toFixed(0)} mm`;
        }
        if (h === "heat") det = `szyna do ${Math.max(...ii.map((i) => r.trail[i])).toFixed(0)} °C`;
        if (h === "wind") det = `porywy do ${Math.max(...ii.map((i) => r.gust[i])).toFixed(0)} km/h`;
        if (h === "ice") det = `marznący opad do ${Math.max(...ii.map((i) => r.p1[i])).toFixed(1)} mm`;
        const kms = ii.filter((i) => SEG[i].km).sort((a, b) => SEG[a].km[0] - SEG[b].km[0]).slice(0, 4)
          .map((i) => `${kmTxt(SEG[i])} (${odDo(SEG[i])})`).join("; ");
        const pr = Math.min(...ii.map((i) => RANK[i] || 1e9));
        return `<li><b>Priorytet ${pr}</b> · <b>Linia ${ln}</b> (${ii.length} odc.${places ? ", " + places : ""}${rivers ? ", dolina " + rivers : ""}) – ${det}, ryzyko ${pct(mx)}` +
          `${kms ? `<br><span class="km">${kms}${ii.length > 4 ? " i inne" : ""}</span>` : ""}` +
          `</li>`;
      }).join("");
      html += `<p><b>${HZ[h]}</b></p><ul>${items}</ul><p><i>Działania do rozważenia przez uprawnionego pracownika:</i> ${ACTION[h]}.</p>`;
    }
    $("#brief").innerHTML = html;
  }

  function openPopup(i, latlng) {
    const v = view(), r = cur();
    if (!r) return;
    const s = SEG[i], h = domHz(r, i), x = r.total[i];
    const why = (r.why && r.why[i] || []).map(([k, val]) =>
      `<div>${k}<div class="bar"><i style="width:${Math.min(100, val * 250)}%"></i></div></div>`).join("");
    const dmg = st.mode === "replay2024" && D.replay2024.damaged.includes(s.id);
    const lead = st.mode === "replay2024" && D.replay2024.lead_hours_by_segment[s.id];
    const lvl = x >= ALARM ? "ALARM" : x >= WARN ? "UWAGA" : "niskie ryzyko";
    const cf = confidence(r, i);
    L.popup({ autoPanPadding: [30, 30], maxWidth: 340, maxHeight: mobile() ? Math.max(220, innerHeight - sheetPx() - 150) : undefined, autoPanPaddingTopLeft: mobile() ? [16, 112] : [400, 90], autoPanPaddingBottomRight: mobile() ? [16, sheetPx() + 16] : [30, 30] }).setLatLng(latlng).setContent(`<div class="pp">
      <h4>${segTitle(s)}</h4>
      <div class="sub">${s.km ? odDo(s) + " · " : ""}${s.river ? "dolina: " + s.river + " · " : ""}${s.elev} m n.p.m. · ${s.len.toFixed(1)} km · ${fmtDay(v.days[st.day])}</div>
      ${qOf(r, i) === 2 ? `<div class="act warnbox"><b>Ocena niedostępna</b> – brak danych pogodowych dla tego odcinka. To NIE oznacza niskiego ryzyka.</div>` : `
      <div class="score"><span class="pill" style="background:${color(x)}">${Math.round(x * 100)}</span><span><b>${lvl}</b>${RANK[i] ? ` · priorytet ${RANK[i]} z ${NWARN}` : ""}<br>główne zagrożenie: ${HZS[h]}</span></div>`}
      <div class="conf">Pewność oceny: <b>${cf.lvl}</b> – ${cf.txt}${v.meta && v.meta.generated ? ` · dane z ${v.meta.generated}` : ""}</div>
      <div class="grid">
        <div><small>Woda${r.flash ? " (ulewa / rzeka)" : ""}</small><b>${pct(r.flood[i])}</b>${r.flash ? ` <span class="muted small">${pct(r.flash[i])} / ${pct(r.river[i])}</span>` : ""}</div>
        <div><small>Opad 1 / 3 doby</small><b>${r.p1[i]} / ${r.p3[i]} mm</b></div>
        <div><small>Upał · szyna</small><b>${pct(r.heat[i])}</b> <span class="muted small">${r.trail[i]} °C</span></div>
        <div><small>Wiatr · porywy</small><b>${pct(r.wind[i])}</b> <span class="muted small">${r.gust[i]} km/h</span></div>
      </div>
      ${why ? `<div class="why"><b>Dlaczego? Wkład czynników do ryzyka</b>${why}</div>` : ""}
      ${x >= WARN ? `<div class="act"><b>Do rozważenia:</b> ${ACTION[h]}.<div class="dec">${DECIDE}</div></div>` : ""}
      ${stale(v) ? `<div class="act warnbox">⚠ ${STALE_TXT}</div>` : ""}
      ${dmg ? `<div class="why"><span class="tag r">Odcinek faktycznie zniszczony 09.2024</span>${lead ? ` – alarm ${lead} h przed zniszczeniem` : ""}</div>` : ""}
    </div>`).openOn(map);
  }
  function focusSeg(i) {
    if (mobile()) setSheet("peek");
    const b = layers[i].getBounds();
    map.fitBounds(b, { ...pad(), maxZoom: 11 });
    setTimeout(() => openPopup(i, b.getCenter()), 350);
  }

  function dayLbl(d, k) {
    if (st.mode === "live" || st.mode === "line") {
      const diff = Math.round((new Date(d + "T12:00:00") - new Date(today() + "T12:00:00")) / 864e5);
      return ({ "-1": "Wczoraj", 0: "Dziś", 1: "Jutro", 2: "Pojutrze" })[diff] || fmtDay(d, 0, true);
    }
    return fmtDay(d, 0, true);
  }
  function fmtDay(d, shift = 0, short = false) {
    if (d === "sim") return "symulacja";
    const x = new Date(d + "T12:00:00"); x.setDate(x.getDate() + shift);
    return x.toLocaleDateString("pl-PL", short ? { weekday: "short", day: "numeric", month: "short" }
      : { weekday: "short", day: "numeric", month: "short", year: "numeric" });
  }

  function setMode(m, fly = true) {
    st.mode = m;
    document.querySelectorAll("#modes button").forEach((x) => x.classList.toggle("on", x.dataset.mode === m));
    st.day = m === "replay2024" || m === "heat" || m === "y1997" ? 1 : 0;
    if ((m === "live" || m === "line") && D.live) st.day = Math.max(0, D.live.days.indexOf(today()));
    lineLayer.clearLayers(); simLayer.clearLayers();
    if (m === "sim" && st.sim.lat == null && st.sim.scope !== "odra") { Object.assign(st.sim, (({ view, ...x }) => x)(PRESETS["2024"])); syncSliders(); }
    if (fly && !(m === "line" && byLine[st.line])) goView(m);
    render();
    if (m === "line") setTimeout(() => renderLine(fly), 0);
    setSheet();
  }
  $("#modes").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) setMode(b.dataset.mode); });
  $("#hazards").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    document.querySelectorAll("#hazards button").forEach((x) => x.classList.toggle("on", x === b));
    st.hz = b.dataset.h; render();
  });
  $("#days").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { st.day = +b.dataset.d; render(); } });
  $("#issue").addEventListener("input", (e) => { st.issue = +e.target.value; render(); });
  $("#top").addEventListener("click", (e) => { const li = e.target.closest("li[data-i]"); if (li) focusSeg(+li.dataset.i); });
  map.on("click", (e) => { if (st.mode !== "sim") return; st.sim.lat = e.latlng.lat; st.sim.lon = e.latlng.lng; st.sim.scope = "storm"; render(); });
  const bind = (id, key, k = 1) => $(id).addEventListener("input", (e) => { st.sim[key] = +e.target.value / k; render(); });
  bind("#sRain", "rain"); bind("#sRad", "radius"); bind("#sSoil", "soil"); bind("#sRiver", "river", 10); bind("#sClim", "climate");
  $("#presets").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    const { view: vw, ...rest } = PRESETS[b.dataset.p];
    Object.assign(st.sim, rest); syncSliders(); presetView(vw); render();
  });
  let playing = null;
  const stopPlay = () => { clearInterval(playing); playing = null; $("#play").textContent = "▶"; };
  $("#play").addEventListener("click", () => {
    if (playing) { stopPlay(); return; }
    st.rain = true; $("#rainBtn").classList.add("on");
    st.issue = 0; st.day = 1; $("#issue").value = 0; render();
    $("#play").textContent = "❚❚";
    playing = setInterval(() => {
      if (st.issue >= D.replay2024.issues.length - 1) { stopPlay(); return; }
      st.issue++; $("#issue").value = st.issue; render();
    }, 1400);
  });
  $("#rainBtn").addEventListener("click", () => { st.rain = !st.rain; $("#rainBtn").classList.toggle("on", st.rain); render(); });
  const dlg = $("#briefDlg");
  $("#briefBtn").addEventListener("click", () => (dlg.showModal ? dlg.showModal() : dlg.setAttribute("open", "")));
  $("#closeDlg").addEventListener("click", () => dlg.close());
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });

  $("#print").addEventListener("click", () => {
    const v = view();
    const now = new Date().toLocaleString("pl-PL", { dateStyle: "long", timeStyle: "short" });
    $("#printArea").innerHTML = `<header><div><b>RailSentinel</b> · Raport dla dyżurnego ruchu</div><div>${v.meta.title || ""}</div></header>
      <p class="meta">Prognoza wydana: <b>${fmtDay(v.meta.issued || v.days[0])}</b> · wydruk: ${now} · widok: ${st.hz === "total" ? "wszystkie zagrożenia" : HZS[st.hz]}</p>
      <div class="body">${$("#brief").innerHTML}</div>
      <table class="sign"><tr><td>Przyjął (dyżurny / toromistrz)</td><td>Data i godzina</td><td>Podjęte działania</td></tr><tr><td></td><td></td><td></td></tr></table>
      <footer>RailSentinel wspiera ocenę zagrożenia i nie zastępuje obowiązujących procedur ani ostrzeżeń IMGW – decyzję podejmuje uprawniony pracownik. ` +
      `Kilometraż orientacyjny (OpenStreetMap). Prototyp studencki, nie jest systemem PKP PLK. railsentinel.pl</footer>`;
    window.print();
  });
  $("#copy").addEventListener("click", () => { navigator.clipboard && navigator.clipboard.writeText($("#brief").innerText); $("#copy").textContent = "✓ Skopiowano"; setTimeout(() => ($("#copy").textContent = "Kopiuj"), 1500); });
  $("#theme").addEventListener("click", () => {
    const r = document.documentElement;
    r.dataset.theme = isDark() ? "light" : "dark"; LS.set("rs_theme", r.dataset.theme); setTiles(); render();
  });
  function sheetHeights() {
    const H = innerHeight, sa = parseFloat(getComputedStyle(side).paddingBottom) || 14;
    const anchor = !$("#statusCard").hidden && $("#statusCard").offsetHeight ? $("#statusCard") : $("#story");
    const peek = Math.max(110, Math.min(H * 0.4, anchor.offsetTop + anchor.offsetHeight + sa));
    return { peek, half: Math.max(peek, H * 0.52), full: H - 66 };
  }
  function setSheet(s = sheet) {
    sheet = s;
    if (!mobile()) { app.style.removeProperty("--sh"); delete app.dataset.sheet; return; }
    app.style.setProperty("--sh", sheetHeights()[s] + "px");
    app.dataset.sheet = s;
    if (s === "peek") side.scrollTop = 0;
  }
  let drag = null;
  const hdr = (t) => t.closest("#grab, #story, #statusCard");
  side.addEventListener("touchstart", (e) => {
    if (!mobile() || !hdr(e.target)) return;
    drag = { y: e.touches[0].clientY, h: side.getBoundingClientRect().height, t: Date.now(), moved: false };
  }, { passive: true });
  side.addEventListener("touchmove", (e) => {
    if (!drag) return;
    const dy = drag.y - e.touches[0].clientY;
    if (!drag.moved && Math.abs(dy) < 6) return;
    drag.moved = true; e.preventDefault();
    side.classList.add("drag"); app.classList.add("drag-on");
    const S = sheetHeights();
    app.style.setProperty("--sh", Math.max(S.peek * 0.8, Math.min(S.full, drag.h + dy)) + "px");
  }, { passive: false });
  side.addEventListener("touchend", (e) => {
    if (!drag) return;
    side.classList.remove("drag"); app.classList.remove("drag-on");
    if (drag.moved) {
      const h = side.getBoundingClientRect().height, v = (h - drag.h) / Math.max(1, Date.now() - drag.t), S = sheetHeights();
      const target = h + v * 220;
      setSheet(Object.keys(S).reduce((a, k) => (Math.abs(S[k] - target) < Math.abs(S[a] - target) ? k : a), "half"));
    }
    drag = null;
  });
  $("#grab").addEventListener("click", () => setSheet({ peek: "half", half: "full", full: "peek" }[sheet]));
  map.on("dragstart", () => { if (mobile() && sheet !== "peek") setSheet("peek"); });
  addEventListener("resize", () => setSheet());

  const savedTheme = LS.get("rs_theme");
  if (savedTheme) { document.documentElement.dataset.theme = savedTheme; setTiles(); }
  if (D.replay2024) {
    const n = D.replay2024.issues.length;
    $("#issue").max = n - 1; st.issue = Math.min(4, n - 1); $("#issue").value = st.issue;
    $("#tlTicks").innerHTML = D.replay2024.issues.map((x) => `<span>${new Date(x.issued + "T12:00:00").getDate() - 1}.09</span>`).join("");
  }

  const hp = new URLSearchParams(location.hash.slice(1));
  if (hp.get("theme")) { document.documentElement.dataset.theme = hp.get("theme"); setTiles(); }
  if (hp.get("line")) { st.line = hp.get("line"); $("#lineInput").value = st.line; }
  if (hp.get("hz")) { st.hz = hp.get("hz"); document.querySelectorAll("#hazards button").forEach((x) => x.classList.toggle("on", x.dataset.h === st.hz)); }
  if (hp.get("rain")) { st.rain = true; $("#rainBtn").classList.add("on"); }
  if (hp.get("preset")) { const { view: vw, ...x } = PRESETS[hp.get("preset")]; Object.assign(st.sim, x); if (hp.get("clim")) st.sim.climate = +hp.get("clim"); syncSliders(); }
  const startMode = hp.get("mode") || (D.live ? "live" : "replay2024");
  if (hp.get("issue")) { st.issue = +hp.get("issue"); $("#issue").value = st.issue; }
  setMode(startMode, false);
  if (hp.get("day")) { st.day = +hp.get("day"); render(); }
  if (hp.get("lat")) map.setView([+hp.get("lat"), +hp.get("lon")], +(hp.get("z") || 9));
  else if (hp.get("preset")) presetView(PRESETS[hp.get("preset")].view);
  else if (startMode === "line" && byLine[st.line]) setTimeout(() => renderLine(true), 0);
  else if (NATIONAL.includes(startMode)) map.fitBounds(PL, pad());
  else { const v = VIEWS[startMode]; presetView([v[0][0], v[0][1], v[1]]); }
  window.addEventListener("load", () => map.invalidateSize());
  if (hp.get("popup")) setSheet("peek");
  if (hp.get("popup")) setTimeout(() => {
    map.invalidateSize();
    const r = cur();
    if (r) {
      const want = hp.get("seg") ? SEG.findIndex((x) => x.id === hp.get("seg")) : -1;
      const i = want >= 0 ? want : r[st.hz].reduce((b, x, k, a) => (x > a[b] ? k : b), 0);
      const c = layers[i].getBounds().getCenter();
      const z = +(hp.get("z") || 11);
      map.setView(c, z, { animate: false });
      const H = map.getSize().y, p = map.latLngToContainerPoint(c);
      map.panBy([mobile() ? 0 : -150, -(0.9 * H - p.y)], { animate: false });
      openPopup(i, c);
    }
  }, 400);
})();
