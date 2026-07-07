import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import ExpensesTab from "./ExpensesTab";
import type { Expense, ExpenseList, GroupDetail } from "../lib/types";
import { api, ApiError } from "../lib/api";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { get: vi.fn(), delete: vi.fn() } };
});

const alice = { id: "alice-id", email: "alice@test.dev", full_name: "Alice", avatar_url: null };
const group: GroupDetail = {
  id: "group-id",
  name: "Trip",
  created_by: alice.id,
  created_at: "2026-01-01T00:00:00Z",
  members: [alice],
};

function expense(id: string, description: string): Expense {
  return {
    id,
    group_id: group.id,
    description,
    category: "General",
    split_type: "EQUAL",
    total_amount: "10.0000",
    currency: "PLN",
    paid_by_user_id: alice.id,
    expense_date: "2026-06-01",
    created_at: "2026-06-01T00:00:00Z",
    splits: [{ user_id: alice.id, owed_amount: "10.0000" }],
  };
}

/** A promise plus its resolve/reject, so a test can assert on the
 *  optimistic UI state before choosing how the "network" responds. */
function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

async function openConfirmDialogFor(description: string) {
  const user = userEvent.setup();
  const row = screen.getByText(description).closest("li")!;
  await user.click(within(row).getByTitle("Delete"));
  // Both the row's trash icon (title="Delete") and the confirm dialog's
  // button are named "Delete"; the dialog's is rendered last in DOM order.
  const buttons = screen.getAllByRole("button", { name: "Delete" });
  await user.click(buttons[buttons.length - 1]);
  return user;
}

describe("ExpensesTab — optimistic delete", () => {
  let serverItems: Expense[];

  beforeEach(() => {
    serverItems = [expense("e1", "Groceries"), expense("e2", "Cinema")];
    vi.mocked(api.get).mockImplementation(
      async () =>
        ({ items: serverItems, limit: 20, offset: 0 }) satisfies ExpenseList,
    );
  });

  it("removes the row immediately, before the delete request resolves", async () => {
    const pending = deferred<void>();
    vi.mocked(api.delete).mockReturnValue(pending.promise);

    renderWithProviders(<ExpensesTab group={group} />);
    await screen.findByText("Groceries");

    await openConfirmDialogFor("Groceries");

    // Optimistic: gone from the DOM even though the mocked request is still
    // in flight (we haven't resolved `pending` yet).
    expect(screen.queryByText("Groceries")).not.toBeInTheDocument();
    expect(screen.getByText("Cinema")).toBeInTheDocument();

    serverItems = serverItems.filter((e) => e.id !== "e1");
    pending.resolve();
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2)); // onSettled refetch
    expect(screen.queryByText("Groceries")).not.toBeInTheDocument();
  });

  it("restores the row and shows an error if the delete request fails", async () => {
    const pending = deferred<void>();
    vi.mocked(api.delete).mockReturnValue(pending.promise);

    renderWithProviders(<ExpensesTab group={group} />);
    await screen.findByText("Groceries");

    await openConfirmDialogFor("Groceries");
    expect(screen.queryByText("Groceries")).not.toBeInTheDocument();

    pending.reject(new ApiError(400, "Cannot delete: group is settled elsewhere"));

    // Rolled back: the row reappears and the mutation error is surfaced.
    await screen.findByText("Groceries");
    expect(
      await screen.findByText("Cannot delete: group is settled elsewhere"),
    ).toBeInTheDocument();
  });

  it("disables the confirm button while a delete is already in flight", async () => {
    // The one shared mutation's `isPending` drives ConfirmDialog's `busy`
    // prop, so a second row's confirm button can't be clicked while an
    // earlier delete hasn't settled — this is what actually prevents the
    // two-concurrent-deletes race a reviewer might otherwise worry about.
    const pending = deferred<void>();
    vi.mocked(api.delete).mockReturnValue(pending.promise);

    renderWithProviders(<ExpensesTab group={group} />);
    await screen.findByText("Groceries");

    await openConfirmDialogFor("Groceries");
    expect(screen.queryByText("Groceries")).not.toBeInTheDocument();

    const user = userEvent.setup();
    const cinemaRow = screen.getByText("Cinema").closest("li")!;
    await user.click(within(cinemaRow).getByTitle("Delete"));
    // Once busy, the confirm button's own accessible name changes ("…"), so
    // locate it via its stable sibling (Cancel) rather than by name.
    const cancelButton = await screen.findByRole("button", { name: "Cancel" });
    const confirmButton = cancelButton.parentElement!.querySelectorAll("button")[1];
    await waitFor(() => expect(confirmButton).toBeDisabled());

    pending.resolve();
    await waitFor(() => expect(vi.mocked(api.get).mock.calls.length).toBeGreaterThanOrEqual(2), {
      timeout: 3000,
    });
  });
});
