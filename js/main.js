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
