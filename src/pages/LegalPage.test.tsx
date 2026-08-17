import { describe, expect, it, beforeEach } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import LegalPage, { renderLegalText } from "./LegalPage";
import { LEGAL_CONTACT_EMAIL, LEGAL_DOCS } from "../lib/legal";
import { renderWithProviders } from "../test/utils";

function renderAt(path: string) {
  return renderWithProviders(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/privacy" element={<LegalPage doc="privacy" />} />
        <Route path="/terms" element={<LegalPage doc="terms" />} />
        <Route path="/" element={<div>app home</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => localStorage.clear());

describe("LegalPage", () => {
  it("renders the privacy policy with its update date and contact address", () => {
    renderAt("/privacy");

    expect(
      screen.getByRole("heading", { level: 1, name: "Privacy Policy" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Last updated:/)).toBeInTheDocument();
    expect(
      screen.getAllByRole("link", { name: LEGAL_CONTACT_EMAIL })[0],
    ).toHaveAttribute("href", `mailto:${LEGAL_CONTACT_EMAIL}`);
  });

  it("names the controller and states that the app moves no money", () => {
    renderAt("/privacy");

    expect(screen.getByText(/Tomasz Giela/)).toBeInTheDocument();
    expect(screen.getByText("The app does not move money.")).toBeInTheDocument();
  });

  it("renders the terms with the processor links opening safely", () => {
    renderAt("/terms");

    expect(
      screen.getByRole("heading", { level: 1, name: "Terms of Service" }),
    ).toBeInTheDocument();
    expect(screen.getByText("SplitDec does not move money.")).toBeInTheDocument();
  });

  it("marks external links as noreferrer and keeps in-app links routed", () => {
    renderAt("/privacy");

    const supabase = screen
      .getAllByRole("link", { name: "Privacy policy" })
      .find((a) => a.getAttribute("href")?.includes("supabase"))!;
    expect(supabase).toHaveAttribute("target", "_blank");
    expect(supabase).toHaveAttribute("rel", "noreferrer");
  });

  it("cross-links the two documents and back to the app", async () => {
    const user = userEvent.setup();
    renderAt("/privacy");

    const footer = screen.getByRole("navigation");
    await user.click(within(footer).getByRole("link", { name: "Terms of Service" }));
    expect(
      screen.getByRole("heading", { level: 1, name: "Terms of Service" }),
    ).toBeInTheDocument();

    await user.click(
      within(screen.getByRole("navigation")).getByRole("link", { name: "Back to SplitDec" }),
    );
    expect(screen.getByText("app home")).toBeInTheDocument();
  });

  it("switches the whole document to Polish", async () => {
    const user = userEvent.setup();
    renderAt("/privacy");

    await user.click(screen.getByRole("button", { name: /pl/i }));
    expect(
      screen.getByRole("heading", { level: 1, name: "Polityka prywatności" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Ostatnia aktualizacja:/)).toBeInTheDocument();
  });
});

describe("legal document content", () => {
  it("keeps the same section structure in both languages", () => {
    for (const doc of ["privacy", "terms"] as const) {
      const { en, pl } = LEGAL_DOCS[doc];
      expect(pl.intro).toHaveLength(en.intro.length);
      expect(pl.sections).toHaveLength(en.sections.length);
      en.sections.forEach((section, i) => {
        const counterpart = pl.sections[i];
        expect(counterpart.blocks).toHaveLength(section.blocks.length);
        section.blocks.forEach((block, j) => {
          // A paragraph must not become a bullet list in translation.
          expect(Array.isArray(counterpart.blocks[j])).toBe(Array.isArray(block));
        });
      });
    }
  });

  it("leaves no unbalanced inline markup behind", () => {
    for (const doc of ["privacy", "terms"] as const) {
      for (const lang of ["en", "pl"] as const) {
        const { intro, sections } = LEGAL_DOCS[doc][lang];
        const texts = [...intro, ...sections.flatMap((s) => s.blocks.flat())];
        for (const text of texts) {
          expect((text.match(/\*\*/g) ?? []).length % 2, text).toBe(0);
          expect(text, text).not.toMatch(/\]\(\s*\)/);
        }
      }
    }
  });
});

describe("renderLegalText", () => {
  it("renders bold runs, links and the plain text around them", () => {
    renderWithProviders(
      <MemoryRouter>
        <p>{renderLegalText("before **bold** [label](/terms) after")}</p>
      </MemoryRouter>,
    );

    expect(screen.getByText("bold").tagName).toBe("STRONG");
    const link = screen.getByRole("link", { name: "label" });
    expect(link).toHaveAttribute("href", "/terms");
    expect(link).not.toHaveAttribute("target");
    expect(screen.getByText(/before/)).toHaveTextContent("before bold label after");
  });

  it("keeps the words but drops the link for a javascript: URL", () => {
    // Static repo-owned copy today, so this is unreachable — and it is exactly
    // what would become a working XSS the day these documents stop being
    // static, because React warns about javascript: URLs without blocking them.
    // Payload deliberately free of parentheses: the href group is `[^)]+`, so
    // `javascript:alert(1)` would end the match at the inner bracket and leave
    // a stray `)` in the text. That is the minimal parser working as written
    // rather than anything to do with this check — and it cannot arise in the
    // real documents, which contain no parenthesised hrefs.
    renderWithProviders(
      <MemoryRouter>
        <p>{renderLegalText("read the [notice](javascript:void 0) first")}</p>
      </MemoryRouter>,
    );

    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText(/read the/)).toHaveTextContent("read the notice first");
  });

  it.each(["data:text/html,<script>alert(1)</script>", "vbscript:msgbox(1)", "http://plain"])(
    "refuses to link %s",
    (href) => {
      renderWithProviders(
        <MemoryRouter>
          <p>{renderLegalText(`x [label](${href}) y`)}</p>
        </MemoryRouter>,
      );

      expect(screen.queryByRole("link")).not.toBeInTheDocument();
    },
  );

  it("still links the three shapes the documents actually use", () => {
    renderWithProviders(
      <MemoryRouter>
        <p>
          {renderLegalText(
            "[a](/privacy) [b](https://example.com) [c](mailto:privacy@split-dec.app)",
          )}
        </p>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "a" })).toHaveAttribute("href", "/privacy");
    const external = screen.getByRole("link", { name: "b" });
    expect(external).toHaveAttribute("href", "https://example.com");
    expect(external).toHaveAttribute("target", "_blank");
    const mail = screen.getByRole("link", { name: "c" });
    expect(mail).toHaveAttribute("href", "mailto:privacy@split-dec.app");
    // A mail client is not a new browsing context.
    expect(mail).not.toHaveAttribute("target");
  });
});
