/* HatKalkanı web UI. No build step; MapLibre GL JS from web/vendor. All displayed numbers come from the API. */
(function () {
  "use strict";

  const params = new URLSearchParams(location.search);
  const MOCK = params.get("mock") === "1";
  const TIERS = ["kritik", "yuksek", "orta", "dusuk"];
  const BASEMAP_STYLE_URL = "https://tiles.openfreemap.org/styles/positron"; // keyless; see docs/ATTRIBUTIONS.md
  const css = getComputedStyle(document.documentElement);
  const TIER_COLOR = Object.fromEntries(TIERS.map((t) => [t, css.getPropertyValue("--t-" + t).trim()]));
  const HALO = css.getPropertyValue("--halo").trim();
  // Line widths (px at zoom 10 / 15) by tier: wider = riskier, so colour is not the only cue.
  const TIER_W = { kritik: [3, 9], yuksek: [2.4, 6.5], orta: [1.8, 4.5], dusuk: [1.4, 3.2] };

  const $ = (id) => document.getElementById(id);
  const state = {
    lang: "tr",
    tab: "work",
    aoi: null,
    health: null,
    sources: null,
    workorders: null, // array of GeoJSON features
    segIndex: new Map(),
    segAsOf: null,
    currentAsOf: null,
    visibleTiers: new Set(TIERS),
    selectedSpan: null,
    selectedSeg: null, // {detail, span}
    dates: null,
    scenario: null,
    scenarioErr: null,
    backtest: null,
    backtestErr: null,
    events: null,
    mapReady: false,
    basemap: "pending",
  };
  try { const l = localStorage.getItem("hk_lang"); if (l === "tr" || l === "en") state.lang = l; } catch (e) { /* storage may be blocked */ }
  if (params.get("lang") === "en" || params.get("lang") === "tr") state.lang = params.get("lang");

  /* ---------- i18n ---------- */
  function t(key, vars) {
    let s = (window.I18N[state.lang] || {})[key];
    if (s === undefined) s = window.I18N.tr[key];
    if (s === undefined) return key;
    if (vars) for (const k in vars) s = s.replace("{" + k + "}", vars[k]);
    return s;
  }
  const locale = () => (state.lang === "tr" ? "tr-TR" : "en-US");
  function fmt(n, digits, opts) {
    if (n === null || n === undefined || Number.isNaN(Number(n))) return t("no_data");
    const d = digits === undefined ? 1 : digits;
    return new Intl.NumberFormat(locale(), Object.assign({ minimumFractionDigits: d, maximumFractionDigits: d }, opts || {})).format(Number(n));
  }
  const pct = (r, d) => (r === null || r === undefined ? t("no_data") : fmt(Number(r) * 100, d === undefined ? 0 : d) + "%");
  const pick = (o, base) => (o ? (o[base + "_" + state.lang] !== undefined ? o[base + "_" + state.lang] : o[base + "_tr"]) : undefined);
  function esc(s) { return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }

  function applyStaticI18n() {
    document.documentElement.lang = state.lang;
    document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    document.querySelectorAll("[data-i18n-aria]").forEach((el) => { el.setAttribute("aria-label", t(el.dataset.i18nAria)); });
    const lb = $("lang-btn");
    lb.textContent = t("lang_switch");
    lb.setAttribute("aria-label", t("lang_switch_label"));
    lb.lang = state.lang === "tr" ? "en" : "tr";
    $("drawer-close").textContent = "×";
    $("src-badge").textContent = MOCK ? t("api_mock") : t("api_live");
    document.title = t("app_title");
  }

  /* ---------- API layer ---------- */
  class ApiError extends Error {
    constructor(status, body) {
      super("HTTP " + status);
      this.status = status;
      const d = body && body.detail && typeof body.detail === "object" ? body.detail : body || {};
      this.detail_tr = d.detail_tr || d.error || (typeof (body && body.detail) === "string" ? body.detail : "");
      this.detail_en = d.detail_en || d.hint || this.detail_tr;
    }
  }
  function apiUrl(path, q) {
    const p = new URLSearchParams();
    for (const k in q || {}) if (q[k] !== undefined && q[k] !== null && q[k] !== "") p.set(k, q[k]);
    const qs = p.toString();
    return path + (qs ? "?" + qs : "");
  }
  function mockFile(path, q) {
    const asof = (q && q.as_of) || state.currentAsOf || "2026-10-30";
    let m;
    if (path === "/api/aoi") return "mock/aoi.json";
    if (path === "/api/aoi/boundary") return "mock/boundary.json";
    if (path === "/api/health") return "mock/health.json";
    if (path === "/api/meta/sources") return "mock/sources.json";
    if (path === "/api/segments") return "mock/segments_" + asof + ".json";
    if ((m = path.match(/^\/api\/segments\/(.+)$/))) return { detail: m[1], asof };
    if (path === "/api/workorders") return "mock/workorders.json";
    if (path === "/api/scenario/dates") return "mock/scenario_dates.json";
    if (path === "/api/scenario") return "mock/scenario.json";
    if (path === "/api/backtest") return "mock/backtest.json";
    if (path === "/api/backtest/events") return "mock/backtest_events.json";
    return null;
  }
  async function getJson(url) {
    let res;
    try { res = await fetch(url, { headers: { Accept: "application/json" } }); } catch (e) { throw new ApiError(0, { detail_tr: "Sunucuya ulaşılamadı.", detail_en: "Server unreachable." }); }
    if (!res.ok) { let b = null; try { b = await res.json(); } catch (e) { /* not json */ } throw new ApiError(res.status, b); }
    return res.json();
  }
  async function api(path, q) {
    if (!MOCK) return getJson(apiUrl(path, q));
    const f = mockFile(path, q);
    if (!f) throw new ApiError(404, { detail_tr: "Mock yok", detail_en: "No mock" });
    if (typeof f === "string") return getJson(f);
    const [seg, det] = await Promise.all([api("/api/segments", { as_of: f.asof }), getJson("mock/segment_details_" + f.asof + ".json")]);
    const feat = seg.features.find((x) => x.properties.segment_id === f.detail);
    if (!feat || !det[f.detail]) throw new ApiError(404, { detail_tr: "Parça yok", detail_en: "Segment not found" });
    const props = Object.assign({}, feat.properties, det[f.detail]);
    return { type: "Feature", geometry: feat.geometry, properties: props };
  }
  function exportUrl(format) {
    if (MOCK) return "mock/workorders." + format;
    return apiUrl("/api/workorders/export", { format });
  }

  /* ---------- Map ---------- */
  let map = null;
  let mapLoaded;
  const mapReady = new Promise((r) => { mapLoaded = r; });
  const EMPTY = { type: "FeatureCollection", features: [] };

  function tierExpr(byTier, fallback) {
    return ["match", ["get", "tier"], "kritik", byTier.kritik, "yuksek", byTier.yuksek, "orta", byTier.orta, fallback];
  }
  function initMap() {
    map = new maplibregl.Map({
      container: "map",
      style: { version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": "#e8ecef" } }] },
      center: [27.13, 38.17],
      zoom: 10,
      attributionControl: { compact: true },
      dragRotate: false,
      pitchWithRotate: false,
    });
    map.touchZoomRotate.disableRotation();
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("error", () => { /* tile/basemap failures are non-fatal: offline fallback */ });
    map.on("load", () => {
      ["boundary", "segments", "scenario", "events", "span", "sel"].forEach((id) => map.addSource(id, { type: "geojson", data: EMPTY }));
      map.addLayer({ id: "boundary-fill", type: "fill", source: "boundary", paint: { "fill-color": "#ffffff", "fill-opacity": 0.25 } });
      map.addLayer({ id: "boundary-line", type: "line", source: "boundary", paint: { "line-color": "#101820", "line-width": 3, "line-dasharray": [3, 2] } });
      const wInterp = (i) => ["interpolate", ["linear"], ["zoom"], 10, tierExpr({ kritik: TIER_W.kritik[0] + i, yuksek: TIER_W.yuksek[0] + i, orta: TIER_W.orta[0] + i }, TIER_W.dusuk[0] + i), 15, tierExpr({ kritik: TIER_W.kritik[1] + i, yuksek: TIER_W.yuksek[1] + i, orta: TIER_W.orta[1] + i }, TIER_W.dusuk[1] + i)];
      map.addLayer({ id: "scenario-halo", type: "line", source: "scenario", layout: { visibility: "none", "line-cap": "round" }, paint: { "line-color": HALO, "line-opacity": 0.55, "line-width": ["interpolate", ["linear"], ["zoom"], 10, 12, 15, 26] } });
      map.addLayer({ id: "span-halo", type: "line", source: "span", layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": "#101820", "line-opacity": 0.85, "line-width": ["interpolate", ["linear"], ["zoom"], 10, 12, 15, 24] } });
      map.addLayer({ id: "seg-casing", type: "line", source: "segments", layout: { "line-cap": "round", "line-join": "round", "line-sort-key": tierExpr({ kritik: 4, yuksek: 3, orta: 2 }, 1) }, paint: { "line-color": "#ffffff", "line-opacity": 0.9, "line-width": wInterp(2.5) } });
      map.addLayer({ id: "seg-line", type: "line", source: "segments", layout: { "line-cap": "round", "line-join": "round", "line-sort-key": tierExpr({ kritik: 4, yuksek: 3, orta: 2 }, 1) }, paint: { "line-color": tierExpr(TIER_COLOR, TIER_COLOR.dusuk), "line-width": wInterp(0) } });
      map.addLayer({ id: "sel-line", type: "line", source: "sel", layout: { "line-cap": "round" }, paint: { "line-color": "#101820", "line-width": 4, "line-gap-width": ["interpolate", ["linear"], ["zoom"], 10, 7, 15, 12] } });
      map.addLayer({ id: "events-ring", type: "circle", source: "events", layout: { visibility: "none" }, paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 9, 15, 22], "circle-color": "#6a1b9a", "circle-opacity": 0.9, "circle-stroke-color": "#ffffff", "circle-stroke-width": 3 } });
      map.on("mousemove", (e) => { map.getCanvas().style.cursor = hitSegment(e.point) ? "pointer" : ""; });
      map.on("click", (e) => { const f = hitSegment(e.point); if (f) openSegment(f.properties.segment_id, null); });
      state.mapReady = true;
      mapLoaded();
      tryBasemap();
    });
  }
  function hitSegment(pt) {
    const r = 7;
    const fs = map.queryRenderedFeatures([[pt.x - r, pt.y - r], [pt.x + r, pt.y + r]], { layers: ["seg-line"] });
    if (!fs.length) return null;
    return fs.reduce((a, b) => ((b.properties.risk || 0) > (a.properties.risk || 0) ? b : a));
  }
  async function tryBasemap() {
    const ctl = new AbortController();
    const to = setTimeout(() => ctl.abort(), 4000);
    try {
      const res = await fetch(BASEMAP_STYLE_URL, { signal: ctl.signal });
      if (!res.ok) throw new Error("style " + res.status);
      const st = await res.json();
      if (st.glyphs) map.setGlyphs(st.glyphs);
      for (const id in st.sources) if (!map.getSource(id)) map.addSource(id, st.sources[id]);
      for (const l of st.layers) {
        if (l.type === "background") continue;
        if (l.type === "symbol" && l.layout) delete l.layout["icon-image"]; // no sprite in this setup
        map.addLayer(l, "boundary-fill");
      }
      state.basemap = "online";
    } catch (e) {
      state.basemap = "offline";
    } finally { clearTimeout(to); }
    renderFooter();
  }
  function setSource(id, data) { if (state.mapReady) map.getSource(id).setData(data || EMPTY); }
  function applyTierFilter() {
    if (!state.mapReady) return;
    const f = ["in", ["get", "tier"], ["literal", Array.from(state.visibleTiers)]];
    map.setFilter("seg-line", f);
    map.setFilter("seg-casing", f);
  }
  function geomBounds(geom) {
    const b = new maplibregl.LngLatBounds();
    const walk = (c) => { if (typeof c[0] === "number") b.extend(c); else c.forEach(walk); };
    walk(geom.coordinates);
    return b;
  }
  function fitTo(bounds, maxZoom) {
    const right = $("drawer").hidden ? 80 : $("drawer").offsetWidth + 40;
    map.fitBounds(bounds, { padding: { top: 90, bottom: 90, left: 80, right }, maxZoom: maxZoom || 16, duration: 700 });
  }

  /* ---------- Data loading ---------- */
  async function loadSegments(asOf) {
    const q = asOf && asOf !== state.currentAsOf ? { as_of: asOf } : {};
    const fc = await api("/api/segments", q);
    state.segIndex = new Map(fc.features.map((f) => [f.properties.segment_id, f]));
    state.segAsOf = asOf || state.currentAsOf;
    await mapReady;
    setSource("segments", fc);
    applyTierFilter();
  }

  async function boot() {
    applyStaticI18n();
    $("mockbar").hidden = !MOCK;
    initMap();
    renderTierLegend();
    const results = await Promise.allSettled([
      api("/api/aoi"), api("/api/aoi/boundary"), api("/api/health"), api("/api/meta/sources"),
      api("/api/workorders", { limit: 50, format: "geojson" }),
    ]);
    const [aoi, boundary, health, sources, wo] = results;
    if (health.status === "fulfilled") { state.health = health.value; state.currentAsOf = health.value.data_version; }
    if (aoi.status === "fulfilled") {
      state.aoi = aoi.value;
      if (!state.currentAsOf && aoi.value.as_of) state.currentAsOf = aoi.value.as_of;
      renderKpis();
      renderTierLegend();
    }
    if (sources.status === "fulfilled") state.sources = sources.value;
    renderFooter();
    renderAbout();
    mapReady.then(() => {
      if (boundary.status === "fulfilled") setSource("boundary", boundary.value);
      if (state.aoi && state.aoi.bbox) map.fitBounds([[state.aoi.bbox[0], state.aoi.bbox[1]], [state.aoi.bbox[2], state.aoi.bbox[3]]], { padding: 40, duration: 0 });
    });
    if (wo.status === "fulfilled") { state.workorders = wo.value.features || wo.value; renderWorkList(); }
    else renderWorkError(wo.reason);
    renderExports();
    loadSegments(state.currentAsOf).catch(() => { /* map stays empty; KPIs still show */ });
    window.__hk = { ready: true };
  }

  /* ---------- Top band, legend, footer ---------- */
  function renderKpis() {
    const s = state.aoi && state.aoi.stats;
    if (!s) return;
    $("kpi-km").textContent = fmt(s.line_km, 1);
    $("kpi-crit").textContent = fmt(s.tier_counts && s.tier_counts.kritik, 0);
    $("kpi-wo").textContent = fmt(s.workorder_count, 0);
  }
  const tierName = (k) => t("tier_" + k);
  function tierChip(k) { return '<span class="tier-chip" style="--tc:' + TIER_COLOR[k] + '"><i></i>' + esc(tierName(k)) + "</span>"; }
  function renderTierLegend() {
    const tc = (state.aoi && state.aoi.stats && state.aoi.stats.tier_counts) || {};
    $("legend-list").innerHTML = TIERS.map((k) =>
      '<li><button type="button" class="lg" data-tier="' + k + '" aria-pressed="' + state.visibleTiers.has(k) + '" title="' + esc(t("legend_toggle")) + '" style="--tc:' + TIER_COLOR[k] + '">' +
      '<span class="sw" style="height:' + Math.round(TIER_W[k][1]) + 'px"></span><span>' + esc(tierName(k)) + '</span><span class="cnt">' + (tc[k] !== undefined ? fmt(tc[k], 0) : "") + "</span></button></li>").join("");
  }
  $("legend-list").addEventListener("click", (e) => {
    const b = e.target.closest(".lg");
    if (!b) return;
    const k = b.dataset.tier;
    if (state.visibleTiers.has(k)) state.visibleTiers.delete(k); else state.visibleTiers.add(k);
    b.setAttribute("aria-pressed", state.visibleTiers.has(k));
    applyTierFilter();
  });
  function renderFooter() {
    const src = state.sources;
    $("foot-sources").innerHTML = src && src.length
      ? "<strong>" + esc(t("footer_data")) + ":</strong> " + src.map((s) => '<a href="' + esc(s.url) + '" target="_blank" rel="noopener">' + esc(s.attribution || s.name) + "</a>").join(" · ")
      : "";
    $("foot-basemap").textContent = state.basemap === "online" ? t("footer_basemap") : state.basemap === "offline" ? t("footer_offline") : "";
  }

  /* ---------- Tabs ---------- */
  const TAB_IDS = ["work", "scenario", "validation", "about"];
  function selectTab(name, focus) {
    const prev = state.tab;
    state.tab = name;
    TAB_IDS.forEach((id) => {
      const on = id === name;
      const tb = $("tab-" + id);
      tb.setAttribute("aria-selected", on);
      tb.tabIndex = on ? 0 : -1;
      $("pane-" + id).hidden = !on;
      if (on && focus) tb.focus();
    });
    if (prev === "validation" && name !== "validation") leaveValidation();
    if (name === "scenario") enterScenario();
    else setLayerVis("scenario-halo", false);
    if (name === "validation") enterValidation();
  }
  function setLayerVis(id, on) { if (state.mapReady) map.setLayoutProperty(id, "visibility", on ? "visible" : "none"); }
  $("tabs").addEventListener("click", (e) => { const b = e.target.closest("[role=tab]"); if (b) selectTab(b.dataset.tab, false); });
  $("tabs").addEventListener("keydown", (e) => {
    const i = TAB_IDS.indexOf(state.tab);
    let n = null;
    if (e.key === "ArrowRight") n = (i + 1) % TAB_IDS.length;
    else if (e.key === "ArrowLeft") n = (i + TAB_IDS.length - 1) % TAB_IDS.length;
    else if (e.key === "Home") n = 0;
    else if (e.key === "End") n = TAB_IDS.length - 1;
    if (n !== null) { e.preventDefault(); selectTab(TAB_IDS[n], true); }
  });

  /* ---------- Work list ---------- */
  function setStatus(el, msg, retry, isErr) {
    el.className = "status" + (isErr ? " err" : "");
    el.innerHTML = esc(msg);
    if (retry) {
      const b = document.createElement("button");
      b.type = "button"; b.className = "btn"; b.textContent = t("retry");
      b.addEventListener("click", retry);
      el.appendChild(b);
    }
  }
  function renderWorkError(err) {
    if (err && (err.status === 503 || err.status === 404)) setStatus($("wo-status"), t("not_computed"), null, false);
    else setStatus($("wo-status"), t("load_error") + (err && err.status ? " (HTTP " + err.status + ")" : ""), () => location.reload(), true);
  }
  function renderWorkList() {
    const list = $("wolist");
    if (!state.workorders) return;
    $("wo-status").textContent = "";
    list.innerHTML = state.workorders.map((f, i) => {
      const p = f.properties;
      const sel = state.selectedSpan === p.span_id;
      return '<li><button type="button" class="wo" data-i="' + i + '" style="--tc:' + TIER_COLOR[p.tier_max] + '"' + (sel ? ' aria-current="true"' : "") + ">" +
        '<div class="wo-top"><span class="wo-prio">#' + esc(p.priority) + "</span>" + tierChip(p.tier_max) + "</div>" +
        '<div class="wo-reason">' + esc(pick(p, "main_reason")) + "</div>" +
        '<div class="wo-meta">' + esc(t("wo_length")) + ": " + fmt(p.length_m, 0) + " " + t("unit_m") + " · " + fmt(p.n_segments, 0) + " " + t("wo_segments") +
        " · " + esc(t("wo_risk_max")) + ": " + fmt(p.risk_max, 1) + " · " + esc(t("wo_strike")) + ": " + fmt(p.strike_tree_count, 0) + "</div></button></li>";
    }).join("");
  }
  function renderExports() {
    [["csv", "exp-csv"], ["geojson", "exp-geojson"], ["gpkg", "exp-gpkg"]].forEach(([f, id]) => { $(id).href = exportUrl(f); });
  }
  $("wolist").addEventListener("click", (e) => { const b = e.target.closest(".wo"); if (b) selectSpan(state.workorders[Number(b.dataset.i)]); });
  $("wolist").addEventListener("keydown", (e) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    const btns = Array.from($("wolist").querySelectorAll(".wo"));
    const i = btns.indexOf(document.activeElement);
    if (i < 0) return;
    e.preventDefault();
    const n = btns[i + (e.key === "ArrowDown" ? 1 : -1)];
    if (n) n.focus();
  });
  async function selectSpan(f) {
    const p = f.properties;
    state.selectedSpan = p.span_id;
    renderWorkList();
    const cur = $("wolist").querySelector('[aria-current="true"]');
    if (cur) cur.focus({ preventScroll: true });
    if (state.segAsOf !== state.currentAsOf) await loadSegments(state.currentAsOf);
    await mapReady;
    setSource("span", f);
    const ids = String(p.segment_ids || "").split(";").filter(Boolean);
    let best = null;
    ids.forEach((id) => { const s = state.segIndex.get(id); if (s && (!best || s.properties.risk > best.properties.risk)) best = s; });
    fitTo(geomBounds(f.geometry), 16);
    if (best) openSegment(best.properties.segment_id, p);
  }

  /* ---------- Drawer ---------- */
  let drawerToken = 0;
  async function openSegment(id, span) {
    const tok = ++drawerToken;
    state.selectedSeg = { id, span, detail: null };
    const dr = $("drawer");
    dr.hidden = false;
    $("drawer-body").innerHTML = '<p class="status">' + esc(t("loading")) + "</p>";
    const feat = state.segIndex.get(id);
    if (feat) setSource("sel", feat);
    try {
      const d = await api("/api/segments/" + encodeURIComponent(id), state.segAsOf !== state.currentAsOf ? { as_of: state.segAsOf } : {});
      if (tok !== drawerToken) return;
      state.selectedSeg.detail = d;
      if (!feat && d.geometry) setSource("sel", d);
      renderDrawer();
      dr.focus({ preventScroll: true });
    } catch (err) {
      if (tok !== drawerToken) return;
      $("drawer-body").innerHTML = '<p class="status err">' + esc(t("load_error")) + (err.status ? " (HTTP " + err.status + ")" : "") + "</p>";
    }
  }
  function closeDrawer() {
    drawerToken++;
    $("drawer").hidden = true;
    state.selectedSeg = null;
    state.selectedSpan = null;
    setSource("sel", EMPTY);
    setSource("span", EMPTY);
    renderWorkList();
  }
  $("drawer-close").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("drawer").hidden) closeDrawer(); });

  function voltLabel(c) {
    const k = "volt_" + c;
    return window.I18N[state.lang][k] ? t(k) : String(c === null || c === undefined ? t("no_data") : c);
  }
  function midpoint(geom) {
    const c = geom.type === "MultiLineString" ? geom.coordinates[0] : geom.coordinates;
    return c[Math.floor(c.length / 2)];
  }
  function rawValue(key, v) {
    if (v === null || v === undefined || Number.isNaN(v)) return t("no_data");
    if (key === "strike_trees") return fmt(v, 0);
    return fmt(v, Math.abs(v) < 1 ? 3 : 2);
  }
  function renderDrawer() {
    const s = state.selectedSeg;
    if (!s || !s.detail) return;
    const d = s.detail, p = d.properties || d;
    const factors = (p.top_factors || []).slice(0, 3);
    const maxC = Math.max.apply(null, factors.map((f) => Math.abs(f.contribution)).concat([0.0001]));
    const mp = d.geometry ? midpoint(d.geometry) : null;
    const gmap = mp ? "https://www.google.com/maps?q=" + mp[1].toFixed(6) + "," + mp[0].toFixed(6) : null;
    let html = "";
    if (s.span) {
      html += '<div class="callout"><strong>' + esc(t("drawer_span")) + " #" + esc(s.span.priority) + "</strong><br>" +
        esc(pick(s.span, "main_reason")) + " · " + fmt(s.span.length_m, 0) + " " + t("unit_m") + " · " + esc(t("wo_risk_max")) + " " + fmt(s.span.risk_max, 1) + "</div>";
    }
    html += '<div class="score"><div class="big" aria-label="' + esc(t("drawer_risk")) + '">' + fmt(p.risk, 1) + "</div><div>" + tierChip(p.tier) + '<div class="small">' + esc(t("drawer_risk")) + "</div></div></div>";
    html += '<p class="small">' + esc(t("drawer_p_ign")) + ": <b>" + fmt(p.p_ignition, 2) + "</b> · " + esc(t("drawer_cons")) + ": <b>" + fmt(p.consequence, 2) + "</b></p>";
    html += "<h3>" + esc(t("drawer_why")) + '</h3>' + (factors.length ? '<ul class="why">' : '<p class="small">' + esc(t("no_factors")) + "</p><ul class=\"why\">") + factors.map((f) =>
      "<li><b>" + esc(pick(f, "label")) + '</b><span class="c">' + esc(t("contrib_fmt", { v: fmt(f.contribution, 1, { signDisplay: "always" }) })) + '</span><div class="cbar" style="width:' + Math.max(4, Math.round(Math.abs(f.contribution) / maxC * 100)) + '%"></div></li>').join("") + "</ul>";
    html += '<p class="small">' + esc(t("drawer_why_note")) + "</p>";
    html += "<h3>" + esc(t("drawer_raw")) + '</h3><table class="raw"><tbody>' + Object.keys(p.raw || {}).map((k) =>
      "<tr><td>" + esc(window.I18N[state.lang]["raw_" + k] ? t("raw_" + k) : k) + "</td><td>" + esc(rawValue(k, p.raw[k])) + "</td></tr>").join("") + "</tbody></table>";
    const chmNote = pick(p, "chm_year_note");
    if (p.chm_year === null || p.chm_year === undefined) html += '<div class="warn">' + esc(chmNote || t("chm_unknown")) + "</div>";
    else html += '<p class="small">' + esc(t("chm_year")) + ": " + esc(p.chm_year) + (chmNote ? " · " + esc(chmNote) : "") + "</p>";
    html += "<h3>" + esc(t("drawer_where")) + '</h3><p class="small">' + esc(t("drawer_line")) + ": " + esc(p.line_id) + " · " + esc(t("drawer_voltage")) + ": " + esc(voltLabel(p.voltage_class)) + "<br>" +
      (mp ? fmt(mp[1], 5, { useGrouping: false }) + ", " + fmt(mp[0], 5, { useGrouping: false }) + "<br>" : "") + "ID: " + esc(p.segment_id) + "</p>";
    if (gmap) html += '<a class="btn" href="' + esc(gmap) + '" target="_blank" rel="noopener">' + esc(t("drawer_open_map")) + "</a>";
    $("drawer-body").innerHTML = html;
  }

  /* ---------- Scenario ---------- */
  function notReady(el, err) {
    const detail = err && (state.lang === "tr" ? err.detail_tr : err.detail_en);
    if (err && (err.status === 503 || err.status === 404)) {
      el.className = "status";
      el.innerHTML = "<strong>" + esc(t("not_computed")) + "</strong><br><span class='small'>" + esc(detail || t("not_computed_hint")) + "</span>";
    } else setStatus(el, t("load_error") + (err && err.status ? " (HTTP " + err.status + ")" : ""), null, true);
  }
  async function enterScenario() {
    setLayerVis("scenario-halo", true);
    if (state.dates) { if (!state.scenario && !state.scenarioErr) runScenario(); return; }
    setStatus($("sc-status"), t("loading"));
    try {
      state.dates = await api("/api/scenario/dates");
    } catch (err) { notReady($("sc-status"), err); state.scenarioErr = err; state.dates = null; return; }
    state.scenarioErr = null;
    $("sc-status").textContent = "";
    initScenarioForm();
    runScenario();
  }
  function initScenarioForm() {
    const dates = state.dates;
    $("sc-date").innerHTML = dates.map((d) => '<option value="' + esc(d.date) + '">' + esc(d.date) + "</option>").join("");
    const maxAll = Math.max.apply(null, dates.map((d) => d.max_gust_kmh));
    const g = $("sc-gust");
    g.min = 0; g.max = Math.ceil(maxAll);
    $("sc-tier").innerHTML = TIERS.slice(0, 3).map((k) => '<option value="' + k + '">' + esc(tierName(k)) + "</option>").join("");
    $("sc-tier").value = "yuksek";
    setGustFromDate();
    $("sc-form").hidden = false;
  }
  function selectedDate() { return (state.dates || []).find((d) => d.date === $("sc-date").value); }
  function setGustFromDate() {
    const d = selectedDate();
    if (d) $("sc-gust").value = Math.floor(d.max_gust_kmh);
    updateGustLabels();
  }
  function updateGustLabels() {
    const d = selectedDate();
    $("sc-gust-out").textContent = fmt($("sc-gust").value, 0);
    $("sc-maxgust").textContent = d ? fmt(d.max_gust_kmh, 1) + " km/h · " + t("sc_max_gust") : "";
  }
  let scTimer = null, scTok = 0;
  function scheduleScenario() { clearTimeout(scTimer); scTimer = setTimeout(runScenario, 250); }
  $("sc-date").addEventListener("change", () => { setGustFromDate(); runScenario(); });
  $("sc-gust").addEventListener("input", () => { updateGustLabels(); scheduleScenario(); });
  $("sc-tier").addEventListener("change", runScenario);
  async function runScenario() {
    if (!state.dates) return;
    const tok = ++scTok;
    const q = { date: $("sc-date").value, gust_kmh: $("sc-gust").value, min_tier: $("sc-tier").value };
    $("sc-result").setAttribute("aria-busy", "true");
    try {
      const r = await api("/api/scenario", q);
      if (tok !== scTok) return;
      state.scenario = r; state.scenarioErr = null;
      $("sc-status").textContent = "";
      await mapReady;
      setSource("scenario", r.segments);
      renderScenario();
    } catch (err) {
      if (tok !== scTok) return;
      state.scenario = null; state.scenarioErr = err;
      setSource("scenario", EMPTY);
      $("sc-result").innerHTML = "";
      notReady($("sc-status"), err);
    } finally { $("sc-result").removeAttribute("aria-busy"); }
  }
  function renderScenario() {
    const r = state.scenario;
    if (!r) return;
    const dw = r.district_wide, tg = r.targeted;
    const card = (cls, title, o, extra) => '<div class="card ' + cls + '"><h3>' + esc(title) + "</h3>" +
      '<div class="row"><span>' + esc(t("sc_line_km")) + "</span><b>" + fmt(o.line_km, 1) + " " + t("unit_km") + "</b></div>" +
      '<div class="row"><span>' + esc(t("sc_buildings")) + "</span><b>" + fmt(o.buildings, 0) + "</b></div>" + (extra || "") + "</div>";
    let html = '<div class="cmp">' + card("", t("sc_district"), dw) +
      card("targeted", t("sc_targeted"), tg, '<div class="row"><span>' + esc(t("sc_covered")) + "</span><b>" + pct(tg.risk_covered_ratio, 0) + "</b></div>") + "</div>";
    html += '<table class="result-table"><tbody><tr><th>' + esc(t("sc_saved_km")) + '</th><td class="n">' + fmt(dw.line_km - tg.line_km, 1) + " " + t("unit_km") + "</td></tr>" +
      "<tr><th>" + esc(t("sc_saved_b")) + '</th><td class="n">' + fmt(dw.buildings - tg.buildings, 0) + "</td></tr></tbody></table>";
    html += '<div class="callout">' + esc(t("sc_proxy")) + "</div>";
    html += '<p class="small">' + esc(t("sc_on_map")) + "</p>";
    const note = pick(r, "note");
    if (note) html += '<p class="small"><strong>' + esc(t("sc_note")) + ":</strong> " + esc(note) + "</p>";
    $("sc-result").innerHTML = html;
  }

  /* ---------- Validation ---------- */
  async function enterValidation() {
    if (!state.backtest && !state.backtestErr) {
      setStatus($("val-status"), t("loading"));
      const [bt, ev] = await Promise.allSettled([api("/api/backtest"), api("/api/backtest/events")]);
      if (bt.status === "fulfilled") { state.backtest = bt.value; state.backtestErr = null; } else state.backtestErr = bt.reason;
      if (ev.status === "fulfilled") state.events = ev.value;
    }
    if (state.tab !== "validation") return;
    if (state.backtestErr && !state.backtest) { notReady($("val-status"), state.backtestErr); $("val-result").innerHTML = ""; return; }
    $("val-status").textContent = "";
    renderValidation();
    await mapReady;
    if (state.events) { setSource("events", state.events); setLayerVis("events-ring", true); $("legend-events").hidden = false; }
    const asOf = state.backtest.as_of;
    if (asOf && asOf !== state.segAsOf) {
      closeDrawer();
      try { await loadSegments(asOf); } catch (e) { /* keep current map when the date is unavailable */ }
    }
    if (state.segAsOf !== state.currentAsOf) { $("map-asof").hidden = false; $("map-asof").textContent = t("val_map_asof") + ": " + state.segAsOf; }
  }
  async function leaveValidation() {
    setLayerVis("events-ring", false);
    $("legend-events").hidden = true;
    $("map-asof").hidden = true;
    if (state.segAsOf !== state.currentAsOf) { closeDrawer(); try { await loadSegments(state.currentAsOf); } catch (e) { /* ignore */ } }
  }
  function ciBlock(o) {
    const lo = o.ci95 && o.ci95[0], hi = o.ci95 && o.ci95[1];
    return '<tr><th>' + esc(t("val_ci")) + '</th><td class="n">' + (lo === undefined ? esc(t("no_data")) : fmt(lo, 1) + " – " + fmt(hi, 1)) + "</td></tr>";
  }
  function liftBar(o) {
    if (!o.ci95) return "";
    const top = Math.max(o.ci95[1], o.lift, 1) * 1.1;
    const x = (v) => (Math.min(v, top) / top * 100).toFixed(1) + "%";
    return '<div class="ci" role="img" aria-label="' + esc(t("val_lift") + " " + fmt(o.lift, 1) + ", " + t("val_ci") + " " + fmt(o.ci95[0], 1) + " – " + fmt(o.ci95[1], 1)) + '">' +
      '<div class="ref" style="left:' + x(1) + '"></div><div class="bar" style="left:' + x(o.ci95[0]) + ";width:" + (((Math.min(o.ci95[1], top) - o.ci95[0]) / top) * 100).toFixed(1) + '%"></div><div class="pt" style="left:' + x(o.lift) + '"></div></div>';
  }
  function renderValidation() {
    const b = state.backtest;
    if (!b) return;
    const block = (title, o) => !o ? "" : "<h3>" + esc(title) + "</h3><table class='result-table'><tbody>" +
      "<tr><th>" + esc(t("val_share")) + '</th><td class="n">' + pct(o.share, 0) + "</td></tr>" +
      "<tr><th>" + esc(t("val_expected")) + '</th><td class="n">' + pct(o.expected, 0) + "</td></tr>" +
      "<tr><th>" + esc(t("val_lift")) + '</th><td class="n">' + fmt(o.lift, 1) + "×</td></tr>" + ciBlock(o) + "</tbody></table>" + liftBar(o);
    let html = "<table class='result-table'><tbody>" +
      "<tr><th>" + esc(t("val_asof")) + '</th><td class="n">' + esc(b.as_of) + "</td></tr>" +
      "<tr><th>" + esc(t("val_season")) + '</th><td class="n">' + esc(b.season) + "</td></tr>" +
      "<tr><th>" + esc(t("val_events")) + '</th><td class="n">' + fmt(b.n_events, 0) + "</td></tr></tbody></table>";
    html += block(t("val_top10"), b.top10) + block(t("val_top20"), b.top20);
    const bl = b.baselines || {};
    const keys = Object.keys(bl);
    if (keys.length) {
      const cell = (o) => (o ? pct(o.share, 0) + " · " + fmt(o.lift, 1) + "× (" + (o.ci95 ? fmt(o.ci95[0], 1) + "–" + fmt(o.ci95[1], 1) : t("no_data")) + ")" : t("no_data"));
      html += "<h3>" + esc(t("val_baselines")) + "</h3><table class='result-table'><thead><tr><th></th><th>" + esc(t("val_top10")) + "</th><th>" + esc(t("val_top20")) + "</th></tr></thead><tbody>" +
        keys.map((k) => { const v = bl[k] || {}; return "<tr><td>" + esc(pick(v, "label") || k.replace(/_/g, " ")) + "</td><td>" + cell(v.top10) + "</td><td>" + cell(v.top20) + "</td></tr>"; }).join("") + "</tbody></table>";
    }
    const lim = pick(b, "limitations") || [];
    if (lim.length) html += "<h3>" + esc(t("val_limits")) + '</h3><ul class="plain">' + lim.map((x) => "<li>" + esc(x) + "</li>").join("") + "</ul>";
    $("val-result").innerHTML = html;
  }

  /* ---------- About ---------- */
  function renderAbout() {
    const h = state.health || {};
    const a = state.aoi || {};
    $("about-meta").innerHTML = '<dl class="meta-grid"><dt>' + esc(t("about_aoi")) + "</dt><dd>" + esc(a.name || h.aoi || "") + "</dd><dt>" + esc(t("about_data_version")) + "</dt><dd>" + esc(h.data_version || "") + "</dd></dl>";
    if (state.sources) {
      $("about-sources").textContent = "";
      $("sources-list").innerHTML = state.sources.map((s) => "<li><strong>" + esc(s.name) + "</strong> — " + esc(s.license) + "<br>" + esc(s.attribution) + '<br><a href="' + esc(s.url) + '" target="_blank" rel="noopener">' + esc(s.url) + "</a></li>").join("");
    } else setStatus($("about-sources"), t("sources_error"), null, true);
  }

  /* ---------- Language toggle ---------- */
  function rerender() {
    applyStaticI18n();
    renderKpis(); renderTierLegend(); renderFooter(); renderAbout(); renderWorkList();
    if (state.selectedSeg && state.selectedSeg.detail) renderDrawer();
    if (state.dates) {
      const v = $("sc-tier").value;
      $("sc-tier").innerHTML = TIERS.slice(0, 3).map((k) => '<option value="' + k + '">' + esc(tierName(k)) + "</option>").join("");
      $("sc-tier").value = v;
      updateGustLabels();
    }
    renderScenario();
    renderValidation();
    if (!$("map-asof").hidden) $("map-asof").textContent = t("val_map_asof") + ": " + state.segAsOf;
    if (state.scenarioErr && state.tab === "scenario") notReady($("sc-status"), state.scenarioErr);
    if (state.backtestErr && !state.backtest && state.tab === "validation") notReady($("val-status"), state.backtestErr);
  }
  $("lang-btn").addEventListener("click", () => {
    state.lang = state.lang === "tr" ? "en" : "tr";
    try { localStorage.setItem("hk_lang", state.lang); } catch (e) { /* ignore */ }
    rerender();
  });

  boot();
})();
