import { describe, expect, it } from "vitest";
import { safeAvatarUrl } from "./avatarUrl";

describe("safeAvatarUrl", () => {
  it("accepts the Google avatar URLs real accounts actually have", () => {
    // The shape every avatar in production carries today.
    const real = "https://lh3.googleusercontent.com/a/ACg8ocK_abc123=s96-c";
    expect(safeAvatarUrl(real)).toBe(real);
  });

  it("accepts the other shards Google rotates between", () => {
    for (const host of ["lh3", "lh4", "lh5", "lh6"]) {
      expect(safeAvatarUrl(`https://${host}.googleusercontent.com/a/x=s96-c`)).not.toBeNull();
    }
  });

  it.each([
    ["javascript:alert(1)", "script URL"],
    ["data:image/svg+xml,<svg onload=alert(1)>", "data URL"],
    ["vbscript:msgbox(1)", "legacy script URL"],
  ])("rejects %s (%s)", (raw) => {
    expect(safeAvatarUrl(raw)).toBeNull();
  });

  it("rejects an arbitrary https host — the tracking-pixel case", () => {
    // Not XSS: the point is that this host would learn every group member's IP
    // address and when they opened the members list.
    expect(safeAvatarUrl("https://attacker.example/pixel.png")).toBeNull();
  });

  it("rejects lookalike hosts that a naive suffix check would allow", () => {
    for (const host of [
      "evilgoogleusercontent.com", // no dot before the allowed suffix
      "googleusercontent.com.attacker.example", // real host is last, not first
      "googleusercontent.com.evil", // ditto, shorter
    ]) {
      expect(safeAvatarUrl(`https://${host}/a.png`), host).toBeNull();
    }
  });

  it("rejects http, including on the allowed host", () => {
    expect(safeAvatarUrl("http://lh3.googleusercontent.com/a/x")).toBeNull();
  });

  it("is case-insensitive about the host", () => {
    expect(safeAvatarUrl("https://LH3.GoogleUserContent.com/a/x")).not.toBeNull();
  });

  it("returns null for empty, missing and unparseable values", () => {
    for (const raw of [null, undefined, "", "   ", "not a url", "/relative/path.png"]) {
      expect(safeAvatarUrl(raw as string | null | undefined), String(raw)).toBeNull();
    }
  });
});
