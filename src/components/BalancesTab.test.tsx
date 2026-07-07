import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test/utils";
import BalancesTab from "./BalancesTab";
import type { Balances, GroupDetail } from "../lib/types";
import { api } from "../lib/api";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { get: vi.fn() } };
});

// BalancesTab colors amounts from the signed-in user's perspective.
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
const carol = { id: "carol-id", email: "carol@test.dev", full_name: "Carol", avatar_url: null };

const group: GroupDetail = {
  id: "group-id",
  name: "Trip",
  created_by: alice.id,
  created_at: "2026-01-01T00:00:00Z",
  members: [alice, bob, carol],
};

beforeEach(() => {
  vi.mocked(api.get).mockResolvedValue({
    PLN: [
      { from_user_id: alice.id, to_user_id: bob.id, amount: "10.0000" }, // I owe
      { from_user_id: carol.id, to_user_id: alice.id, amount: "5.0000" }, // owed to me
      { from_user_id: bob.id, to_user_id: carol.id, amount: "3.0000" }, // not mine
    ],
  } satisfies Balances);
});

describe("BalancesTab — direction colors from my perspective", () => {
  it("marks money I owe red, money owed to me green, third-party neutral", async () => {
    renderWithProviders(<BalancesTab group={group} />);

    const owed = await screen.findByText("10.00 PLN");
    expect(owed.className).toContain("text-red-600");

    const incoming = screen.getByText("5.00 PLN");
    expect(incoming.className).toContain("text-emerald-600");

    const thirdParty = screen.getByText("3.00 PLN");
    expect(thirdParty.className).not.toContain("text-red-600");
    expect(thirdParty.className).not.toContain("text-emerald-600");
  });

  it("labels my transfers and shows me as 'You'", async () => {
    renderWithProviders(<BalancesTab group={group} />);
    await screen.findByText("10.00 PLN");

    expect(screen.getByText("you pay")).toBeInTheDocument();
    expect(screen.getByText("you receive")).toBeInTheDocument();
    // Alice never appears by name in her own rows.
    expect(screen.queryByText("Alice")).not.toBeInTheDocument();
    expect(screen.getAllByText("You")).toHaveLength(2);
  });
});
