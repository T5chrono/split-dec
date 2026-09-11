import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import UnsubscribePage from "./UnsubscribePage";
import { renderWithProviders } from "../test/utils";

const post = vi.fn();

vi.mock("../lib/api", () => ({
  api: {
    get: vi.fn(),
    post: (...args: unknown[]) => post(...args),
    delete: vi.fn(),
    patch: vi.fn(),
  },
  ApiError: class extends Error {},
  newIdempotencyKey: () => "key",
}));

function render(search: string) {
  return renderWithProviders(
    <MemoryRouter initialEntries={[`/unsubscribe${search}`]}>
      <Routes>
        <Route path="/unsubscribe" element={<UnsubscribePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("UnsubscribePage", () => {
  beforeEach(() => {
    post.mockReset();
    post.mockResolvedValue(undefined);
  });

  it("does not unsubscribe anyone on render", async () => {
    // The API route is POST-only so that a link scanner prefetching the URL
    // cannot unsubscribe somebody. A page that fired on mount would put that
    // straight back, one layer up.
    render("?token=abc");
    expect(await screen.findByRole("button")).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });

  it("sends the token when the reader asks it to", async () => {
    render("?token=abc.def");
    await userEvent.click(await screen.findByRole("button"));
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post.mock.calls[0][0]).toBe("/unsubscribe?token=abc.def");
    expect(await screen.findByRole("status")).toHaveTextContent(/won't email you/i);
  });

  it("says so when there is no token to send", () => {
    render("");
    expect(screen.getByRole("alert")).toHaveTextContent(/not valid/i);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("keeps the button usable when the request fails", async () => {
    post.mockRejectedValue(new Error("nope"));
    render("?token=abc");
    await userEvent.click(await screen.findByRole("button"));
    expect(await screen.findByRole("alert")).toHaveTextContent(/didn't work/i);
    expect(screen.getByRole("button")).toBeEnabled();
  });
});
