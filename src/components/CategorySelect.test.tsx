import { describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import CategorySelect from "./CategorySelect";

describe("CategorySelect", () => {
  it("shows the current category on the trigger", () => {
    renderWithProviders(<CategorySelect value="Groceries" onChange={vi.fn()} />);
    expect(screen.getByRole("button")).toHaveTextContent("Groceries");
  });

  it("opens the listbox and lists categories grouped, including Sports", async () => {
    renderWithProviders(<CategorySelect value="General" onChange={vi.fn()} />);
    await userEvent.click(screen.getByRole("button"));
    const listbox = screen.getByRole("listbox");
    expect(within(listbox).getByText("Sports")).toBeInTheDocument();
    expect(within(listbox).getByRole("option", { name: "Climbing" })).toBeInTheDocument();
    expect(within(listbox).getByRole("option", { name: "Skiing" })).toBeInTheDocument();
  });

  it("calls onChange and closes when an option is picked", async () => {
    const onChange = vi.fn();
    renderWithProviders(<CategorySelect value="General" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button"));
    await userEvent.click(screen.getByRole("option", { name: "Biking" }));
    expect(onChange).toHaveBeenCalledWith("Biking");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("marks the current value as the selected option", async () => {
    renderWithProviders(<CategorySelect value="Running" onChange={vi.fn()} />);
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByRole("option", { name: "Running" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("lists General first so the picker always starts at the top", async () => {
    renderWithProviders(<CategorySelect value="Water" onChange={vi.fn()} />);
    await userEvent.click(screen.getByRole("button"));
    const options = screen.getAllByRole("option");
    expect(options[0]).toHaveTextContent("General");
  });

  it("closes on Escape without changing the value", async () => {
    const onChange = vi.fn();
    renderWithProviders(<CategorySelect value="General" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button"));
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });
});
