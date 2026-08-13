/** Privacy Policy and Terms of Service, in both app languages.
 *
 *  These live here rather than in `i18n.tsx`'s `dict` on purpose: that table is
 *  for UI chrome — short strings a component interpolates — while these are
 *  long-form documents whose EN and PL versions must be read and revised
 *  side by side. Keeping each document's two languages adjacent is what makes
 *  a legal edit reviewable; 200 loose `t()` keys would not be.
 *
 *  Facts asserted here are checked against the implementation (processors and
 *  their regions, what account deletion actually erases, what group members
 *  can see). When any of that changes, this file changes with it — and bump
 *  `LEGAL_UPDATED`.
 */

import type { Lang } from "./i18n";

/** Shown as "Last updated" on both documents. Date-only, local (see dates.ts). */
export const LEGAL_UPDATED = "2026-08-13";

export const LEGAL_CONTACT_EMAIL = "privacy@split-dec.app";

export type LegalDocId = "privacy" | "terms";

/** A paragraph (string) or a bullet list (array of strings). Both support
 *  `**bold**` and `[label](href)` — see `renderLegalText` in LegalPage. */
export type LegalBlock = string | readonly string[];

export interface LegalSection {
  heading: string;
  blocks: readonly LegalBlock[];
}

export interface LegalDoc {
  title: string;
  intro: readonly string[];
  sections: readonly LegalSection[];
}

const MAILTO = `[${LEGAL_CONTACT_EMAIL}](mailto:${LEGAL_CONTACT_EMAIL})`;

const PRIVACY_EN: LegalDoc = {
  title: "Privacy Policy",
  intro: [
    "SplitDec is a free tool for keeping track of who paid what in a group. This policy explains what personal data it collects, why, who else sees it, and what you can do about it.",
    `SplitDec is operated by Tomasz Giela, a private individual based in Poland, who is the data controller for the purposes of the GDPR. You can reach us at ${MAILTO}.`,
  ],
  sections: [
    {
      heading: "What we collect",
      blocks: [
        "We collect only what the app needs to work. There is no advertising network and no tracking pixel anywhere in SplitDec, and nothing you record in it is ever sold, rented or used to target you.",
        [
          "**Account data** — your email address, the name you signed up with, and, if you sign in with Google, the address of the profile picture Google provides.",
          "**What you record in the app** — your groups and their names, expenses (description, category, amount, currency, date, who paid, and how the cost is split), the settlements you register, and the email addresses you invite to a group.",
          "**Technical data** — our hosting providers keep short-lived server logs (IP address, time, requested address, browser user-agent) so the service can be operated and abuse investigated.",
          "**Aggregate usage measurement** — Vercel Web Analytics counts page views, so we can see which parts of SplitDec people actually use. It records the page address, the site you arrived from, and coarse device and country information. It sets no cookies, stores nothing on your device, and cannot follow you to other websites or link a visit to your account.",
          "**Performance measurement** — Vercel Speed Insights records how quickly pages load and respond on your device (the Core Web Vitals). It is told the route pattern rather than the exact address, so the identifier of a group you open is never part of it. Like the measurement above, it sets no cookies and identifies nobody.",
          "**Settings kept on your device** — your language, your light/dark preference and your sign-in session live in your browser's local storage, not on our servers.",
        ],
        "SplitDec never asks for and never stores card numbers, bank details, your location or your contacts. **The app does not move money.** It records who owes whom; the actual transfers happen outside SplitDec, however you normally pay each other.",
      ],
    },
    {
      heading: "Why we use it",
      blocks: [
        "Every use below is tied to a legal basis under Article 6 of the GDPR:",
        [
          "**Running the service** — creating your account, showing your groups, computing balances. Necessary to perform our agreement with you (Art. 6(1)(b)).",
          "**Sending you service email** — sign-up confirmation, password resets and group invitations. Also part of that agreement (Art. 6(1)(b)).",
          "**Keeping SplitDec safe** — verifying sign-ins, limiting how many invitations one account can send, investigating abuse. Our legitimate interest in a service that is not used to spam or attack people (Art. 6(1)(f)).",
          "**Understanding how SplitDec is used and how well it runs** — counting page views in aggregate, and measuring loading speed, so we know what is worth improving and can tell when a change made the app slower. Our legitimate interest in developing the service (Art. 6(1)(f)); neither uses cookies and neither identifies anybody.",
          "**Meeting legal obligations**, where one applies to us (Art. 6(1)(c)).",
        ],
        "We do not profile you, do not advertise to you, do not make automated decisions about you with legal effects, and do not sell or rent personal data to anyone.",
      ],
    },
    {
      heading: "Who else handles your data",
      blocks: [
        "We use a small number of providers to run the service. They act as our processors — they may handle your data only on our instructions:",
        [
          "**Supabase** — database and sign-in, hosted in the EU (Paris region). [Privacy policy](https://supabase.com/privacy).",
          "**Vercel** — hosting for the website and the API, with the API function pinned to the EU (Paris region), and the usage and performance measurement described above. [Privacy policy](https://vercel.com/legal/privacy-policy).",
          "**Resend** — delivery of the emails listed above, EU region (Ireland). [Privacy policy](https://resend.com/legal/privacy-policy).",
          "**Google** — only if you choose to sign in with Google. Google confirms who you are and passes us your name, email address and profile-picture address. Your use of Google is governed by [Google's privacy policy](https://policies.google.com/privacy).",
        ],
        "Your account and everything you record is stored in the European Union. Where a provider's own support or infrastructure reaches outside the EEA, that transfer relies on the safeguards in their data-processing terms, such as the European Commission's standard contractual clauses.",
      ],
    },
    {
      heading: "What other people can see",
      blocks: [
        "SplitDec is a shared ledger, so some of your data is visible to the people you share it with:",
        [
          "Everyone in a group you belong to sees your display name, your profile picture, and every expense, settlement and balance in that group — including the ones you created.",
          "When you invite someone by email, they are told who invited them and to which group.",
          "When you are invited, the person who invited you sees whether the invitation is still pending, accepted or declined — but never whether the address already had a SplitDec account.",
        ],
        "Nothing you record is public, indexed by search engines, or visible to people outside your groups.",
      ],
    },
    {
      heading: "How long we keep it",
      blocks: [
        [
          "Your account data is kept until you delete your account.",
          "You can delete your account yourself at any time from **Account → Delete account**, once you are settled up in every group. This removes your sign-in credentials and replaces your name and email address in our database with anonymous placeholders.",
          "Expenses and settlements you took part in stay in the group after that, attributed to a deleted user. They cannot be removed without corrupting the balances of everyone else in the group, and they no longer identify you.",
          "Invitations still waiting for your email address are deleted along with your account; ones you already answered have the address removed.",
          "Server logs are kept briefly by our hosting providers, under their own retention schedules.",
        ],
      ],
    },
    {
      heading: "Your rights",
      blocks: [
        "Under the GDPR you can ask us for a copy of your data, or to correct it, delete it, restrict or object to how we use it, or hand it over in a portable format. You can also complain to a supervisory authority.",
        `Write to ${MAILTO} and we will answer within one month. Deleting your account is quicker to do yourself — it is a button in the app.`,
        "The authority for Poland is the President of the Personal Data Protection Office (Prezes Urzędu Ochrony Danych Osobowych), ul. Stawki 2, 00-193 Warszawa. You may also complain to the authority where you live or work.",
      ],
    },
    {
      heading: "Cookies and local storage",
      blocks: [
        "SplitDec sets no advertising or analytics cookies and stores no identifier that could follow you to another website, which is why you are never asked to accept any. The usage and performance measurement described above are both cookieless: they count visits and timings without recognising who you are.",
        "The app stores four things in your browser: your sign-in session (so you stay signed in), your language, your light/dark preference, and — only if a file goes missing after an update — a timestamp that stops the page reloading in a loop. If you install SplitDec as an app, a service worker also caches its files so it starts quickly and works offline. Clearing your browser storage removes all of it and signs you out.",
      ],
    },
    {
      heading: "Security",
      blocks: [
        [
          "All traffic is encrypted in transit (HTTPS, with HSTS).",
          "Passwords are hashed by our authentication provider; we never see or store them. Signing in with Google means we never handle a password at all.",
          "Every request to the API is authorized individually — the database is not reachable directly from the internet, and one group's data cannot be read by anyone outside it.",
        ],
        "No online service can promise perfect security. If you believe someone else has accessed your account, email us.",
      ],
    },
    {
      heading: "Children",
      blocks: [
        "SplitDec is not intended for children under 16. If you are under 16, please do not create an account. If you believe a child has given us personal data, write to us and we will delete it.",
      ],
    },
    {
      heading: "Changes to this policy",
      blocks: [
        "If this policy changes we will update the date at the top of it. If a change materially affects you, we will tell you in the app or by email before it takes effect.",
      ],
    },
    {
      heading: "Contact",
      blocks: [
        `Questions, requests or complaints: ${MAILTO}.`,
        "This policy is published in English and Polish. If the two versions differ, the Polish version prevails.",
      ],
    },
  ],
};

const PRIVACY_PL: LegalDoc = {
  title: "Polityka prywatności",
  intro: [
    "SplitDec to bezpłatne narzędzie do zapisywania, kto za co zapłacił w grupie. Ta polityka wyjaśnia, jakie dane osobowe zbiera, po co, kto jeszcze je widzi i co możesz z tym zrobić.",
    `SplitDec prowadzi Tomasz Giela, osoba prywatna z Polski, będąca administratorem danych w rozumieniu RODO. Kontakt: ${MAILTO}.`,
  ],
  sections: [
    {
      heading: "Jakie dane zbieramy",
      blocks: [
        "Zbieramy tylko to, co jest potrzebne do działania aplikacji. W SplitDec nie ma żadnej sieci reklamowej ani piksela śledzącego, a tego, co w niej zapisujesz, nikomu nie sprzedajemy, nie wynajmujemy i nie używamy do kierowania do Ciebie reklam.",
        [
          "**Dane konta** — Twój adres e-mail, imię i nazwisko podane przy rejestracji oraz — jeśli logujesz się przez Google — adres zdjęcia profilowego przekazany przez Google.",
          "**To, co zapisujesz w aplikacji** — Twoje grupy i ich nazwy, wydatki (opis, kategoria, kwota, waluta, data, kto zapłacił i jak dzielony jest koszt), zarejestrowane rozliczenia oraz adresy e-mail zapraszane przez Ciebie do grupy.",
          "**Dane techniczne** — nasi dostawcy hostingu przechowują krótkotrwałe logi serwera (adres IP, czas, wywołany adres, identyfikator przeglądarki), aby można było prowadzić usługę i badać nadużycia.",
          "**Zbiorcze pomiary użycia** — Vercel Web Analytics zlicza odsłony stron, żebyśmy wiedzieli, z których części SplitDec faktycznie korzystacie. Zapisuje adres strony, witrynę, z której przyszedłeś(-łaś), oraz ogólne informacje o urządzeniu i kraju. Nie ustawia plików cookie, nic nie zapisuje na Twoim urządzeniu i nie może śledzić Cię na innych stronach ani powiązać wizyty z Twoim kontem.",
          "**Pomiary wydajności** — Vercel Speed Insights zapisuje, jak szybko strony wczytują się i reagują na Twoim urządzeniu (wskaźniki Core Web Vitals). Otrzymuje wzorzec ścieżki, a nie dokładny adres, więc identyfikator otwieranej grupy nigdy do niego nie trafia. Podobnie jak pomiary powyżej nie ustawia plików cookie i nikogo nie identyfikuje.",
          "**Ustawienia zapisane na Twoim urządzeniu** — język, tryb jasny/ciemny i sesja logowania są przechowywane w pamięci lokalnej przeglądarki, a nie na naszych serwerach.",
        ],
        "SplitDec nigdy nie prosi o numery kart, dane bankowe, Twoją lokalizację ani kontakty i ich nie przechowuje. **Aplikacja nie przelewa pieniędzy.** Zapisuje, kto komu ile jest winien; same przelewy odbywają się poza SplitDec, tak jak zwykle płacicie sobie nawzajem.",
      ],
    },
    {
      heading: "Po co ich używamy",
      blocks: [
        "Każde z poniższych zastosowań ma podstawę prawną z art. 6 RODO:",
        [
          "**Świadczenie usługi** — założenie konta, pokazywanie grup, obliczanie sald. Niezbędne do wykonania umowy z Tobą (art. 6 ust. 1 lit. b).",
          "**Wysyłanie e-maili serwisowych** — potwierdzenie rejestracji, reset hasła i zaproszenia do grup. Również element tej umowy (art. 6 ust. 1 lit. b).",
          "**Bezpieczeństwo SplitDec** — weryfikacja logowań, ograniczanie liczby zaproszeń wysyłanych z jednego konta, badanie nadużyć. Nasz prawnie uzasadniony interes, aby usługa nie służyła do spamu ani ataków (art. 6 ust. 1 lit. f).",
          "**Zrozumienie, jak używany jest SplitDec i jak szybko działa** — zbiorcze zliczanie odsłon oraz pomiary szybkości wczytywania, żeby wiedzieć, co warto poprawić i rozpoznać, kiedy zmiana spowolniła aplikację. Nasz prawnie uzasadniony interes w rozwijaniu usługi (art. 6 ust. 1 lit. f); żadne z nich nie korzysta z plików cookie ani nikogo nie identyfikuje.",
          "**Wypełnianie obowiązków prawnych**, jeśli nas dotyczą (art. 6 ust. 1 lit. c).",
        ],
        "Nie profilujemy Cię, nie wyświetlamy Ci reklam, nie podejmujemy wobec Ciebie zautomatyzowanych decyzji wywołujących skutki prawne i nikomu nie sprzedajemy ani nie wynajmujemy danych osobowych.",
      ],
    },
    {
      heading: "Kto jeszcze przetwarza Twoje dane",
      blocks: [
        "Do prowadzenia usługi korzystamy z kilku dostawców. Działają jako nasze podmioty przetwarzające — mogą przetwarzać Twoje dane wyłącznie na nasze polecenie:",
        [
          "**Supabase** — baza danych i logowanie, hosting w UE (region Paryż). [Polityka prywatności](https://supabase.com/privacy).",
          "**Vercel** — hosting strony i API, z funkcją API przypiętą do UE (region Paryż), oraz opisane wyżej pomiary użycia i wydajności. [Polityka prywatności](https://vercel.com/legal/privacy-policy).",
          "**Resend** — dostarczanie wymienionych wyżej e-maili, region UE (Irlandia). [Polityka prywatności](https://resend.com/legal/privacy-policy).",
          "**Google** — tylko jeśli wybierzesz logowanie przez Google. Google potwierdza Twoją tożsamość i przekazuje nam Twoje imię i nazwisko, adres e-mail oraz adres zdjęcia profilowego. Korzystanie z Google podlega [polityce prywatności Google](https://policies.google.com/privacy).",
        ],
        "Twoje konto i wszystko, co w nim zapisujesz, jest przechowywane w Unii Europejskiej. Jeżeli własne wsparcie lub infrastruktura dostawcy sięga poza EOG, taki transfer opiera się na zabezpieczeniach z jego warunków powierzenia przetwarzania, na przykład na standardowych klauzulach umownych Komisji Europejskiej.",
      ],
    },
    {
      heading: "Co widzą inni",
      blocks: [
        "SplitDec to wspólny rejestr, więc część Twoich danych widzą osoby, z którymi go dzielisz:",
        [
          "Każdy członek Twojej grupy widzi Twoją nazwę wyświetlaną, zdjęcie profilowe oraz wszystkie wydatki, rozliczenia i salda w tej grupie — w tym te utworzone przez Ciebie.",
          "Gdy zapraszasz kogoś e-mailem, ta osoba dowiaduje się, kto ją zaprosił i do jakiej grupy.",
          "Gdy to Ty jesteś zapraszany(-a), osoba zapraszająca widzi, czy zaproszenie czeka, zostało przyjęte czy odrzucone — ale nigdy tego, czy dany adres miał już konto w SplitDec.",
        ],
        "Nic, co zapisujesz, nie jest publiczne, indeksowane przez wyszukiwarki ani widoczne dla osób spoza Twoich grup.",
      ],
    },
    {
      heading: "Jak długo je przechowujemy",
      blocks: [
        [
          "Dane konta przechowujemy do czasu jego usunięcia.",
          "Konto możesz usunąć samodzielnie w każdej chwili w **Konto → Usuń konto**, gdy jesteś rozliczony(-a) w każdej grupie. Usuwa to Twoje dane logowania i zastępuje imię, nazwisko oraz adres e-mail w naszej bazie anonimowymi wartościami.",
          "Wydatki i rozliczenia, w których brałeś(-aś) udział, zostają po tym w grupie i są przypisane do usuniętego użytkownika. Nie można ich usunąć bez zaburzenia sald pozostałych osób, a nie identyfikują już Ciebie.",
          "Zaproszenia oczekujące na Twój adres są usuwane razem z kontem; w tych, na które już odpowiedziano, adres zostaje usunięty.",
          "Logi serwera nasi dostawcy hostingu przechowują krótko, zgodnie z własnymi zasadami retencji.",
        ],
      ],
    },
    {
      heading: "Twoje prawa",
      blocks: [
        "Na podstawie RODO możesz zażądać kopii swoich danych, ich sprostowania, usunięcia, ograniczenia przetwarzania lub zgłosić wobec niego sprzeciw, a także otrzymać dane w formacie nadającym się do przeniesienia. Możesz też złożyć skargę do organu nadzorczego.",
        `Napisz na ${MAILTO}, a odpowiemy w ciągu miesiąca. Usunięcie konta szybciej wykonasz samodzielnie — to przycisk w aplikacji.`,
        "Organem właściwym w Polsce jest Prezes Urzędu Ochrony Danych Osobowych, ul. Stawki 2, 00-193 Warszawa. Skargę możesz złożyć również do organu w kraju, w którym mieszkasz lub pracujesz.",
      ],
    },
    {
      heading: "Pliki cookie i pamięć lokalna",
      blocks: [
        "SplitDec nie ustawia żadnych plików cookie reklamowych ani analitycznych i nie zapisuje identyfikatora, który mógłby śledzić Cię na innych stronach — dlatego nigdy nie prosimy Cię o zgodę na cookies. Opisane wyżej pomiary użycia i wydajności działają bez plików cookie: zliczają wizyty i czasy, nie rozpoznając, kim jesteś.",
        "Aplikacja zapisuje w Twojej przeglądarce cztery rzeczy: sesję logowania (żebyś pozostał(a) zalogowany(-a)), język, wybór trybu jasnego lub ciemnego oraz — tylko jeśli po aktualizacji brakuje któregoś pliku — znacznik czasu, który zapobiega zapętlonemu przeładowywaniu strony. Jeśli zainstalujesz SplitDec jako aplikację, service worker dodatkowo zapisuje w pamięci podręcznej jej pliki, aby szybciej się uruchamiała i działała offline. Wyczyszczenie danych przeglądarki usuwa to wszystko i wylogowuje Cię.",
      ],
    },
    {
      heading: "Bezpieczeństwo",
      blocks: [
        [
          "Cały ruch jest szyfrowany w transporcie (HTTPS z HSTS).",
          "Hasła są hashowane przez naszego dostawcę uwierzytelniania; nigdy ich nie widzimy ani nie przechowujemy. Przy logowaniu przez Google w ogóle nie mamy do czynienia z hasłem.",
          "Każde żądanie do API jest autoryzowane osobno — baza danych nie jest dostępna bezpośrednio z internetu, a danych jednej grupy nie odczyta nikt spoza niej.",
        ],
        "Żadna usługa internetowa nie może obiecać doskonałego bezpieczeństwa. Jeśli podejrzewasz, że ktoś inny uzyskał dostęp do Twojego konta, napisz do nas.",
      ],
    },
    {
      heading: "Dzieci",
      blocks: [
        "SplitDec nie jest przeznaczony dla dzieci poniżej 16. roku życia. Jeśli masz mniej niż 16 lat, nie zakładaj konta. Jeśli sądzisz, że dziecko przekazało nam dane osobowe, napisz do nas, a je usuniemy.",
      ],
    },
    {
      heading: "Zmiany polityki",
      blocks: [
        "Jeśli ta polityka się zmieni, zaktualizujemy datę na jej górze. Jeżeli zmiana istotnie Cię dotyczy, poinformujemy Cię w aplikacji lub e-mailem, zanim wejdzie w życie.",
      ],
    },
    {
      heading: "Kontakt",
      blocks: [
        `Pytania, żądania i skargi: ${MAILTO}.`,
        "Ta polityka jest publikowana po polsku i po angielsku. W razie rozbieżności rozstrzyga wersja polska.",
      ],
    },
  ],
};

const TERMS_EN: LegalDoc = {
  title: "Terms of Service",
  intro: [
    "These terms are the agreement between you and SplitDec. By creating an account or using the app you accept them. If you do not, please do not use SplitDec.",
    `SplitDec is operated by Tomasz Giela, a private individual based in Poland. Contact: ${MAILTO}.`,
  ],
  sections: [
    {
      heading: "What SplitDec is — and what it is not",
      blocks: [
        "SplitDec is a shared record of who paid what in a group, and a calculator that works out the smallest set of transfers that would even everybody up.",
        "**SplitDec does not move money.** It is not a bank, a payment service, an e-money issuer or an escrow. It never touches your card, your account or your balance. Every payment between you and the people you split with happens outside the app, exactly as it would without it.",
        "The balances the app shows are a convenience calculation from the figures you entered. They are not an invoice, an accounting record, a tax document or a legally binding statement of debt, and SplitDec does not give financial, accounting, tax or legal advice.",
      ],
    },
    {
      heading: "Your account",
      blocks: [
        [
          "You must be at least 16 years old to use SplitDec.",
          "Give an email address you actually control — it is how you sign in, recover access and receive invitations.",
          "Keep your password to yourself. You are responsible for what happens through your account; tell us promptly if you think someone else has got into it.",
          "One person, one account. Do not sign up on someone else's behalf.",
        ],
      ],
    },
    {
      heading: "What SplitDec costs",
      blocks: [
        "SplitDec is free to use. It has no ads and no paid tier.",
        "If a voluntary support option is offered (for example a “buy me a coffee” link), contributions are exactly that — voluntary. They buy no extra features, no guarantees and no priority, they are not refundable, and they are handled entirely by the payment provider under its own terms. We never receive your card details.",
      ],
    },
    {
      heading: "How you may use it",
      blocks: [
        "Use SplitDec for its purpose — splitting shared costs with people you know. You agree not to:",
        [
          "break the law with it, or use it to harass, defraud or threaten anyone;",
          "enter other people's personal data that you have no right to share, or invite addresses whose owners would not expect to hear from you — invitations are for people you actually split costs with, not a mailing list;",
          "try to reach data that is not yours, or to bypass the checks that keep groups separate;",
          "scan, probe, overload or otherwise interfere with the service or its infrastructure;",
          "scrape it, access it in bulk by automated means, or resell access to it.",
        ],
        "Invitation sending is rate-limited to keep the service off spam lists. Hitting a limit is not a fault; wait and try again.",
      ],
    },
    {
      heading: "Your content and the group",
      blocks: [
        "What you record stays yours. By adding it you allow us to store it and show it to the other members of the groups you put it in — that is what the app is for, and the only licence we ask for.",
        "Remember that everything you add to a group is visible to everyone in it, and that leaving a group does not erase the expenses other people's balances depend on.",
        "You are responsible for the accuracy of what you enter. We take care to compute splits exactly, down to the smallest unit of each currency, but the numbers are yours — check them before you settle. Disagreements about who owes what are between you and the other members: SplitDec keeps the record, it does not arbitrate.",
      ],
    },
    {
      heading: "Availability",
      blocks: [
        "SplitDec is provided as it is and as it is available. It is a free service, so there is no uptime guarantee, no support commitment and no service level agreement.",
        "We may change, suspend or withdraw features, and we may take the service offline for maintenance. Where a change matters to you, we will try to give notice in the app or by email.",
        "Keep your own record of anything you cannot afford to lose. Deleting an account or a group is permanent — see the [Privacy Policy](/privacy) for what is removed and what necessarily stays.",
      ],
    },
    {
      heading: "Ending it",
      blocks: [
        "You can stop using SplitDec at any time and delete your account from within the app, once you are settled up in every group.",
        "We may suspend or close an account that breaks these terms, puts other users at risk, or is used to abuse the service. Unless the law or the circumstances prevent it, we will tell you why and give you a chance to respond.",
      ],
    },
    {
      heading: "Our rights in the app",
      blocks: [
        "The SplitDec software, name, logo and design belong to its operator. These terms give you permission to use the service, not ownership of it, and do not allow you to copy, resell or reverse-engineer it beyond what the law expressly permits.",
      ],
    },
    {
      heading: "Liability",
      blocks: [
        "To the fullest extent the law allows, and given that SplitDec is provided free of charge, we are not liable for indirect or consequential loss, lost profit, lost data, or for financial disagreements between members of a group.",
        "Nothing here excludes or limits liability that cannot be excluded by law — including liability for intentional harm, for gross negligence, and for death or personal injury — or any rights you have as a consumer under mandatory Polish and EU law. Those rights come first and are unaffected by anything in these terms.",
      ],
    },
    {
      heading: "Changes to these terms",
      blocks: [
        "We will update the date at the top when these terms change, and tell you in the app or by email if a change materially affects you. Continuing to use SplitDec after a change takes effect means you accept the new version; if you would rather not, you can delete your account.",
      ],
    },
    {
      heading: "Law and disputes",
      blocks: [
        "These terms are governed by Polish law. If you are a consumer, this does not deprive you of the protections of the mandatory law of the country you live in.",
        `If something goes wrong, please write to ${MAILTO} first — nearly everything is easier to sort out that way than through a court.`,
        "These terms are published in English and Polish. If the two versions differ, the Polish version prevails.",
      ],
    },
  ],
};

const TERMS_PL: LegalDoc = {
  title: "Regulamin",
  intro: [
    "Ten regulamin to umowa między Tobą a SplitDec. Zakładając konto lub korzystając z aplikacji, akceptujesz go. Jeśli się z nim nie zgadzasz, nie korzystaj ze SplitDec.",
    `SplitDec prowadzi Tomasz Giela, osoba prywatna z Polski. Kontakt: ${MAILTO}.`,
  ],
  sections: [
    {
      heading: "Czym SplitDec jest, a czym nie jest",
      blocks: [
        "SplitDec to wspólny zapis tego, kto za co zapłacił w grupie, oraz kalkulator wyznaczający najmniejszy zestaw przelewów, który wyrówna rachunki między wszystkimi.",
        "**SplitDec nie przelewa pieniędzy.** Nie jest bankiem, usługą płatniczą, instytucją pieniądza elektronicznego ani depozytem. Nigdy nie dotyka Twojej karty, konta ani salda. Każda płatność między Tobą a osobami, z którymi dzielisz koszty, odbywa się poza aplikacją — dokładnie tak, jak odbywałaby się bez niej.",
        "Salda pokazywane przez aplikację to wynik wyliczenia z wprowadzonych przez Was danych. Nie są fakturą, dokumentem księgowym, dokumentem podatkowym ani wiążącym prawnie oświadczeniem o długu, a SplitDec nie udziela porad finansowych, księgowych, podatkowych ani prawnych.",
      ],
    },
    {
      heading: "Twoje konto",
      blocks: [
        [
          "Aby korzystać ze SplitDec, musisz mieć ukończone 16 lat.",
          "Podaj adres e-mail, do którego naprawdę masz dostęp — służy do logowania, odzyskiwania dostępu i odbierania zaproszeń.",
          "Zachowaj hasło dla siebie. Odpowiadasz za to, co dzieje się na Twoim koncie; napisz do nas niezwłocznie, jeśli podejrzewasz, że ktoś inny się na nie dostał.",
          "Jedna osoba, jedno konto. Nie zakładaj konta w cudzym imieniu.",
        ],
      ],
    },
    {
      heading: "Ile SplitDec kosztuje",
      blocks: [
        "Korzystanie ze SplitDec jest bezpłatne. Nie ma w nim reklam ani wersji płatnej.",
        "Jeśli udostępniona zostanie opcja dobrowolnego wsparcia (na przykład link „postaw kawę”), wpłaty są właśnie takie — dobrowolne. Nie dają dodatkowych funkcji, gwarancji ani pierwszeństwa, nie podlegają zwrotowi i są w całości obsługiwane przez dostawcę płatności na jego warunkach. Nigdy nie otrzymujemy danych Twojej karty.",
      ],
    },
    {
      heading: "Jak możesz korzystać z aplikacji",
      blocks: [
        "Korzystaj ze SplitDec zgodnie z jego przeznaczeniem — do dzielenia wspólnych kosztów ze znanymi Ci osobami. Zobowiązujesz się nie:",
        [
          "łamać przy jego użyciu prawa ani nękać, oszukiwać czy grozić komukolwiek;",
          "wprowadzać cudzych danych osobowych, do których udostępniania nie masz prawa, ani zapraszać adresów, których właściciele nie spodziewaliby się od Ciebie wiadomości — zaproszenia służą osobom, z którymi faktycznie dzielisz koszty, a nie do wysyłki masowej;",
          "próbować sięgać po dane, które nie należą do Ciebie, ani obchodzić zabezpieczeń oddzielających grupy;",
          "skanować, sondować, przeciążać ani w inny sposób zakłócać działania usługi lub jej infrastruktury;",
          "pobierać jej zawartości automatycznie, korzystać z niej masowo za pomocą botów ani odsprzedawać do niej dostępu.",
        ],
        "Wysyłka zaproszeń jest ograniczana liczbowo, aby usługa nie trafiła na listy spamerów. Osiągnięcie limitu nie jest błędem — odczekaj i spróbuj ponownie.",
      ],
    },
    {
      heading: "Twoje treści i grupa",
      blocks: [
        "To, co zapisujesz, pozostaje Twoje. Dodając treści, pozwalasz nam je przechowywać i pokazywać pozostałym członkom grup, do których je wprowadzasz — po to jest ta aplikacja i tylko o taką licencję prosimy.",
        "Pamiętaj, że wszystko, co dodasz do grupy, widzi każdy jej członek, a opuszczenie grupy nie usuwa wydatków, od których zależą salda innych osób.",
        "Odpowiadasz za poprawność wprowadzanych danych. Dokładamy starań, aby podziały liczyły się dokładnie, co do najmniejszej jednostki każdej waluty, ale liczby są Twoje — sprawdź je przed rozliczeniem. Spory o to, kto komu ile jest winien, pozostają między Tobą a pozostałymi członkami: SplitDec prowadzi zapis, nie rozstrzyga.",
      ],
    },
    {
      heading: "Dostępność",
      blocks: [
        "SplitDec udostępniamy w takim stanie, w jakim jest, i w miarę dostępności. To usługa bezpłatna, więc nie ma gwarancji dostępności, zobowiązania do wsparcia ani umowy o poziomie usług.",
        "Możemy zmieniać, zawieszać i wycofywać funkcje oraz wyłączać usługę na czas prac serwisowych. Gdy zmiana będzie dla Ciebie istotna, postaramy się uprzedzić w aplikacji lub e-mailem.",
        "Zachowaj własny zapis wszystkiego, czego nie możesz stracić. Usunięcie konta lub grupy jest trwałe — w [Polityce prywatności](/privacy) opisujemy, co znika, a co musi zostać.",
      ],
    },
    {
      heading: "Zakończenie korzystania",
      blocks: [
        "Możesz przestać korzystać ze SplitDec w każdej chwili i usunąć konto z poziomu aplikacji, gdy jesteś rozliczony(-a) w każdej grupie.",
        "Możemy zawiesić lub zamknąć konto, które narusza ten regulamin, naraża innych użytkowników albo służy do nadużyć. Jeśli prawo ani okoliczności tego nie uniemożliwią, wyjaśnimy powód i damy Ci możliwość odniesienia się.",
      ],
    },
    {
      heading: "Nasze prawa do aplikacji",
      blocks: [
        "Oprogramowanie SplitDec, jego nazwa, logo i projekt graficzny należą do jego operatora. Ten regulamin daje Ci prawo do korzystania z usługi, a nie własność do niej, i nie pozwala jej kopiować, odsprzedawać ani poddawać inżynierii wstecznej poza zakresem wyraźnie dozwolonym przez prawo.",
      ],
    },
    {
      heading: "Odpowiedzialność",
      blocks: [
        "W najszerszym zakresie dozwolonym przez prawo i biorąc pod uwagę, że SplitDec jest udostępniany nieodpłatnie, nie odpowiadamy za szkody pośrednie i następcze, utracone korzyści, utratę danych ani za finansowe nieporozumienia między członkami grupy.",
        "Nic w tym regulaminie nie wyłącza ani nie ogranicza odpowiedzialności, której nie można wyłączyć na mocy prawa — w tym za winę umyślną, rażące niedbalstwo oraz śmierć lub uszczerbek na zdrowiu — ani praw przysługujących Ci jako konsumentowi na podstawie bezwzględnie obowiązujących przepisów polskich i unijnych. Te prawa mają pierwszeństwo i pozostają nienaruszone.",
      ],
    },
    {
      heading: "Zmiany regulaminu",
      blocks: [
        "Przy zmianie regulaminu zaktualizujemy datę na jego górze, a jeśli zmiana istotnie Cię dotyczy, poinformujemy Cię w aplikacji lub e-mailem. Dalsze korzystanie ze SplitDec po wejściu zmiany w życie oznacza akceptację nowej wersji; jeśli wolisz tego nie robić, możesz usunąć konto.",
      ],
    },
    {
      heading: "Prawo i spory",
      blocks: [
        "Regulamin podlega prawu polskiemu. Jeżeli jesteś konsumentem, nie pozbawia Cię to ochrony wynikającej z bezwzględnie obowiązujących przepisów kraju, w którym mieszkasz.",
        `Jeśli coś pójdzie nie tak, napisz najpierw na ${MAILTO} — prawie wszystko łatwiej rozwiązać w ten sposób niż przed sądem.`,
        "Regulamin jest publikowany po polsku i po angielsku. W razie rozbieżności rozstrzyga wersja polska.",
      ],
    },
  ],
};

export const LEGAL_DOCS: Record<LegalDocId, Record<Lang, LegalDoc>> = {
  privacy: { en: PRIVACY_EN, pl: PRIVACY_PL },
  terms: { en: TERMS_EN, pl: TERMS_PL },
};
