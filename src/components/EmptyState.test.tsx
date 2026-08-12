import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Users } from "lucide-react";
import EmptyState from "./EmptyState";
import { renderWithProviders } from "../test/utils";

describe("EmptyState", () => {
  it("shows the message with no button when there is no next step", () => {
    renderWithProviders(<EmptyState icon={Users} message="No groups yet." />);

    expect(screen.getByText("No groups yet.")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("runs the action when one is offered", async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <EmptyState message="No groups yet." action={{ label: "New group", onClick }} />,
    );

    await user.click(screen.getByRole("button", { name: "New group" }));
    expect(onClick).toHaveBeenCalledOnce();
  });
});
