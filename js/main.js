const toggle = document.querySelector('.nav-toggle');
const menu = document.querySelector('#nav-menu');

if (toggle && menu) {
  toggle.addEventListener('click', () => {
    const isOpen = menu.classList.toggle('open');
    toggle.setAttribute('aria-expanded', String(isOpen));
  });

  menu.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      menu.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
    });
  });
}

const form = document.querySelector('.contact-form');
if (form) {
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    alert('Dzięki! Formularz jest demonstracyjny — podłączymy go w kolejnym etapie.');
  });
}

// Karuzele kategorii na stronie głównej: strzałki w lewo i w prawo.
document.querySelectorAll('.category-grid.carousel').forEach((grid) => {
  const wrap = document.createElement('div');
  wrap.className = 'carousel-wrap';
  grid.parentNode.insertBefore(wrap, grid);
  wrap.appendChild(grid);

  const makeBtn = (dir, label) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = `carousel-btn ${dir}`;
    btn.setAttribute('aria-label', label);
    btn.textContent = dir === 'prev' ? '←' : '→';
    wrap.appendChild(btn);
    return btn;
  };
  const prev = makeBtn('prev', 'Przewiń w lewo');
  const next = makeBtn('next', 'Przewiń w prawo');

  const cardWidth = () => {
    const card = grid.querySelector('.category-card');
    return card ? card.getBoundingClientRect().width + 20 : grid.clientWidth;
  };
  prev.addEventListener('click', () => grid.scrollBy({ left: -cardWidth(), behavior: 'smooth' }));
  next.addEventListener('click', () => grid.scrollBy({ left: cardWidth(), behavior: 'smooth' }));

  const update = () => {
    prev.disabled = grid.scrollLeft <= 2;
    next.disabled = grid.scrollLeft >= grid.scrollWidth - grid.clientWidth - 2;
  };
  grid.addEventListener('scroll', update, { passive: true });
  window.addEventListener('resize', update);
  update();
});

// Podstrony artykułowe: przenieś zdjęcie z treści do prawej, przyklejonej kolumny.
// Na telefonie zdjęcie zostaje na początku tekstu.
const articleFigure = document.querySelector('.article-card .article-figure');
const articleCard = document.querySelector('.article-card');
const sideNav = document.querySelector('.side-nav');
if (articleFigure && sideNav) {
  const rail = document.createElement('div');
  rail.className = 'side-rail';
  sideNav.parentNode.insertBefore(rail, sideNav);
  rail.appendChild(sideNav);

  const wide = window.matchMedia('(min-width: 841px)');
  const placeFigure = () => {
    if (wide.matches) {
      rail.insertBefore(articleFigure, sideNav);
    } else {
      articleCard.insertBefore(articleFigure, articleCard.firstChild);
    }
  };
  placeFigure();
  wide.addEventListener('change', placeFigure);
}

// Podświetl w bocznym menu link do bieżącej strony.
if (sideNav) {
  const here = location.pathname.split('/').pop();
  sideNav.querySelectorAll('a').forEach((a) => {
    if (a.getAttribute('href') === here) a.classList.add('active');
  });
}

// Przełącznik ciemnego motywu — wstrzykiwany do nawigacji na każdej stronie.
(function () {
  const saved = localStorage.getItem('fishpoint-theme');
  if (saved === 'dark') document.documentElement.classList.add('dark');

  const nav = document.querySelector('.nav');
  if (!nav) return;

  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'theme-toggle';
  btn.setAttribute('aria-label', 'Przełącz ciemny motyw');
  const setIcon = () => { btn.textContent = document.documentElement.classList.contains('dark') ? '☀️' : '🌙'; };
  setIcon();

  btn.addEventListener('click', () => {
    const dark = document.documentElement.classList.toggle('dark');
    localStorage.setItem('fishpoint-theme', dark ? 'dark' : 'light');
    setIcon();
  });

  nav.appendChild(btn);
})();

// === Afiliacja ===
// Centralny rejestr linków partnerskich: podmieniasz URL w jednym miejscu,
// a wszystkie przyciski <a data-aff="klucz"> na stronie dostają właściwy adres.
// Po zapisaniu się do sieci (Ceneo Partner, Awin, webePartners...) wklej tu swoje linki.
const AFF_LINKS = {
  'zestaw-feeder-start': 'https://www.ceneo.pl/Wedkarstwo;szukaj-zestaw+feeder',
  'zestaw-spinning-predator': 'https://www.ceneo.pl/Wedkarstwo;szukaj-zestaw+spinningowy',
  'zestaw-karp-weekend': 'https://www.ceneo.pl/Wedkarstwo;szukaj-zestaw+karpiowy',
  'wedka-spinning-start': 'https://www.ceneo.pl/Wedkarstwo;szukaj-wedka+spinningowa',
  'wedka-feeder-start': 'https://www.ceneo.pl/Wedkarstwo;szukaj-wedka+feeder',
  'kolowrotek-uniwersalny': 'https://www.ceneo.pl/Wedkarstwo;szukaj-kolowrotek+2500',
};

(function () {
  const links = document.querySelectorAll('a[data-aff]');
  if (!links.length) return;

  links.forEach((a) => {
    const url = AFF_LINKS[a.dataset.aff];
    if (url) a.href = url;
    a.target = '_blank';
    a.rel = 'sponsored noopener';
  });

  // Automatyczna nota o linkach partnerskich w stopce (wymóg przejrzystości / UOKiK).
  const footer = document.querySelector('.footer .container');
  if (footer && !footer.querySelector('.aff-note')) {
    const note = document.createElement('p');
    note.className = 'aff-note';
    note.textContent = 'Niektóre odnośniki na tej stronie to linki partnerskie — kupując przez nie, wspierasz rozwój serwisu, a Ty nie płacisz ani grosza więcej.';
    footer.appendChild(note);
  }
})();

// === Ikony SVG kart kategorii ===
// Podmienia emoji w <span class="icon"> na liniowe ikony SVG (glassmorphism robi CSS).
(function () {
  const svg = (inner) =>
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + inner + '</svg>';

  const ICONS = {
    rod: svg('<path d="M4 20 18 4"/><path d="M18 4c3.2 4.2 1 9.2-4.2 10.4"/><circle cx="13.5" cy="16.5" r="1.7"/>'),
    gear: svg('<circle cx="12" cy="12" r="3.2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.2 5.2l2.1 2.1M16.7 16.7l2.1 2.1M18.8 5.2l-2.1 2.1M7.3 16.7l-2.1 2.1"/>'),
    fish: svg('<path d="M3.5 12c4-5 9.5-5 13.5 0-4 5-9.5 5-13.5 0z"/><path d="M17 12l4.5-3.5v7z"/><circle cx="7.8" cy="11" r=".4" fill="currentColor"/>'),
    moon: svg('<path d="M20 14.5A8.5 8.5 0 1 1 9.5 4 7 7 0 0 0 20 14.5z"/>'),
    snow: svg('<path d="M12 2v20M3.3 7l17.4 10M20.7 7 3.3 17"/>'),
    anchor: svg('<circle cx="12" cy="5" r="2.2"/><path d="M12 7.2V21M5 13a7 7 0 0 0 14 0M2.8 13H7M17 13h4.2"/>'),
    waves: svg('<path d="M2 9.5c3-4.5 6.5 4.5 10 0s7-4.5 10 0M2 16c3-4.5 6.5 4.5 10 0s7-4.5 10 0"/>'),
    sonar: svg('<circle cx="12" cy="13" r="1.6"/><path d="M12 6.5a6.5 6.5 0 0 1 6.5 6.5M12 2.5A10.5 10.5 0 0 1 22.5 13"/>'),
    calendar: svg('<rect x="3.5" y="5" width="17" height="16" rx="2.5"/><path d="M3.5 10h17M8 2.8V7M16 2.8V7"/>'),
    wind: svg('<path d="M3 8.5h10.5a3 3 0 1 0-3-3M3 13.5h14.5a3 3 0 1 1-3 3M3 18.5h7"/>'),
    book: svg('<path d="M4.5 19.5A2.5 2.5 0 0 1 7 17h12.5V2.5H7A2.5 2.5 0 0 0 4.5 5z"/><path d="M19.5 17v4.5H7a2.5 2.5 0 0 1-2.5-2.5"/>'),
    ruler: svg('<rect x="2.8" y="9" width="18.4" height="6.5" rx="1.2"/><path d="M7 9v3.2M11 9v3.2M15 9v3.2M19 9v3.2"/>'),
    scale: svg('<path d="M12 4v16M8.5 20h7M5.5 7.5 12 6l6.5 1.5"/><path d="M5.5 7.5 3.5 13a2.8 2.8 0 0 0 5.6 0zM18.5 6 16.5 11.5a2.8 2.8 0 0 0 5.6 0z"/>'),
    target: svg('<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.3" fill="currentColor"/>'),
    pot: svg('<path d="M4 10.5h16V14a6 6 0 0 1-6 6h-4a6 6 0 0 1-6-6zM2.5 10.5h19"/><path d="M9.5 7c0-2.2 5-2.2 5 0"/>'),
    tree: svg('<path d="M12 3l5 7h-3.2l4.2 6.5H6L10.2 10H7z"/><path d="M12 16.5V21"/>'),
    bobber: svg('<path d="M12 2.8V7M12 17v4.2"/><ellipse cx="12" cy="12" rx="3.6" ry="5"/><path d="M8.4 12h7.2"/>'),
    lure: svg('<path d="M3 12c3-6 6 6 9 0s6 6 9 0"/><circle cx="20" cy="9.5" r=".4" fill="currentColor"/>'),
    hook: svg('<path d="M12 3v9.5a4.5 4.5 0 0 0 9 0V11"/><circle cx="12" cy="3" r="1.2"/><path d="M21 11l-1.6 1.8"/>'),
  };

  const EMOJI_MAP = {
    '🎣': 'rod', '⚙️': 'gear',
    '🐟': 'fish', '🦈': 'fish', '🐋': 'fish', '🐊': 'fish', '🦓': 'fish',
    '🌙': 'moon', '❄️': 'snow', '🧊': 'snow',
    '⚓': 'anchor', '🚤': 'anchor', '🌊': 'waves',
    '📡': 'sonar', '📅': 'calendar',
    '💨': 'wind', '🌦️': 'wind',
    '📚': 'book', '📖': 'book', '📄': 'book', '🗂️': 'book',
    '📏': 'ruler', '⚖️': 'scale',
    '🎯': 'target', '🥇': 'target', '👑': 'target', '🚩': 'target',
    '🔥': 'pot', '🍳': 'pot', '🍲': 'pot', '🥞': 'pot', '🔪': 'pot', '🥣': 'pot', '🫒': 'pot', '🧺': 'pot',
    '🌿': 'tree', '🌳': 'tree', '🎄': 'tree', '🏔️': 'tree', '🏕️': 'tree',
    '🔴': 'bobber', '🟠': 'bobber',
    '🧵': 'lure', '🪢': 'lure', '🪱': 'lure',
    '🥾': 'hook', '🤲': 'hook', '🪶': 'hook', '🧰': 'gear',
  };

  document.querySelectorAll('.icon').forEach((el) => {
    const key = EMOJI_MAP[el.textContent.trim()] || 'hook';
    el.innerHTML = ICONS[key];
    el.classList.add('icon-glass');
  });
})();
