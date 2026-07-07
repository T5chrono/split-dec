import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import DatePicker from "./DatePicker";

// shouldAdvanceTime keeps real timers ticking (userEvent's internal delays
// still work) while Date is pinned for deterministic "today" assertions.
beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date(2026, 5, 15)); // June 15, 2026
});
afterEach(() => vi.useRealTimers());

describe("DatePicker", () => {
  it("shows the selected date on the trigger button", () => {
    renderWithProviders(<DatePicker value="2026-06-15" onChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: /June 15, 2026/i })).toBeInTheDocument();
  });

  it("opens a dialog showing the month and year on click", async () => {
    const user = userEvent.setup();
    renderWithProviders(<DatePicker value="2026-06-15" onChange={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /June 15, 2026/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/June 2026/i)).toBeInTheDocument();
  });

  it("selects a day, calls onChange with the local ISO date, and closes", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderWithProviders(<DatePicker value="2026-06-15" onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /June 15, 2026/i }));
    await user.click(screen.getByRole("button", { name: /June 20, 2026/i }));
    expect(onChange).toHaveBeenCalledWith("2026-06-20");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("navigates to the next/previous month without changing the selection", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderWithProviders(<DatePicker value="2026-06-15" onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /June 15, 2026/i }));
    await user.click(screen.getByRole("button", { name: /next month/i }));
    expect(screen.getByText(/July 2026/i)).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /previous month/i }));
    expect(screen.getByText(/June 2026/i)).toBeInTheDocument();
  });

  it("the Today shortcut selects the current date regardless of the viewed month", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderWithProviders(<DatePicker value="2026-06-15" onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /June 15, 2026/i }));
    await user.click(screen.getByRole("button", { name: /next month/i }));
    await user.click(screen.getByRole("button", { name: "Today" }));
    expect(onChange).toHaveBeenCalledWith("2026-06-15"); // system time is June 15
  });

  it("closes on Escape without firing onChange", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderWithProviders(<DatePicker value="2026-06-15" onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /June 15, 2026/i }));
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("closes when clicking outside", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <div>
        <DatePicker value="2026-06-15" onChange={vi.fn()} />
        <button>outside</button>
      </div>,
    );
    await user.click(screen.getByRole("button", { name: /June 15, 2026/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "outside" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
