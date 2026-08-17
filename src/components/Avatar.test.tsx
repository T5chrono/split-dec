import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import Avatar from "./Avatar";
import type { User } from "../lib/types";

const user = (avatar_url: string | null): User => ({
  id: "u1",
  email: "ada@test.dev",
  full_name: "Ada Lovelace",
  avatar_url,
});

describe("Avatar", () => {
  it("renders the image when the URL is an allowed Google avatar", () => {
    const src = "https://lh3.googleusercontent.com/a/x=s96-c";
    render(<Avatar user={user(src)} />);

    expect(screen.getByRole("img")).toHaveAttribute("src", src);
  });

  it("falls back to initials for a URL pointing anywhere else", () => {
    // The regression this guards: a member who set their own avatar_url to a
    // host they control would otherwise have every other member's browser
    // fetch it. Initials are the normal empty state, so nothing looks broken.
    render(<Avatar user={user("https://attacker.example/pixel.png")} />);

    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText("AL")).toBeInTheDocument();
  });

  it("falls back to initials for a javascript: URL", () => {
    render(<Avatar user={user("javascript:alert(1)")} />);

    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText("AL")).toBeInTheDocument();
  });

  it("still renders initials when there is no avatar at all", () => {
    render(<Avatar user={user(null)} />);

    expect(screen.getByText("AL")).toBeInTheDocument();
  });
});
