/* Urzędowe wykazy RZGW sprawdzone 2026-07-24; dane nie zastępują dokumentu źródłowego. */
(function (window, document) {
  'use strict';

  const GDANSK_URL = 'https://www.gov.pl/web/wody-polskie-gdansk/lista-obwodow';
  const BYDGOSZCZ_URL = 'https://www.gov.pl/web/wody-polskie-bydgoszcz/lista-obwodow-rybackich-2026';
  const GDANSK_LABEL = 'RZGW Gdańsk — lista obwodów, 25.06.2026';
  const BYDGOSZCZ_LABEL = 'RZGW Bydgoszcz — lista obwodów rybackich i łowisk 2026';
  const BIALYSTOK_URL = 'https://www.gov.pl/web/wody-polskie-bialystok/lista-obwodow-rybackich';
  const BIALYSTOK_LABEL = 'RZGW Białystok — lista obwodów udostępnionych do amatorskiego połowu ryb w 2026 r., 29.12.2025';
  const BIALYSTOK_TABLE_NOTE = 'Brak dodatkowych ograniczeń wskazanych w tabeli źródłowej.';
  const GD_RESTRICTION = 'Przy rozstrzygnięciu konkursu zezwolenia roczne obowiązują do zawarcia umowy użytkowania.';
  const RAPR = 'RAPR 2026.';
  const water = function (id, name, operator, municipality, restrictions, contest, sourceUrl, sourceLabel) {
    return { id: id, name: name, operator: operator, municipality: municipality, restrictions: restrictions, contest: contest, sourceUrl: sourceUrl, sourceLabel: sourceLabel };
  };

  const records = [
    water('gd-01', 'Obwód jeziora Młynek na cieku bez nazwy w zlewni rzeki Drwęca', 'RZGW Gdańsk', '', GD_RESTRICTION, false, GDANSK_URL, GDANSK_LABEL),
    water('gd-02', 'Obwód jeziora Samińskie na cieku Samionka w zlewni rzeki Brynica', 'RZGW Gdańsk', '', GD_RESTRICTION, false, GDANSK_URL, GDANSK_LABEL),
    water('gd-03', 'Obwód jeziora Szczytno na rzece Brda nr 3', 'RZGW Gdańsk', '', GD_RESTRICTION, false, GDANSK_URL, GDANSK_LABEL),
    water('gd-04', 'Obwód jeziora Płaszczyckie na cieku bez nazwy w zlewni rzeki Brda', 'RZGW Gdańsk', '', GD_RESTRICTION, false, GDANSK_URL, GDANSK_LABEL),
    water('gd-05', 'Obwód jeziora Wyrówno na cieku bez nazwy w zlewni rzeki Wda', 'RZGW Gdańsk', '', GD_RESTRICTION, false, GDANSK_URL, GDANSK_LABEL),
    water('gd-06', 'Obwód jeziora Słone na cieku bez nazwy w zlewni rzeki Wda', 'RZGW Gdańsk', '', GD_RESTRICTION, false, GDANSK_URL, GDANSK_LABEL),
    water('gd-07', 'Obwód jeziora Krąg na cieku bez nazwy w zlewni rzeki Wierzyca', 'RZGW Gdańsk', '', GD_RESTRICTION, false, GDANSK_URL, GDANSK_LABEL),
    water('gd-08', 'Obwód jeziora Damaszka na cieku bez nazwy w zlewni rzeki Motława (Szpęgawa)', 'RZGW Gdańsk', '', GD_RESTRICTION, false, GDANSK_URL, GDANSK_LABEL),
    water('gd-09', 'Obwód jeziora Wielkie na rzece Łeba nr 1', 'RZGW Gdańsk', '', GD_RESTRICTION, false, GDANSK_URL, GDANSK_LABEL),
    water('gd-10', 'Obwód rzeki Łeba nr 4', 'RZGW Gdańsk', '', GD_RESTRICTION, false, GDANSK_URL, GDANSK_LABEL),
    water('gd-11', 'Obwód jeziora Otalżyno na rzece Gościcina nr 1', 'RZGW Gdańsk', '', GD_RESTRICTION, false, GDANSK_URL, GDANSK_LABEL),
    water('gd-12', 'Obwód rzeki Bezleda nr 1', 'RZGW Gdańsk', '', GD_RESTRICTION, false, GDANSK_URL, GDANSK_LABEL),
    water('gd-13', 'Obwód jeziora Nowy Dwór na cieku bez nazwy w zlewni rzeki Skarlanka', 'RZGW Gdańsk', '', '', true, GDANSK_URL, GDANSK_LABEL),
    water('gd-14', 'Obwód jeziora Długie na cieku bez nazwy w zlewni rzeki Mała Wierzyca', 'RZGW Gdańsk', '', '', true, GDANSK_URL, GDANSK_LABEL),
    water('gd-15', 'Obwód jeziora Dąbrowskie na cieku bez nazwy w zlewni rzeki Radunia', 'RZGW Gdańsk', '', '', true, GDANSK_URL, GDANSK_LABEL),
    water('gd-16', 'Obwód jeziora Trzebocińskie na rzece Słupia nr 2', 'RZGW Gdańsk', '', '', true, GDANSK_URL, GDANSK_LABEL),
    water('gd-17', 'Obwód rzeki Piaśnica nr 1', 'RZGW Gdańsk', '', '', true, GDANSK_URL, GDANSK_LABEL),
    water('gd-18', 'Obwód jeziora Dłużki II (Dłużeczek) na cieku bez nazwy w zlewni rzeki Pasłęka', 'RZGW Gdańsk', '', '', true, GDANSK_URL, GDANSK_LABEL),
    water('gd-19', 'Obwód rzeki Giłwa nr 2', 'RZGW Gdańsk', '', '', true, GDANSK_URL, GDANSK_LABEL),
    water('gd-20', 'Obwód jeziora Barduń (Barduny) w zlewni rzeki Pasłęka', 'RZGW Gdańsk', '', '', true, GDANSK_URL, GDANSK_LABEL),
    water('by-01', 'Obwód Jeziora Białe na rzece Miała nr 1', 'RZGW Bydgoszcz', 'Wieleń', RAPR + ' Przy rozstrzygnięciu konkursu zezwolenia roczne obowiązują do zawarcia umowy użytkowania.', true, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-02', 'Obwód Jeziora Wielkie na rzece Miała nr 2', 'RZGW Bydgoszcz', 'Wieleń', RAPR, false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-03', 'Obwód Jeziora Borówno na cieku Skicka Struga nr 1', 'RZGW Bydgoszcz', 'Zakrzewo', RAPR, false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-04', 'Obwód Jeziora Sławianowo na cieku Skicka Struga nr 4', 'RZGW Bydgoszcz', 'Złotów', RAPR, false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-05', 'Obwód Jeziora Wilczyńskie na cieku bez nazwy w zlewni kanału Ostrowo–Gopło nr 1', 'RZGW Bydgoszcz', 'Wilczyn', RAPR + ' Przy rozstrzygnięciu konkursu zezwolenia roczne obowiązują do zawarcia umowy użytkowania.', true, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-06', 'Obwód rzeki Szczyra nr 1', 'RZGW Bydgoszcz', 'Czarne', RAPR + ' Wody pstrągowe.', false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-07', 'Obwód Jeziora Głomskie na rzece Głomia nr 1', 'RZGW Bydgoszcz', 'Zakrzewo', RAPR + ' Połów z łodzi dozwolony od 1 czerwca do 31 października.', true, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-08', 'Obwód jeziora Bobkowo na cieku bez nazwy w zlewni rzeki Piławka nr 2', 'RZGW Bydgoszcz', 'Mirosławiec', RAPR + ' Zakaz stosowania zanęt i ograniczenie liczby jednostek pływających.', true, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-09', 'Obwód rzeki Noteć Zachodnia nr 4', 'RZGW Bydgoszcz', 'Mogilno', RAPR, true, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-10', 'Obwód jeziora Kochlin Mały na cieku bez nazwy w zlewni rzeki Słopica nr 2', 'RZGW Bydgoszcz', 'Człopa', RAPR, false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-11', 'Obwód jeziora Zamkowe na cieku bez nazwy w zlewni rzeki Żydówka nr 2', 'RZGW Bydgoszcz', 'Wałcz', RAPR, false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-12', 'Obwód jeziora Śmiardówka na cieku bez nazwy w zlewni rzeki Głomia nr 1', 'RZGW Bydgoszcz', 'Zakrzewo', RAPR, true, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-13', 'Obwód jeziora Kleszczyński Staw na cieku bez nazwy w zlewni rzeki Skicka Struga nr 1', 'RZGW Bydgoszcz', 'Złotów', RAPR, true, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-14', 'Obwód jeziora Zieleniewo Duże na cieku bez nazwy w zlewni rzeki Koczynka nr 2', 'RZGW Bydgoszcz', 'Bierzwnik', RAPR, false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-15', 'Obwód jeziora Ramka Duża na cieku bez nazwy w zlewni rzeki Koczynka nr 3', 'RZGW Bydgoszcz', 'Bierzwnik', RAPR, false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-16', 'Obwód jeziora Osiek (Chomętowskie) na cieku Mierzęcka Struga nr 2', 'RZGW Bydgoszcz', 'Dobiegniew', RAPR, false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-17', 'Obwód Jeziora Leśne na cieku bez nazwy w zlewni rzeki Nizica nr 1', 'RZGW Bydgoszcz', 'Szczecinek', RAPR, true, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-18', 'Obwód Jeziora Wapińskie na cieku bez nazwy w zlewni rzeki Gwda nr 1', 'RZGW Bydgoszcz', 'Skórka', RAPR + ' Zakaz stosowania zanęt od 15 czerwca do 31 sierpnia, poza tym okresem 1 kg na dobę.', false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-19', 'Obwód Jeziora Długie na cieku bez nazwy w zlewni rzeki Bukówka nr 1', 'RZGW Bydgoszcz', 'Trzcianka', RAPR, false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-20', 'Obwód jeziora Miłogoszcz Wielka na cieku bez nazwy w zlewni rzeki Runica nr 1', 'RZGW Bydgoszcz', 'Tuczno', RAPR, false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-21', 'Obwód jeziora Danków Duży na kanale Pełcz nr 2', 'RZGW Bydgoszcz', 'Strzelce Krajeńskie', RAPR, true, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-22', 'Obwód Jeziora Straduńskie na rzece Bukówka nr 4', 'RZGW Bydgoszcz', 'Trzcianka', RAPR, false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-23', 'Obwód jeziora Raduń na rzece Żydówka nr 2', 'RZGW Bydgoszcz', 'Wałcz', RAPR + ' Na Raduń Mały zakaz pływania jednostką pływającą.', false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-24', 'Obwód jeziora Busko na bezimiennym cieku w zlewni rzeki Wąsawa nr 1', 'RZGW Bydgoszcz', 'Wierzchowo', RAPR, true, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-25', 'Obwód Jeziora Budzisławskie na cieku bez nazwy w zlewni kanału Ostrowo–Gopło nr 1', 'RZGW Bydgoszcz', 'Kleczew', RAPR + ' Zakaz stosowania zanęt od 15 czerwca do 31 sierpnia, poza tym okresem 1 kg na dobę.', true, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-26', 'Obwód Jeziora Kościelne na rzece Ogardna nr 1', 'RZGW Bydgoszcz', 'Krzęcin', RAPR, false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-27', 'Obwód Zbiornika Wodnego Zalew Nadarzycki na rzece Piława nr 3', 'RZGW Bydgoszcz', 'Borne Sulinowo', RAPR, false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-28', 'Obszar Rezerwatu Doliny Pięciu Jezior', 'RZGW Bydgoszcz', 'Połczyn-Zdrój', RAPR + ' Zakaz wędkowania ze środków pływających i nęcenia; tylko świt–zmierzch oraz wyznaczone miejsca.', false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-29', 'Jezioro Piasecznik', 'RZGW Bydgoszcz', 'Czaplinek', RAPR, false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-30', 'Jezioro Przytyk Duży', 'RZGW Bydgoszcz', 'Człopa', RAPR, false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('by-31', 'Jezioro Nowoworowskie', 'RZGW Bydgoszcz', 'Złocieniec', RAPR, false, BYDGOSZCZ_URL, BYDGOSZCZ_LABEL),
    water('bi-01', 'rzeki Narew nr 5', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL),
    water('bi-02', 'rzeki Pisa nr 1', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL),
    water('bi-03', 'rzeki Pisa nr 2', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL),
    water('bi-04', 'jeziora Iławki w zlewni rzeki Pisa nr 5', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL),
    water('bi-05', 'jeziora Stoczek w zlewni rzeki Pisa nr 19', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL),
    water('bi-06', 'jeziora Łaźno w zlewni rzeki Ełk nr 1', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL),
    water('bi-07', 'jeziora Kiełki w zlewni rzeki Ełk nr 9', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL),
    water('bi-08', 'jeziora Krzywe w zlewni rzeki Ełk nr 21', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL),
    water('bi-09', 'jeziora Wityny w zlewni rzeki Ełk nr 28', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL),
    water('bi-10', 'jeziora Reszki w zlewni rzeki Jegrznia nr 5', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL),
    water('bi-11', 'jeziora Silec w zlewni rzeki Omet nr 3', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL),
    water('bi-12', 'jeziora Klimunt w zlewni rzeki Pisa nr 44', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL),
    water('bi-13', 'jeziora Wądołek Duży w zlewni rzeki Pisa nr 64', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL),
    water('bi-14', 'jeziora Klebarskie w zlewni rzeki Łyna nr 17', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL),
    water('bi-15', 'jeziora Limajno w zlewni rzeki Łyna nr 47', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL),
    water('bi-16', 'jeziora Luterskie w zlewni rzeki Łyna nr 48', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL),
    water('bi-17', 'jeziora Rydzówka na Kanale Mazurskim nr 1', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL),
    water('bi-18', 'jeziora Biała Piska w zlewni rzeki Pisa nr 57', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL),
    water('bi-19', 'jeziora Czarne w zlewni rzeki Węgorapa nr 12', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL),
    water('bi-20', 'jeziora Kożuchy Młyn w zlewni rzeka Pisa nr 52', 'RZGW Białystok', '', BIALYSTOK_TABLE_NOTE, false, BIALYSTOK_URL, BIALYSTOK_LABEL)
  ];

  const filters = {
    operator: document.querySelector('[data-water-filter="operator"]'),
    status: document.querySelector('[data-water-filter="status"]'),
    query: document.getElementById('water-query')
  };
  const cards = Array.prototype.slice.call(document.querySelectorAll('[data-water]'));
  const count = document.getElementById('water-count');
  const empty = document.getElementById('water-empty');
  const mapOperators = Array.prototype.slice.call(document.querySelectorAll('[data-map-operator]'));
  if (!filters.operator || !filters.status || !filters.query || !cards.length || !count || !empty) return;

  const byId = records.reduce(function (index, record) { index[record.id] = record; return index; }, {});
  function normalized(value) { return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/ł/g, 'l'); }
  function matches(record) {
    const query = normalized(filters.query.value.trim());
    return (filters.operator.value === 'all' || normalized(record.operator) === normalized(filters.operator.options[filters.operator.selectedIndex].text)) &&
      (filters.status.value === 'all' || (filters.status.value === 'postepowanie') === record.contest) &&
      (!query || normalized(record.name + ' ' + record.municipality).includes(query));
  }
  function update() {
    const visibleOperators = {};
    let visible = 0;
    cards.forEach(function (card) {
      const record = byId[card.dataset.water];
      const show = Boolean(record && matches(record));
      card.hidden = !show;
      if (show) { visible += 1; visibleOperators[record.operator] = true; }
    });
    mapOperators.forEach(function (operator) {
      const option = filters.operator.querySelector('option[value="' + operator.dataset.mapOperator + '"]');
      operator.setAttribute('display', option && visibleOperators[option.text] ? 'inline' : 'none');
    });
    empty.hidden = visible !== 0;
    count.textContent = 'Pokazano ' + visible + ' z ' + records.length + ' rekordów zweryfikowanych wód.';
  }
  filters.operator.addEventListener('change', update);
  filters.status.addEventListener('change', update);
  filters.query.addEventListener('input', update);
  mapOperators.forEach(function (operator) {
    operator.addEventListener('click', function (event) {
      event.preventDefault();
      filters.operator.value = operator.dataset.mapOperator;
      update();
      document.getElementById('water-list').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
  update();
}(window, document));
