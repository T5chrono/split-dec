import { describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import { I18nProvider, useI18n } from "./i18n";

function useT() {
  return renderHook(() => useI18n(), {
    wrapper: ({ children }) => <I18nProvider>{children}</I18nProvider>,
  }).result.current.t;
}

describe("t() placeholder filling", () => {
  it("puts the value where the placeholder is", () => {
    expect(useT()("editedBy", { name: "Bob" })).toBe("edited by Bob");
  });

  it.each([
    ["$&", "edited by $&"],
    ["$`", "edited by $`"],
    ["$'", "edited by $'"],
    ["$$", "edited by $$"],
    ["$<name>", "edited by $<name>"],
    ["A$&B$'C", "edited by A$&B$'C"],
  ])("renders a name containing %j literally", (name, expected) => {
    // The reason this exists. The old convention was
    // `t("editedBy").replace("{name}", name)`, and `String.replace` gives
    // these sequences special meaning in a *replacement string* — `$&` becomes
    // the matched text, `` $` `` everything before it, and so on — so a display
    // name containing one came out garbled. Nothing unsafe (this is text, not
    // markup), but it was silently wrong in six call sites. Passing the values
    // to `t` routes them through a replacer function, where no sequence is
    // special.
    expect(useT()("editedBy", { name })).toBe(expected);
  });

  it("fills every placeholder in a string that has more than one", () => {
    const text = useT()("amountTooPrecise", { currency: "JPY", n: 0 });
    expect(text).toContain("JPY");
    expect(text).toContain("0");
    expect(text).not.toContain("{");
  });

  it("leaves a placeholder alone when no value is given for it", () => {
    // A hole in the sentence is harder to notice than a visible `{name}`, and
    // a missing value is a bug in the caller either way.
    expect(useT()("editedBy", { other: "x" })).toBe("edited by {name}");
  });

  it("returns the string untouched when called with no values", () => {
    expect(useT()("editedBy")).toBe("edited by {name}");
  });
});
