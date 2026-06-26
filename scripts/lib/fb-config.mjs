// Dane strony FishPoint na Facebooku — UZUPEŁNIJ przed pierwszym użyciem
// /fejs-posty i /fejs-komcie. Jedno miejsce dla obu skryptów.
//
// Jak zdobyć wartości:
//   - PAGE_NAME  : dokładna nazwa Twojej strony FB (tak, jak wyświetla się jako autor)
//   - PAGE_ID    : numeryczny ID strony (Meta Business Suite → Ustawienia strony,
//                  albo z URL-a strony). Używany do twardej bramki tożsamości.
//   - ASSET_ID   : asset_id strony w Meta Business Suite (jest w URL-u composera:
//                  business.facebook.com/latest/composer?asset_id=XXXX)
//   - BAD_ACCOUNTS: nazwy Twoich PRYWATNYCH kont, z których komentarze NIGDY nie
//                  mają wychodzić — bramka przerwie run, jeśli wykryje takie konto.
//
// Dopóki PAGE_NAME zostaje placeholderem, /fejs-komcie i tak NIC nie opublikuje —
// bramka tożsamości nie potwierdzi strony i bezpiecznie przerwie cały run.
export const FB = {
  PAGE_NAME: 'UZUPEŁNIJ — nazwa strony FB FishPoint',
  PAGE_ID: 'UZUPELNIJ_PAGE_ID',
  ASSET_ID: 'UZUPELNIJ_ASSET_ID',
  BAD_ACCOUNTS: ['UZUPELNIJ_PRYWATNE_KONTO'],
};
