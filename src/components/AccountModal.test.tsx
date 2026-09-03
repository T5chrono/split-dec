import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AccountModal from "./AccountModal";
import { SUPPORT_URL } from "../lib/support";
import { renderWithProviders } from "../test/utils";

vi.mock("../lib/api", () => ({ api: { delete: vi.fn() } }));

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    session: {
      user: {
        email: "ada@example.com",
        user_metadata: { full_name: "Ada Lovelace" },
      },
    },
    loading: false,
    signOut: vi.fn(),
  }),
}));

describe("AccountModal", () => {
  it("offers the support link, above the danger zone", () => {
    renderWithProviders(
      <MemoryRouter>
        <AccountModal onClose={vi.fn()} />
      </MemoryRouter>,
    );

    const link = screen
      .getAllByRole("link")
      .find((a) => a.getAttribute("href") === SUPPORT_URL);
    expect(link).toBeDefined();

    // Ordering matters here rather than being cosmetic: "buy me a coffee"
    // sitting directly under "delete account" reads as a parting shot.
    const danger = screen.getByText("Danger zone");
    expect(link!.compareDocumentPosition(danger)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  });
});
