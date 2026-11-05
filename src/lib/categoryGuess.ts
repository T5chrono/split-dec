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
  // Food and drink
  [
    "Dining out",
    [
      "restaurant", "restaurac", "dinner", "lunch", "breakfast", "obiad", "kolacja",
      "sniadan", "pizza", "sushi", "burger", "kebab", "mcdonald", "kfc", "bistro", "jedzenie",
    ],
  ],
  ["Takeout/delivery", ["takeout", "delivery", "dostaw", "wolt", "glovo", "pyszne", "catering"]],
  [
    "Coffee & snacks",
    ["coffee", "kawa", "kawy", "cafe", "kawiarni", "starbucks", "snack", "przekask", "lody",
      "dessert", "deser", "slodycz", "ciast"],
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
  [
    "Alcohol",
    ["beer", "wine", "vodka", "whisky", "liquor", "alkohol", "piwo", "wino", "wodka", "bar",
      "pub", "drink"],
  ],

  // Personal care & health
  [
    "Hygiene/cosmetics",
    ["kosmetyk", "cosmetic", "drogeri", "rossmann", "hebe", "szampon", "shampoo"],
  ],
  ["Hair/beauty", ["fryzjer", "barber", "haircut", "kosmetyczk", "manicure", "pedicure"]],
  ["Pharmacy", ["apteka", "apteki", "pharmacy", "leki", "lekow", "recept", "suplement"]],
  [
    "Medical expenses",
    ["doctor", "lekarz", "medic", "dentyst", "dentist", "szpital", "hospital", "okulist",
      "badani"],
  ],

  // Clothing & footwear
  ["Clothing", ["clothes", "clothing", "ubran", "odziez", "koszul", "kurtka", "spodni"]],
  ["Footwear", ["buty", "butow", "shoes", "obuwie", "sneakers"]],
  ["Accessories", ["torebk", "plecak", "zegarek", "bizuteri", "jewelry", "pasek"]],

  // Entertainment
  ["Books", ["book", "ksiazk", "ebook", "audiobook", "podrecznik"]],
  ["Movies", ["movie", "cinema", "kino", "kina", "film", "teatr", "theatre", "theater"]],
  ["Music", ["music", "muzyk", "vinyl", "winyl", "plyta"]],
  ["Games", ["game", "gaming", "gra", "gry", "konsol", "playstation", "xbox", "steam", "nintendo"]],
  ["Streaming", ["netflix", "spotify", "hbo", "disney", "youtube", "streaming"]],
  ["Hobbies", ["hobby"]],
  ["Concerts & events", ["concert", "koncert", "festival", "festiwal", "mecz"]],

  // Learning
  ["Courses", ["course", "kurs", "szkolenie", "bootcamp", "warsztat", "studia", "czesne", "tuition"]],
  ["Tutor", ["tutor", "korepetycj", "lekcj"]],
  ["Other Learning", ["school", "szkol"]],

  // Sports
  ["Climbing", ["climb", "wspinacz", "scianka", "boulder"]],
  ["Skiing", ["ski", "skiing", "skipass", "narty", "narciar", "snowboard", "wyciag"]],
  ["Swimming", ["swim", "basen", "plywa", "aquapark"]],
  ["Running", ["bieg", "marathon", "maraton"]],
  ["Biking", ["bike", "bicycle", "rower"]],
  ["Gym/fitness", ["gym", "silown", "fitness", "yoga", "joga", "karnet", "multisport"]],
  ["Sports gear", ["decathlon"]],
  ["Competitions", ["zawody", "competition", "startow"]],
  ["Other Sports", ["tennis", "tenis", "squash"]],

  // Transportation
  ["Bus/train", ["bus", "train", "tram", "metro", "pkp", "autobus", "pociag", "kolej"]],
  ["Highways", ["autostrad", "highway", "winiet", "toll"]],
  ["Gas/fuel", ["fuel", "petrol", "diesel", "gas", "paliw", "benzyn", "tankow", "lpg"]],
  ["Car", ["car", "cars", "auto", "samochod", "tire", "opon", "myjnia"]],
  ["Parking", ["park", "parkomat"]],
  ["Taxi", ["taxi", "taks", "uber", "bolt", "lyft"]],

  // Travel and vacations
  ["Flights", ["plane", "flight", "airline", "airfare", "samolot", "lotnisk", "ryanair", "wizzair"]],
  ["Hotel", ["hotel", "hostel", "motel", "airbnb", "nocleg", "booking", "pensjonat", "kemping"]],
  ["Travel transport", ["wypozyczal", "rental", "kamper", "camper"]],
  ["Attractions & tours", ["muzeum", "museum", "wycieczk", "tour", "przewodnik", "zwiedzan"]],
  ["Travel insurance & visas", ["visa", "visas", "wiza", "wizy"]],
  ["Other Travel", ["pamiatk", "souvenir"]],

  // Tech, Software & AI
  ["Phone", ["phone", "telefon", "komork", "doladow"]],
  ["Internet", ["internet", "wifi", "swiatlowod", "netia"]],
  // No "office" or "github": both lead descriptions that mean something else
  // ("Office supplies", "GitHub Copilot"), and "microsoft" already covers the
  // Office subscription.
  ["Software", ["software", "licenc", "adobe", "microsoft", "jetbrains"]],
  // The chat products people subscribe to are named after the model, so the
  // model's name means the subscription; API credits say so ("Anthropic API").
  [
    "AI subscriptions",
    ["claude", "chatgpt", "gpt", "copilot", "cursor", "midjourney", "dalle", "sora", "runway",
      "veo", "elevenlabs", "perplexity"],
  ],
  ["LLM APIs", ["openai", "anthropic", "llm", "api", "gemini", "mistral", "deepseek", "openrouter"]],
  ["Cloud & hosting", ["hosting", "vercel", "aws", "domen", "domain", "serwer", "server", "vps", "cloud"]],
  ["Memberships", ["membership", "czlonkost", "prime", "subscription", "subskrypc", "abonament"]],

  // Home and appliances
  ["Rent", ["rent", "najem", "wynajem"]],
  ["Mortgage", ["mortgage", "hipotek", "kredyt"]],
  ["Building fees", ["czynsz", "wspolnot", "spoldzielni"]],
  [
    "Bills",
    ["bill", "bills", "rachun", "electric", "prad", "energia", "tauron", "enea", "pge", "water",
      "woda", "wodociag", "heating", "ogrzewan", "cieplo", "gaz", "trash", "garbage", "smieci",
      "odpady"],
  ],
  ["Appliances", ["pralk", "lodowk", "zmywark", "odkurzacz", "appliance", "agd"]],
  [
    "Electronics",
    ["laptop", "komputer", "computer", "monitor", "tablet", "elektronik", "electronic",
      "sluchawki", "telewizor"],
  ],
  ["Furniture", ["furniture", "mebl", "sofa", "kanapa", "krzesl", "lozko", "szafa", "ikea"]],
  [
    "Household supplies",
    ["detergent", "chemia", "proszek", "supplies", "clean", "sprzat", "pralnia", "laundry"],
  ],
  ["Maintenance", ["repair", "naprawa", "remont", "hydraulik", "plumber", "mechanik", "malowan"]],
  ["Other Home", ["pet", "pets", "dog", "dogs", "cat", "cats", "pies", "psa", "kot", "vet",
    "weterynar", "karma", "ogrod", "garden", "rosli"]],

  // Finance and life
  ["Bank fees", ["prowizj", "bank", "przewalutow"]],
  ["Insurance", ["insurance", "ubezpiecz", "polisa", "oc", "ac"]],
  ["Taxes", ["tax", "taxes", "podat", "skarbow"]],
  ["Gifts", ["gift", "prezent", "upominek"]],
  ["Childcare", ["childcare", "babysit", "przedszkol", "zlobek", "opiekunka", "niania"]],
  ["Other Life", ["notariusz", "notary", "prawnik", "lawyer", "urzad"]],

  // Uncategorized
  ["Big purchases", ["wesel", "wedding", "kaucj", "deposit"]],
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
