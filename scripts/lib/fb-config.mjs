// Dane strony FishPoint na Facebooku. Wspólne dla /fejs-posty i /fejs-komcie.
//
//   - PAGE_NAME   : nazwa strony FB (autor postów/komentarzy)
//   - PAGE_ID     : numeryczne ID strony (do twardej bramki tożsamości)
//   - ASSET_ID    : asset_id strony w Meta Business Suite (URL composera)
//   - BAD_ACCOUNTS: konta, z których komentarze NIGDY nie mają wychodzić —
//                   bramka przerwie run, jeśli wykryje którekolwiek z nich.
//
// Strona utworzona 2026-06-26: facebook.com/profile.php?id=61591546555168
export const FB = {
  PAGE_NAME: 'FishPoint',
  PAGE_ID: '61591546555168',
  ASSET_ID: '1171074182758982',
  // Konto osobiste + pozostałe strony (newsy) — fail-safe, żeby komentarze
  // FishPoint nie wyszły przypadkiem z nieprawidłowej tożsamości.
  BAD_ACCOUNTS: ['Maciek Baniewicz', 'Fachowiec.pro', 'World News No Spin'],
};
