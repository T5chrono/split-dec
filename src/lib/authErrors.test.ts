import { describe, expect, it } from "vitest";
import { MAX_FULL_NAME_LENGTH, capFullName } from "./authErrors";

/** A high surrogate with no low surrogate after it: half a character. */
const LONE_SURROGATE = /[\uD800-\uDBFF](?![\uDC00-\uDFFF])/;

describe("capFullName", () => {
  it("leaves an ordinary name alone, trimming only", () => {
    expect(capFullName("  Tomasz Giela  ")).toBe("Tomasz Giela");
    expect(capFullName("Zażółć Gęślą")).toBe("Zażółć Gęślą");
    expect(capFullName("")).toBe("");
    expect(capFullName("   ")).toBe("");
  });

  it("cuts a long name to the cap", () => {
    expect(capFullName("A".repeat(MAX_FULL_NAME_LENGTH + 50))).toBe(
      "A".repeat(MAX_FULL_NAME_LENGTH),
    );
  });

  it("never leaves half a character behind", () => {
    // The whole reason this is `Array.from` and not `slice`. An emoji is two
    // UTF-16 code units, so `slice` counts it as two and can cut between them,
    // storing a lone surrogate in the signup metadata — a character no font
    // draws and nothing downstream expects.
    //
    // The single leading letter is load-bearing: the cap is even, so a name of
    // pure emoji happens to land `slice` on a pair boundary and the bug hides.
    // One odd character ahead of them is what puts the cut inside a pair.
    const name = "a" + "🙂".repeat(MAX_FULL_NAME_LENGTH);
    const naive = name.slice(0, MAX_FULL_NAME_LENGTH);

    expect(LONE_SURROGATE.test(naive)).toBe(true); // what we are avoiding
    expect(LONE_SURROGATE.test(capFullName(name))).toBe(false);
    expect(Array.from(capFullName(name))).toHaveLength(MAX_FULL_NAME_LENGTH);
  });

  it("cuts a mixed name on a character boundary", () => {
    const capped = capFullName("a".repeat(MAX_FULL_NAME_LENGTH - 1) + "🙂🙂");

    expect(Array.from(capped)).toHaveLength(MAX_FULL_NAME_LENGTH);
    expect(capped.endsWith("🙂")).toBe(true);
    expect(LONE_SURROGATE.test(capped)).toBe(false);
  });

  it("counts a name of exactly the cap as fitting", () => {
    const name = "🙂".repeat(MAX_FULL_NAME_LENGTH);
    expect(capFullName(name)).toBe(name);
  });
});
