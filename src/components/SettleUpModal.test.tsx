import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import SettleUpModal from "./SettleUpModal";
import type { GroupDetail, Settlement } from "../lib/types";
import { api } from "../lib/api";

// A different value on every call, so a test can tell a reused key from a
// freshly minted one — which is the whole difference between a retry and a
// settlement recorded twice.
const { newIdempotencyKey } = vi.hoisted(() => {
  let issued = 0;
  return { newIdempotencyKey: () => `test-idempotency-key-${++issued}` };
});

vi.mock("../lib/api", () => ({
  api: { post: vi.fn(), put: vi.fn() },
  newIdempotencyKey,
}));

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

beforeEach(() => {
  vi.mocked(api.post).mockReset();
});

describe("SettleUpModal — edit attribution", () => {
  const stored = {
    id: "s1",
    group_id: group.id,
    paid_by_user_id: alice.id,
    paid_to_user_id: bob.id,
    amount: "5.0000",
    currency: "PLN",
    created_at: "2026-06-01T00:00:00Z",
    created_by: alice.id,
    updated_by: null as string | null,
    updated_at: null as string | null,
  };

  function open(overrides: Partial<typeof stored>) {
    renderWithProviders(
      <SettleUpModal
        group={group}
        editing={{ ...stored, ...overrides }}
        onClose={() => {}}
      />,
    );
  }

  it("names whoever last changed somebody else's settlement", () => {
    open({ updated_by: bob.id, updated_at: "2026-06-02T00:00:00Z" });
    expect(screen.getByText(/edited by Bob/)).toBeInTheDocument();
  });

  it("stays quiet when the person who recorded it made the change", () => {
    open({ updated_by: alice.id, updated_at: "2026-06-02T00:00:00Z" });
    expect(screen.queryByText(/edited by/)).not.toBeInTheDocument();
  });

  it("stays quiet on an untouched settlement", () => {
    open({});
    expect(screen.queryByText(/edited by/)).not.toBeInTheDocument();
  });
});

describe("SettleUpModal — idempotency key across retries", () => {
  it("resends the same key after a failed attempt", async () => {
    // A settlement whose response was lost is the worst thing to record twice:
    // it reports a debt as paid off two times over. Retrying under the key the
    // server has already seen is what lets it answer with the row it stored.
    vi.mocked(api.post)
      .mockRejectedValueOnce(new Error("Failed to fetch"))
      .mockResolvedValueOnce({} as Settlement);
    renderWithProviders(<SettleUpModal group={group} onClose={vi.fn()} />);
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText("120,50"), "20,00");

    const submit = screen.getByRole("button", { name: /record payment/i });
    await user.click(submit);
    expect(await screen.findByText("Failed to fetch")).toBeInTheDocument();
    await user.click(submit);

    const keys = vi.mocked(api.post).mock.calls.map(([, , key]) => key);
    expect(keys).toHaveLength(2);
    expect(keys[0]).toBe(keys[1]);
    expect(keys[0]).toBeTruthy();
  });
});
