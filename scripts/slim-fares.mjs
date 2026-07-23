// Slim the raw ODPT fare dumps down to only the fields build-data.mjs reads,
// with short keys, so JSON.parse at build time doesn't pay for dead weight
// (@id, @type, dc:date, @context, owl:sameAs, etc).

import { readFileSync, writeFileSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SRC = join(ROOT, 'data');

const STATION_PREFIX = 'odpt.Station:';
const OPERATOR_PREFIX = 'odpt.Operator:';

const FILES = ['RailwayFares.Challenge2026', 'RailwayFares.ODPT'];

for (const name of FILES) {
  const inPath = join(SRC, `${name}.json`);
  const outPath = join(SRC, `${name}.slim.json`);

  const raw = JSON.parse(readFileSync(inPath, 'utf8'));
  const slim = raw.map((rec) => ({
    op: rec['odpt:operator'].slice(OPERATOR_PREFIX.length),
    from: rec['odpt:fromStation'].slice(STATION_PREFIX.length),
    to: rec['odpt:toStation'].slice(STATION_PREFIX.length),
    ic: rec['odpt:icCardFare'],
    tk: rec['odpt:ticketFare'],
    cic: rec['odpt:childIcCardFare'],
    ctk: rec['odpt:childTicketFare'],
    iss: rec['dct:issued'],
  }));

  writeFileSync(outPath, JSON.stringify(slim));

  const before = statSync(inPath).size;
  const after = statSync(outPath).size;
  console.log(
    `  ${name}: ${(before / 1024 / 1024).toFixed(2)} MB -> ${(after / 1024 / 1024).toFixed(2)} MB (${slim.length} records)`,
  );
}
