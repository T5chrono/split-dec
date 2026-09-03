import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SupportLink from "./SupportLink";
import { useI18n } from "../lib/i18n";
import { SUPPORT_URL } from "../lib/support";
import { renderWithProviders } from "../test/utils";

describe("SupportLink", () => {
  it("points at the support profile and opens safely in a new tab", () => {
    renderWithProviders(<SupportLink />);

    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", SUPPORT_URL);
    expect(link).toHaveAttribute("target", "_blank");
    // Without both, the opened page gets a handle on ours via window.opener.
    expect(link.getAttribute("rel")).toContain("noopener");
    expect(link.getAttribute("rel")).toContain("noreferrer");
  });

  it("serves the provider's mark from our own origin, never from theirs", () => {
    const { container } = renderWithProviders(<SupportLink variant="brand" />);

    // Their cup ships as a monochrome black and a monochrome white file, so it
    // can sit on our teal without anyone recolouring someone else's mark — and
    // both files are ours to serve. Hotlinking the provider's copy would make
    // every render a request carrying the visitor's IP, and would need an
    // img-src change to boot.
    expect(
      [...container.querySelectorAll("img")].map((i) => i.getAttribute("src")),
    ).toEqual(["/buycoffee/cup-white.png", "/buycoffee/cup-black.png"]);
  });

  it("swaps the mark with the theme, following the label's colour", () => {
    const { container } = renderWithProviders(<SupportLink variant="quiet" />);

    // The quiet variant inverts the pairing, because its label is teal on the
    // page background rather than white on a filled pill.
    expect(
      [...container.querySelectorAll("img")].map((i) => i.getAttribute("src")),
    ).toEqual(["/buycoffee/cup-black.png", "/buycoffee/cup-white.png"]);
  });

  it("is named by its visible label, not by the artwork", () => {
    // One image of each pair is always display:none, so an alt on it would be
    // a name that vanishes with the theme.
    const { container } = renderWithProviders(<SupportLink />);

    expect(screen.getByRole("link", { name: "Buy me a coffee" })).toBeInTheDocument();
    for (const img of container.querySelectorAll("img")) {
      expect(img.getAttribute("alt")).toBe("");
    }
  });

  it("translates the label", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <>
        <SupportLink />
        <LanguageToggle />
      </>,
    );

    await user.click(screen.getByRole("button", { name: "pl" }));
    expect(screen.getByRole("link", { name: "Postaw kawę" })).toBeInTheDocument();
  });
});

/** Minimal harness: the real toggle lives in Layout, which this component
 *  never renders inside on the landing page. */
function LanguageToggle() {
  const { setLang } = useI18n();
  return (
    <button onClick={() => setLang("pl")} type="button">
      pl
    </button>
  );
}
