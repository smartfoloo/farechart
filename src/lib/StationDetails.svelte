<script>
  import { fareColor, fareOf } from './fare.js';

  let {
    t,
    lang,
    fareMode,
    passenger,
    activeOperator,
    stationName,
    stationSub,
    originName,
    isOrigin,
    lines,
    rows,
    onPick,
    onSetOrigin,
    onClose,
  } = $props();

  const range = $derived.by(() => {
    if (!rows.length) return [0, 0];
    const fares = rows.map((r) => r.fare);
    return [Math.min(...fares), Math.max(...fares)];
  });

  const lineName = (l) => (lang === 'ja' ? l.ja : l.en);

  // The same trip priced the other way round, so both fare types are always on show.
  const alt = (row) => {
    const other = fareMode === 'ic' ? 'ticket' : 'ic';
    return [other === 'ic' ? t.ic : t.ticket, fareOf(row, other, passenger)];
  };
  const child = (row) => fareOf(row, fareMode, 'child');
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && onClose()} />

<div class="backdrop" role="presentation" onclick={(e) => e.target === e.currentTarget && onClose()}>
  <div class="modal" role="dialog" aria-modal="true" aria-label={stationName}>
    <div class="head">
      <div>
        <div class="eyebrow">{t.stationDetails}</div>
        <div class="title">{stationName}</div>
        <div class="sub">{stationSub}</div>
      </div>
      <button class="close" onclick={onClose} aria-label="Close">✕</button>
    </div>

    <div class="body">
      <section>
        <div class="section-title">{t.lines}</div>
        <div class="lines">
          {#each lines as line (line.ja)}
            <div class="line-row">
              <span class="line-dot" style="background: {line.color}"></span>
              <span class="line-name">{lineName(line)}</span>
            </div>
          {/each}
        </div>
      </section>

      <section>
        <div class="section-title">{t.fareLabel}</div>
        {#if isOrigin}
          <p class="note">{t.originHere}</p>
        {:else if originName === null}
          <p class="note">{t.pickOriginHint}</p>
        {:else if rows.length === 0}
          <p class="note">{t.noDest}</p>
        {:else}
          <p class="fare-lede">{originName} → {stationName}</p>
          {#each rows as row (row.key)}
            {@const color = fareColor(row.fare, range[0], range[1])}
            {@const [altLabel, altFare] = alt(row)}
            <button
              class="option"
              class:active={row.key === activeOperator}
              onclick={() => onPick(row.key)}
            >
              <span class="meta">
                <span class="label">{row.label}</span>
                <span class="detail">
                  {altLabel} ¥{altFare}{#if passenger === 'adult'} · {t.child} ¥{child(row)}{/if}
                </span>
              </span>
              <span class="fare" style="color: {color}">¥{row.fare}</span>
            </button>
          {/each}
        {/if}
      </section>
    </div>

    {#if !isOrigin}
      <div class="foot">
        <button class="set-origin" onclick={onSetOrigin}>{t.setOrigin}</button>
      </div>
    {/if}
  </div>
</div>

<style>
  .backdrop {
    position: absolute;
    inset: 0;
    z-index: 40;
    background: rgb(26 32 44 / 0.45);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .modal {
    width: 420px;
    max-width: calc(100% - 40px);
    max-height: 640px;
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 30px 60px -12px rgb(0 0 0 / 0.4);
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .head {
    padding: 18px 22px;
    border-bottom: 1px solid var(--line-soft);
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
  }
  .eyebrow {
    font-weight: 500;
    font-size: 11px;
    color: var(--muted-3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 4px;
  }
  .title {
    font-family: 'Libre Baskerville', 'Hiragino Sans', serif;
    font-size: 20px;
    color: var(--ink);
  }
  .sub {
    font-size: 12.5px;
    color: var(--muted-2);
    margin-top: 2px;
  }
  .close {
    flex: 0 0 auto;
    border: none;
    background: var(--surface);
    color: var(--muted);
    width: 30px;
    height: 30px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 16px;
    line-height: 1;
  }

  .body {
    padding: 8px 22px 16px;
    overflow-y: auto;
  }
  section {
    padding: 12px 0;
  }
  section + section {
    border-top: 1px solid var(--line-soft);
  }
  .section-title {
    font-weight: 700;
    font-size: 12px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 10px;
  }

  .lines {
    display: flex;
    flex-direction: column;
    gap: 9px;
  }
  .line-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .line-dot {
    flex: 0 0 auto;
    width: 12px;
    height: 12px;
    border-radius: 50%;
  }
  .line-name {
    font-weight: 600;
    font-size: 14px;
    color: var(--ink);
  }

  .note {
    margin: 2px 0 0;
    font-size: 13px;
    color: var(--muted-2);
  }
  .fare-lede {
    margin: 0 0 12px;
    font-size: 13px;
    color: var(--muted-2);
  }

  .option {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    width: 100%;
    padding: 13px 15px;
    border-radius: 12px;
    cursor: pointer;
    margin-bottom: 8px;
    background: var(--surface);
    border: 1px solid var(--line-soft);
    font: inherit;
    text-align: left;
  }
  .option.active {
    background: #ebf8ff;
    border-color: #bee3f8;
  }
  .meta {
    display: flex;
    flex-direction: column;
  }
  .label {
    font-weight: 700;
    font-size: 14.5px;
    color: var(--ink);
  }
  .detail {
    font-size: 12px;
    color: var(--muted-2);
    margin-top: 2px;
  }
  .fare {
    font-weight: 700;
    font-size: 24px;
  }

  .foot {
    padding: 14px 22px;
    border-top: 1px solid var(--line-soft);
  }
  .set-origin {
    width: 100%;
    padding: 11px;
    border: none;
    border-radius: 10px;
    background: var(--accent);
    color: #fff;
    font: inherit;
    font-weight: 600;
    font-size: 14px;
    cursor: pointer;
  }
</style>
