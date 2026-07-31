/** Best-effort category guessing from an expense description.
 *
 *  Deliberately dumb: a keyword table, no model, no network. It exists to save
 *  a click in the common case ("Parking" → Parking), not to be right every
 *  time — the user can always override, and doing so stops the guessing
 *  (see `ExpenseFormModal`).
 *
 *  Both languages live in one table rather than being keyed by the UI
 *  language: people mix them ("Uber do hotelu"), and a Polish speaker running
 *  the app in English still writes Polish descriptions.
 */

/** Stems, not words: matching is `token.startsWith(stem)`, so "park" covers
 *  parking/parkingu/parkowanie and "hipotek" covers hipoteka/hipoteczny.
 *  Stems under 4 characters must match a whole token (see MIN_PREFIX_LEN) —
 *  that is what keeps "bus" off "business" and makes "tv" and the Polish
 *  insurance "OC" safe to list. Short words that do inflect ("tax" → "taxes")
 *  carry the inflected form as a second stem. */
const KEYWORDS: ReadonlyArray<readonly [category: string, stems: readonly string[]]> = [
  // Transportation
  ["Parking", ["park", "parkomat"]],
  ["Gas/fuel", ["fuel", "petrol", "diesel", "gas", "paliw", "benzyn", "tankow", "lpg"]],
  ["Taxi", ["taxi", "taks", "uber", "bolt", "lyft"]],
  ["Plane", ["plane", "flight", "airline", "airfare", "samolot", "lotnisk"]],
  ["Bus/train", ["bus", "train", "tram", "metro", "pkp", "autobus", "pociag", "kolej"]],
  ["Car", ["car", "cars", "auto", "samochod", "tire", "opon", "myjnia"]],
  ["Hotel", ["hotel", "hostel", "motel", "airbnb", "nocleg", "booking", "pensjonat"]],
  ["Bicycle", ["bike", "bicycle", "rower"]],

  // Food and drink
  [
    "Dining out",
    [
      "restaurant", "restaurac", "dinner", "lunch", "breakfast", "obiad", "kolacja",
      "sniadan", "pizza", "sushi", "burger", "kebab", "bar", "pub", "cafe", "kawiarni",
      "mcdonald", "kfc", "bistro", "jedzenie",
    ],
  ],
  [
    "Groceries",
    [
      // "biedron", not "biedronk": Polish declension mutates the k
      // ("w Biedronce"), so the stem has to stop before it.
      "grocer", "supermarket", "spozyw", "zakup", "biedron", "lidl", "zabk", "auchan",
      "carrefour", "kaufland", "tesco", "aldi", "warzyw",
    ],
  ],
  ["Liquor", ["beer", "wine", "vodka", "whisky", "liquor", "alkohol", "piwo", "wino", "wodka"]],
  ["Other Food and drink", ["coffee", "kawa", "snack", "przekask", "lody", "dessert", "deser"]],

  // Entertainment
  ["Movies", ["movie", "cinema", "kino", "kina", "film"]],
  ["Games", ["game", "gaming", "gra", "gry", "konsol", "playstation", "xbox", "steam", "nintendo"]],
  ["Music", ["concert", "koncert", "music", "muzyk", "festival", "festiwal"]],

  // Sports
  ["Skiing", ["ski", "skiing", "skipass", "narty", "narciar", "snowboard", "wyciag"]],
  ["Climbing", ["climb", "wspinacz", "scianka", "boulder"]],
  ["Swimming", ["swim", "basen", "plywa"]],
  ["Running", ["bieg", "marathon", "maraton"]],
  ["Other Sports", ["gym", "silown", "fitness", "yoga", "joga", "tennis", "tenis", "squash"]],

  // Home
  ["Rent", ["rent", "czynsz", "najem", "wynajem"]],
  ["Mortgage", ["mortgage", "hipotek", "kredyt"]],
  ["Maintenance", ["repair", "naprawa", "remont", "hydraulik", "plumber", "mechanik", "malowan"]],
  ["Furniture", ["furniture", "mebl", "sofa", "kanapa", "krzesl", "lozko", "szafa", "ikea"]],
  [
    "Electronics",
    ["laptop", "komputer", "computer", "monitor", "tablet", "elektronik", "electronic", "sluchawki"],
  ],
  ["Household supplies", ["detergent", "chemia", "proszek", "supplies"]],
  ["Pets", ["pet", "pets", "dog", "dogs", "cat", "cats", "pies", "psa", "kot", "vet", "weterynar", "karma"]],
  ["Services", ["service", "uslug"]],

  // Utilities
  ["Electricity", ["electric", "prad", "energia", "tauron", "enea", "pge"]],
  ["Water", ["water", "woda", "wodociag"]],
  ["Heat/gas", ["heating", "ogrzewan", "cieplo", "gaz"]],
  ["Trash", ["trash", "garbage", "smieci", "odpady"]],
  [
    "TV/Phone/Internet",
    ["internet", "wifi", "phone", "telefon", "komork", "netia", "swiatlowod", "tv"],
  ],
  ["Cleaning", ["clean", "sprzat", "pralnia", "laundry"]],

  // Life
  [
    "Medical expenses",
    ["doctor", "lekarz", "apteka", "pharmacy", "medic", "dentyst", "dentist", "szpital",
      "hospital", "leki", "recept"],
  ],
  ["Childcare", ["childcare", "babysit", "przedszkol", "zlobek", "opiekunka", "niania"]],
  ["Clothing", ["clothes", "clothing", "ubran", "odziez", "buty", "shoes", "koszul", "kurtka"]],
  ["Education", ["school", "szkol", "studia", "czesne", "tuition"]],
  ["Gifts", ["gift", "prezent", "upominek"]],
  ["Insurance", ["insurance", "ubezpiecz", "polisa", "oc", "ac"]],
  ["Taxes", ["tax", "taxes", "podat", "skarbow"]],

  // Subscriptions
  ["Streaming", ["netflix", "spotify", "hbo", "disney", "youtube", "streaming"]],
  // No "office" or "github": both lead descriptions that mean something else
  // ("Office supplies", "GitHub Copilot"), and "microsoft" already covers the
  // Office subscription.
  ["Software", ["software", "licenc", "adobe", "microsoft", "jetbrains"]],
  ["Memberships", ["membership", "karnet", "czlonkost"]],
  ["Other Subscriptions", ["subscription", "subskrypc", "abonament"]],

  // Learning
  ["Books", ["book", "ksiazk", "ebook", "audiobook", "podrecznik"]],
  ["Courses", ["course", "kurs", "szkolenie", "bootcamp", "warsztat"]],
  ["Tutor", ["tutor", "korepetycj", "lekcj"]],

  // AI Expenses
  [
    "LLM APIs",
    ["openai", "anthropic", "claude", "gpt", "chatgpt", "llm", "gemini", "mistral", "deepseek"],
  ],
  ["Copilots", ["copilot", "cursor"]],
  ["Generation Tools", ["midjourney", "dalle", "sora", "runway", "veo", "elevenlabs"]],
];

/** Every category this module can return. Exported so a test can assert the
 *  table only names categories that actually exist in `CATEGORY_GROUPS` — a
 *  typo here would otherwise select a category the picker cannot display. */
export const GUESSABLE_CATEGORIES: readonly string[] = KEYWORDS.map(([category]) => category);

/** Below this length a stem must match the whole token. Three-letter prefixes
 *  are mostly noise: "bus" fires on "business", "car" on "carpet". */
const MIN_PREFIX_LEN = 4;

/** Lowercase, strip diacritics, split into word tokens. Stripping diacritics
 *  is what lets "smieci" match a description typed as "śmieci" and vice
 *  versa — Polish is routinely typed both ways. */
function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .split(/[^a-z0-9]+/)
    .filter(Boolean);
}

/** Best guess for `description`, or null when nothing matches.
 *
 *  The earliest matching word wins, because that is where people put the
 *  subject and the rest is context: "Parking przy hotelu" is parking, "Uber
 *  to the airport" is a taxi, "Claude subscription" is an LLM bill. Within a
 *  single word the longest stem wins regardless of table order, so "autobus"
 *  scores Bus/train (7) over Car's "auto" (4) and "carrefour" scores
 *  Groceries over Car's "car". */
export function guessCategory(description: string): string | null {
  for (const token of tokenize(description)) {
    let best: string | null = null;
    let bestLen = 0;

    for (const [category, stems] of KEYWORDS) {
      for (const stem of stems) {
        if (stem.length <= bestLen) continue; // can't beat the incumbent
        const hit =
          stem.length < MIN_PREFIX_LEN ? token === stem : token.startsWith(stem);
        if (hit) {
          best = category;
          bestLen = stem.length;
        }
      }
    }

    if (best) return best;
  }

  return null;
}
