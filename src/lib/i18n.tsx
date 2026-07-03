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
  },
} as const;

export type TKey = keyof (typeof dict)["en"];

const CATEGORY_PL: Record<string, string> = {
  Games: "Gry",
  Movies: "Filmy",
  Music: "Muzyka",
  Sports: "Sport",
  "Other Entertainment": "Inna rozrywka",
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

  useEffect(() => {
    setMoneyLocale(lang);
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
