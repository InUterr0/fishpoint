const toggle = document.querySelector('.nav-toggle');
const menu = document.querySelector('#nav-menu');

if (toggle && menu) {
  const closeMenu = () => {
    menu.classList.remove('open');
    toggle.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('nav-open');
  };

  toggle.addEventListener('click', () => {
    const isOpen = menu.classList.toggle('open');
    toggle.setAttribute('aria-expanded', String(isOpen));
    document.body.classList.toggle('nav-open', isOpen);
  });

  menu.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      if (window.matchMedia('(max-width: 840px)').matches && link.matches('.has-sub > a')) return;
      closeMenu();
    });
  });

  menu.querySelectorAll('.has-sub > a').forEach((link) => {
    link.addEventListener('click', (event) => {
      if (!window.matchMedia('(max-width: 840px)').matches) return;
      const item = link.parentElement;
      if (!item.classList.contains('sub-open')) {
        event.preventDefault();
        menu.querySelectorAll('.has-sub.sub-open').forEach((openItem) => {
          if (openItem !== item) openItem.classList.remove('sub-open');
        });
        item.classList.add('sub-open');
      }
    });
  });

  document.addEventListener('click', (event) => {
    if (!menu.contains(event.target) && !toggle.contains(event.target)) closeMenu();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && menu.classList.contains('open')) {
      closeMenu();
      toggle.focus();
    }
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
  let saved = null;
  try {
    saved = window.localStorage.getItem('fishpoint-theme');
  } catch {
    // Prywatny tryb lub zablokowane dane witryny: użyj motywu domyślnego.
  }
  if (saved === 'dark') document.documentElement.classList.add('dark');

  const nav = document.querySelector('.nav');
  if (!nav) return;

  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'theme-toggle';
  btn.setAttribute('aria-label', 'Przełącz ciemny motyw');
  btn.setAttribute('aria-pressed', document.documentElement.classList.contains('dark') ? 'true' : 'false');
  const setIcon = () => {
    const dark = document.documentElement.classList.contains('dark');
    btn.textContent = dark ? '☀️' : '🌙';
    btn.setAttribute('aria-pressed', String(dark));
  };
  setIcon();

  btn.addEventListener('click', () => {
    const dark = document.documentElement.classList.toggle('dark');
    try {
      window.localStorage.setItem('fishpoint-theme', dark ? 'dark' : 'light');
    } catch {
      // Bieżący wybór pozostaje aktywny, ale nie będzie zapamiętany.
    }
    setIcon();
  });

  nav.appendChild(btn);
})();

// Lekka fasada YouTube: odtwarzacz ładuje się dopiero po świadomym kliknięciu.
document.querySelectorAll('.youtube-facade[data-video-id]').forEach((facade) => {
  facade.addEventListener('click', () => {
    const videoId = facade.dataset.videoId;
    if (!/^[A-Za-z0-9_-]{11}$/.test(videoId || '')) return;

    const iframe = document.createElement('iframe');
    iframe.title = facade.dataset.videoTitle || 'Film YouTube';
    iframe.loading = 'lazy';
    iframe.allowFullscreen = true;
    iframe.setAttribute('allow', 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share');
    iframe.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
    iframe.src = `https://www.youtube-nocookie.com/embed/${videoId}?autoplay=1&rel=0`;
    facade.replaceWith(iframe);
  }, { once: true });
});

// Analityka jest ładowana wyłącznie po wyraźnej zgodzie użytkownika.
(function () {
  const ANALYTICS_ID = 'G-33TKR9MEB7';
  const CONSENT_KEY = 'fishpoint-analytics-consent';
  let consent = null;

  try {
    consent = window.localStorage.getItem(CONSENT_KEY);
  } catch {
    // Bez dostępu do pamięci ustawienie obowiązuje tylko w bieżącej karcie.
  }

  const saveConsent = (value) => {
    consent = value;
    try {
      window.localStorage.setItem(CONSENT_KEY, value);
    } catch {
      // Brak trwałej pamięci nie może blokować wyboru użytkownika.
    }
  };

  const loadAnalytics = () => {
    if (document.querySelector('script[data-fishpoint-analytics]')) return;
    window[`ga-disable-${ANALYTICS_ID}`] = false;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function gtag() { window.dataLayer.push(arguments); };
    window.gtag('js', new Date());
    window.gtag('config', ANALYTICS_ID);

    const script = document.createElement('script');
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${ANALYTICS_ID}`;
    script.dataset.fishpointAnalytics = 'true';
    document.head.appendChild(script);
  };

  const removeAnalyticsCookies = () => {
    const names = document.cookie.split(';').map((item) => item.trim().split('=')[0])
      .filter((name) => /^_(?:ga|gid|gat)(?:_|$)/.test(name));
    const domains = location.hostname.split('.').map((_, index, parts) => `.${parts.slice(index).join('.')}`);
    names.forEach((name) => {
      [`${name}=; Max-Age=0; path=/`, ...domains.map((domain) => `${name}=; Max-Age=0; path=/; domain=${domain}`)]
        .forEach((cookie) => { document.cookie = cookie; });
    });
  };

  const revokeAnalytics = () => {
    window[`ga-disable-${ANALYTICS_ID}`] = true;
    document.querySelectorAll('script[data-fishpoint-analytics]').forEach((script) => script.remove());
    removeAnalyticsCookies();
    window.location.reload();
  };

  const settings = document.createElement('button');
  settings.type = 'button';
  settings.className = 'analytics-settings';
  settings.textContent = 'Ustawienia prywatności';
  settings.setAttribute('aria-haspopup', 'dialog');

  const notice = document.createElement('section');
  notice.className = 'analytics-consent';
  notice.hidden = true;
  notice.setAttribute('role', 'dialog');
  notice.setAttribute('aria-modal', 'false');
  notice.setAttribute('aria-labelledby', 'analytics-consent-title');

  const title = document.createElement('h2');
  title.id = 'analytics-consent-title';
  title.textContent = 'Pomóż nam rozwijać FishPoint';
  const copy = document.createElement('p');
  copy.textContent = 'Za Twoją zgodą używamy Google Analytics do statystycznego pomiaru odwiedzin. Możesz zmienić decyzję w każdej chwili.';
  const actions = document.createElement('div');
  actions.className = 'analytics-consent-actions';
  const reject = document.createElement('button');
  reject.type = 'button';
  reject.className = 'analytics-consent-reject';
  reject.textContent = 'Odrzuć';
  const accept = document.createElement('button');
  accept.type = 'button';
  accept.className = 'analytics-consent-accept';
  accept.textContent = 'Akceptuję';
  actions.append(reject, accept);
  notice.append(title, copy, actions);
  document.body.append(settings, notice);

  const openNotice = () => {
    notice.hidden = false;
    accept.focus();
  };
  const closeNotice = () => {
    notice.hidden = true;
    settings.focus();
  };

  settings.addEventListener('click', openNotice);
  accept.addEventListener('click', () => {
    saveConsent('granted');
    loadAnalytics();
    closeNotice();
  });
  reject.addEventListener('click', () => {
    const revoke = consent === 'granted';
    saveConsent('denied');
    closeNotice();
    if (revoke) revokeAnalytics();
  });

  if (consent === 'granted') {
    loadAnalytics();
  } else if (consent !== 'denied') {
    openNotice();
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
    compass: svg('<circle cx="12" cy="12" r="8.5"/><path d="m15.5 8.5-2.2 4.8-4.8 2.2 2.2-4.8z"/>'),
    pin: svg('<path d="M12 21s6-5.1 6-11a6 6 0 0 0-12 0c0 5.9 6 11 6 11z"/><circle cx="12" cy="10" r="2"/>'),
    chat: svg('<path d="M5 5.5h14v10H9l-4 3v-3.5z"/><path d="M8 9.5h8M8 12.5h5"/>'),
    smile: svg('<circle cx="12" cy="12" r="9"/><path d="M8 14.5c1.2 1.5 2.8 2.2 4 2.2s2.8-.7 4-2.2M9 9h.01M15 9h.01"/>'),
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
    '🧭': 'compass', '📍': 'pin', '💬': 'chat', '😄': 'smile',
    '🎣': 'rod', '⚙️': 'gear', '🛠️': 'gear',
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

// Tabele w artykułach: przewijalny, opisany obszar tylko tam, gdzie tabela jest szersza od ekranu.
document.querySelectorAll('table.decision-table, table.starter-kit, .decision-table > table, .starter-kit > table').forEach((table) => {
  if (table.parentElement.classList.contains('article-table-scroll')) return;

  const wrapper = document.createElement('div');
  const caption = table.querySelector('caption');
  const section = table.closest('.decision-table, .starter-kit');
  const heading = section && section.querySelector('h2, h3, h4');
  const name = (caption && caption.textContent.trim()) || (heading && heading.textContent.trim()) || 'tabela';
  const label = `Przewijana ${name}`;

  wrapper.className = 'article-table-scroll';
  wrapper.tabIndex = 0;
  wrapper.setAttribute('role', 'region');
  wrapper.setAttribute('aria-label', label);
  table.parentNode.insertBefore(wrapper, table);
  wrapper.appendChild(table);

  const updateScrollState = () => {
    const hasOverflow = wrapper.scrollWidth > wrapper.clientWidth + 1;
    wrapper.classList.toggle('is-scrollable', hasOverflow);
    wrapper.classList.toggle('is-at-end', !hasOverflow || wrapper.scrollLeft >= wrapper.scrollWidth - wrapper.clientWidth - 1);
  };

  wrapper.addEventListener('scroll', updateScrollState, { passive: true });
  window.addEventListener('resize', updateScrollState);
  if ('ResizeObserver' in window) new ResizeObserver(updateScrollState).observe(wrapper);
  updateScrollState();
});
