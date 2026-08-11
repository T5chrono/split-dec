import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { renderWithProviders } from "../test/utils";
import GroupPage from "./GroupPage";
import { api } from "../lib/api";
import type { CurrencyTotal, GroupDetail } from "../lib/types";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } };
});

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    session: { user: { id: "alice-id" } },
    loading: false,
    signInWithGoogle: vi.fn(),
    signOut: vi.fn(),
  }),
}));

const alice = { id: "alice-id", email: "alice@test.dev", full_name: "Alice", avatar_url: null };
const bob = { id: "bob-id", email: "bob@test.dev", full_name: "Bob", avatar_url: null };

const group: GroupDetail = {
  id: "group-id",
  name: "Trip",
  created_by: alice.id,
  created_at: "2026-01-01T00:00:00Z",
  members: [alice, bob],
};

let totals: CurrencyTotal[];

beforeEach(() => {
  totals = [{ currency: "PLN", total: "1234.5000" }];
  vi.mocked(api.get).mockImplementation(async (path: string) => {
    if (path.endsWith("/totals")) return totals as never;
    if (path.endsWith("/expenses") || path.includes("/expenses?")) {
      return { items: [], limit: 20, offset: 0 } as never;
    }
    if (path.endsWith("/balances")) return {} as never;
    if (path.endsWith("/settlements") || path.endsWith("/invitations")) return [] as never;
    return group as never;
  });
});

const renderPage = () =>
  renderWithProviders(
    <MemoryRouter initialEntries={["/groups/group-id"]}>
      <Routes>
        <Route path="/groups/:groupId" element={<GroupPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe("GroupPage — total spent in the header", () => {
  it("shows the group's total spend next to the member count", async () => {
    renderPage();
    expect(await screen.findByText("1 234.50 PLN")).toBeInTheDocument();
  });

  it("lists each currency separately — totals are never summed", async () => {
    totals = [
      { currency: "PLN", total: "1234.5000" },
      { currency: "EUR", total: "20.0000" },
    ];
    renderPage();
    expect(await screen.findByText("1 234.50 PLN · 20.00 EUR")).toBeInTheDocument();
  });

  it("omits the total entirely when the group has no expenses", async () => {
    totals = [];
    renderPage();
    expect(await screen.findByText("Trip")).toBeInTheDocument();
    expect(screen.queryByText(/Total spent/)).not.toBeInTheDocument();
  });
});
