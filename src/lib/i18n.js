export const LABELS = {
  ja: {
    explorerSub: '運賃エクスプローラー',
    origin: '出発駅',
    fareScale: '運賃の目安',
    dest: '行き先',
    searchPh: '駅を検索…',
    operator: '運行会社',
    departingVia: '出発駅の路線',
    fareType: '運賃種別',
    ic: 'ICカード',
    ticket: 'きっぷ',
    child: 'こども',
    compareLabel: '運賃を比較',
    compareSub: '両駅を経由する複数の運行会社があります。運賃を比較して選んでください。',
    noDest: '運賃データがありません',
    loading: '読み込み中…',
  },
  en: {
    explorerSub: 'Pick a station to compare fares',
    origin: 'Origin',
    fareScale: 'Fare scale',
    dest: 'Destinations',
    searchPh: 'Search a station…',
    operator: 'Operator',
    departingVia: 'For the departure station',
    fareType: 'Fare type',
    ic: 'IC card',
    ticket: 'Ticket',
    child: 'Child',
    compareLabel: 'Compare fares',
    compareSub: 'Multiple operators run between these two stations. Compare fares and pick one.',
    noDest: 'No fare data',
    loading: 'Loading…',
  },
};

export const stationName = (station, lang) => (lang === 'ja' ? station.ja : station.en);
export const stationSub = (station, lang) => (lang === 'ja' ? station.en : station.ja);
export const operatorName = (operator, lang) => (lang === 'ja' ? operator.ja : operator.en);
