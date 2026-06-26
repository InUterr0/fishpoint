// Wspólny helper IndexNow (Bing/Yandex/Seznam — Google nie wspiera).
// Używany przez skrypty promo (/x-posty) jako dodatkowy
// „szturchaniec" dla świeżo promowanych artykułów.
//
// UWAGA: IndexNow wymaga pliku-klucza dostępnego pod https://fish-point.pl/<KEY>.txt
// (o treści równej kluczowi). Dopóki taki plik nie istnieje, ping zwróci 403/422,
// ale NIGDY nie wywali runu. Ustaw własny klucz przez zmienną INDEXNOW_KEY albo
// wpisz go niżej i dodaj plik <KEY>.txt do repo strony.
const HOST = 'fish-point.pl';
const KEY = process.env.INDEXNOW_KEY || '';

/**
 * Zgłasza listę URL-i do IndexNow. Nigdy nie rzuca — zwraca status HTTP albo
 * null przy błędzie/braku klucza, żeby nie wywalić wołającego skryptu.
 */
export async function pingIndexNow(urls) {
  const urlList = [...new Set((urls || []).filter(Boolean))];
  if (urlList.length === 0 || !KEY) return null;
  try {
    const res = await fetch('https://api.indexnow.org/indexnow', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
      body: JSON.stringify({
        host: HOST,
        key: KEY,
        keyLocation: `https://${HOST}/${KEY}.txt`,
        urlList,
      }),
    });
    return res.status;
  } catch {
    return null;
  }
}
