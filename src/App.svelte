<script>
  import { loadNetwork, destinationsFrom, fareBetween } from './lib/data.js';
  import { fareOf } from './lib/fare.js';
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
  let passenger = $state('adult');
  let selected = $state(null);
  let detailTarget = $state(null); // station whose details popup is open
  let network = $state(null);
  let detailFares = $state(null);

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
      .map((e) => ({ ...e, fare: fareOf(e, fareMode, passenger) }))
      .sort((a, b) => a.fare - b.fare);
  });

  const range = $derived(rows.length ? [rows[0].fare, rows[rows.length - 1].fare] : [0, 0]);

  const sharedOperators = (a, b) => stations[a].ops.filter((k) => stations[b].ops.includes(k));
  const opLabel = (key) => operatorName(operators.find((o) => o.key === key), lang);

  // Every operator that sells a fare from the origin to the open station. Fares are
  // derived from the loaded networks, so the fare-type and passenger toggles stay live.
  $effect(() => {
    const target = detailTarget;
    if (target === null || origin === null || target === origin) {
      detailFares = null;
      return;
    }
    const from = origin;
    let stale = false;
    Promise.all(sharedOperators(from, target).map(loadNetwork)).then((nets) => {
      if (!stale) detailFares = { from, target, nets };
    });
    return () => (stale = true);
  });

  const detailRows = $derived.by(() => {
    const d = detailFares;
    if (!d || d.target !== detailTarget || d.from !== origin) return [];

    const out = [];
    for (const net of d.nets) {
      const e = fareBetween(net, d.from, d.target);
      if (e) out.push({ ...e, key: net.key, label: opLabel(net.key), fare: fareOf(e, fareMode, passenger) });
    }
    return out.sort((a, b) => a.fare - b.fare);
  });

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
    {passenger}
    {rows}
    {selected}
    {range}
    onSetLang={(l) => (lang = l)}
    onPickOrigin={pickOrigin}
    onSetOperator={setOperator}
    onSetFareMode={(m) => (fareMode = m)}
    onSetPassenger={(p) => (passenger = p)}
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
      {passenger}
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
