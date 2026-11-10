/* RailSentinel – dashboard. Dane z window.RS_DATA (generowane przez src/05_predict.py). */
(() => {
  const D = window.RS_DATA || {};
  const SEG = D.segments || [];
  const HZ = { total: "Łącznie", flood: "Woda: ulewa (ML) lub fala wezbraniowa", heat: "Wyboczenie toru (upał)", wind: "Wiatr / powalone drzewa", ice: "Oblodzenie sieci" };
  const ACTION = {
    flood: "obchód toru i kontrola przepustów, mostów i nasypów przed pierwszym pociągiem; ograniczenie prędkości do 40 km/h; gotowość pociągu sieciowego i sprzętu do zabezpieczenia skarp; przy fali wezbraniowej – obserwacja filarów mostów i usuwanie spływającego drewna (zatory)",
    heat: "kontrola geometrii toru w godz. 13–19, szczególnie na odcinkach po robotach torowych; doraźne ograniczenie prędkości do 60–80 km/h",
    wind: "gotowość brygad do usuwania powalonych drzew; objazd linii po przejściu frontu przed wznowieniem ruchu",
    ice: "kursy pociągów odladzających sieć trakcyjną; rozważenie trakcji spalinowej na odcinkach krytycznych",
  };
  const ALARM = 0.5, WARN = 0.3;

  const st = { mode: "replay2024", hz: "total", day: 0, issue: 3, rain: false,
    sim: { lat: null, lon: null, rain: 180, radius: 35, soil: 80, river: 0.5, climate: 0 } };
  let simRisk = null, simBase = null;
  const $ = (s) => document.querySelector(s);
  const pct = (v) => Math.round(v * 100) + "%";

  // ---------- mapa ----------
  const map = L.map("map", { zoomControl: true, preferCanvas: true }).setView([52.0, 19.2], 6);
  window.RS_MAP = map; // dostęp do mapy dla automatycznych testów i nagrań
  let tiles;
  function setTiles() {
    const dark = document.documentElement.dataset.theme === "dark" ||
      (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
    if (tiles) map.removeLayer(tiles);
    const base = dark ? "World_Dark_Gray_Base" : "World_Light_Gray_Base";
    tiles = L.tileLayer(`https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/${base}/MapServer/tile/{z}/{y}/{x}`, {
      attribution: 'Podkład: Esri, HERE, Garmin, © OpenStreetMap contributors · Linie: © OpenStreetMap (ODbL)',
      maxZoom: 16,
    }).addTo(map);
  }
  setTiles();

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

  const layers = SEG.map((s, i) => {
    const pl = L.polyline(s.g, { weight: 3, opacity: 0.95, color: "#888" }).addTo(map);
    pl.on("click", (e) => openPopup(i, e.latlng));
    return pl;
  });
  const dmgLayer = L.layerGroup().addTo(map);
  map.createPane("rainPane"); map.getPane("rainPane").style.zIndex = 350;
  const rainLayer = L.layerGroup().addTo(map);
  const simLayer = L.layerGroup().addTo(map);
  const centers = SEG.map((s) => { const b = L.polyline(s.g).getBounds().getCenter(); return [b.lat, b.lng]; });

  // ---------- dane bieżącego widoku ----------
  function view() {
    if (st.mode === "sim") return simRisk ? { days: ["sim"], risk: { sim: simRisk }, meta: { title: "Symulator" } } : null;
    if (st.mode === "model") return null;
    if (st.mode === "line") { const m = D.live; return m ? { days: m.days, risk: m.risk, meta: m.meta } : null; }
    const m = D[st.mode];
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

  function where(i) {
    const s = SEG[i];
    const parts = [`linia ${s.line}`];
    if (s.place) parts.push(`rejon ${s.place}`);
    if (s.river) parts.push(`dolina: ${s.river}`);
    return parts.join(" · ");
  }
  const domHz = (r, i) => ["flood", "heat", "wind", "ice"].reduce((a, h) => (r[h][i] > r[a][i] ? h : a), "flood");

  // ---------- render ----------
  function render() {
    const v = view();
    const r = cur();
    $("#panel-map").hidden = st.mode === "model";
    $("#panel-model").hidden = st.mode !== "model";
    if (st.mode === "model") { renderModel(); return; }
    $("#simCtrl").hidden = st.mode !== "sim";
    $("#lineCtrl").hidden = st.mode !== "line";
    $("#daysCtrl").hidden = st.mode === "sim";
    if (st.mode === "sim") runSim();
    const r2 = cur();
    if (!r2) { $("#brief").innerHTML = "<p>Brak danych dla tego trybu – uruchom <code>src/05_predict.py</code>.</p>"; return; }
    return renderView(view(), r2);
  }

  function renderView(v, r) {

    // przyciski dni
    $("#days").innerHTML = v.days.map((d, k) =>
      `<button data-d="${k}" class="${k === st.day ? "on" : ""}">${fmtDay(d)}</button>`).join("");
    $("#issueCtrl").hidden = st.mode !== "replay2024";
    if (st.mode === "replay2024") $("#issueLbl").textContent = fmtDay(v.issued, -1) + " wieczorem";

    const vals = r[st.hz];
    layers.forEach((pl, i) => {
      const x = vals[i] || 0;
      pl.setStyle({ color: color(x), weight: x >= ALARM ? 5 : x >= WARN ? 4 : 2.5, opacity: x >= WARN ? 1 : 0.75 });
    });
    layers.forEach((pl, i) => { if ((vals[i] || 0) >= WARN) pl.bringToFront(); });

    // odcinki faktycznie zniszczone (backtest)
    dmgLayer.clearLayers();
    const dmg = st.mode === "replay2024" ? new Set(D.replay2024.damaged) : new Set();
    $("#lgDmg").style.display = dmg.size ? "flex" : "none";
    SEG.forEach((s, i) => {
      if (dmg.has(s.id)) L.polyline(s.g, { color: getComputedStyle(document.documentElement).getPropertyValue("--ink"),
        weight: 9, opacity: 0.55, dashArray: "4 7", interactive: false }).addTo(dmgLayer);
    });

    // KPI
    const idx = vals.map((x, i) => [x, i]).sort((a, b) => b[0] - a[0]);
    const alarm = idx.filter(([x]) => x >= ALARM);
    $("#kAlarm").textContent = alarm.length;
    $("#kKm").textContent = Math.round(alarm.reduce((a, [, i]) => a + SEG[i].len, 0));
    $("#kMax").textContent = pct(idx[0][0]);

    // top 10
    $("#top").innerHTML = idx.slice(0, 10).map(([x, i]) =>
      `<li data-i="${i}">${where(i)}${dmg.has(SEG[i].id) ? " <span class='tag r'>zniszczony</span>" : ""}<span class="v">${pct(x)}</span></li>`).join("");

    renderStory(v);
    renderBrief(v, r, alarm.map(([, i]) => i), idx.filter(([x]) => x >= WARN && x < ALARM).map(([, i]) => i));
    renderRain(r);
    if (st.mode === "line") renderLine();
  }

  // ---------- Moja linia (tryb dla kolejarzy) ----------
  const LS = { get: (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } },
               set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) { /* tryb prywatny */ } } };
  const byLine = {};
  SEG.forEach((s, i) => { (byLine[s.line] = byLine[s.line] || []).push(i); });
  const lineNames = Object.keys(byLine).filter((l) => l !== "bn").sort((a, b) => (+a || 9999) - (+b || 9999));
  $("#lineList").innerHTML = lineNames.map((l) => {
    const pl = [...new Set(byLine[l].map((i) => SEG[i].place).filter(Boolean))];
    return `<option value="${l}">${pl.slice(0, 1).join("")}${pl.length > 1 ? " – " + pl[pl.length - 1] : ""}</option>`;
  }).join("");
  st.line = LS.get("rs_line") || "";
  $("#lineInput").value = st.line;
  const chipCol = (x) => color(x);
  function lineOrder(ii) {
    // porządek wzdłuż linii: rzut na główną oś rozrzutu punktów
    const c = ii.map((i) => centers[i]);
    const mx = c.reduce((a, p) => a + p[1], 0) / c.length, my = c.reduce((a, p) => a + p[0], 0) / c.length;
    let sxx = 0, syy = 0, sxy = 0;
    c.forEach(([y, x]) => { sxx += (x - mx) ** 2; syy += (y - my) ** 2; sxy += (x - mx) * (y - my); });
    const ang = 0.5 * Math.atan2(2 * sxy, sxx - syy);
    return ii.map((i, k) => [i, (c[k][1] - mx) * Math.cos(ang) + (c[k][0] - my) * Math.sin(ang)]).sort((a, b) => a[1] - b[1]).map((x) => x[0]);
  }
  let lineLayer = L.layerGroup().addTo(map);
  function renderLine(fit) {
    const v = view();
    lineLayer.clearLayers();
    if (!v) { $("#lineStatus").innerHTML = "Brak prognozy – uruchom src/05_predict.py live"; return; }
    const ii = byLine[st.line];
    if (!ii) {
      $("#lineStatus").className = "linestatus";
      $("#lineStatus").innerHTML = st.line ? `Nie znam linii „${st.line}”. Wybierz numer z listy albo użyj 📍.` :
        "Wpisz numer swojej linii albo kliknij <b>📍 Gdzie jestem</b> – pokażę prognozę zagrożeń dla każdego jej odcinka na 3 dni.";
      $("#lineTable").innerHTML = ""; return;
    }
    const ord = lineOrder(ii);
    let worst = { x: -1 };
    v.days.forEach((d, k) => ord.forEach((i) => {
      const r = v.risk[d];
      if (r.total[i] > worst.x) worst = { x: r.total[i], d, k, i, h: domHz(r, i) };
    }));
    const lvl = worst.x >= ALARM ? "alarm" : worst.x >= WARN ? "warn" : "ok";
    const km = Math.round(ord.reduce((a, i) => a + SEG[i].len, 0));
    const places = [...new Set(ord.map((i) => SEG[i].place).filter(Boolean))];
    const hzTxt = { flood: "woda (podmycie / fala)", heat: "wyboczenie toru (upał)", wind: "wiatr – drzewa na torze", ice: "oblodzenie sieci" };
    $("#lineStatus").className = "linestatus " + lvl;
    $("#lineStatus").innerHTML = `<b class="big">Linia ${st.line}: ${lvl === "alarm" ? "ALARM" : lvl === "warn" ? "UWAGA" : "bez zagrożeń"}</b>
      ${places[0] || ""}${places.length > 1 ? " – " + places[places.length - 1] : ""} · ${ord.length} odc. · ${km} km toru<br>
      ${lvl === "ok" ? "W ciągu 72 h nie przewiduję zagrożeń pogodowych powyżej progu uwagi." :
        `Najwyższe ryzyko: <b>${pct(worst.x)}</b> – ${hzTxt[worst.h]}, ${fmtDay(worst.d)}, rejon ${SEG[worst.i].place || "?"}.<br><i>Zalecane:</i> ${ACTION[worst.h]}.`}`;
    $("#lineTable").innerHTML = `<table class="ltab"><tr><th>Odcinek</th>${v.days.map((d) => `<th class="c">${fmtDay(d).split(",")[0]}</th>`).join("")}</tr>` +
      ord.map((i) => `<tr data-i="${i}"><td>${SEG[i].place || "–"}${SEG[i].river ? ` <span class="muted small">· ${SEG[i].river}</span>` : ""}</td>` +
        v.days.map((d) => { const x = v.risk[d].total[i]; return `<td class="c"><span class="chip" style="background:${chipCol(x)}">${Math.round(x * 100)}</span></td>`; }).join("") + "</tr>").join("") + "</table>";
    $("#lineUpd").textContent = `prognoza z ${fmtDay(v.meta.issued || v.days[0])}`;
    ord.forEach((i) => L.polyline(SEG[i].g, { color: "#2563eb", weight: 10, opacity: 0.25, interactive: false }).addTo(lineLayer));
    if (fit) map.fitBounds(L.featureGroup(ord.map((i) => layers[i])).getBounds(), { padding: [30, 30], maxZoom: 11 });
    st.lineText = $("#lineStatus").innerText;
  }
  function setLine(l, fit = true) { st.line = String(l).trim(); LS.set("rs_line", st.line); $("#lineInput").value = st.line; render(); renderLine(fit); }
  $("#lineInput").addEventListener("change", (e) => setLine(e.target.value));
  $("#lineTable").addEventListener("click", (e) => { const tr = e.target.closest("tr[data-i]"); if (!tr) return; const i = +tr.dataset.i; const b = layers[i].getBounds(); map.fitBounds(b, { maxZoom: 12 }); openPopup(i, b.getCenter()); });
  $("#geoBtn").addEventListener("click", () => {
    if (!navigator.geolocation) { alert("Ta przeglądarka nie udostępnia lokalizacji."); return; }
    $("#geoBtn").textContent = "⏳ Szukam…";
    navigator.geolocation.getCurrentPosition((pos) => {
      $("#geoBtn").textContent = "📍 Gdzie jestem";
      const { latitude: la, longitude: lo } = pos.coords;
      let best = [1e9, 0];
      centers.forEach((c, i) => { const d = (c[0] - la) ** 2 + ((c[1] - lo) * Math.cos(la * Math.PI / 180)) ** 2; if (d < best[0]) best = [d, i]; });
      setLine(SEG[best[1]].line);
      L.circleMarker([la, lo], { radius: 7, color: "#fff", weight: 2, fillColor: "#2563eb", fillOpacity: 1 }).addTo(lineLayer);
    }, () => { $("#geoBtn").textContent = "📍 Gdzie jestem"; alert("Brak dostępu do lokalizacji – wpisz numer linii."); }, { enableHighAccuracy: true, timeout: 10000 });
  });
  $("#shareBtn").addEventListener("click", async () => {
    const txt = `RailSentinel – ${st.lineText || ""}\n${location.origin + location.pathname}#mode=line&line=${st.line}`;
    try { if (navigator.share) await navigator.share({ title: "RailSentinel", text: txt }); else { await navigator.clipboard.writeText(txt); $("#shareBtn").textContent = "✓ Skopiowano"; } } catch (e) { /* anulowano */ }
  });
  // instalacja aplikacji (PWA)
  let deferred = null;
  window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); deferred = e; $("#installBtn").hidden = false; });
  $("#installBtn").addEventListener("click", async () => { if (!deferred) return; deferred.prompt(); await deferred.userChoice; deferred = null; $("#installBtn").hidden = true; });

  // ---------- warstwa opadu (średnia z odcinków w komórce siatki) ----------
  function renderRain(r) {
    rainLayer.clearLayers();
    if (!st.rain || !r) return;
    const cells = {};
    SEG.forEach((s, i) => { const c = s.cell || ""; (cells[c] = cells[c] || []).push(r.p1[i]); });
    for (const [c, arr] of Object.entries(cells)) {
      if (!c) continue;
      const [la, lo] = c.split(",").map(Number);
      const p = arr.reduce((a, b) => a + b, 0) / arr.length;
      if (p < 2) continue;
      L.rectangle([[la - 0.125, lo - 0.125], [la + 0.125, lo + 0.125]], {
        stroke: false, fillColor: "#2563eb", fillOpacity: Math.min(0.45, p / 130), interactive: false, pane: "rainPane",
      }).addTo(rainLayer);
    }
  }

  // ---------- symulator (model ML w przeglądarce) ----------
  function runSim() {
    if (!window.RS_SIM) return;
    const p = st.sim;
    simRisk = window.RS_SIM.compute(p, centers);
    simBase = p.climate > 0 ? window.RS_SIM.compute({ ...p, climate: 0 }, centers) : null;
    $("#vRain").textContent = p.rain + " mm"; $("#vRad").textContent = p.radius + " km";
    $("#vSoil").textContent = p.soil + " mm"; $("#vRiver").textContent = p.river.toFixed(1);
    $("#vClim").textContent = "+" + p.climate + "%";
    const cnt = (rr) => rr.total.filter((x) => x >= ALARM).length;
    const km = (rr) => Math.round(rr.total.reduce((a, x, i) => a + (x >= ALARM ? SEG[i].len : 0), 0));
    $("#climDelta").innerHTML = simBase
      ? `<b>Test klimatyczny:</b> przy opadach intensywniejszych o ${p.climate}% w alarmie jest <b>${cnt(simRisk)}</b> odcinków zamiast ${cnt(simBase)} (<b>+${km(simRisk) - km(simBase)} km</b> toru do sprawdzenia).`
      : "";
    $("#simHint").innerHTML = (p.lat == null ? "Kliknij na mapie, aby postawić ulewę – albo wybierz scenariusz. " : "") +
      `<span class="mlbadge">model ML w przeglądarce · ${window.RS_SIM.trees} drzew · ${window.RS_SIM.n} odcinków · ${simRisk.ms.toFixed(0)} ms</span>`;
    simLayer.clearLayers();
    if (p.lat != null) {
      L.circle([p.lat, p.lon], { radius: p.radius * 1000, color: "#2563eb", weight: 1, fillOpacity: 0.08, interactive: false }).addTo(simLayer);
      L.circle([p.lat, p.lon], { radius: p.radius * 450, color: "#2563eb", weight: 1, dashArray: "3 4", fillOpacity: 0.12, interactive: false }).addTo(simLayer);
    }
  }
  const PRESETS = {
    "2024": { lat: 50.33, lon: 16.85, rain: 260, radius: 45, soil: 120, river: 3.0, climate: 0, scope: "storm", view: [50.45, 16.9, 9] },
    storm: { lat: 50.86, lon: 15.62, rain: 160, radius: 22, soil: 90, river: 0.8, climate: 0, scope: "storm", view: [50.88, 15.7, 10] },
    odra: { lat: null, lon: null, rain: 20, radius: 30, soil: 60, river: 3.2, climate: 0, scope: "odra", view: [51.0, 17.2, 8] },
    clear: { lat: null, lon: null, rain: 180, radius: 35, soil: 80, river: 0.5, climate: 0, scope: "storm" },
  };
  function syncSliders() {
    const p = st.sim;
    $("#sRain").value = p.rain; $("#sRad").value = p.radius; $("#sSoil").value = p.soil;
    $("#sRiver").value = Math.round(p.river * 10); $("#sClim").value = p.climate;
  }

  function renderStory(v) {
    let h = "";
    if (st.mode === "replay2024") {
      const s = D.replay2024.summary;
      h = `<h3>Czy system ostrzegłby przed powodzią 2024?</h3>
        <p>Model widzi tylko obserwacje do wieczora dnia poprzedniego i <b>archiwalną prognozę ECMWF</b> wydaną w tamtym momencie. Przesuń suwak „Prognoza wydana”.</p>
        <div class="big"><div><b>${s.detected}/${s.damaged_segments}</b><small>zniszczonych odcinków z alarmem</small></div>
        <div><b>${s.median_lead_hours ?? "–"} h</b><small>mediana wyprzedzenia przed pierwszymi zniszczeniami</small></div>
        <div><b>${s.other_in_alarm_pct.toFixed(0)}%</b><small>pozostałej sieci w alarmie w szczycie</small></div></div>`;
    } else if (st.mode === "live") {
      h = `<h3>Prognoza bieżąca</h3><p>Wydana ${fmtDay(v.meta.issued)}. Łączy prognozę numeryczną (Open-Meteo) z modelem ML i modułami fizycznymi.</p>`;
    } else if (st.mode === "heat") {
      h = `<h3>${v.meta.title}</h3><p>Moduł fizyczny szacuje temperaturę szyny (powietrze + nasłonecznienie). Powyżej ~50 °C rośnie ryzyko wyboczenia toru bezstykowego.</p>`;
    } else if (st.mode === "y1997") {
      const m = D.metrics || {};
      h = `<h3>${v.meta.title}</h3><p>Niezależny test – model nigdy nie widział 1997 r. Dwa mechanizmy powodzi: ulewa w górach (moduł ML) i fala wezbraniowa na Odrze (moduł hydrologiczny z wodowskazów IMGW).</p>
        <div class="big"><div><b>${m.test1997_sites_detected_system ?? "–"}/${m.test1997_sites ?? "–"}</b><small>udokumentowanych miejsc zniszczeń wykrytych</small></div>
        <div><b>${m.test1997_sites_detected_ml ?? "–"}/${m.test1997_sites ?? "–"}</b><small>bez modułu hydrologicznego</small></div></div>`;
    } else if (st.mode === "line") {
      h = `<h3>Moja linia – dla kolejarzy</h3><p>Status Twojej linii na 3 dni: każdy odcinek, kolor = ryzyko. Działa na telefonie i bez zasięgu (ostatnia pobrana prognoza). Zainstaluj jako aplikację: menu przeglądarki → „Dodaj do ekranu głównego”.</p>`;
    } else if (st.mode === "sim") {
      h = `<h3>Symulator: co jeśli?</h3><p>Postaw ulewę w dowolnym miejscu, podnieś stan rzek albo wzmocnij opady scenariuszem klimatycznym – ten sam model ML co w backteście przelicza ryzyko na żywo.</p>`;
    }
    $("#story").innerHTML = h;
  }

  function renderBrief(v, r, alarm, warn) {
    const day = v.days[st.day];
    if (!alarm.length && !warn.length) {
      $("#brief").innerHTML = `<p><b>${fmtDay(day)}:</b> brak odcinków powyżej progu uwagi. Utrzymać standardowy tryb utrzymania.</p>`;
      return;
    }
    const byHz = {};
    alarm.forEach((i) => { const h = st.hz === "total" ? domHz(r, i) : st.hz; (byHz[h] = byHz[h] || []).push(i); });
    let html = `<p><b>${fmtDay(day)}</b> – <span class="tag r">ALARM</span> ${alarm.length} odc. · <span class="tag o">UWAGA</span> ${warn.length} odc.</p>`;
    for (const [h, list] of Object.entries(byHz)) {
      const lines = {};
      list.forEach((i) => { (lines[SEG[i].line] = lines[SEG[i].line] || []).push(i); });
      const items = Object.entries(lines).sort((a, b) => b[1].length - a[1].length).slice(0, 6).map(([ln, ii]) => {
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
        if (h === "ice") det = `opad do ${Math.max(...ii.map((i) => r.p1[i])).toFixed(1)} mm przy temperaturze ok. 0 °C`;
        return `<li><b>Linia ${ln}</b> (${ii.length} odc.${places ? ", " + places : ""}${rivers ? ", dolina " + rivers : ""}) – ${det}, ryzyko ${pct(mx)}</li>`;
      }).join("");
      html += `<p><b>${HZ[h]}</b></p><ul>${items}</ul><p><i>Zalecane działania:</i> ${ACTION[h]}.</p>`;
    }
    $("#brief").innerHTML = html;
  }

  function openPopup(i, latlng) {
    const v = view(), r = cur();
    if (!r) return;
    const s = SEG[i];
    const why = (r.why[i] || []).map(([k, val]) =>
      `<div>${k}<div class="bar"><i style="width:${Math.min(100, val * 250)}%"></i></div></div>`).join("");
    const dmg = st.mode === "replay2024" && D.replay2024.damaged.includes(s.id);
    const lead = st.mode === "replay2024" && D.replay2024.lead_hours_by_segment[s.id];
    L.popup({ autoPanPadding: [20, 20], maxWidth: 340 }).setLatLng(latlng).setContent(`<div class="pp">
      <h4>Linia ${s.line}${s.place ? " · " + s.place : ""}</h4>
      <div class="sub">${s.river ? "dolina: " + s.river + " · " : ""}${s.elev} m n.p.m. · ${s.len.toFixed(1)} km toru · ${fmtDay(v.days[st.day])}</div>
      <table>
        <tr><td><b>Ryzyko łączne</b></td><td><b>${pct(r.total[i])}</b></td></tr>
        <tr><td>Woda łącznie</td><td>${pct(r.flood[i])}</td></tr>
        ${r.flash ? `<tr><td>&nbsp;· ulewa / podmycie (ML)</td><td>${pct(r.flash[i])}</td></tr><tr><td>&nbsp;· fala wezbraniowa (IMGW)</td><td>${pct(r.river[i])}</td></tr>` : ""}
        <tr><td>Wyboczenie (upał)</td><td>${pct(r.heat[i])}</td></tr>
        <tr><td>Wiatr</td><td>${pct(r.wind[i])}</td></tr>
        <tr><td>Oblodzenie</td><td>${pct(r.ice[i])}</td></tr>
        <tr><td>Opad dobowy / 3-dobowy</td><td>${r.p1[i]} / ${r.p3[i]} mm</td></tr>
        <tr><td>Porywy wiatru</td><td>${r.gust[i]} km/h</td></tr>
        <tr><td>Temp. szyny (szac.)</td><td>${r.trail[i]} °C</td></tr>
      </table>
      ${why ? `<div class="why"><b>Dlaczego? (wkład czynników do ryzyka)</b>${why}</div>` : ""}
      ${dmg ? `<div class="why"><span class="tag r">Odcinek faktycznie zniszczony 09.2024</span>${lead ? ` – alarm ${lead} h przed pierwszymi zniszczeniami` : ""}</div>` : ""}
    </div>`).openOn(map);
  }

  function renderModel() {
    const m = D.metrics || {};
    const f = (x, d = 3) => (x == null || isNaN(x) ? "–" : (+x).toFixed(d));
    $("#panel-model").innerHTML = `
      <h3>Jak działa RailSentinel</h3>
      <p>Dla każdego z ${SEG.length} odcinków (ok. 4–5 km) sieci na Dolnym Śląsku i Opolszczyźnie model łączy prognozę pogody
      z cechami terenu i infrastruktury i liczy prawdopodobieństwo uszkodzenia w horyzoncie 72 h.</p>
      <ul>
        <li><b>Ulewa / podmycie</b> – model ML (gradient boosting) z ograniczeniami monotoniczności: więcej deszczu, bliżej rzeki, niżej w dolinie ⇒ ryzyko nigdy nie maleje.</li>
        <li><b>Fala wezbraniowa</b> – moduł hydrologiczny: stany wód z ${"~200"} wodowskazów IMGW, próg ustalony z góry.</li>
        <li><b>Wyboczenie, wiatr, oblodzenie</b> – moduły fizyczne (temperatura szyny, progi IMGW, marznący opad).</li>
        <li><b>Wyjaśnialność</b> – każdy alarm pokazuje, które czynniki go spowodowały.</li>
      </ul>
      <h3>Walidacja (GroupKFold po liniach – model ocenia linie, których nie widział)</h3>
      <div class="mgrid">
        <div class="mcell"><b>${f(m.pr_auc_model)}</b><small>PR-AUC modelu</small><div class="vs">reguła „opad 3-dobowy”: ${f(m.pr_auc_baseline_p3)}</div></div>
        <div class="mcell"><b>${f(m.precision_event_days_model * 100, 0)}%</b><small>precyzja alarmów w dniach powodzi</small><div class="vs">reguła: ${f(m.precision_event_days_baseline * 100, 0)}%</div></div>
        <div class="mcell"><b>${f(m.event_auc_model)}</b><small>AUC w dniach powodzi</small><div class="vs">reguła: ${f(m.event_auc_baseline)} – czy model trafia w <em>właściwe</em> odcinki w strefie ulewy</div></div>
        <div class="mcell"><b>${f(m.other_alarm_pct_model, 0)}%</b><small>pozostałej sieci w alarmie w dniach powodzi</small><div class="vs">reguła: ${f(m.other_alarm_pct_baseline, 0)}% – <em>o połowę mniej</em> zbędnych obchodów</div></div>
      </div>
      <h3>Niezależny test: powódź 1997 (model jej nie widział)</h3>
      <div class="mgrid">
        <div class="mcell"><b>${m.test1997_sites_detected_system ?? "–"}/${m.test1997_sites ?? "–"}</b><small>miejsc zniszczeń wykrytych – system</small><div class="vs">sam model ML: ${m.test1997_sites_detected_ml ?? "–"}/${m.test1997_sites ?? "–"}</div></div>
        <div class="mcell"><b>${f(m.test1997_network_alarm_pct_system, 0)}%</b><small>sieci w alarmie w oknie powodzi</small><div class="vs">reguła opadowa: ${f(m.test1997_network_alarm_pct_baseline, 0)}%</div></div>
      </div>
      <p>Etykiety: ${m.positive_segments} odcinków (2024, komunikaty PLK/PAP) i 3 miejsca zniszczeń z 1997 r. („Z Biegiem Szyn” nr 133).
      Po podłączeniu rejestru zdarzeń PLK model można douczyć na tysiącach przypadków bez zmiany architektury.</p>`;
  }

  function fmtDay(d, shift = 0) {
    if (d === "sim") return "symulacja";
    const x = new Date(d + "T12:00:00"); x.setDate(x.getDate() + shift);
    return x.toLocaleDateString("pl-PL", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
  }

  // ---------- zdarzenia ----------
  $("#modes").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    document.querySelectorAll("#modes button").forEach((x) => x.classList.toggle("on", x === b));
    st.mode = b.dataset.mode; st.day = st.mode === "replay2024" ? 1 : st.mode === "heat" || st.mode === "y1997" ? 1 : 0;
    if (st.mode === "line") { st.day = 0; setTimeout(() => renderLine(true), 0); }
    if (st.mode === "sim" && st.sim.lat == null) { Object.assign(st.sim, (({ view, ...x }) => x)(PRESETS["2024"])); syncSliders(); map.setView([50.45, 16.9], 9); }
    render();
  });
  $("#hazards").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    document.querySelectorAll("#hazards button").forEach((x) => x.classList.toggle("on", x === b));
    st.hz = b.dataset.h; render();
  });
  $("#days").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { st.day = +b.dataset.d; render(); } });
  $("#issue").addEventListener("input", (e) => { st.issue = +e.target.value; render(); });
  $("#top").addEventListener("click", (e) => {
    const li = e.target.closest("li"); if (!li) return;
    const i = +li.dataset.i; const b = layers[i].getBounds();
    map.fitBounds(b, { maxZoom: 12 }); openPopup(i, b.getCenter());
  });
  // symulator – zdarzenia
  map.on("click", (e) => { if (st.mode !== "sim") return; st.sim.lat = e.latlng.lat; st.sim.lon = e.latlng.lng; st.sim.scope = "storm"; render(); });
  const bind = (id, key, k = 1) => $(id).addEventListener("input", (e) => { st.sim[key] = +e.target.value / k; render(); });
  bind("#sRain", "rain"); bind("#sRad", "radius"); bind("#sSoil", "soil"); bind("#sRiver", "river", 10); bind("#sClim", "climate");
  $("#presets").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    const pr = PRESETS[b.dataset.p]; const { view: vw, ...rest } = pr;
    Object.assign(st.sim, rest); syncSliders();
    if (vw) map.setView([vw[0], vw[1]], vw[2]);
    render();
  });
  // animacja powodzi 2024
  let playing = null;
  $("#play").addEventListener("click", () => {
    if (playing) { clearInterval(playing); playing = null; $("#play").textContent = "▶ Odtwórz"; return; }
    st.rain = true; $("#rainBtn").classList.add("on");
    st.issue = 0; st.day = 1; $("#issue").value = 0; render();
    $("#play").textContent = "❚❚ Pauza";
    playing = setInterval(() => {
      if (st.issue >= D.replay2024.issues.length - 1) { clearInterval(playing); playing = null; $("#play").textContent = "▶ Odtwórz"; return; }
      st.issue++; $("#issue").value = st.issue; render();
    }, 1400);
  });
  $("#rainBtn").addEventListener("click", () => { st.rain = !st.rain; $("#rainBtn").classList.toggle("on", st.rain); render(); });
  $("#copy").addEventListener("click", () => navigator.clipboard && navigator.clipboard.writeText($("#brief").innerText));
  $("#theme").addEventListener("click", () => {
    const r = document.documentElement;
    const dark = r.dataset.theme ? r.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    r.dataset.theme = dark ? "light" : "dark"; setTiles(); render();
  });

  if (D.replay2024) { $("#issue").max = D.replay2024.issues.length - 1; st.issue = Math.min(4, D.replay2024.issues.length - 1); $("#issue").value = st.issue; st.day = 1; }
  if (!D.replay2024) { st.mode = "live"; }
  // parametry w adresie, np. index.html#mode=heat&day=1&issue=3&hz=flood&lat=50.4&lon=16.8&z=10
  const hp = new URLSearchParams(location.hash.slice(1));
  if (hp.get("theme")) { document.documentElement.dataset.theme = hp.get("theme"); setTiles(); }
  if (hp.get("mode")) { st.mode = hp.get("mode"); if (st.mode === "live") st.day = 0; }
  if (hp.get("day")) st.day = +hp.get("day");
  if (hp.get("issue")) { st.issue = +hp.get("issue"); $("#issue").value = st.issue; }
  if (hp.get("hz")) st.hz = hp.get("hz");
  if (hp.get("line")) { st.line = hp.get("line"); $("#lineInput").value = st.line; }
  if (hp.get("rain")) { st.rain = true; $("#rainBtn").classList.add("on"); }
  if (hp.get("preset")) { const { view: vw, ...x } = PRESETS[hp.get("preset")]; Object.assign(st.sim, x); if (hp.get("clim")) st.sim.climate = +hp.get("clim"); syncSliders(); if (vw && !hp.get("lat")) map.setView([vw[0], vw[1]], vw[2]); }
  if (hp.get("lat")) map.setView([+hp.get("lat"), +hp.get("lon")], +(hp.get("z") || 9));
  document.querySelectorAll("#modes button").forEach((x) => x.classList.toggle("on", x.dataset.mode === st.mode));
  document.querySelectorAll("#hazards button").forEach((x) => x.classList.toggle("on", x.dataset.h === st.hz));
  render();
  window.addEventListener("load", () => map.invalidateSize());
  if (hp.get("popup")) setTimeout(() => {
    // otwórz szczegóły najbardziej zagrożonego odcinka (do zrzutów ekranu)
    map.invalidateSize();
    const r = cur();
    if (r) {
      const i = r[st.hz].reduce((b, x, k, a) => (x > a[b] ? k : b), 0);
      const c = layers[i].getBounds().getCenter();
      const z = +(hp.get("z") || 11);
      map.setView(c, z, { animate: false });
      const H = map.getSize().y, p = map.latLngToContainerPoint(c);
      map.panBy([0, -(0.9 * H - p.y)], { animate: false });
      openPopup(i, c);
    }
  }, 400);
})();
