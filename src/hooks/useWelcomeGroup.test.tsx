import { beforeEach, describe, expect, it, vi } from "vitest";
import { waitFor } from "@testing-library/react";
import type { Session } from "@supabase/supabase-js";
import { useWelcomeGroup } from "./useWelcomeGroup";
import { renderWithProviders } from "../test/utils";

vi.mock("../lib/api", () => ({ api: { post: vi.fn() } }));
import { api } from "../lib/api";

let session: Session | null = null;
vi.mock("./useAuth", () => ({ useAuth: () => ({ session }) }));

function Probe() {
  useWelcomeGroup();
  return null;
}

const sessionFor = (userId: string) => ({ user: { id: userId } }) as Session;

describe("useWelcomeGroup", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    session = sessionFor("user-1");
    vi.mocked(api.post).mockResolvedValue({ created: false });
  });

  it("asks the API to seed the account, with the current language", async () => {
    renderWithProviders(<Probe />);
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith("/users/me/welcome", { lang: "en" }),
    );
  });

  it("refetches the groups list only when a group was actually created", async () => {
    vi.mocked(api.post).mockResolvedValue({ created: true });
    const { queryClient } = renderWithProviders(<Probe />);
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    await waitFor(() =>
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ["groups"] }),
    );
  });

  it("leaves the groups list alone when the account already had one", async () => {
    const { queryClient } = renderWithProviders(<Probe />);
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    await waitFor(() => expect(api.post).toHaveBeenCalled());
    expect(invalidate).not.toHaveBeenCalled();
  });

  it("asks once per signed-in user, not once per render", async () => {
    const { rerender } = renderWithProviders(<Probe />);
    rerender(<Probe />);
    rerender(<Probe />);
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
  });

  it("does nothing while signed out", async () => {
    session = null;
    renderWithProviders(<Probe />);
    await waitFor(() => expect(api.post).not.toHaveBeenCalled());
  });

  it("stays silent when the request fails", async () => {
    vi.mocked(api.post).mockRejectedValue(new Error("offline"));
    const { queryClient } = renderWithProviders(<Probe />);
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    await waitFor(() => expect(api.post).toHaveBeenCalled());
    expect(invalidate).not.toHaveBeenCalled();
  });
});
