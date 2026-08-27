import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import ExpenseFormModal from "./ExpenseFormModal";
import type { Expense, GroupDetail } from "../lib/types";
import { api } from "../lib/api";

// A different value on every call, so a test can tell a reused key from a
// freshly minted one — which is the whole difference between a retry and a
// duplicate expense.
const { newIdempotencyKey } = vi.hoisted(() => {
  let issued = 0;
  return { newIdempotencyKey: () => `test-idempotency-key-${++issued}` };
});

vi.mock("../lib/api", () => ({
  api: { post: vi.fn(), patch: vi.fn() },
  newIdempotencyKey,
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
  vi.mocked(api.post).mockReset();
  vi.mocked(api.patch).mockReset();
});

async function switchToPercentage() {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: /percentages/i }));
  return user;
}

describe("ExpenseFormModal — percentage split autofill", () => {
  it("does not autofill while more than one member is still empty", async () => {
    renderWithProviders(
      <ExpenseFormModal group={group} expense={null} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    const user = await switchToPercentage();

    const percentageInputs = screen
      .getAllByRole("textbox")
      .filter((el) => el.className.includes("text-right"));
    // Set Alice = 60; Bob and Carol remain empty -> not "the sole empty one".
    await user.type(percentageInputs[0], "60");

    expect(screen.getByText(/Sum of percentages: 60/)).toBeInTheDocument();
    expect(percentageInputs[1]).toHaveAttribute("placeholder", "0");
    expect(percentageInputs[2]).toHaveAttribute("placeholder", "0");
  });

  it("shows the autofilled value as a placeholder and includes it in the sum", async () => {
    const twoMemberGroup: GroupDetail = { ...group, members: [alice, bob] };
    renderWithProviders(
      <ExpenseFormModal
        group={twoMemberGroup}
        expense={null}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    );
    const user = await switchToPercentage();

    const percentageInputs = screen
      .getAllByRole("textbox")
      .filter((el) => el.className.includes("text-right"));
    expect(percentageInputs).toHaveLength(2);

    await user.type(percentageInputs[0], "70");

    // Bob's field is still empty, but is now the sole empty one -> autofilled.
    expect(percentageInputs[1]).toHaveAttribute("placeholder", "30");
    expect(screen.getByText(/Sum of percentages: 100/)).toBeInTheDocument();
  });

  it("does not autofill when more than one percentage is still empty", async () => {
    renderWithProviders(
      <ExpenseFormModal group={group} expense={null} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    await switchToPercentage();

    const percentageInputs = screen
      .getAllByRole("textbox")
      .filter((el) => el.className.includes("text-right"));
    expect(percentageInputs).toHaveLength(3);
    // All three empty: none should show an autofilled (non-"0") placeholder.
    percentageInputs.forEach((el) => expect(el).toHaveAttribute("placeholder", "0"));
  });

  it("submits the autofilled percentage as part of the split payload", async () => {
    const twoMemberGroup: GroupDetail = { ...group, members: [alice, bob] };
    vi.mocked(api.post).mockResolvedValue({} as Expense);
    renderWithProviders(
      <ExpenseFormModal
        group={twoMemberGroup}
        expense={null}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    );
    const user = await switchToPercentage();

    await user.type(screen.getByPlaceholderText("Dinner at Nolio"), "Dinner");
    // Total amount field: use comma decimal input, mirroring Polish input.
    await user.type(screen.getByPlaceholderText("120,50"), "100,00");
    const percentageInputs = screen
      .getAllByRole("textbox")
      .filter((el) => el.className.includes("text-right"));
    await user.type(percentageInputs[0], "70");

    await user.click(screen.getByRole("button", { name: /add expense/i }));

    expect(api.post).toHaveBeenCalledTimes(1);
    const [, payload] = vi.mocked(api.post).mock.calls[0];
    expect(payload).toMatchObject({
      total_amount: "100.00", // comma normalized to dot
      split_type: "PERCENTAGE",
    });
    const splits = (payload as { splits: { user_id: string; percentage: string }[] }).splits;
    expect(splits.find((s) => s.user_id === alice.id)?.percentage).toBe("70");
    expect(splits.find((s) => s.user_id === bob.id)?.percentage).toBe("30");
  });
});

describe("ExpenseFormModal — exact split autofill", () => {
  it("autofills the sole empty amount as total minus the rest and submits it", async () => {
    const twoMemberGroup: GroupDetail = { ...group, members: [alice, bob] };
    vi.mocked(api.post).mockResolvedValue({} as Expense);
    renderWithProviders(
      <ExpenseFormModal
        group={twoMemberGroup}
        expense={null}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /exact amounts/i }));

    await user.type(screen.getByPlaceholderText("Dinner at Nolio"), "Dinner");
    await user.type(screen.getByPlaceholderText("120,50"), "100,00");
    const amountInputs = screen
      .getAllByRole("textbox")
      .filter((el) => el.className.includes("text-right"));
    await user.type(amountInputs[0], "62,50"); // comma decimal, like Polish input

    // Bob's field is the sole empty one: autofilled with the remainder.
    expect(amountInputs[1]).toHaveAttribute("placeholder", "37.50");
    expect(screen.getByText(/Sum of amounts: 100\.00/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /add expense/i }));
    const [, payload] = vi.mocked(api.post).mock.calls[0];
    const splits = (payload as { splits: { user_id: string; amount: string }[] }).splits;
    expect(splits.find((s) => s.user_id === alice.id)?.amount).toBe("62.50");
    expect(splits.find((s) => s.user_id === bob.id)?.amount).toBe("37.50");
  });

  it("does not autofill when the entered amounts already exceed the total", async () => {
    const twoMemberGroup: GroupDetail = { ...group, members: [alice, bob] };
    renderWithProviders(
      <ExpenseFormModal
        group={twoMemberGroup}
        expense={null}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /exact amounts/i }));
    await user.type(screen.getByPlaceholderText("120,50"), "50");
    const amountInputs = screen
      .getAllByRole("textbox")
      .filter((el) => el.className.includes("text-right"));
    await user.type(amountInputs[0], "60"); // already over the 50 total
    expect(amountInputs[1]).toHaveAttribute("placeholder", "0,00");
  });
});

describe("ExpenseFormModal — delete from edit view", () => {
  it("shows a red delete button when editing and fires onDelete", async () => {
    const onDelete = vi.fn();
    const expense: Expense = {
      id: "e1",
      group_id: group.id,
      description: "Rent",
      category: "Rent",
      split_type: "EQUAL",
      total_amount: "100.0000",
      currency: "PLN",
      paid_by_user_id: alice.id,
      expense_date: "2026-06-01",
      created_at: "2026-06-01T00:00:00Z",
      splits: [{ user_id: alice.id, owed_amount: "100.0000" }],
    };
    renderWithProviders(
      <ExpenseFormModal
        group={group}
        expense={expense}
        onClose={vi.fn()}
        onSaved={vi.fn()}
        onDelete={onDelete}
      />,
    );
    const deleteButton = screen.getByRole("button", { name: /delete expense/i });
    expect(deleteButton.className).toContain("bg-red-600");
    const user = userEvent.setup();
    await user.click(deleteButton);
    expect(onDelete).toHaveBeenCalledTimes(1);
  });

  it("shows no delete button when creating", () => {
    renderWithProviders(
      <ExpenseFormModal group={group} expense={null} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    expect(screen.queryByRole("button", { name: /delete expense/i })).not.toBeInTheDocument();
  });
});

describe("ExpenseFormModal — category guessed from the description", () => {
  // The picker's accessible name is its aria-label ("Category"), so the
  // selected value has to be read off its text content.
  const selectedCategory = () =>
    screen.getByRole("button", { name: "Category" }).textContent;

  it("follows the description while the category is untouched", async () => {
    renderWithProviders(
      <ExpenseFormModal group={group} expense={null} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    const user = userEvent.setup();
    const description = screen.getByPlaceholderText("Dinner at Nolio");

    await user.type(description, "Parking");
    expect(selectedCategory()).toBe("Parking");

    // Refining the description re-guesses rather than sticking on the first hit.
    await user.clear(description);
    await user.type(description, "Pizza");
    expect(selectedCategory()).toBe("Dining out");

    await user.clear(description);
    expect(selectedCategory()).toBe("General");
  });

  it("stops guessing once the user picks a category", async () => {
    renderWithProviders(
      <ExpenseFormModal group={group} expense={null} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Category" }));
    await user.click(screen.getByRole("option", { name: "Gifts" }));
    expect(selectedCategory()).toBe("Gifts");

    await user.type(screen.getByPlaceholderText("Dinner at Nolio"), "Parking");
    expect(selectedCategory()).toBe("Gifts");
  });

  it("leaves an already-categorized expense alone while editing", async () => {
    const expense: Expense = {
      id: "e2",
      group_id: group.id,
      description: "Hotel",
      category: "Hotel",
      split_type: "EQUAL",
      total_amount: "100.0000",
      currency: "PLN",
      paid_by_user_id: alice.id,
      expense_date: "2026-06-01",
      created_at: "2026-06-01T00:00:00Z",
      splits: [{ user_id: alice.id, owed_amount: "100.0000" }],
    };
    renderWithProviders(
      <ExpenseFormModal group={group} expense={expense} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    const user = userEvent.setup();

    const description = screen.getByPlaceholderText("Dinner at Nolio");
    await user.clear(description);
    await user.type(description, "Parking");
    expect(selectedCategory()).toBe("Hotel");
  });
});

describe("ExpenseFormModal — accidental dismissal", () => {
  it("survives a click on the backdrop but still closes via the X button", async () => {
    const onClose = vi.fn();
    const { container } = renderWithProviders(
      <ExpenseFormModal group={group} expense={null} onClose={onClose} onSaved={vi.fn()} />,
    );
    const user = userEvent.setup();
    // A stray click outside the panel must not discard a half-filled form.
    await user.click(container.querySelector(".fixed")!);
    expect(onClose).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe("ExpenseFormModal — metadata-only edits never resubmit financials", () => {
  const percentageExpense: Expense = {
    id: "e9",
    group_id: group.id,
    description: "Rent",
    category: "Rent",
    split_type: "PERCENTAGE",
    total_amount: "1000.0000",
    currency: "PLN",
    paid_by_user_id: alice.id,
    expense_date: "2026-06-01",
    created_at: "2026-06-01T00:00:00Z",
    splits: [
      // 333.33/666.67 does not reconstruct to exact percentages — the case
      // where resubmitting financials would silently shift money.
      { user_id: alice.id, owed_amount: "333.3300" },
      { user_id: bob.id, owed_amount: "666.6700" },
    ],
  };
  const twoMemberGroup: GroupDetail = { ...group, members: [alice, bob] };

  it("sends only metadata when just the description changes", async () => {
    vi.mocked(api.patch).mockResolvedValue({} as Expense);
    renderWithProviders(
      <ExpenseFormModal
        group={twoMemberGroup}
        expense={percentageExpense}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    );
    const user = userEvent.setup();
    const description = screen.getByPlaceholderText("Dinner at Nolio");
    await user.clear(description);
    await user.type(description, "Rent (June)");
    await user.click(screen.getByRole("button", { name: /save changes/i }));

    expect(api.patch).toHaveBeenCalledTimes(1);
    const [, body] = vi.mocked(api.patch).mock.calls[0];
    expect(body).toEqual({
      description: "Rent (June)",
      category: "Rent",
      expense_date: "2026-06-01",
    });
  });

  it("sends the full payload when a financial field changes", async () => {
    vi.mocked(api.patch).mockResolvedValue({} as Expense);
    renderWithProviders(
      <ExpenseFormModal
        group={twoMemberGroup}
        expense={percentageExpense}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    );
    const user = userEvent.setup();
    const amount = screen.getByPlaceholderText("120,50");
    await user.clear(amount);
    await user.type(amount, "1200.00");
    await user.click(screen.getByRole("button", { name: /save changes/i }));

    const [, body] = vi.mocked(api.patch).mock.calls[0];
    expect(body).toHaveProperty("splits");
    expect(body).toHaveProperty("total_amount", "1200.00");
  });
});

describe("ExpenseFormModal — editing a percentage expense", () => {
  it("derives percentages from stored owed amounts, leaving the last for autofill", () => {
    const expense: Expense = {
      id: "e1",
      group_id: group.id,
      description: "Rent",
      category: "Rent",
      split_type: "PERCENTAGE",
      total_amount: "100.0000",
      currency: "PLN",
      paid_by_user_id: alice.id,
      expense_date: "2026-06-01",
      created_at: "2026-06-01T00:00:00Z",
      splits: [
        { user_id: alice.id, owed_amount: "70.0000" },
        { user_id: bob.id, owed_amount: "30.0000" },
      ],
    };
    renderWithProviders(
      <ExpenseFormModal
        group={{ ...group, members: [alice, bob] }}
        expense={expense}
        onClose={vi.fn()}
        onSaved={vi.fn()}
      />,
    );
    // Editing opens directly on the PERCENTAGE tab with values pre-filled.
    const percentageInputs = screen
      .getAllByRole("textbox")
      .filter((el) => el.className.includes("text-right"));
    expect(percentageInputs[0]).toHaveValue("70");
    // Last participant's percentage is intentionally left for the autofill.
    expect(percentageInputs[1]).toHaveValue("");
    expect(percentageInputs[1]).toHaveAttribute("placeholder", "30");
  });
});

describe("ExpenseFormModal — the amount is explained, not echoed back as a 422", () => {
  // The labels are not `htmlFor`-associated, so the placeholder is the handle.
  const amountField = () => screen.getByPlaceholderText("120,50");

  it("explains a zero amount and refuses to submit it", async () => {
    renderWithProviders(
      <ExpenseFormModal group={group} expense={null} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText("Dinner at Nolio"), "Dinner");
    await user.type(amountField(), "0000.00");

    expect(screen.getByText("Amount must be greater than 0.")).toBeInTheDocument();
    expect(amountField()).toHaveAttribute("aria-invalid", "true");

    const submit = screen.getByRole("button", { name: /add expense/i });
    expect(submit).toBeDisabled();
    await user.click(submit);
    expect(api.post).not.toHaveBeenCalled();
  });

  it("clears the message once the amount is positive", async () => {
    renderWithProviders(
      <ExpenseFormModal group={group} expense={null} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    const user = userEvent.setup();
    await user.type(amountField(), "0");
    expect(screen.getByText("Amount must be greater than 0.")).toBeInTheDocument();

    await user.clear(amountField());
    await user.type(amountField(), "12,50");
    expect(screen.queryByText("Amount must be greater than 0.")).not.toBeInTheDocument();
    expect(amountField()).toHaveAttribute("aria-invalid", "false");
  });

  it("names the currency's own precision instead of letting the API reject it", async () => {
    renderWithProviders(
      <ExpenseFormModal group={group} expense={null} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    const user = userEvent.setup();
    await user.type(amountField(), "10.123");
    expect(
      screen.getByText("PLN amounts can have at most 2 decimal places."),
    ).toBeInTheDocument();
  });
});

describe("ExpenseFormModal — idempotency key across retries", () => {
  it("resends the same key after a failed attempt", async () => {
    // The failure that matters is the one where the request *arrived* and only
    // the response was lost. The client cannot tell that apart from a request
    // that never landed, so it must retry under the same key and let the
    // server decide — a new key would record the expense twice.
    vi.mocked(api.post)
      .mockRejectedValueOnce(new Error("Failed to fetch"))
      .mockResolvedValueOnce({} as Expense);
    renderWithProviders(
      <ExpenseFormModal group={group} expense={null} onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    const user = userEvent.setup();
    await user.type(screen.getByPlaceholderText("Dinner at Nolio"), "Dinner");
    await user.type(screen.getByPlaceholderText("120,50"), "100,00");

    const submit = screen.getByRole("button", { name: /add expense/i });
    await user.click(submit);
    expect(await screen.findByText("Failed to fetch")).toBeInTheDocument();
    await user.click(submit);

    const keys = vi.mocked(api.post).mock.calls.map(([, , key]) => key);
    expect(keys).toHaveLength(2);
    expect(keys[0]).toBe(keys[1]);
    expect(keys[0]).toBeTruthy();
  });
});
