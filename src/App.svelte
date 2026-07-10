<script>
  import { untrack } from 'svelte';
  import { loadNetwork, destinationsFrom, fareBetween } from './lib/data.js';
  import { LABELS, stationName, operatorName } from './lib/i18n.js';
  import FareMap from './lib/FareMap.svelte';
  import Panel from './lib/Panel.svelte';
  import Legend from './lib/Legend.svelte';
  import CompareModal from './lib/CompareModal.svelte';

  let { meta } = $props();

  const stations = $derived(meta.stations);
  const operators = $derived(meta.operators);

  let lang = $state('ja');
  let origin = $state(untrack(() => Math.max(0, meta.stations.findIndex((s) => s.en === 'Shibuya'))));
  let operatorChoice = $state(null);
  let fareMode = $state('ic');
  let selected = $state(null);
  let compareTarget = $state(null);
  let network = $state(null);
  let compareFares = $state([]);

  const t = $derived(LABELS[lang]);

  // The origin's own operators decide what you can pick; interchange complexes offer a choice.
  const activeOperator = $derived(
    operatorChoice && stations[origin].ops.includes(operatorChoice)
      ? operatorChoice
      : stations[origin].ops[0],
  );

  $effect(() => {
    const key = activeOperator;
    let stale = false;
    loadNetwork(key).then((net) => {
      if (!stale) network = net;
    });
    return () => (stale = true);
  });

  const rows = $derived.by(() => {
    if (!network || network.key !== activeOperator) return [];
    return destinationsFrom(network, origin)
      .map((e) => ({ ...e, fare: fareMode === 'ic' ? e.ic : e.ticket }))
      .sort((a, b) => a.fare - b.fare);
  });

  const range = $derived(rows.length ? [rows[0].fare, rows[rows.length - 1].fare] : [0, 0]);

  const sharedOperators = (a, b) => stations[a].ops.filter((k) => stations[b].ops.includes(k));

  // A pair is only comparable when two operators both actually sell a fare for it.
  $effect(() => {
    const target = compareTarget;
    if (target === null) {
      compareFares = [];
      return;
    }
    const from = origin;
    let stale = false;
    Promise.all(sharedOperators(from, target).map(loadNetwork)).then((nets) => {
      if (stale) return;
      const found = nets
        .map((net) => {
          const fare = fareBetween(net, from, target);
          return fare && { key: net.key, ...fare };
        })
        .filter(Boolean);
      if (found.length < 2) {
        compareTarget = null;
        selected = target;
      } else {
        compareFares = found;
      }
    });
    return () => (stale = true);
  });

  const compareRows = $derived(
    compareFares
      .map((r) => ({
        ...r,
        label: operatorName(operators.find((o) => o.key === r.key), lang),
        fare: fareMode === 'ic' ? r.ic : r.ticket,
      }))
      .sort((a, b) => a.fare - b.fare),
  );

  function pickOrigin(idx) {
    origin = idx;
    operatorChoice = null;
    selected = null;
    compareTarget = null;
  }

  function setOperator(key) {
    operatorChoice = key;
    selected = null;
    compareTarget = null;
  }

  function selectDest(idx) {
    if (idx === origin) return;
    if (sharedOperators(origin, idx).length > 1) {
      compareTarget = idx;
      return;
    }
    selected = selected === idx ? null : idx;
  }

  function pickCompared(key) {
    operatorChoice = key;
    selected = compareTarget;
    compareTarget = null;
  }
</script>

<main class="stage">
  <FareMap
    {stations}
    {rows}
    {origin}
    {selected}
    {lang}
    operator={activeOperator}
    onSelect={selectDest}
  />

  <Panel
    {t}
    {lang}
    {stations}
    {operators}
    {origin}
    {activeOperator}
    {fareMode}
    {rows}
    {selected}
    {range}
    onSetLang={(l) => (lang = l)}
    onPickOrigin={pickOrigin}
    onSetOperator={setOperator}
    onSetFareMode={(m) => (fareMode = m)}
    onSelectDest={selectDest}
  />

  {#if rows.length}
    <Legend {t} min={range[0]} max={range[1]} />
  {/if}

  {#if compareTarget !== null && compareRows.length > 1}
    <CompareModal
      {t}
      {fareMode}
      {activeOperator}
      originName={stationName(stations[origin], lang)}
      destName={stationName(stations[compareTarget], lang)}
      rows={compareRows}
      onPick={pickCompared}
      onClose={() => (compareTarget = null)}
    />
  {/if}
</main>

<style>
  .stage {
    position: fixed;
    inset: 0;
    overflow: hidden;
    background: var(--line);
  }
</style>
