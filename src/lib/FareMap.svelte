<script>
  import { untrack } from 'svelte';
  import maplibregl from 'maplibre-gl';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import { loadLines } from './data.js';
  import { fareColor, ACCENT } from './fare.js';
  import { stationName } from './i18n.js';
  import { isMobile } from './media.svelte.js';

  let { stations, rows, origin, selected, hovered, operator, lang, onSelect } = $props();

  const STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';
  const NAME_ZOOM = 11;

  // The panel eats the left edge on desktop and the bottom on mobile, so the
  // network has to be framed into whatever is left.
  function fitOptions() {
    if (!isMobile.current) {
      return { padding: { top: 70, bottom: 70, left: 400, right: 70 }, duration: 600 };
    }
    const bottom = Math.min(340, Math.round(window.innerHeight * 0.42)); // the half-open sheet
    return { padding: { top: 90, bottom, left: 20, right: 20 }, duration: 600 };
  }

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
      // A fare map is read north-up, and on a touch screen both gestures are
      // mostly triggered by accident.
      dragRotate: false,
      pitchWithRotate: false,
      touchPitch: false,
    });
    m.touchZoomRotate.disableRotation();
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

    // Sliding the sheet uncovers or buries pills without moving the map, so the
    // cull has to rerun when it settles. Pill hover animates transform too — hence
    // the check for the panel itself.
    const stage = container.parentElement;
    const onSheetSettled = (e) => {
      if (e.propertyName === 'transform' && e.target.classList.contains('panel')) scheduleCull();
    };
    stage.addEventListener('transitionend', onSheetSettled);

    map = m;

    return () => {
      removed = true;
      stage.removeEventListener('transitionend', onSheetSettled);
      for (const { marker } of markers.values()) marker.remove();
      markers.clear();
      m.remove();
      map = null;
      linesReady = false;
      camera = null;
    };
  });

  // MapLibre ships the attribution expanded, which costs two lines of a phone
  // screen. Collapse it to the ⓘ button there; the credit is one tap away.
  $effect(() => {
    if (!map) return;
    const attrib = container.querySelector('.maplibregl-ctrl-attrib');
    attrib?.classList.toggle('maplibregl-compact-show', !isMobile.current);
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
      if (!camera) map.fitBounds(networkBounds(), fitOptions());
      else if (camera.origin !== nextOrigin)
        map.flyTo({
          center: stations[nextOrigin].coord,
          zoom: Math.max(map.getZoom(), 10.6),
          speed: 0.9,
          // Lift the origin clear of the sheet instead of parking it under one.
          offset: isMobile.current ? [0, -Math.round(window.innerHeight * 0.16)] : [0, 0],
        });
      else if (camera.operator !== nextOperator) map.fitBounds(networkBounds(), fitOptions());
      camera = { origin: nextOrigin, operator: nextOperator };
    });
  });

  $effect(() => {
    if (!map) return;
    // Referenced only for its reactive dependency: a hover change repaints pills
    // without touching which markers exist.
    void hovered;

    const fares = byStation;
    const wanted = new Set(fares.keys());
    if (origin !== null) wanted.add(origin);

    for (const [key, entry] of markers) {
      if (!wanted.has(entry.idx)) {
        entry.marker.remove();
        markers.delete(key);
      }
    }

    const [min, max] = range;
    const showName = zoom >= NAME_ZOOM;

    // A complex spanning several physically distinct stations (members) gets one
    // marker per member, all keyed to the same fare node — clicking any of them
    // opens that node, since the fare is per complex, not per platform.
    for (const idx of wanted) {
      const points = stations[idx].members ?? [stations[idx]];
      for (let n = 0; n < points.length; n++) {
        const point = points[n];
        const key = points.length > 1 ? `${idx}:${n}` : `${idx}`;
        let entry = markers.get(key);
        if (!entry) {
          const el = document.createElement('div');
          el.className = 'farepill';
          el.addEventListener('click', (e) => {
            e.stopPropagation();
            onSelect(idx, n); // the node's fare, but opened on the station you tapped
          });
          const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
            .setLngLat(point.coord)
            .addTo(map);
          entry = { idx, el, marker, point };
          markers.set(key, entry);
        }
        paint(entry.el, idx, point, fares.get(idx), min, max, showName);
      }
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
    // A rank, not a chain of early returns: a complex can now contribute several
    // markers sharing one idx, so both sides of a comparison can be the origin.
    const rank = (idx) => (idx === origin ? 0 : idx === selected ? 1 : 2);
    const order = [...markers.keys()].sort((a, b) => {
      const ea = markers.get(a);
      const eb = markers.get(b);
      return (
        rank(ea.idx) - rank(eb.idx) ||
        (byStation.get(ea.idx)?.fare ?? 0) - (byStation.get(eb.idx)?.fare ?? 0)
      );
    });

    // Measure every pill at full size so the outcome doesn't depend on the last pass.
    for (const key of order) markers.get(key).el.classList.remove('dot');

    const boxes = order.map((key) => {
      const entry = markers.get(key);
      const { x, y } = map.project(entry.point.coord);
      const w = entry.el.offsetWidth / 2 + 2;
      const h = entry.el.offsetHeight / 2 + 2;
      return [x - w, y - h, x + w, y + h];
    });

    // The panel and legend sit above the map, so pills behind them are wasted.
    const kept = overlayBoxes();
    for (let i = 0; i < order.length; i++) {
      const entry = markers.get(order[i]);
      if (entry.idx === origin || entry.idx === selected || !kept.some((k) => overlaps(k, boxes[i])))
        kept.push(boxes[i]);
      else entry.el.classList.add('dot');
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

  function paint(el, idx, point, row, min, max, showName) {
    const name = esc(stationName(point, lang));

    if (idx === origin) {
      el.style.cursor = 'pointer';
      el.style.pointerEvents = 'auto';
      el.style.zIndex = '30';
      el.innerHTML = `<div class="pill-inner pill-origin" style="background:${ACCENT}">${name}</div>`;
      return;
    }
    if (!row) return;

    const isSelected = idx === selected;
    const isHovered = idx === hovered;
    const color = fareColor(row.fare, min, max);
    const border = isSelected || isHovered ? '#1A202C' : '#fff';
    const fare = `<span class="pill-fare" style="background:${color}">¥${row.fare}</span>`;

    const pill =
      showName || isSelected || isHovered
        ? `<div class="pill-inner pill-stack" style="border-color:${border}"><span class="pill-name">${name}</span>${fare}</div>`
        : `<div class="pill-inner pill-flat" style="border-color:${border}">${fare}</div>`;

    el.style.cursor = 'pointer';
    el.style.pointerEvents = 'auto';
    el.style.zIndex = isSelected || isHovered ? '28' : '15';
    el.title = `${stationName(point, lang)} ¥${row.fare}`;
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

  @media (hover: hover) {
    :global(.farepill:hover) {
      z-index: 40 !important;
    }
    :global(.farepill:hover .pill-inner) {
      transform: translateY(-1px) scale(1.06);
    }
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

  @media (max-width: 768px) {
    /* A pill is a small target for a thumb; grow the hit area without growing the pill. */
    :global(.farepill::after) {
      content: '';
      position: absolute;
      inset: -8px;
    }
    :global(.pill-name) {
      font-size: 12px;
      padding: 3px 10px;
    }
    :global(.pill-fare) {
      font-size: 13px;
      padding: 3px 10px;
    }
    :global(.pill-dot) {
      width: 11px;
      height: 11px;
    }
    /* Pinch does the job, and the buttons would sit under the sheet anyway. */
    :global(.maplibregl-ctrl-bottom-right .maplibregl-ctrl-group) {
      display: none;
    }
    /* The sheet owns the bottom of the screen, so attribution moves out from under it. */
    :global(.maplibregl-ctrl-bottom-right) {
      top: 0;
      right: auto;
      bottom: auto;
      left: 0;
    }
  }
</style>
