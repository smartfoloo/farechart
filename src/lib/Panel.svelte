<script>
  import { fareColor } from './fare.js';
  import { stationName, stationSub, operatorName } from './i18n.js';
  import MultiRouteIcon from './MultiRouteIcon.svelte';

  let {
    t,
    lang,
    stations,
    operators,
    origin,
    activeOperator,
    fareMode,
    rows,
    selected,
    range,
    onSetLang,
    onPickOrigin,
    onSetOperator,
    onSetFareMode,
    onSelectDest,
  } = $props();

  const MAX_SUGGESTIONS = 40;

  let query = $state(null);
  let open = $state(false);

  const originName = $derived(stationName(stations[origin], lang));
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
    stations[origin].ops.map((key) => operators.find((o) => o.key === key)).filter(Boolean),
  );

  function pick(idx) {
    query = null;
    open = false;
    onPickOrigin(idx);
  }
</script>

<aside class="panel">
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
      <span class="glyph" aria-hidden="true">⌕</span>
      <input
        id="origin-input"
        value={text}
        placeholder={t.searchPh}
        autocomplete="off"
        role="combobox"
        aria-expanded={open && suggestions.length > 0}
        aria-controls="origin-suggestions"
        oninput={(e) => {
          query = e.currentTarget.value;
          open = true;
        }}
        onfocus={() => (open = true)}
        onkeydown={(e) => e.key === 'Escape' && (open = false)}
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
            onclick={() => pick(idx)}
          >
            <span class="primary">{stationName(stations[idx], lang)}</span>
            <span class="secondary">{stationSub(stations[idx], lang)}</span>
          </button>
        {/each}
      </div>
    {/if}
  </div>

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
  </div>

  <div class="block">
    <div class="block-head"><span class="block-title">{t.fareType}</span></div>
    <div class="segmented">
      <button class:active={fareMode === 'ic'} onclick={() => onSetFareMode('ic')}>{t.ic}</button>
      <button class:active={fareMode === 'ticket'} onclick={() => onSetFareMode('ticket')}>{t.ticket}</button>
    </div>
  </div>

  <div class="list-head">{t.dest}</div>
  <div class="list">
    {#if !rows.length}
      <div class="empty">{t.loading}</div>
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
    left: 12px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--muted-3);
    font-size: 15px;
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
</style>
