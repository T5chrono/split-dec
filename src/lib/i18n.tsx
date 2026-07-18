import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { setMoneyLocale } from "./currency";

export type Lang = "en" | "pl";

const STORAGE_KEY = "splitdec.lang";

const dict = {
  en: {
    // common
    loading: "Loading…",
    cancel: "Cancel",
    delete: "Delete",
    edit: "Edit",
    saving: "Saving…",
    saveChanges: "Save changes",
    you: "You",
    formerMember: "Former member",
    unnamedUser: "Unnamed user",
    // login
    tagline: "Split expenses with friends, minus the spreadsheets.",
    continueWithGoogle: "Continue with Google",
    orDivider: "or",
    email: "Email",
    password: "Password",
    fullName: "Full name",
    signUp: "Sign up",
    createAccount: "Create account",
    signingIn: "Signing in…",
    noAccountYet: "New to SplitDec?",
    alreadyHaveAccount: "Already have an account?",
    forgotPassword: "Forgot password?",
    sendResetLink: "Send reset link",
    sendingResetLink: "Sending…",
    signInWithEmail: "Sign in with email",
    checkEmailTitle: "Check your email",
    checkEmailSignupBody:
      "If {email} can be registered, we've sent it a confirmation link. Click it to activate your account.",
    checkEmailResetBody:
      "If an account exists for {email}, a password reset link is on its way.",
    backToSignIn: "Back to sign in",
    resetPasswordTitle: "Reset your password",
    newPassword: "New password",
    confirmPassword: "Confirm password",
    setNewPassword: "Set new password",
    updatingPassword: "Saving…",
    passwordUpdated: "Password updated — you're signed in.",
    resetLinkInvalid:
      "This link is invalid or has expired. Request a new one from the sign-in screen.",
    signOutRecovery: "Not you? Sign out",
    errInvalidCredentials: "Incorrect email or password.",
    errEmailNotConfirmed: "Confirm your email first — check your inbox for the link.",
    errEmailExists: "An account with this email already exists.",
    errWeakPassword: "Password must be at least 8 characters.",
    errSamePassword: "The new password must be different from the old one.",
    errEmailRateLimit: "Too many emails sent — try again in a few minutes.",
    errInvalidEmail: "Enter a valid email address.",
    errPasswordMismatch: "Passwords don't match.",
    errOtpExpired: "That link has expired — sign in or request a new one.",
    errAuthGeneric: "Something went wrong. Please try again.",
    // landing
    signIn: "Sign in",
    landingHeadline1: "Split expenses,",
    landingHeadline2: "not friendships.",
    landingSub:
      "Track who paid what — on trips, with flatmates, at dinner — in any currency, and settle the whole group in the fewest transfers possible.",
    landingSeeHow: "See how it works",
    landingTrust: "Free · No ads · Installs like an app",
    landingFeaturesKicker: "Why SplitDec",
    landingFeaturesTitle: "Built for how groups actually spend",
    featGroupsTitle: "Groups for everything",
    featGroupsBody:
      "Trips, flatmates, couples — a 1-on-1 is just a two-person group. Invite people by email and start adding expenses.",
    featCurrencyTitle: "Any currency, exact math",
    featCurrencyBody:
      "From złoty to yen: every split is computed at the currency's real precision and always adds up to the total — to the last grosz.",
    featSimplifyTitle: "Fewest possible transfers",
    featSimplifyBody:
      "Balances are simplified so the whole group settles up in a handful of payments instead of a tangle of IOUs.",
    featSplitTitle: "Split your way",
    featSplitBody:
      "Equally, by exact amounts or by percentages — with the rounding handled for you, fairly.",
    featPwaTitle: "An app when you want one",
    featPwaBody:
      "Install SplitDec on your phone or desktop straight from the browser — no app store required.",
    featPrivateTitle: "Private by design",
    featPrivateBody:
      "Groups are invitation-only and your data stays yours: no ads, no tracking, no selling.",
    landingHowKicker: "How it works",
    landingHowTitle: "Settled up in three steps",
    landingStep1Title: "Create a group",
    landingStep1Body:
      "Name it after the trip, the flat or the friend group, and invite people by email.",
    landingStep2Title: "Add expenses",
    landingStep2Body:
      "Whoever pays logs it in seconds — pick a category, a currency and how to split it.",
    landingStep3Title: "Settle up",
    landingStep3Body:
      "SplitDec shows who pays whom. Record the payment and everyone is even again.",
    landingCtaTitle: "Ready to ditch the spreadsheet?",
    landingCtaBody: "Sign in and settle your first group tonight.",
    landingFooterTag: "Split fairly. Stay friends.",
    demoExpenseCable: "Cable car tickets",
    demoExpenseHotel: "Mountain hostel, 2 nights",
    demoExpenseGroceries: "Groceries",
    demoToast: "Settled up!",
    // header / account
    signOut: "Sign out",
    account: "Account",
    signedInAs: "Signed in as",
    language: "Language",
    theme: "Theme",
    darkMode: "Dark mode",
    lightMode: "Light mode",
    dangerZone: "Danger zone",
    deleteAccount: "Delete account",
    deleteAccountTitle: "Delete your account?",
    deleteAccountWarning:
      "This permanently removes your sign-in and personal data. Your past expenses stay visible to your groups as “Deleted user”. You must be fully settled up in every group first. This cannot be undone.",
    deleteAccountConfirm: "Yes, delete my account",
    deletingAccount: "Deleting…",
    // groups
    yourGroups: "Your groups",
    newGroup: "New group",
    loadingGroups: "Loading groups…",
    noGroups:
      "No groups yet. Create one to start splitting expenses — a 1-on-1 is just a 2-person group.",
    createdOn: "Created",
    createGroup: "Create group",
    creating: "Creating…",
    groupNamePlaceholder: "Trip to Zakopane",
    // group page tabs
    tabExpenses: "Expenses",
    tabBalances: "Balances",
    tabSettlements: "Settlements",
    tabMembers: "Members",
    // expenses
    addExpense: "Add expense",
    editExpense: "Edit expense",
    loadingExpenses: "Loading expenses…",
    noExpenses: "No expenses yet. Add the first one!",
    paidVerb: "paid",
    newer: "Newer",
    older: "Older",
    deleteExpenseTitle: "Delete this expense?",
    deleteExpenseMsg:
      "It will be removed from the group's balances. This can't be undone from the app.",
    description: "Description",
    descriptionPlaceholder: "Dinner at Nolio",
    date: "Date",
    today: "Today",
    prevMonth: "Previous month",
    nextMonth: "Next month",
    amount: "Amount",
    currency: "Currency",
    category: "Category",
    paidBy: "Paid by",
    split: "Split",
    splitEqually: "Equally",
    splitExact: "Exact amounts",
    splitPercent: "Percentages",
    sumOfAmounts: "Sum of amounts",
    mustEqual: "must equal",
    theTotal: "the total",
    sumOfPercentages: "Sum of percentages",
    mustBe100: "must be 100",
    // balances
    computingBalances: "Computing balances…",
    allSettled: "All settled up — nobody owes anything.",
    settle: "Settle",
    balancesNote:
      "Suggested payments fully settle the group in as few transfers as we can find.",
    // settlements
    settleUp: "Settle up",
    editSettlement: "Edit settlement",
    recordPayment: "Record payment",
    loadingSettlements: "Loading settlements…",
    noPayments: "No payments recorded yet.",
    whoPaid: "Who paid",
    whoReceived: "Who received",
    samePersonWarning: "Payer and receiver must be different people.",
    deleteSettlementTitle: "Delete this payment?",
    deleteSettlementMsg: "The group's balances will be recalculated without it.",
    // members
    inviteByEmail: "Invite by email",
    find: "Find",
    add: "Add",
    removeMemberTitle: "Remove this member?",
    removeMemberMsg:
      "They can only be removed if they are fully settled up in this group.",
    removeMemberTip: "Remove from group (must be fully settled)",
    searchFailed: "Search failed",
    invite: "Invite",
    invitationSentInApp: "Invitation sent — they can accept it next time they open SplitDec.",
    invitationEmailSent: "Invitation email sent.",
    inviteeNotOnSplitDec:
      "This person isn't on SplitDec yet. The invitation is saved and will greet them when they sign up with this email — you can also invite them yourself:",
    openEmailDraft: "Open email draft",
    pendingInvitations: "Pending invitations",
    cancelInvitation: "Cancel invitation",
    invitedYouTo: "invited you to",
    accept: "Accept",
    decline: "Decline",
    inviteEmailSubject: "You're invited to SplitDec",
    inviteEmailBody:
      'I\'d like to split expenses with you in the group "{group}" on SplitDec. Sign in using this email address and the invitation will be waiting for you.',
    deleteExpense: "Delete expense",
    renameGroup: "Rename group",
    save: "Save",
    youOwe: "you pay",
    owedToYou: "you receive",
    deleteGroup: "Delete group",
    deleteGroupHint:
      "Permanently deletes this group and its expenses and settlements for everyone. Only possible when the group is fully settled.",
    deleteGroupTitle: "Delete this group?",
    deleteGroupMsg:
      "This permanently removes the group and all its expenses and settlements for every member. It can only be done when everyone is settled up, and it cannot be undone.",
  },
  pl: {
    loading: "Wczytywanie…",
    cancel: "Anuluj",
    delete: "Usuń",
    edit: "Edytuj",
    saving: "Zapisywanie…",
    saveChanges: "Zapisz zmiany",
    you: "Ty",
    formerMember: "Były członek",
    unnamedUser: "Użytkownik bez nazwy",
    tagline: "Dziel wydatki ze znajomymi — bez arkuszy kalkulacyjnych.",
    continueWithGoogle: "Kontynuuj z Google",
    orDivider: "albo",
    email: "E-mail",
    password: "Hasło",
    fullName: "Imię i nazwisko",
    signUp: "Zarejestruj się",
    createAccount: "Utwórz konto",
    signingIn: "Logowanie…",
    noAccountYet: "Nie masz jeszcze konta?",
    alreadyHaveAccount: "Masz już konto?",
    forgotPassword: "Nie pamiętasz hasła?",
    sendResetLink: "Wyślij link resetujący",
    sendingResetLink: "Wysyłanie…",
    signInWithEmail: "Zaloguj się e-mailem",
    checkEmailTitle: "Sprawdź swoją skrzynkę",
    checkEmailSignupBody:
      "Jeśli adres {email} może zostać zarejestrowany, wysłaliśmy na niego link potwierdzający. Kliknij go, aby aktywować konto.",
    checkEmailResetBody:
      "Jeśli istnieje konto dla adresu {email}, link do zresetowania hasła jest w drodze.",
    backToSignIn: "Wróć do logowania",
    resetPasswordTitle: "Zresetuj hasło",
    newPassword: "Nowe hasło",
    confirmPassword: "Potwierdź hasło",
    setNewPassword: "Ustaw nowe hasło",
    updatingPassword: "Zapisywanie…",
    passwordUpdated: "Hasło zmienione — jesteś zalogowany(-a).",
    resetLinkInvalid:
      "Ten link jest nieprawidłowy lub wygasł. Poproś o nowy na ekranie logowania.",
    signOutRecovery: "To nie Ty? Wyloguj się",
    errInvalidCredentials: "Nieprawidłowy e-mail lub hasło.",
    errEmailNotConfirmed: "Najpierw potwierdź swój e-mail — poszukaj linku w skrzynce.",
    errEmailExists: "Konto z tym adresem e-mail już istnieje.",
    errWeakPassword: "Hasło musi mieć co najmniej 8 znaków.",
    errSamePassword: "Nowe hasło musi się różnić od poprzedniego.",
    errEmailRateLimit: "Wysłano zbyt wiele e-maili — spróbuj ponownie za kilka minut.",
    errInvalidEmail: "Podaj poprawny adres e-mail.",
    errPasswordMismatch: "Hasła nie są takie same.",
    errOtpExpired: "Ten link wygasł — zaloguj się lub poproś o nowy.",
    errAuthGeneric: "Coś poszło nie tak. Spróbuj ponownie.",
    signIn: "Zaloguj się",
    landingHeadline1: "Dziel wydatki,",
    landingHeadline2: "nie przyjaźnie.",
    landingSub:
      "Śledź, kto za co zapłacił — na wyjazdach, we wspólnym mieszkaniu, przy kolacji — w dowolnej walucie, i rozlicz całą grupę w jak najmniejszej liczbie przelewów.",
    landingSeeHow: "Zobacz, jak to działa",
    landingTrust: "Za darmo · Bez reklam · Instaluje się jak aplikacja",
    landingFeaturesKicker: "Dlaczego SplitDec",
    landingFeaturesTitle: "Stworzony do tego, jak grupy naprawdę wydają",
    featGroupsTitle: "Grupy na wszystko",
    featGroupsBody:
      "Wyjazdy, współlokatorzy, pary — rozliczenie 1 na 1 to po prostu grupa dwuosobowa. Zaproś przez e-mail i dodawaj wydatki.",
    featCurrencyTitle: "Każda waluta, dokładna matematyka",
    featCurrencyBody:
      "Od złotego po jena: każdy podział jest liczony z dokładnością danej waluty i zawsze sumuje się do całości — co do grosza.",
    featSimplifyTitle: "Jak najmniej przelewów",
    featSimplifyBody:
      "Salda są upraszczane tak, aby cała grupa rozliczyła się kilkoma płatnościami zamiast plątaniną długów.",
    featSplitTitle: "Dziel po swojemu",
    featSplitBody:
      "Po równo, dokładnymi kwotami albo procentami — zaokrągleniami zajmiemy się za Ciebie, uczciwie.",
    featPwaTitle: "Aplikacja, gdy jej chcesz",
    featPwaBody:
      "Zainstaluj SplitDec na telefonie lub komputerze prosto z przeglądarki — bez sklepu z aplikacjami.",
    featPrivateTitle: "Prywatność w standardzie",
    featPrivateBody:
      "Grupy działają wyłącznie na zaproszenia, a Twoje dane pozostają Twoje: bez reklam, bez śledzenia, bez sprzedawania.",
    landingHowKicker: "Jak to działa",
    landingHowTitle: "Rozliczeni w trzech krokach",
    landingStep1Title: "Utwórz grupę",
    landingStep1Body:
      "Nazwij ją od wyjazdu, mieszkania albo paczki znajomych i zaproś ludzi przez e-mail.",
    landingStep2Title: "Dodawaj wydatki",
    landingStep2Body:
      "Kto płaci, ten zapisuje — w kilka sekund wybierz kategorię, walutę i sposób podziału.",
    landingStep3Title: "Rozliczcie się",
    landingStep3Body:
      "SplitDec pokazuje, kto komu płaci. Zarejestruj płatność i wszyscy znów są kwita.",
    landingCtaTitle: "Gotowi porzucić arkusz kalkulacyjny?",
    landingCtaBody: "Zaloguj się i rozlicz pierwszą grupę jeszcze dziś.",
    landingFooterTag: "Dzielcie uczciwie. Zostańcie przyjaciółmi.",
    demoExpenseCable: "Bilety na kolejkę",
    demoExpenseHotel: "Schronisko, 2 noce",
    demoExpenseGroceries: "Zakupy spożywcze",
    demoToast: "Rozliczone!",
    signOut: "Wyloguj się",
    account: "Konto",
    signedInAs: "Zalogowano jako",
    language: "Język",
    theme: "Motyw",
    darkMode: "Tryb ciemny",
    lightMode: "Tryb jasny",
    dangerZone: "Strefa zagrożenia",
    deleteAccount: "Usuń konto",
    deleteAccountTitle: "Usunąć Twoje konto?",
    deleteAccountWarning:
      "To trwale usunie Twoje logowanie i dane osobowe. Twoje wydatki pozostaną widoczne w grupach jako „Usunięty użytkownik”. Najpierw musisz być w pełni rozliczony w każdej grupie. Tej operacji nie można cofnąć.",
    deleteAccountConfirm: "Tak, usuń moje konto",
    deletingAccount: "Usuwanie…",
    yourGroups: "Twoje grupy",
    newGroup: "Nowa grupa",
    loadingGroups: "Wczytywanie grup…",
    noGroups:
      "Nie masz jeszcze grup. Utwórz jedną, aby dzielić wydatki — rozliczenie 1 na 1 to po prostu grupa 2-osobowa.",
    createdOn: "Utworzono",
    createGroup: "Utwórz grupę",
    creating: "Tworzenie…",
    groupNamePlaceholder: "Wyjazd do Zakopanego",
    tabExpenses: "Wydatki",
    tabBalances: "Salda",
    tabSettlements: "Rozliczenia",
    tabMembers: "Członkowie",
    addExpense: "Dodaj wydatek",
    editExpense: "Edytuj wydatek",
    loadingExpenses: "Wczytywanie wydatków…",
    noExpenses: "Brak wydatków. Dodaj pierwszy!",
    paidVerb: "zapłacił(a)",
    newer: "Nowsze",
    older: "Starsze",
    deleteExpenseTitle: "Usunąć ten wydatek?",
    deleteExpenseMsg:
      "Zostanie usunięty z sald grupy. Nie można tego cofnąć z poziomu aplikacji.",
    description: "Opis",
    descriptionPlaceholder: "Kolacja w Nolio",
    date: "Data",
    today: "Dziś",
    prevMonth: "Poprzedni miesiąc",
    nextMonth: "Następny miesiąc",
    amount: "Kwota",
    currency: "Waluta",
    category: "Kategoria",
    paidBy: "Zapłacone przez",
    split: "Podział",
    splitEqually: "Po równo",
    splitExact: "Dokładne kwoty",
    splitPercent: "Procenty",
    sumOfAmounts: "Suma kwot",
    mustEqual: "musi być równa",
    theTotal: "sumie",
    sumOfPercentages: "Suma procentów",
    mustBe100: "musi wynosić 100",
    computingBalances: "Obliczanie sald…",
    allSettled: "Wszystko rozliczone — nikt nikomu nic nie jest winien.",
    settle: "Rozlicz",
    balancesNote:
      "Sugerowane płatności w pełni rozliczają grupę w możliwie najmniejszej znalezionej liczbie przelewów.",
    settleUp: "Rozlicz się",
    editSettlement: "Edytuj rozliczenie",
    recordPayment: "Zarejestruj płatność",
    loadingSettlements: "Wczytywanie rozliczeń…",
    noPayments: "Brak zarejestrowanych płatności.",
    whoPaid: "Kto zapłacił",
    whoReceived: "Kto otrzymał",
    samePersonWarning: "Płacący i odbiorca muszą być różnymi osobami.",
    deleteSettlementTitle: "Usunąć tę płatność?",
    deleteSettlementMsg: "Salda grupy zostaną przeliczone bez niej.",
    inviteByEmail: "Zaproś przez e-mail",
    find: "Szukaj",
    add: "Dodaj",
    removeMemberTitle: "Usunąć tego członka?",
    removeMemberMsg:
      "Można go usunąć tylko wtedy, gdy jest w pełni rozliczony w tej grupie.",
    removeMemberTip: "Usuń z grupy (wymaga pełnego rozliczenia)",
    searchFailed: "Wyszukiwanie nie powiodło się",
    invite: "Zaproś",
    invitationSentInApp:
      "Zaproszenie wysłane — będzie można je zaakceptować przy następnym otwarciu SplitDec.",
    invitationEmailSent: "E-mail z zaproszeniem został wysłany.",
    inviteeNotOnSplitDec:
      "Ta osoba nie korzysta jeszcze ze SplitDec. Zaproszenie zostało zapisane i pojawi się po rejestracji na ten adres — możesz też zaprosić ją samodzielnie:",
    openEmailDraft: "Otwórz szkic e-maila",
    pendingInvitations: "Oczekujące zaproszenia",
    cancelInvitation: "Anuluj zaproszenie",
    invitedYouTo: "zaprasza Cię do grupy",
    accept: "Akceptuj",
    decline: "Odrzuć",
    inviteEmailSubject: "Zaproszenie do SplitDec",
    inviteEmailBody:
      "Chcę dzielić z Tobą wydatki w grupie „{group}” w SplitDec. Zaloguj się, używając tego adresu e-mail, a zaproszenie będzie na Ciebie czekać.",
    deleteExpense: "Usuń wydatek",
    renameGroup: "Zmień nazwę grupy",
    save: "Zapisz",
    youOwe: "płacisz",
    owedToYou: "otrzymujesz",
    deleteGroup: "Usuń grupę",
    deleteGroupHint:
      "Trwale usuwa tę grupę wraz z jej wydatkami i rozliczeniami dla wszystkich. Możliwe tylko, gdy grupa jest w pełni rozliczona.",
    deleteGroupTitle: "Usunąć tę grupę?",
    deleteGroupMsg:
      "To trwale usunie grupę oraz wszystkie jej wydatki i rozliczenia dla każdego członka. Można to zrobić tylko, gdy wszyscy są rozliczeni. Tej operacji nie można cofnąć.",
  },
} as const;

export type TKey = keyof (typeof dict)["en"];

const CATEGORY_PL: Record<string, string> = {
  Games: "Gry",
  Movies: "Filmy",
  Music: "Muzyka",
  Sports: "Sport",
  "Other Entertainment": "Inna rozrywka",
  Climbing: "Wspinaczka",
  Skiing: "Narciarstwo",
  Swimming: "Pływanie",
  Running: "Bieganie",
  Biking: "Jazda na rowerze",
  "Other Sports": "Inne sporty",
  "Dining out": "Jedzenie na mieście",
  Groceries: "Zakupy spożywcze",
  Liquor: "Alkohol",
  "Other Food and drink": "Inne jedzenie i napoje",
  Electronics: "Elektronika",
  Furniture: "Meble",
  "Household supplies": "Artykuły domowe",
  Maintenance: "Konserwacja",
  Mortgage: "Kredyt hipoteczny",
  Pets: "Zwierzęta",
  Rent: "Czynsz",
  Services: "Usługi",
  "Other Home": "Inne domowe",
  Childcare: "Opieka nad dziećmi",
  Clothing: "Odzież",
  Education: "Edukacja",
  Gifts: "Prezenty",
  Insurance: "Ubezpieczenie",
  "Medical expenses": "Wydatki medyczne",
  Taxes: "Podatki",
  "Other Life": "Inne życiowe",
  Bicycle: "Rower",
  "Bus/train": "Autobus/pociąg",
  Car: "Samochód",
  "Gas/fuel": "Paliwo",
  Hotel: "Hotel",
  Parking: "Parking",
  Plane: "Samolot",
  Taxi: "Taksówka",
  "Other Transportation": "Inny transport",
  Cleaning: "Sprzątanie",
  Electricity: "Prąd",
  "Heat/gas": "Ogrzewanie/gaz",
  Trash: "Śmieci",
  "TV/Phone/Internet": "TV/Telefon/Internet",
  Water: "Woda",
  "Other Utilities": "Inne media",
  Software: "Oprogramowanie",
  Streaming: "Streaming",
  Memberships: "Członkostwa",
  "Other Subscriptions": "Inne subskrypcje",
  Tutor: "Korepetycje",
  Courses: "Kursy",
  Books: "Książki",
  "Other Learning": "Inna nauka",
  "LLM APIs": "API modeli LLM",
  Copilots: "Copiloty",
  "Generation Tools": "Narzędzia generatywne",
  "Other AI Expenses": "Inne wydatki AI",
  General: "Ogólne",
};

const CATEGORY_GROUP_PL: Record<string, string> = {
  Entertainment: "Rozrywka",
  Sports: "Sport",
  "Food and drink": "Jedzenie i napoje",
  Home: "Dom",
  Life: "Życie",
  Transportation: "Transport",
  Utilities: "Media",
  Subscriptions: "Subskrypcje",
  Learning: "Nauka",
  "AI Expenses": "Wydatki AI",
  Uncategorized: "Bez kategorii",
};

interface I18n {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: TKey) => string;
  /** Backend category value -> localized label. */
  tCategory: (value: string) => string;
  tCategoryGroup: (group: string) => string;
  dateLocale: string;
  membersLabel: (n: number) => string;
}

const I18nContext = createContext<I18n | null>(null);

function detectLang(): Lang {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "en" || stored === "pl") return stored;
  return navigator.language?.toLowerCase().startsWith("pl") ? "pl" : "en";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(detectLang);

  // Set during render, not in an effect: consumers re-rendering on a language
  // switch call formatMoney immediately, and an effect would leave that first
  // render with the previous decimal separator. Idempotent module state.
  setMoneyLocale(lang);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    localStorage.setItem(STORAGE_KEY, l);
    setLangState(l);
  }, []);

  const t = useCallback((key: TKey) => dict[lang][key], [lang]);
  const tCategory = useCallback(
    (value: string) => (lang === "pl" ? (CATEGORY_PL[value] ?? value) : value),
    [lang],
  );
  const tCategoryGroup = useCallback(
    (group: string) => (lang === "pl" ? (CATEGORY_GROUP_PL[group] ?? group) : group),
    [lang],
  );
  const membersLabel = useCallback(
    (n: number) => {
      if (lang === "pl") {
        if (n === 1) return "1 członek";
        const mod10 = n % 10;
        const mod100 = n % 100;
        if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14))
          return `${n} członków`; // genitive reads naturally for group sizes
        return `${n} członków`;
      }
      return n === 1 ? "1 member" : `${n} members`;
    },
    [lang],
  );

  return (
    <I18nContext.Provider
      value={{
        lang,
        setLang,
        t,
        tCategory,
        tCategoryGroup,
        dateLocale: lang === "pl" ? "pl-PL" : "en-US",
        membersLabel,
      }}
    >
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n(): I18n {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside I18nProvider");
  return ctx;
}
