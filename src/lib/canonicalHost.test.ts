import { describe, it, expect, vi } from "vitest";
import { canonicalUrl, enforceCanonicalOrigin } from "./canonicalHost";

describe("canonicalUrl", () => {
  it("strips www so the app lands on the origin that serves /api", () => {
    expect(canonicalUrl("https://www.split-dec.app/")).toBe("https://split-dec.app/");
  });

  it("keeps the path, query and hash", () => {
    expect(canonicalUrl("https://www.split-dec.app/groups/abc?tab=expenses#top")).toBe(
      "https://split-dec.app/groups/abc?tab=expenses#top",
    );
    // An auth callback must not lose its code / tokens on the way over.
    expect(canonicalUrl("https://www.split-dec.app/reset-password?code=xyz")).toBe(
      "https://split-dec.app/reset-password?code=xyz",
    );
    expect(canonicalUrl("https://www.split-dec.app/#access_token=abc")).toBe(
      "https://split-dec.app/#access_token=abc",
    );
  });

  it("leaves origins that serve their own API alone", () => {
    // Redirecting a working origin strands PWAs installed from it.
    expect(canonicalUrl("https://split-dec.app/groups")).toBeNull();
    expect(canonicalUrl("https://split-dec.vercel.app/groups")).toBeNull();
    expect(canonicalUrl("https://split-dec-git-develop.vercel.app/")).toBeNull();
    expect(canonicalUrl("http://localhost:5173/groups")).toBeNull();
  });
});

describe("enforceCanonicalOrigin", () => {
  it("replaces (not pushes) so back does not return to the broken origin", () => {
    const replace = vi.fn();
    const location = { href: "https://www.split-dec.app/groups", replace } as unknown as Location;
    expect(enforceCanonicalOrigin(location)).toBe(true);
    expect(replace).toHaveBeenCalledWith("https://split-dec.app/groups");
  });

  it("is a no-op on the canonical origin", () => {
    const replace = vi.fn();
    const location = { href: "https://split-dec.app/groups", replace } as unknown as Location;
    expect(enforceCanonicalOrigin(location)).toBe(false);
    expect(replace).not.toHaveBeenCalled();
  });
});
