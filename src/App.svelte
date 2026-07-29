<script>
  import { loadNetwork, destinationsFrom } from './lib/data.js';
  import { fareOf } from './lib/fare.js';
  import { candidateRoutes, operatorsFor, priceRoutes, rankRoutes } from './lib/route.js';
  import { LABELS, facet, stationName, stationSub } from './lib/i18n.js';
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
  let hoverDest = $state(null); // station whose destination-search suggestion is hovered/focused
  let detailTarget = $state(null); // station whose details popup is open
  // Which physical station of a complex the user picked. Purely presentational --
  // fares are keyed to the complex, so this only decides which name leads.
  let originMember = $state(0);
  let detailMember = $state(0);

  let network = $state(null);
  let detailPricing = $state(null);

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

  // Candidate routes from the origin to the open station, priced against every
  // network they touch. Two phases so route-finding stays synchronous while
  // fare networks load asynchronously (and are shared via the loadNetwork cache).
  $effect(() => {
    const target = detailTarget;
    if (target === null || origin === null || target === origin) {
      detailPricing = null;
      return;
    }
    const from = origin;
    const candidates = candidateRoutes(meta, from, target);
    let stale = false;
    const nets = {};
    Promise.all(
      [...operatorsFor(candidates)].map((key) => loadNetwork(key).then((net) => (nets[key] = net))),
    ).then(() => {
      if (!stale) detailPricing = { from, target, candidates, nets };
    });
    return () => (stale = true);
  });

  const detailRoutes = $derived.by(() => {
    const d = detailPricing;
    if (!d || d.target !== detailTarget || d.from !== origin) return [];
    const priced = priceRoutes(meta, d.candidates, d.nets, fareMode, passenger);
    return rankRoutes(priced);
  });

  // Railways serving the open station, resolved to names and colors.
  // A complex can span differently-named stations (虎ノ門 / 虎ノ門ヒルズ). Group its
  // railways under the name you'd actually walk to, so changing to a line at a
  // differently-named station is visible rather than hidden behind one label.
  const detailLines = $derived.by(() => {
    if (detailTarget === null) return [];
    const s = stations[detailTarget];
    const groups = s.members ?? [{ ja: s.ja, en: s.en, lines: s.lines }];
    // The station the user actually picked leads; the rest are the walk-to ones.
    const ordered = [groups[detailMember], ...groups.filter((_, i) => i !== detailMember)];
    return ordered.map((g) => ({ ja: g.ja, en: g.en, lines: g.lines.map((id) => meta.lines[id]) }));
  });

  function pickOrigin(idx, m = 0) {
    origin = idx;
    originMember = m;
    operatorChoice = null;
    selected = null;
    detailTarget = null;
  }

  function setOperator(key) {
    operatorChoice = key;
    selected = null;
    detailTarget = null;
  }

  function selectDest(idx, m = 0) {
    detailTarget = idx;
    detailMember = m;
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
    {range}
    {origin}
    {selected}
    hovered={hoverDest}
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
    {originMember}
    {activeOperator}
    {fareMode}
    {passenger}
    onSetLang={(l) => (lang = l)}
    onPickOrigin={pickOrigin}
    onSetOperator={setOperator}
    onSetFareMode={(m) => (fareMode = m)}
    onSetPassenger={(p) => (passenger = p)}
    onSelectDest={selectDest}
    onHoverDest={(i) => (hoverDest = i)}
  />

  {#if rows.length}
    <Legend {t} min={range[0]} max={range[1]} />
  {/if}

  {#if detailTarget !== null}
    <StationDetails
      {t}
      {lang}
      {activeOperator}
      stationName={stationName(facet(stations, detailTarget, detailMember), lang)}
      stationSub={stationSub(facet(stations, detailTarget, detailMember), lang)}
      originName={stationName(facet(stations, origin, originMember), lang)}
      isOrigin={detailTarget === origin}
      lines={detailLines}
      lineMeta={meta.lines}
      routes={detailRoutes}
      onPick={pickFromDetails}
      onSetOrigin={() => pickOrigin(detailTarget, detailMember)}
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
