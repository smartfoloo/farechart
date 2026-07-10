<script>
  import { fareColor } from './fare.js';

  let { t, originName, destName, rows, fareMode, activeOperator, onPick, onClose } = $props();

  const range = $derived.by(() => {
    const fares = rows.map((r) => r.fare);
    return [Math.min(...fares), Math.max(...fares)];
  });

  const alt = (row) => (fareMode === 'ic' ? [t.ticket, row.ticket] : [t.ic, row.ic]);
  const child = (row) => (fareMode === 'ic' ? row.childIc : row.childTicket);
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && onClose()} />

<div
  class="backdrop"
  role="presentation"
  onclick={(e) => e.target === e.currentTarget && onClose()}
>
  <div class="modal" role="dialog" aria-modal="true" aria-label={t.compareLabel}>
    <div class="head">
      <div>
        <div class="eyebrow">{t.compareLabel}</div>
        <div class="title">{originName} → {destName}</div>
      </div>
      <button class="close" onclick={onClose} aria-label="Close">✕</button>
    </div>

    <div class="body">
      <p class="lede">{t.compareSub}</p>
      {#each rows as row (row.key)}
        {@const color = fareColor(row.fare, range[0], range[1])}
        {@const [altLabel, altFare] = alt(row)}
        <button class="option" class:active={row.key === activeOperator} onclick={() => onPick(row.key)}>
          <span class="meta">
            <span class="label">{row.label}</span>
            <span class="detail">{altLabel} ¥{altFare} · {t.child} ¥{child(row)}</span>
          </span>
          <span class="fare" style="color: {color}">¥{row.fare}</span>
        </button>
      {/each}
    </div>
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
    padding: 14px 22px 20px;
    overflow-y: auto;
  }
  .lede {
    margin: 0 0 14px;
    font-size: 12.5px;
    color: var(--muted-2);
  }

  .option {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    width: 100%;
    padding: 14px 16px;
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
    font-family: 'Libre Baskerville', serif;
    font-weight: 700;
    font-size: 24px;
  }
</style>
