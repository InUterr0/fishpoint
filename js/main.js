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

// Podstrony artykułowe: przenieś zdjęcie z treści do prawej, przyklejonej kolumny.
const articleFigure = document.querySelector('.article-card .article-figure');
const sideNav = document.querySelector('.side-nav');
if (articleFigure && sideNav) {
  const rail = document.createElement('div');
  rail.className = 'side-rail';
  sideNav.parentNode.insertBefore(rail, sideNav);
  rail.appendChild(articleFigure);
  rail.appendChild(sideNav);
}

// Podświetl w bocznym menu link do bieżącej strony.
if (sideNav) {
  const here = location.pathname.split('/').pop();
  sideNav.querySelectorAll('a').forEach((a) => {
    if (a.getAttribute('href') === here) a.classList.add('active');
  });
}
