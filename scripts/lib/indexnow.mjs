// Wspólny helper IndexNow (Bing/Yandex/Seznam — Google nie wspiera).
// Używany przez automatyzację wdrożenia i skrypty promo (/x-posty).
//
// Klucz IndexNow nie jest sekretem: protokół wymaga publicznego pliku
// https://fish-point.pl/<KEY>.txt. Zmienna środowiskowa pozwala go obrócić
// bez zmiany kodu, o ile odpowiadający plik trafi na produkcję.
const HOST = 'fish-point.pl';
const DEFAULT_KEY = 'a39db5495ae6e2738bab111816879bac94952af2c3003f3a11b16182cb7eb013';
const KEY = process.env.INDEXNOW_KEY || DEFAULT_KEY;

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
