import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SettlementsTab from "./SettlementsTab";
import { PAGE_SIZE } from "../lib/queries";
import type { GroupDetail, Settlement, SettlementList } from "../lib/types";
import { renderWithProviders } from "../test/utils";

vi.mock("../lib/api", () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
  },
  ApiError: class extends Error {},
  newIdempotencyKey: () => "key",
}));

import { api } from "../lib/api";

const alice = { id: "alice-id", email: "alice@test.dev", full_name: "Alice", avatar_url: null };
const bob = { id: "bob-id", email: "bob@test.dev", full_name: "Bob", avatar_url: null };

const group: GroupDetail = {
  id: "group-id",
  name: "Trip",
  created_by: alice.id,
  created_at: "2026-01-01T00:00:00Z",
  members: [alice, bob],
};

function settlement(id: string, amount: string): Settlement {
  return {
    id,
    group_id: group.id,
    paid_by_user_id: bob.id,
    paid_to_user_id: alice.id,
    amount,
    currency: "PLN",
    created_at: "2026-06-01T00:00:00Z",
    created_by: bob.id,
    updated_by: null,
    updated_at: null,
  };
}

/** `n` rows, each with a distinct amount so a test can name one on screen. */
function page(n: number, offset: number): SettlementList {
  return {
    items: Array.from({ length: n }, (_, i) => settlement(`s${offset + i}`, `${offset + i + 1}.00`)),
    limit: PAGE_SIZE,
    offset,
  };
}

/** Serve whichever page the component asks for, by reading its own query. */
function serve(pages: Record<number, SettlementList>) {
  vi.mocked(api.get).mockImplementation(async (url?: string) => {
    const query = (url ?? "").split("?")[1] ?? "";
    const offset = Number(new URLSearchParams(query).get("offset") ?? 0);
    return pages[offset] as never;
  });
}

describe("SettlementsTab — paging", () => {
  beforeEach(() => vi.mocked(api.get).mockReset());

  /** Rows on screen. Counting beats matching text here: the amounts go through
   *  `formatMoney`, whose output depends on the locale the test env happens to
   *  pick, and the member names repeat on every row. */
  const rows = () => screen.queryAllByRole("listitem");
  const offsetsRequested = () =>
    vi.mocked(api.get).mock.calls.map((c) =>
      Number(new URLSearchParams(((c[0] as string) ?? "").split("?")[1] ?? "").get("offset")),
    );

  it("asks for one page, not the whole history", async () => {
    serve({ 0: page(3, 0) });
    renderWithProviders(<SettlementsTab group={group} />);
    await waitFor(() => expect(rows()).toHaveLength(3));
    const url = vi.mocked(api.get).mock.calls[0][0] as string;
    expect(url).toContain(`limit=${PAGE_SIZE}`);
    expect(url).toContain("offset=0");
  });

  it("hides the controls while everything fits on one page", async () => {
    serve({ 0: page(3, 0) });
    renderWithProviders(<SettlementsTab group={group} />);
    await waitFor(() => expect(rows()).toHaveLength(3));
    expect(screen.queryByRole("button", { name: /older/i })).not.toBeInTheDocument();
  });

  it("walks forward and back through the pages", async () => {
    serve({ 0: page(PAGE_SIZE, 0), [PAGE_SIZE]: page(2, PAGE_SIZE) });
    renderWithProviders(<SettlementsTab group={group} />);
    await waitFor(() => expect(rows()).toHaveLength(PAGE_SIZE));

    await userEvent.click(screen.getByRole("button", { name: /older/i }));
    await waitFor(() => expect(rows()).toHaveLength(2));
    expect(offsetsRequested()).toContain(PAGE_SIZE);
    // A short page is the last one.
    expect(screen.getByRole("button", { name: /older/i })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: /newer/i }));
    await waitFor(() => expect(rows()).toHaveLength(PAGE_SIZE));
    expect(screen.getByRole("button", { name: /newer/i })).toBeDisabled();
  });

  it("shows the empty state only on the first page", async () => {
    // An empty *later* page means you paged past the end, not that the group
    // has never settled anything — the encouraging empty state would be wrong.
    serve({ 0: page(PAGE_SIZE, 0), [PAGE_SIZE]: page(0, PAGE_SIZE) });
    renderWithProviders(<SettlementsTab group={group} />);
    await waitFor(() => expect(rows()).toHaveLength(PAGE_SIZE));

    await userEvent.click(screen.getByRole("button", { name: /older/i }));
    await waitFor(() => expect(rows()).toHaveLength(0));
    expect(screen.queryByText(/no payments/i)).not.toBeInTheDocument();
  });

  it("still shows the empty state for a group that has settled nothing", async () => {
    serve({ 0: page(0, 0) });
    renderWithProviders(<SettlementsTab group={group} />);
    expect(await screen.findByText(/no payments/i)).toBeInTheDocument();
  });
});
