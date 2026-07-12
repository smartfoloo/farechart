<script>
  import { loadNetwork, destinationsFrom, fareBetween } from './lib/data.js';
  import { LABELS, stationName, operatorName } from './lib/i18n.js';
  import FareMap from './lib/FareMap.svelte';
  import Panel from './lib/Panel.svelte';
  import Legend from './lib/Legend.svelte';
  import StationDetails from './lib/StationDetails.svelte';

  let { meta } = $props();

  const stations = $derived(meta.stations);
  const operators = $derived(meta.operators);

  let lang = $state('ja');
  let origin = $state(null); // nothing loads until the user picks a station
  let operatorChoice = $state(null);
  let fareMode = $state('ic');
  let selected = $state(null);
  let detailTarget = $state(null); // station whose details popup is open
  let network = $state(null);
  let detailFares = $state([]);

  const t = $derived(LABELS[lang]);

  // The origin's own operators decide what you can pick; interchange complexes offer a choice.
  const activeOperator = $derived.by(() => {
    if (origin === null) return null;
    return operatorChoice && stations[origin].ops.includes(operatorChoice)
      ? operatorChoice
      : stations[origin].ops[0];
  });

  $effect(() => {
    const key = activeOperator;
    if (!key) {
      network = null;
      return;
    }
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

  // Every fare from the origin to the open station, one per operator that sells it.
  $effect(() => {
    const target = detailTarget;
    if (target === null || origin === null || target === origin) {
      detailFares = [];
      return;
    }
    const from = origin;
    let stale = false;
    Promise.all(sharedOperators(from, target).map(loadNetwork)).then((nets) => {
      if (stale) return;
      detailFares = nets
        .map((net) => {
          const fare = fareBetween(net, from, target);
          return fare && { key: net.key, ...fare };
        })
        .filter(Boolean);
    });
    return () => (stale = true);
  });

  const detailRows = $derived(
    detailFares
      .map((r) => ({
        ...r,
        label: operatorName(operators.find((o) => o.key === r.key), lang),
        fare: fareMode === 'ic' ? r.ic : r.ticket,
      }))
      .sort((a, b) => a.fare - b.fare),
  );

  // Railways serving the open station, resolved to names and colors.
  const detailLines = $derived(
    detailTarget === null ? [] : stations[detailTarget].lines.map((id) => meta.lines[id]),
  );

  function pickOrigin(idx) {
    origin = idx;
    operatorChoice = null;
    selected = null;
    detailTarget = null;
  }

  function setOperator(key) {
    operatorChoice = key;
    selected = null;
    detailTarget = null;
  }

  function selectDest(idx) {
    detailTarget = idx;
    selected = idx === origin ? null : idx;
  }

  function pickFromDetails(key) {
    operatorChoice = key;
    selected = detailTarget;
    detailTarget = null;
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

  {#if detailTarget !== null}
    <StationDetails
      {t}
      {lang}
      {fareMode}
      {activeOperator}
      stationName={stationName(stations[detailTarget], lang)}
      stationSub={lang === 'ja' ? stations[detailTarget].en : stations[detailTarget].ja}
      originName={origin === null ? null : stationName(stations[origin], lang)}
      isOrigin={detailTarget === origin}
      lines={detailLines}
      rows={detailRows}
      onPick={pickFromDetails}
      onSetOrigin={() => pickOrigin(detailTarget)}
      onClose={() => (detailTarget = null)}
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
