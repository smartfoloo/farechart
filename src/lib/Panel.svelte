<script>
  import { fareColor } from './fare.js';
  import { stationName, stationSub, operatorName } from './i18n.js';
  import { isMobile, viewport } from './media.svelte.js';
  import { dragY } from './drag.js';
  import MultiRouteIcon from './MultiRouteIcon.svelte';

  let {
    t,
    lang,
    stations,
    operators,
    origin,
    activeOperator,
    fareMode,
    passenger,
    rows,
    selected,
    range,
    onSetLang,
    onPickOrigin,
    onSetOperator,
    onSetFareMode,
    onSetPassenger,
    onSelectDest,
  } = $props();

  const MAX_SUGGESTIONS = 40;

  let query = $state(null);
  let open = $state(false);

  const originName = $derived(origin === null ? '' : stationName(stations[origin], lang));
  const text = $derived(query ?? originName);

  const suggestions = $derived.by(() => {
    const term = (query ?? '').trim();
    const showAll = !term || term === originName;
    const lower = term.toLowerCase();
    const out = [];
    for (let i = 0; i < stations.length && out.length < MAX_SUGGESTIONS; i++) {
      const s = stations[i];
      if (showAll || s.ja.includes(term) || s.en.toLowerCase().includes(lower)) out.push(i);
    }
    return out;
  });

  const operatorChips = $derived(
    origin === null
      ? []
      : stations[origin].ops.map((key) => operators.find((o) => o.key === key)).filter(Boolean),
  );

  // ODPT publishes each operator's tariff as of a date, and some are years stale.
  const issued = $derived(operators.find((o) => o.key === activeOperator)?.issued);

  // --- Bottom sheet (mobile only) -------------------------------------------
  // Ordered top to bottom: a larger offset means less of the sheet is on screen.
  const DETENTS = ['full', 'half', 'collapsed'];
  const FLICK = 0.4; // px/ms past which a release counts as a flick, not a drop
  const TAP = 4; // px of travel under which a drag on the handle is really a tap

  const mobile = $derived(isMobile.current);

  let detent = $state('half');
  let dragOffset = $state(null); // live translateY mid-drag; null when settled
  let dragBase = 0;

  // Visual viewport, so the sheet sizes to what's actually on screen once a
  // keyboard is up rather than to the full (unchanged) layout viewport.
  const viewH = $derived(viewport.height);
  const keyboard = $derived(mobile ? viewport.keyboard : 0);

  let sheetH = $state(0);
  let peekH = $state(0); // the handle + search block, the only part left visible when collapsed
  let safeB = $state(0); // home-indicator inset, measured from env() by the probe

  const offsets = $derived.by(() => {
    const collapsed = Math.max(0, sheetH - peekH - safeB);
    const half = Math.min(collapsed, Math.max(0, sheetH - Math.round(viewH * 0.45)));
    return { full: 0, half, collapsed };
  });

  const offset = $derived(dragOffset ?? offsets[detent]);
  const collapsed = $derived(mobile && detent === 'collapsed' && dragOffset === null);

  const clamp = (y) => Math.min(offsets.collapsed, Math.max(0, y));

  const nearest = (y) =>
    DETENTS.reduce((best, d) => (Math.abs(offsets[d] - y) < Math.abs(offsets[best] - y) ? d : best));

  function snapTo(next) {
    detent = next;
    dragOffset = null;
  }

  function step(dir) {
    const i = DETENTS.indexOf(detent) + dir;
    snapTo(DETENTS[Math.min(DETENTS.length - 1, Math.max(0, i))]);
  }

  const toggle = () => snapTo(detent === 'collapsed' ? 'half' : 'collapsed');

  function onDragStart() {
    dragBase = offsets[detent];
    dragOffset = dragBase;
  }

  function onDrag(dy) {
    dragOffset = clamp(dragBase + dy);
  }

  // A flick carries the sheet one detent further than where the finger left it.
  function onDragEnd(dy, velocity) {
    if (Math.abs(dy) < TAP) {
      toggle();
      return;
    }
    const from = DETENTS.indexOf(nearest(clamp(dragBase + dy)));
    const i = Math.abs(velocity) > FLICK ? from + (velocity > 0 ? 1 : -1) : from;
    snapTo(DETENTS[Math.min(DETENTS.length - 1, Math.max(0, i))]);
  }

  let input;

  function pick(idx) {
    query = null;
    open = false;
    input?.blur(); // dismiss the keyboard; the choice is made
    onPickOrigin(idx);
    if (mobile) snapTo('half'); // hand the map back once a station is chosen
  }

  // iOS Safari doesn't focus a button on tap, so the input's focusout fires with a
  // null relatedTarget and tears the list down before the click can land. Commit on
  // pointerdown and keep focus where it is; click then only has to serve keyboards.
  function onSuggestionDown(e, idx) {
    e.preventDefault();
    pick(idx);
  }

  // The suggestion list drops below the input, so it needs the sheet open to land on screen.
  function focusSearch() {
    open = true;
    if (mobile && detent !== 'full') snapTo('full');
  }
</script>

<aside
  class="panel"
  class:sheet={mobile}
  class:dragging={dragOffset !== null}
  bind:clientHeight={sheetH}
  style={mobile
    ? `--sheet-y: ${offset}px; --sheet-h: ${Math.round(viewH * 0.88)}px; --kb: ${keyboard}px`
    : ''}
>
  <div class="safe-probe" bind:clientHeight={safeB} aria-hidden="true"></div>

  <div class="peek" bind:clientHeight={peekH}>
    {#if mobile}
      <button
        class="grabber"
        aria-label={t.sheetHandle}
        aria-expanded={detent !== 'collapsed'}
        use:dragY={{ onStart: onDragStart, onMove: onDrag, onEnd: onDragEnd }}
        onclick={(e) => e.detail === 0 && toggle()}
        onkeydown={(e) => {
          if (e.key === 'ArrowUp') step(-1);
          else if (e.key === 'ArrowDown') step(1);
          else return;
          e.preventDefault();
        }}
      >
        <span class="grip"></span>
      </button>
    {/if}

    <div class="head">
      <div class="head-row">
        <h1 class="brand">Farechart</h1>
        <div class="langs" role="group" aria-label="Language">
          <button
            class:active={lang === 'en'}
            aria-pressed={lang === 'en'}
            onclick={() => onSetLang('en')}>EN</button
          >
          <button
            class:active={lang === 'ja'}
            aria-pressed={lang === 'ja'}
            onclick={() => onSetLang('ja')}>JA</button
          >
        </div>
      </div>
      <div class="sub">{t.explorerSub}</div>
    </div>

    <!-- Keep the list open while focus moves between the input and its options. -->
    <div
      class="block search"
      onfocusout={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) open = false;
      }}
    >
      <label for="origin-input">{t.origin}</label>
      <div class="field">
        <svg class="glyph" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2" />
          <path d="M16 16l4.5 4.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        </svg>
        <input
          id="origin-input"
          bind:this={input}
          value={text}
          placeholder={t.searchPh}
          autocomplete="off"
          autocorrect="off"
          autocapitalize="off"
          spellcheck="false"
          enterkeyhint="search"
          role="combobox"
          aria-expanded={open && suggestions.length > 0}
          aria-controls="origin-suggestions"
          oninput={(e) => {
            query = e.currentTarget.value;
            open = true;
          }}
          onfocus={focusSearch}
          onkeydown={(e) => {
            if (e.key === 'Escape') {
              open = false;
              e.currentTarget.blur();
            } else if (e.key === 'Enter' && open && suggestions.length) {
              e.preventDefault();
              pick(suggestions[0]);
            }
          }}
        />
      </div>

      {#if open && suggestions.length}
        <div class="suggestions" id="origin-suggestions" role="listbox">
          {#each suggestions as idx (idx)}
            <button
              class="suggestion"
              class:current={idx === origin}
              role="option"
              aria-selected={idx === origin}
              onpointerdown={(e) => onSuggestionDown(e, idx)}
              onclick={(e) => e.detail === 0 && pick(idx)}
            >
              <span class="primary">{stationName(stations[idx], lang)}</span>
              <span class="secondary">{stationSub(stations[idx], lang)}</span>
            </button>
          {/each}
        </div>
      {/if}
    </div>
  </div>

  <!-- Below the peek line: unreachable by keyboard while the sheet is collapsed. -->
  <div class="rest" inert={collapsed}>
    {#if operatorChips.length}
      <div class="block">
        <div class="block-head">
          <span class="block-title">{t.operator}</span>
          <span class="block-hint">{t.departingVia}</span>
        </div>
        <div class="chips">
          {#each operatorChips as op (op.key)}
            <button
              class="chip"
              class:active={op.key === activeOperator}
              disabled={operatorChips.length === 1}
              onclick={() => onSetOperator(op.key)}
            >
              {operatorName(op, lang)}
            </button>
          {/each}
        </div>
        {#if issued}
          <div class="vintage">{t.faresAsOf} {issued}</div>
        {/if}
      </div>
    {/if}

    <div class="block">
      <div class="block-head"><span class="block-title">{t.fareType}</span></div>
      <div class="segmented">
        <button class:active={fareMode === 'ic'} onclick={() => onSetFareMode('ic')}>{t.ic}</button>
        <button class:active={fareMode === 'ticket'} onclick={() => onSetFareMode('ticket')}>{t.ticket}</button>
      </div>
    </div>

    <div class="block">
      <div class="block-head"><span class="block-title">{t.passengerType}</span></div>
      <div class="segmented">
        <button class:active={passenger === 'adult'} onclick={() => onSetPassenger('adult')}>{t.adult}</button>
        <button class:active={passenger === 'child'} onclick={() => onSetPassenger('child')}>{t.child}</button>
      </div>
    </div>

    <div class="list-head">{t.dest}</div>
    <div class="list">
      {#if !rows.length}
        <div class="empty">{origin === null ? t.startPrompt : t.loading}</div>
      {/if}
      {#each rows as row (row.station)}
        {@const color = fareColor(row.fare, range[0], range[1])}
        <button class="row" class:selected={row.station === selected} onclick={() => onSelectDest(row.station)}>
          <span class="row-name">{stationName(stations[row.station], lang)}</span>
          <span class="row-fare">
            {#if stations[row.station].ops.length > 1}
              <MultiRouteIcon size={13} {color} />
            {/if}
            <span class="amount" style="color: {color}">¥{row.fare}</span>
          </span>
        </button>
      {/each}
    </div>
  </div>
</aside>

<style>
  .panel {
    position: absolute;
    top: 20px;
    left: 20px;
    width: 340px;
    max-height: calc(100% - 40px);
    z-index: 5;
    display: flex;
    flex-direction: column;
    background: #fff;
    border-radius: 14px;
    border: 1px solid var(--line);
    box-shadow: var(--shadow-panel);
    overflow: hidden;
  }
  .peek {
    flex: 0 0 auto;
  }
  .rest {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .safe-probe {
    position: absolute;
    bottom: 0;
    left: 0;
    width: 0;
    height: env(safe-area-inset-bottom, 0px);
    pointer-events: none;
  }

  .head {
    padding: 18px 20px 16px;
  }
  .head-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }
  .langs {
    display: inline-flex;
    gap: 2px;
    flex: 0 0 auto;
    border: 1px solid var(--line);
    background: var(--surface);
    border-radius: 8px;
    padding: 2px;
  }
  .langs button {
    font: inherit;
    font-weight: 600;
    font-size: 11.5px;
    letter-spacing: 0.3px;
    padding: 4px 9px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    transition: all 0.12s;
  }
  .langs button.active {
    background: var(--accent);
    color: #fff;
  }
  .brand {
    font-family: 'Libre Baskerville', serif;
    font-size: 22px;
    font-weight: 400;
    line-height: 1.2;
    margin: 0;
    color: var(--ink);
    letter-spacing: -0.3px;
  }
  .sub {
    font-size: 12.5px;
    color: var(--muted-2);
    margin-top: 3px;
  }

  .block {
    padding: 12px 20px 14px;
    border-bottom: 1px solid var(--line-soft);
  }
  .search {
    position: relative;
    padding-top: 0;
  }
  .search label {
    display: block;
    font-weight: 500;
    font-size: 12px;
    color: var(--muted);
    margin-bottom: 6px;
  }

  .field {
    position: relative;
  }
  .glyph {
    position: absolute;
    left: 11px;
    top: 50%;
    transform: translateY(-50%);
    width: 16px;
    height: 16px;
    color: var(--muted-3);
    pointer-events: none;
  }
  input {
    width: 100%;
    height: 42px;
    padding: 0 12px 0 32px;
    font: inherit;
    font-size: 15px;
    color: var(--ink);
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 8px;
    outline: none;
  }
  input:focus {
    border-color: var(--accent);
    background: #fff;
    box-shadow: 0 0 0 3px rgb(49 130 206 / 0.18);
  }

  .suggestions {
    position: absolute;
    top: 100%;
    left: 20px;
    right: 20px;
    z-index: 30;
    margin-top: 4px;
    background: #fff;
    border: 1px solid var(--line);
    border-radius: 10px;
    box-shadow: 0 12px 28px -6px rgb(0 0 0 / 0.24);
    max-height: 244px;
    overflow-y: auto;
    padding: 4px;
  }
  .suggestion {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 9px 12px;
    border: none;
    border-radius: 7px;
    background: transparent;
    font: inherit;
    font-size: 14px;
    color: var(--ink);
    cursor: pointer;
    text-align: left;
  }
  .suggestion:hover {
    background: var(--surface-2);
  }
  .suggestion.current {
    background: #ebf8ff;
  }
  .primary {
    font-weight: 500;
  }
  .secondary {
    color: var(--muted-3);
    font-size: 12px;
  }

  .block-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 8px;
  }
  .block-title {
    font-weight: 500;
    font-size: 12px;
    color: var(--muted);
  }
  .block-hint {
    font-size: 12px;
    color: var(--muted-3);
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .vintage {
    margin-top: 8px;
    font-size: 11.5px;
    color: var(--muted-3);
  }
  .chip {
    font: inherit;
    font-weight: 600;
    font-size: 12.5px;
    padding: 7px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.12s;
    background: #fff;
    color: var(--muted);
    border: 1px solid var(--line);
  }
  .chip.active {
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
  }
  .chip:disabled {
    cursor: default;
  }

  .segmented {
    display: flex;
    gap: 3px;
    border: 1px solid var(--line);
    background: var(--surface);
    border-radius: 9px;
    padding: 3px;
  }
  .segmented button {
    flex: 1;
    font: inherit;
    font-weight: 600;
    font-size: 12.5px;
    padding: 6px 10px;
    border: none;
    border-radius: 7px;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    transition: all 0.12s;
  }
  .segmented button.active {
    background: var(--accent);
    color: #fff;
  }

  .list-head {
    padding: 12px 20px 8px;
    font-weight: 700;
    font-size: 13px;
    color: #2d3748;
  }
  .list {
    flex: 1;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    overscroll-behavior: contain;
    padding: 0 12px 12px;
  }
  .empty {
    padding: 16px 8px;
    font-size: 13px;
    color: var(--muted-3);
  }

  .row {
    display: flex;
    align-items: center;
    gap: 11px;
    width: 100%;
    padding: 10px;
    border-radius: 9px;
    cursor: pointer;
    margin-bottom: 6px;
    transition: all 0.12s;
    background: var(--surface);
    border: 1px solid var(--line-soft);
    font: inherit;
    text-align: left;
  }
  .row:hover {
    border-color: var(--line);
  }
  .row.selected {
    background: #fff;
    border-color: var(--accent);
    box-shadow: 0 4px 12px -4px rgb(0 0 0 / 0.18);
  }
  .row-name {
    flex: 1;
    min-width: 0;
    font-weight: 500;
    font-size: 14.5px;
    color: var(--ink);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .row-fare {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .amount {
    font-weight: 700;
    font-size: 16px;
  }

  .grabber {
    display: none;
  }

  /* --- Bottom sheet ------------------------------------------------------ */
  .panel.sheet {
    top: auto;
    right: 0;
    left: 0;
    width: auto;
    max-height: none;
    border: none;
    border-radius: 16px 16px 0 0;
    box-shadow: 0 -8px 30px -8px rgb(0 0 0 / 0.25);
    transform: translateY(var(--sheet-y, 0px));
    transition:
      transform 0.3s cubic-bezier(0.32, 0.72, 0, 1),
      bottom 0.25s ease-out,
      height 0.25s ease-out;
    /* Sized and lifted off the visual viewport, so an open keyboard shrinks the
       sheet and pushes it up instead of burying it. */
    bottom: var(--kb, 0px);
    height: var(--sheet-h, 88dvh);
  }
  .panel.sheet.dragging {
    transition: none;
  }

  .sheet .grabber {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 28px;
    padding: 0;
    border: none;
    background: transparent;
    cursor: grab;
    touch-action: none; /* the drag is ours, not the browser's */
  }
  .sheet .grabber:active {
    cursor: grabbing;
  }
  .grip {
    width: 40px;
    height: 4px;
    border-radius: 999px;
    background: var(--line);
  }
  .sheet .grabber:hover .grip,
  .sheet .grabber:focus-visible .grip {
    background: var(--muted-3);
  }

  .sheet .peek {
    padding-bottom: 8px; /* keeps the search field off the screen edge when collapsed */
  }
  .sheet .head {
    padding: 2px 18px 12px;
  }
  .sheet .sub {
    display: none; /* the peek height is precious; the search label carries the intent */
  }
  .sheet .block {
    padding: 10px 18px 12px;
  }
  .sheet .suggestions {
    left: 18px;
    right: 18px;
    max-height: calc(var(--sheet-h, 40dvh) * 0.5);
    overscroll-behavior: contain;
    -webkit-overflow-scrolling: touch;
  }
  .sheet .list-head {
    padding: 10px 18px 8px;
  }
  .sheet .list {
    padding-bottom: calc(12px + env(safe-area-inset-bottom, 0px));
  }

  @media (max-width: 768px) {
    /* Touch targets: 44px minimum on everything you can hit with a thumb. */
    .langs button {
      padding: 8px 12px;
    }
    .chip {
      padding: 11px 14px;
    }
    .segmented button {
      padding: 11px 10px;
      font-size: 13.5px;
    }
    .suggestion {
      padding: 13px 12px;
    }
    .row {
      padding: 13px 12px;
    }
    input {
      height: 46px;
      font-size: 16px; /* iOS zooms the page in on any input below 16px */
    }
  }

  /* Hover lift is a lie on touch; it sticks after a tap. */
  @media (hover: none) {
    .suggestion:hover {
      background: transparent;
    }
    .row:hover {
      border-color: var(--line-soft);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .panel.sheet {
      transition: none;
    }
  }
</style>
