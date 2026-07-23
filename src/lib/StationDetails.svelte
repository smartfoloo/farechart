<script>
  import { fareColor, yen } from './fare.js';
  import { isMobile } from './media.svelte.js';
  import { dragY } from './drag.js';

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
    lineMeta,
    routes,
    onPick,
    onSetOrigin,
    onClose,
  } = $props();

  const DISMISS = 96; // px of downward travel that closes the sheet
  const FLICK = 0.5; // px/ms

  const mobile = $derived(isMobile.current);

  let pull = $state(0); // downward drag distance, mobile only
  let dragging = $state(false);

  const range = $derived.by(() => {
    if (!routes.length) return [0, 0];
    const fares = routes.map((r) => r.fare);
    return [Math.min(...fares), Math.max(...fares)];
  });

  const lineName = (l) => (l ? (lang === 'ja' ? l.ja : l.en) : '');

  // `lines` is this station's own railways, for the Lines section. Route legs need
  // `lineMeta`, the full keyed map, because a route passes through railways that
  // don't serve this station.
  const lineList = $derived(lines ?? []);

  const singleRoutes = $derived(routes.filter((r) => r.operators.length === 1));
  const multiRoutes = $derived(routes.filter((r) => r.operators.length > 1));

  // Platform-to-platform walking transfer: only called out when the names differ.
  const boundaryName = (prevLeg, nextLeg) =>
    prevLeg.toName === nextLeg.fromName ? prevLeg.toName : `${prevLeg.toName}・・・${nextLeg.fromName}`;

  // Operator keys ship as bare identifiers (e.g. "TokyoMetro"); split the
  // camelCase into words since no localized operator name is available here.

  function onDragEnd(dy, velocity) {
    dragging = false;
    if (dy > DISMISS || velocity > FLICK) onClose();
    else pull = 0;
  }
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && onClose()} />

<div
  class="backdrop"
  class:bottom={mobile}
  role="presentation"
  onclick={(e) => e.target === e.currentTarget && onClose()}
>
  <div
    class="modal"
    class:sheet={mobile}
    class:dragging
    style={mobile ? `--pull: ${pull}px` : ''}
    role="dialog"
    aria-modal="true"
    aria-label={stationName}
  >
    {#if mobile}
      <button
        class="grabber"
        aria-label={t.close}
        use:dragY={{
          onStart: () => (dragging = true),
          onMove: (dy) => (pull = Math.max(0, dy)),
          onEnd: onDragEnd,
        }}
        onclick={(e) => e.detail === 0 && onClose()}
      >
        <span class="grip"></span>
      </button>
    {/if}

    <div class="head">
      <div>
        <div class="title">{stationName}</div>
        <div class="sub">{stationSub}</div>
      </div>
      <button class="close" onclick={onClose} aria-label={t.close}>✕</button>
    </div>

    <div class="body">
      <section>
        <div class="section-title">{t.lines}</div>
        {#each lineList as group, gi (group.ja)}
          <!-- The first group is the station the modal is already titled with; only
               the differently-named ones need calling out. -->
          {#if gi > 0}
            <div class="line-station">
              {lang === 'ja' ? group.ja : group.en}
              <span class="walk">{t.walkTransfer}</span>
            </div>
          {/if}
          <div class="lines" class:other-station={gi > 0}>
            {#each group.lines as line (line.ja)}
              <div class="line-row">
                <span class="line-dot" style="background: {line.color}"></span>
                <span class="line-name">{lineName(line)}</span>
              </div>
            {/each}
          </div>
        {/each}
      </section>

      <section>
        <div class="section-title">{t.routes}</div>
        {#if isOrigin}
          <p class="note">{t.originHere}</p>
        {:else if originName === null}
          <p class="note">{t.pickOriginHint}</p>
        {:else if routes.length === 0}
          <p class="note">{t.noRoutes}</p>
        {:else}
          <p class="fare-lede">{originName} → {stationName}</p>

          {#if singleRoutes.length}
            <div class="route-group-title">{t.singleOperator}</div>
            {#each singleRoutes as route, i (`s${i}`)}
              {@render routeCard(route)}
            {/each}
          {/if}

          {#if multiRoutes.length}
            <div class="route-group-title">{t.multiOperator}</div>
            {#each multiRoutes as route, i (`m${i}`)}
              {@render routeCard(route)}
            {/each}
          {/if}
        {/if}
      </section>
    </div>

    {#snippet routeCard(route)}
      {@const color = fareColor(route.fare, range[0], range[1])}
      <button
        class="route"
        class:active={route.operators[0] === activeOperator}
        onclick={() => onPick(route.operators[0])}
      >
        <div class="route-path">
          <span class="stop">{route.legs[0].fromName}</span>
          {#each route.legs as leg, i (i)}
            {@const line = lineMeta?.[leg.railway]}
            <span class="chip" style="--chip-color: {line?.color ?? 'var(--muted-3)'}">
              {lineName(line) || leg.railway}
            </span>
            {#if i < route.legs.length - 1}
              <span class="stop transfer">{boundaryName(leg, route.legs[i + 1])}</span>
            {:else}
              <span class="stop">{leg.toName}</span>
            {/if}
          {/each}
        </div>

        <div class="route-bottom">
          <span class="route-meta">
            {t.stops(route.hops)}
          </span>

          <span class="route-fare-group">
            {#if route.discount > 0}
              <span class="fare-gross">{yen(route.gross)}</span>
            {/if}
            <span
              class="fare"
              style="color: {color}"
              title={route.discountAssumed ? t.approxFare : undefined}
            >
              {#if route.discountAssumed}≈{/if}{yen(route.fare)}
            </span>
          </span>
        </div>

        {#if route.discount > 0}
          <div class="discount-note">
            −{yen(route.discount)} {t.transferDiscount}
            {#if route.discountAssumed}
              <span class="approx-flag" title={t.approxFare}>*</span>
            {/if}
          </div>
        {/if}
      </button>
    {/snippet}

    {#if !isOrigin}
      <div class="foot">
        <button class="set-origin" onclick={onSetOrigin}>{t.setOrigin}</button>
      </div>
    {/if}
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 40;
    background: rgb(26 32 44 / 0.45);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .modal {
    width: 560px;
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
  /* Lines belonging to a differently-named station in the complex are set off by a
     rule, so they don't read as lines you can reach without walking. */
  .lines.other-station {
    padding-left: 10px;
    border-left: 2px solid var(--line);
  }
  /* A station in the complex with a different name gets its own heading, so a change
     that means walking to it reads as one. */
  .line-station {
    display: flex;
    align-items: baseline;
    gap: 7px;
    font-weight: 700;
    font-size: 13px;
    color: var(--ink);
    margin: 12px 0 7px;
  }
  .walk {
    font-weight: 500;
    font-size: 11px;
    color: var(--muted-3);
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
    margin: 0 0 14px;
    font-size: 17px;
    font-weight: 700;
    color: var(--ink);
  }

  .route-group-title {
    font-weight: 700;
    font-size: 11px;
    color: var(--muted-3);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 14px 0 8px;
  }
  .route-group-title:first-child {
    margin-top: 0;
  }

  .route {
    display: flex;
    flex-direction: column;
    gap: 10px;
    width: 100%;
    min-height: 44px;
    padding: 13px 15px;
    border-radius: 12px;
    cursor: pointer;
    margin-bottom: 8px;
    background: var(--surface);
    border: 1px solid var(--line-soft);
    font: inherit;
    text-align: left;
  }
  .route.active {
    background: #ebf8ff;
    border-color: #bee3f8;
  }

  /* Wrap, never scroll sideways -- the bottom sheet has no room for that. */
  .route-path {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 6px;
    min-width: 0;
  }
  .stop {
    font-weight: 600;
    font-size: 12px;
    color: var(--ink);
  }
  .stop.transfer {
    font-weight: 500;
    color: var(--ink);
  }
  .chip {
    flex: 0 0 auto;
    font-weight: 600;
    font-size: 10px;
    padding: 1px 6px;
    border-radius: 999px;
    color: var(--chip-color);
    background: color-mix(in srgb, var(--chip-color) 14%, transparent);
    white-space: nowrap;
  }

  .route-bottom {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }
  .route-meta {
    font-size: 12px;
    color: var(--muted-2);
  }
  .route-fare-group {
    display: flex;
    align-items: baseline;
    gap: 7px;
  }
  .fare-gross {
    font-size: 13px;
    color: var(--muted-3);
    text-decoration: line-through;
  }
  .fare {
    font-weight: 700;
    font-size: 24px;
  }
  .discount-note {
    font-size: 11.5px;
    color: var(--accent);
    margin-top: -4px;
  }
  .approx-flag {
    cursor: help;
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

  .grabber {
    display: none;
  }

  /* --- Bottom sheet ------------------------------------------------------ */
  .backdrop.bottom {
    align-items: flex-end;
  }
  .modal.sheet {
    width: 100%;
    max-width: 100%;
    max-height: 86dvh;
    border-radius: 16px 16px 0 0;
    padding-bottom: env(safe-area-inset-bottom, 0px);
    transform: translateY(var(--pull, 0px));
    transition: transform 0.3s cubic-bezier(0.32, 0.72, 0, 1);
    animation: rise 0.28s cubic-bezier(0.32, 0.72, 0, 1);
  }
  .modal.sheet.dragging {
    transition: none;
  }
  @keyframes rise {
    from {
      transform: translateY(100%);
    }
  }

  .sheet .grabber {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 26px;
    padding: 0;
    border: none;
    background: transparent;
    cursor: grab;
    touch-action: none;
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
  .sheet .head {
    padding: 4px 18px 16px;
  }
  .sheet .body {
    padding: 8px 18px 16px;
    overscroll-behavior: contain;
  }
  .sheet .foot {
    padding: 14px 18px;
  }

  @media (max-width: 768px) {
    /* Touch targets: 44px minimum. */
    .close {
      width: 40px;
      height: 40px;
    }
    .route {
      padding: 15px;
    }
    .set-origin {
      padding: 14px;
      font-size: 15px;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .modal.sheet {
      transition: none;
      animation: none;
    }
  }
</style>
