import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { renderWithProviders } from "../test/utils";
import GroupSettingsModal from "./GroupSettingsModal";
import type { GroupDetail } from "../lib/types";
import { api } from "../lib/api";

vi.mock("../lib/api", () => ({
  api: { patch: vi.fn(), delete: vi.fn() },
}));

const alice = { id: "alice-id", email: "alice@test.dev", full_name: "Alice", avatar_url: null };
const group: GroupDetail = {
  id: "group-id",
  name: "Trip",
  created_by: alice.id,
  created_at: "2026-01-01T00:00:00Z",
  members: [alice],
};

function renderModal(onClose = vi.fn()) {
  const rendered = renderWithProviders(
    <MemoryRouter>
      <GroupSettingsModal group={group} onClose={onClose} />
    </MemoryRouter>,
  );
  return { ...rendered, onClose };
}

beforeEach(() => {
  vi.mocked(api.patch).mockReset();
  vi.mocked(api.delete).mockReset();
});

describe("GroupSettingsModal", () => {
  it("renames the group and closes", async () => {
    vi.mocked(api.patch).mockResolvedValue({ ...group, name: "Trip 2" });
    const { onClose } = renderModal();
    const user = userEvent.setup();

    const input = screen.getByLabelText("Group name");
    await user.clear(input);
    await user.type(input, "Trip 2");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(api.patch).toHaveBeenCalledWith("/groups/group-id", { name: "Trip 2" });
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });

  it("does not offer to save an unchanged name", () => {
    renderModal();
    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("deletes the group only after the confirmation is accepted", async () => {
    vi.mocked(api.delete).mockResolvedValue(undefined);
    renderModal();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: /delete group/i }));
    expect(api.delete).not.toHaveBeenCalled();

    // The confirm dialog reuses the same "Delete group" label, and stacks on
    // top of the settings modal — the second match is the confirming one.
    const confirm = screen.getAllByRole("button", { name: /delete group/i })[1];
    await user.click(confirm);
    expect(api.delete).toHaveBeenCalledWith("/groups/group-id");
  });

  it("keeps the panel open when the backdrop is clicked", async () => {
    const { container, onClose } = renderModal();
    await userEvent.setup().click(container.querySelector(".fixed")!);
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Group name")).toBeInTheDocument();
  });
});
