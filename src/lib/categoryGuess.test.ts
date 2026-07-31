import { describe, expect, it } from "vitest";
import { GUESSABLE_CATEGORIES, guessCategory } from "./categoryGuess";
import { CATEGORY_GROUPS } from "./categories";

describe("guessCategory", () => {
  it("only ever names a category the picker can display", () => {
    const real = new Set(CATEGORY_GROUPS.flatMap((g) => g.categories.map((c) => c.value)));
    for (const category of GUESSABLE_CATEGORIES) {
      expect(real, `unknown category "${category}" in the keyword table`).toContain(category);
    }
  });

  it("returns null when nothing matches", () => {
    expect(guessCategory("")).toBeNull();
    expect(guessCategory("   ")).toBeNull();
    expect(guessCategory("zzz qqq")).toBeNull();
  });

  it.each([
    ["Parking", "Parking"],
    ["parking przy hotelu", "Parking"],
    ["Uber to the airport", "Taxi"],
    ["Pizza dinner", "Dining out"],
    ["Netflix", "Streaming"],
    ["Zakupy w Biedronce", "Groceries"],
    ["Bilety do kina", "Movies"],
    ["Naprawa pralki", "Maintenance"],
    ["Claude subscription", "LLM APIs"],
  ])("maps %j to %j", (description, expected) => {
    expect(guessCategory(description)).toBe(expected);
  });

  it("matches inflected forms via stems", () => {
    // The whole point of matching prefixes rather than whole words: Polish
    // declines, English pluralises, and neither should need its own entry.
    expect(guessCategory("Parkingu")).toBe("Parking");
    expect(guessCategory("Taxes")).toBe("Taxes");
    expect(guessCategory("Korepetycje z matematyki")).toBe("Tutor");
  });

  it("ignores case and diacritics in both directions", () => {
    expect(guessCategory("ŚMIECI")).toBe("Trash");
    expect(guessCategory("smieci")).toBe("Trash");
    expect(guessCategory("Prąd")).toBe("Electricity");
  });

  it("reads the leading word as the subject and the rest as context", () => {
    expect(guessCategory("Parking przy hotelu")).toBe("Parking");
    expect(guessCategory("Hotel z parkingiem")).toBe("Hotel");
    expect(guessCategory("Claude subscription")).toBe("LLM APIs");
  });

  it("does not let a brand in the leading word hijack the real subject", () => {
    expect(guessCategory("GitHub Copilot")).toBe("Copilots");
    expect(guessCategory("Office supplies")).toBe("Household supplies");
  });

  it("does not fire a short stem off the front of a longer word", () => {
    // "bus" must not match "business", nor "car" match "carpet".
    expect(guessCategory("business dinner")).toBe("Dining out");
    expect(guessCategory("carpet")).toBeNull();
  });

  it("prefers the most specific keyword over a generic one", () => {
    // "autobus" contains Car's "auto" and Bus/train's "autobus"; the longer
    // stem must win regardless of which sits earlier in the table.
    expect(guessCategory("autobus")).toBe("Bus/train");
    expect(guessCategory("Carrefour")).toBe("Groceries");
    // "booking" would otherwise trip Books' "book".
    expect(guessCategory("Booking")).toBe("Hotel");
  });
});
