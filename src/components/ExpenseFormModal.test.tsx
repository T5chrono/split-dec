import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import ExpenseFormModal from "./ExpenseFormModal";
import type { Expense, GroupDetail } from "../lib/types";
import { api } from "../lib/api";

vi.mock("../lib/api", () => ({
  api: { post: vi.fn(), patch: vi.fn() },
  newIdempotencyKey: () => "test-idempotency-key",
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
