import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import CategorySummaryModal from "./CategorySummaryModal";
import { api } from "../lib/api";
import type { CategoryTotal } from "../lib/types";

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, api: { get: vi.fn(), delete: vi.fn(), patch: vi.fn(), post: vi.fn() } };
});

const get = vi.mocked(api.get);

function serve(totals: CategoryTotal[]) {
  get.mockResolvedValue(totals);
}

function renderModal() {
  return renderWithProviders(
    <CategorySummaryModal
      groupId="group-id"
      month="2026-10"
      monthLabel="October 2026"
      onClose={() => {}}
    />,
  );
}

beforeEach(() => get.mockReset());
afterEach(() => localStorage.clear());

describe("CategorySummaryModal", () => {
  it("asks for the month's per-category totals", async () => {
    serve([]);
    renderModal();
    await screen.findByText("No expenses in this month.");
    expect(get).toHaveBeenCalledWith(
      "/groups/group-id/expenses/by-category?date_from=2026-10-01&date_to=2026-10-31",
    );
    // Nothing to copy, so no button offering to.
    expect(screen.queryByRole("button", { name: /copy for excel/i })).not.toBeInTheDocument();
  });

  it("shows all twelve groups with a total, and copies twelve plain numbers", async () => {
    serve([
      { category: "Groceries", currency: "PLN", total: "1234.5000" },
      { category: "Dining out", currency: "PLN", total: "10.2500" },
      { category: "Rent", currency: "PLN", total: "2000.0000" },
    ]);
    const user = userEvent.setup();
    renderModal();

    const table = await screen.findByRole("table");
    expect(within(table).getAllByRole("row")).toHaveLength(13); // 12 groups + total
    expect(within(table).getByText("Food and drink")).toBeInTheDocument();
    expect(within(table).getByText("Uncategorized")).toBeInTheDocument();
    const totalRow = within(table).getByText("Total").closest("tr")!;
    expect(totalRow.textContent?.replace(/\s/g, " ")).toContain("3 244.75 PLN");

    await user.click(screen.getByRole("button", { name: /copy for excel/i }));
    expect(await navigator.clipboard.readText()).toBe(
      ["1244.75", ...Array(7).fill("0.00"), "2000.00", "0.00", "0.00", "0.00"].join("\n"),
    );
    expect(screen.getByRole("button", { name: /copied/i })).toBeInTheDocument();
  });

  it("uses a decimal comma when the app is in Polish", async () => {
    localStorage.setItem("splitdec.lang", "pl");
    serve([{ category: "Taxi", currency: "PLN", total: "42.5000" }]);
    const user = userEvent.setup();
    renderModal();

    await user.click(await screen.findByRole("button", { name: /kopiuj do excela/i }));
    const lines = (await navigator.clipboard.readText()).split("\n");
    expect(lines).toHaveLength(12);
    expect(lines[5]).toBe("42,50"); // Transportation is the sixth group
  });

  it("switches between currencies and copies only the one shown", async () => {
    serve([
      { category: "Hotel", currency: "PLN", total: "300.0000" },
      { category: "Hotel", currency: "EUR", total: "80.0000" },
    ]);
    const user = userEvent.setup();
    renderModal();

    // Alphabetical: EUR first.
    expect(await screen.findByRole("button", { name: "EUR" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await user.click(screen.getByRole("button", { name: "PLN" }));
    await user.click(screen.getByRole("button", { name: /copy for excel/i }));
    expect((await navigator.clipboard.readText()).split("\n")[6]).toBe("300.00"); // Travel
  });

  it("says so when the clipboard refuses", async () => {
    serve([{ category: "Taxi", currency: "PLN", total: "1.0000" }]);
    const user = userEvent.setup();
    renderModal();
    const button = await screen.findByRole("button", { name: /copy for excel/i });
    vi.spyOn(navigator.clipboard, "writeText").mockRejectedValueOnce(new Error("denied"));
    await user.click(button);
    expect(screen.getByRole("alert")).toHaveTextContent(/couldn't copy/i);
  });
});
