import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "../test/utils";
import ConfirmDialog from "./ConfirmDialog";

describe("ConfirmDialog", () => {
  it("shows the title and message", () => {
    renderWithProviders(
      <ConfirmDialog
        title="Delete this expense?"
        message="This can't be undone."
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText("Delete this expense?")).toBeInTheDocument();
    expect(screen.getByText("This can't be undone.")).toBeInTheDocument();
  });

  it("calls onConfirm when the confirm button is clicked", async () => {
    const onConfirm = vi.fn();
    renderWithProviders(
      <ConfirmDialog
        title="t"
        message="m"
        confirmLabel="Yes, delete"
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Yes, delete" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("calls onCancel when Cancel is clicked", async () => {
    const onCancel = vi.fn();
    renderWithProviders(
      <ConfirmDialog title="t" message="m" onConfirm={vi.fn()} onCancel={onCancel} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("calls onCancel when the backdrop is clicked", async () => {
    const onCancel = vi.fn();
    const { container } = renderWithProviders(
      <ConfirmDialog title="t" message="m" onConfirm={vi.fn()} onCancel={onCancel} />,
    );
    // The backdrop is the outermost fixed-position element rendered by Modal.
    await userEvent.click(container.querySelector(".fixed")!);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("disables both buttons while busy", () => {
    renderWithProviders(
      <ConfirmDialog title="t" message="m" busy onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "…" })).toBeDisabled();
  });
});
