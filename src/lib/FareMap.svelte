<script>
  import { untrack } from 'svelte';
  import maplibregl from 'maplibre-gl';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import { loadLines } from './data.js';
  import { fareColor, ACCENT } from './fare.js';
  import { stationName } from './i18n.js';

  let { stations, rows, origin, selected, operator, lang, onSelect } = $props();

  const STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';
  const NAME_ZOOM = 11;
  const FIT = { padding: { top: 70, bottom: 70, left: 400, right: 70 }, duration: 600 };

  let container;
  let map = $state(null);
  let linesReady = $state(false);
  let zoom = $state(9.6);

  const markers = new Map();
  let camera = null;

  const byStation = $derived(new Map(rows.map((r) => [r.station, r])));

  const range = $derived.by(() => {
    if (!rows.length) return [0, 0];
    let min = Infinity;
    let max = -Infinity;
    for (const r of rows) {
      if (r.fare < min) min = r.fare;
      if (r.fare > max) max = r.fare;
    }
    return [min, max];
  });

  function networkBounds() {
    const b = new maplibregl.LngLatBounds();
    b.extend(stations[origin].coord);
    for (const r of rows) b.extend(stations[r.station].coord);
    return b;
  }

  $effect(() => {
    const m = new maplibregl.Map({
      container,
      style: STYLE,
      center: [139.6, 35.6],
      zoom: 9.6,
      attributionControl: false,
    });
    // Source attribution is required by both data providers.
    m.addControl(
      new maplibregl.AttributionControl({
        compact: true,
        customAttribution: [
          '<a href="https://www.odpt.org/" rel="noreferrer">Open Data Platform for Transportation</a>',
          '<a href="https://uedayou.net/jrslod/" rel="noreferrer">JR-SLOD</a>',
        ],
      }),
    );
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
    m.on('zoomend', () => (zoom = m.getZoom()));
    m.on('moveend', scheduleCull);
    m.on('error', (e) => console.error('maplibre:', e.error?.message ?? e));

    // Markers are DOM overlays, so they must not wait on the basemap style or its
    // tiles. Line layers do need a parsed style, which `styledata` announces.
    let removed = false;
    const pending = loadLines().catch((e) => void console.error(e));
    const attachLines = () => {
      if (linesReady) return;
      pending
        .then((data) => {
          if (!data || linesReady || removed || m.getSource('lines')) return;
          m.addSource('lines', { type: 'geojson', data });
          m.addLayer({
            id: 'lines-dim',
            type: 'line',
            source: 'lines',
            layout: { 'line-cap': 'round', 'line-join': 'round' },
            paint: { 'line-color': ['get', 'color'], 'line-width': 1.6, 'line-opacity': 0.28 },
          });
          m.addLayer({
            id: 'lines-active',
            type: 'line',
            source: 'lines',
            layout: { 'line-cap': 'round', 'line-join': 'round' },
            paint: {
              'line-color': ['get', 'color'],
              'line-width': ['interpolate', ['linear'], ['zoom'], 8, 2.2, 13, 4],
              'line-opacity': 0.95,
            },
          });
          linesReady = true;
        })
        .catch(() => {}); // style not parsed yet; the next styledata retries
    };
    m.on('styledata', attachLines);

    map = m;

    return () => {
      removed = true;
      for (const { marker } of markers.values()) marker.remove();
      markers.clear();
      m.remove();
      map = null;
      linesReady = false;
      camera = null;
    };
  });

  // Highlight the operator whose fares are on screen; recede the rest. With no
  // origin picked there is no operator, so the whole network stays faint.
  $effect(() => {
    if (!map || !linesReady) return;
    const active = operator ?? '';
    map.setFilter('lines-active', ['==', ['get', 'operator'], active]);
    map.setFilter('lines-dim', ['!=', ['get', 'operator'], active]);
  });

  // First paint frames the whole network; picking an origin flies to it;
  // switching operator reframes the network that replaced it.
  $effect(() => {
    const nextOrigin = origin;
    const nextOperator = operator;
    if (!map || !rows.length) return;

    untrack(() => {
      if (!camera) map.fitBounds(networkBounds(), FIT);
      else if (camera.origin !== nextOrigin)
        map.flyTo({ center: stations[nextOrigin].coord, zoom: Math.max(map.getZoom(), 10.6), speed: 0.9 });
      else if (camera.operator !== nextOperator) map.fitBounds(networkBounds(), FIT);
      camera = { origin: nextOrigin, operator: nextOperator };
    });
  });

  $effect(() => {
    if (!map) return;

    const fares = byStation;
    const wanted = new Set(fares.keys());
    if (origin !== null) wanted.add(origin);

    for (const [idx, { marker }] of markers) {
      if (!wanted.has(idx)) {
        marker.remove();
        markers.delete(idx);
      }
    }

    const [min, max] = range;
    const showName = zoom >= NAME_ZOOM;

    for (const idx of wanted) {
      let entry = markers.get(idx);
      if (!entry) {
        const el = document.createElement('div');
        el.className = 'farepill';
        el.addEventListener('click', (e) => {
          e.stopPropagation();
          onSelect(idx);
        });
        const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
          .setLngLat(stations[idx].coord)
          .addTo(map);
        entry = { el, marker };
        markers.set(idx, entry);
      }
      paint(entry.el, idx, fares.get(idx), min, max, showName);
    }
    scheduleCull();
  });

  // A network runs to ~200 stations, so at low zoom the pills pile up. Origin and
  // selection always win, then the cheapest fares; whatever still collides drops
  // to a fare-coloured dot rather than disappearing.
  let cullQueued = false;
  function scheduleCull() {
    if (cullQueued || !map) return;
    cullQueued = true;
    requestAnimationFrame(() => {
      cullQueued = false;
      if (map) cull();
    });
  }

  function cull() {
    const order = [...markers.keys()].sort((a, b) => {
      if (a === origin) return -1;
      if (b === origin) return 1;
      if (a === selected) return -1;
      if (b === selected) return 1;
      return (byStation.get(a)?.fare ?? 0) - (byStation.get(b)?.fare ?? 0);
    });

    // Measure every pill at full size so the outcome doesn't depend on the last pass.
    for (const idx of order) markers.get(idx).el.classList.remove('dot');

    const boxes = order.map((idx) => {
      const el = markers.get(idx).el;
      const { x, y } = map.project(stations[idx].coord);
      const w = el.offsetWidth / 2 + 2;
      const h = el.offsetHeight / 2 + 2;
      return [x - w, y - h, x + w, y + h];
    });

    // The panel and legend sit above the map, so pills behind them are wasted.
    const kept = overlayBoxes();
    for (let i = 0; i < order.length; i++) {
      const idx = order[i];
      if (idx === origin || idx === selected || !kept.some((k) => overlaps(k, boxes[i]))) kept.push(boxes[i]);
      else markers.get(idx).el.classList.add('dot');
    }
  }

  function overlayBoxes() {
    const base = container.getBoundingClientRect();
    return [...container.parentElement.querySelectorAll('.panel, .legend')].map((el) => {
      const r = el.getBoundingClientRect();
      return [r.left - base.left, r.top - base.top, r.right - base.left, r.bottom - base.top];
    });
  }

  const overlaps = (a, b) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];

  function paint(el, idx, row, min, max, showName) {
    const name = esc(stationName(stations[idx], lang));

    if (idx === origin) {
      el.style.cursor = 'pointer';
      el.style.pointerEvents = 'auto';
      el.style.zIndex = '30';
      el.innerHTML = `<div class="pill-inner pill-origin" style="background:${ACCENT}">${name}</div>`;
      return;
    }
    if (!row) return;

    const isSelected = idx === selected;
    const color = fareColor(row.fare, min, max);
    const border = isSelected ? '#1A202C' : '#fff';
    const fare = `<span class="pill-fare" style="background:${color}">¥${row.fare}</span>`;

    const pill =
      showName || isSelected
        ? `<div class="pill-inner pill-stack" style="border-color:${border}"><span class="pill-name">${name}</span>${fare}</div>`
        : `<div class="pill-inner pill-flat" style="border-color:${border}">${fare}</div>`;

    el.style.cursor = 'pointer';
    el.style.pointerEvents = 'auto';
    el.style.zIndex = isSelected ? '28' : '15';
    el.title = `${stationName(stations[idx], lang)} ¥${row.fare}`;
    el.innerHTML = `${pill}<span class="pill-dot" style="background:${color}"></span>`;
  }

  const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
  const esc = (s) => s.replace(/[&<>"]/g, (c) => ESCAPES[c]);
</script>

<div class="map" bind:this={container}></div>

<style>
  /* Own stacking context, so marker z-indexes stay under the panel and legend. */
  .map {
    position: absolute;
    inset: 0;
    z-index: 0;
    background: #e2e8f0;
  }

  :global(.farepill:hover) {
    z-index: 40 !important;
  }
  :global(.farepill:hover .pill-inner) {
    transform: translateY(-1px) scale(1.06);
  }
  :global(.pill-inner) {
    font-family: 'Inter', 'Hiragino Sans', sans-serif;
    white-space: nowrap;
    transition: transform 0.12s ease;
  }
  :global(.pill-origin) {
    display: inline-flex;
    align-items: center;
    font-weight: 700;
    font-size: 12px;
    color: #fff;
    padding: 4px 10px;
    border-radius: 8px;
    border: 2px solid #fff;
    box-shadow: 0 3px 8px rgb(0 0 0 / 0.3);
  }
  :global(.pill-stack),
  :global(.pill-flat) {
    border-radius: 8px;
    overflow: hidden;
    border: 2px solid #fff;
    box-shadow: 0 2px 6px rgb(0 0 0 / 0.28);
  }
  :global(.pill-stack) {
    display: flex;
    flex-direction: column;
    align-items: stretch;
  }
  :global(.pill-flat) {
    display: inline-flex;
  }
  :global(.pill-name) {
    background: #fff;
    color: #1a202c;
    font-weight: 600;
    font-size: 11px;
    padding: 2px 9px;
    text-align: center;
    border-bottom: 1px solid rgb(0 0 0 / 0.08);
  }
  :global(.pill-fare) {
    color: #fff;
    font-weight: 700;
    font-size: 12px;
    padding: 2px 9px;
    text-align: center;
  }

  :global(.pill-dot) {
    display: none;
    width: 9px;
    height: 9px;
    border-radius: 50%;
    border: 1.5px solid #fff;
    box-shadow: 0 1px 3px rgb(0 0 0 / 0.35);
  }
  :global(.farepill.dot .pill-inner) {
    display: none;
  }
  :global(.farepill.dot .pill-dot) {
    display: block;
  }
  :global(.farepill.dot:hover .pill-dot) {
    transform: scale(1.3);
  }
  :global(.maplibregl-ctrl-attrib) {
    font-size: 9px;
    opacity: 0.55;
  }
</style>
