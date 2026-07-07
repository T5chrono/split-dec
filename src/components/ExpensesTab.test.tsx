import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import ExpensesTab from "./ExpensesTab";
import type { Expense, ExpenseList, GroupDetail } from "../lib/types";
import { api, ApiError } from "../lib/api";

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

/** New deletion flow: click the row (opens the edit view), click the red
 *  "Delete expense" button, then confirm in the dialog. */
async function deleteViaEditView(description: string) {
  const user = userEvent.setup();
  await user.click(screen.getByText(description)); // row click -> edit modal
  await user.click(screen.getByRole("button", { name: /delete expense/i }));
  await user.click(screen.getByRole("button", { name: "Delete" })); // confirm dialog
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

    await deleteViaEditView("Groceries");

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

    await deleteViaEditView("Groceries");
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

    await deleteViaEditView("Groceries");
    expect(screen.queryByText("Groceries")).not.toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByText("Cinema")); // row click -> edit modal
    await user.click(screen.getByRole("button", { name: /delete expense/i }));
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

describe("ExpensesTab — row interactions", () => {
  beforeEach(() => {
    vi.mocked(api.get).mockResolvedValue({
      items: [
        {
          ...(() => expense("e1", "Groceries"))(),
        },
      ],
      limit: 20,
      offset: 0,
    } satisfies ExpenseList);
    vi.mocked(api.patch).mockReset();
  });

  it("clicking the row opens the edit view", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ExpensesTab group={group} />);
    await user.click(await screen.findByText("Groceries"));
    expect(screen.getByText("Edit expense")).toBeInTheDocument();
    // The delete action lives inside the edit view now, styled as a button.
    expect(screen.getByRole("button", { name: /delete expense/i })).toBeInTheDocument();
  });

  it("clicking the category icon opens the quick picker without the edit view", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ExpensesTab group={group} />);
    await screen.findByText("Groceries");

    const row = screen.getByText("Groceries").closest("li")!;
    await user.click(within(row).getByRole("button", { name: /category/i }));

    // Quick picker open, edit view NOT open.
    expect(screen.getByRole("listbox")).toBeInTheDocument();
    expect(screen.queryByText("Edit expense")).not.toBeInTheDocument();
    // General leads the list (first option at the top).
    const options = screen.getAllByRole("option");
    expect(options[0]).toHaveTextContent("General");
  });

  it("picking a category from the quick picker PATCHes only the category", async () => {
    vi.mocked(api.patch).mockResolvedValue(expense("e1", "Groceries"));
    const user = userEvent.setup();
    renderWithProviders(<ExpensesTab group={group} />);
    await screen.findByText("Groceries");

    const row = screen.getByText("Groceries").closest("li")!;
    await user.click(within(row).getByRole("button", { name: /category/i }));
    await user.click(screen.getByRole("option", { name: "Climbing" }));

    expect(api.patch).toHaveBeenCalledWith("/expenses/e1", { category: "Climbing" });
    expect(screen.queryByText("Edit expense")).not.toBeInTheDocument();
  });
});
