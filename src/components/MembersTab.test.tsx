import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { renderWithProviders } from "../test/utils";
import MembersTab from "./MembersTab";
import type { GroupDetail, Invitation } from "../lib/types";
import { api } from "../lib/api";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { get: vi.fn(), delete: vi.fn(), patch: vi.fn(), post: vi.fn() } };
});

const alice = { id: "alice-id", email: "alice@test.dev", full_name: "Alice", avatar_url: null };
const group: GroupDetail = {
  id: "group-id",
  name: "Trip",
  created_by: alice.id,
  created_at: "2026-01-01T00:00:00Z",
  members: [alice],
};

function invitation(email: string): Invitation {
  return {
    id: "invitation-id",
    group_id: group.id,
    email,
    status: "PENDING",
    created_at: "2026-06-01T00:00:00Z",
  };
}

function renderTab() {
  return renderWithProviders(
    <MemoryRouter>
      <MembersTab group={group} />
    </MemoryRouter>,
  );
}

async function invite(email: string) {
  const user = userEvent.setup();
  await user.type(screen.getByPlaceholderText("friend@example.com"), email);
  await user.click(screen.getByRole("button", { name: /invite/i }));
  return user;
}

describe("MembersTab invitations", () => {
  beforeEach(() => {
    vi.mocked(api.get).mockResolvedValue([] as Invitation[]);
    vi.mocked(api.post).mockClear();
  });

  it("shows one outcome regardless of who the address belongs to", async () => {
    // The API answers identically for registered and unregistered addresses
    // (it must not be an enumeration oracle), so the UI must not branch on
    // the response either — it has nothing to branch on.
    vi.mocked(api.post).mockResolvedValue(invitation("friend@test.dev"));
    renderTab();
    await invite("friend@test.dev");

    await waitFor(() => expect(screen.getByText(/invitation saved/i)).toBeInTheDocument());
    // The manual draft is always offered, never as a "they aren't a user" hint.
    const draft = screen.getByRole("link", { name: /open email draft/i });
    expect(draft).toHaveAttribute("href", expect.stringContaining("mailto:friend@test.dev"));
    expect(screen.queryByText(/isn't on SplitDec/i)).not.toBeInTheDocument();
  });

  it("surfaces the rate-limit error instead of a success message", async () => {
    vi.mocked(api.post).mockRejectedValue(
      new Error("Too many invitations sent recently. Please try again later."),
    );
    renderTab();
    await invite("friend@test.dev");

    await waitFor(() =>
      expect(screen.getByText(/too many invitations sent recently/i)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/invitation saved/i)).not.toBeInTheDocument();
  });
});
