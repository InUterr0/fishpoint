/* Service worker FishPoint.
 *
 * Powód istnienia jest terenowy: nad wodą zasięg bywa szczątkowy, a strony,
 * które wędkarz sprawdza na miejscu — okresy ochronne, wymiary, karta gatunku,
 * węzły — muszą otworzyć się także wtedy, gdy sieć nie odpowiada.
 *
 * Zasady, których ten plik pilnuje:
 *   1. Dokumenty idą network-first. Treść prawna zmienia się w trakcie sezonu
 *      i nigdy nie wolno podać wersji z cache, jeśli sieć potrafi zwrócić
 *      świeższą. Cache jest wyłącznie awaryjny.
 *   2. Cache-first dostają tylko zasoby statyczne (/css/, /js/, /assets/),
 *      które są wersjonowane albo niezmienne w obrębie wydania.
 *   3. Wszystko, co nie jest tym samym originem, przechodzi bez dotknięcia —
 *      reklamy, komentarze i newsletter mają własne reguły i nie należą do nas.
 *   4. Cache jest nazwany hashem wydania. Nowe wydanie = nowa nazwa = stare
 *      zasoby znikają w activate, więc nie da się utknąć na starym CSS.
 *
 * CACHE_VERSION stempluje generator (seo_inject.py) hashem treści css/js/sw.
 */
const CACHE_VERSION = '19b1b35f';
const CACHE_NAME = `fishpoint-${CACHE_VERSION}`;

// Powłoka: strona główna jako zapas nawigacyjny plus zasoby, bez których
// dokument z cache wyglądałby jak surowy HTML.
const SHELL = [
  '/',
  '/css/style.css',
  '/js/main.js',
  '/assets/img/logo.svg',
];

const OFFLINE_HTML = `<!doctype html><html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Brak połączenia — FishPoint</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#eef3ee;
color:#12332e;font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:32rem;padding:2rem;text-align:center}h1{font-size:1.5rem;margin:0 0 .75rem}
p{margin:0 0 1rem}a{color:#0e5e54}</style></head><body><main>
<h1>Brak połączenia</h1>
<p>Ta strona nie została jeszcze zapisana na urządzeniu, a sieć nie odpowiada.</p>
<p>Strony otwarte wcześniej działają offline — wróć do nich przyciskiem wstecz.</p>
<p><a href="/">Otwórz stronę główną</a></p>
</main></body></html>`;

const offlineResponse = () =>
  new Response(OFFLINE_HTML, {
    status: 503,
    headers: { 'Content-Type': 'text/html; charset=utf-8' },
  });

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      // Pojedynczy brak w powłoce nie może wywrócić instalacji — dlatego
      // każdy zasób dokładamy osobno i błąd tylko pomijamy.
      .then((cache) => Promise.all(SHELL.map((url) => cache.add(url).catch(() => null))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter((name) => name.startsWith('fishpoint-') && name !== CACHE_NAME)
            .map((name) => caches.delete(name))
        )
      )
      .then(() => self.clients.claim())
  );
});

const isStaticAsset = (url) =>
  url.pathname.startsWith('/css/') ||
  url.pathname.startsWith('/js/') ||
  url.pathname.startsWith('/assets/');

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Dokumenty: sieć decyduje, cache tylko ratuje.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response && response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() =>
          caches
            .match(request)
            .then((hit) => hit || caches.match('/'))
            .then((hit) => hit || offlineResponse())
        )
    );
    return;
  }

  if (!isStaticAsset(url)) return;

  // Zasoby statyczne: cache-first, ale z cichym odświeżeniem w tle.
  event.respondWith(
    caches.match(request).then((hit) => {
      const network = fetch(request)
        .then((response) => {
          if (response && response.ok) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => hit);
      return hit || network;
    })
  );
});
