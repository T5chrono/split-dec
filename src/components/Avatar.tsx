import type { User } from "../lib/types";

export default function Avatar({ user, size = 8 }: { user: User; size?: 6 | 8 | 10 }) {
  const cls = { 6: "h-6 w-6 text-[10px]", 8: "h-8 w-8 text-xs", 10: "h-10 w-10 text-sm" }[size];
  if (user.avatar_url) {
    return (
      <img
        src={user.avatar_url}
        alt={user.full_name ?? user.email}
        referrerPolicy="no-referrer"
        className={`${cls} rounded-full object-cover`}
      />
    );
  }
  const initials = (user.full_name ?? user.email ?? "?")
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return (
    <div
      className={`${cls} flex items-center justify-center rounded-full bg-teal-100 font-semibold text-teal-700 dark:bg-teal-900 dark:text-teal-300`}
    >
      {initials}
    </div>
  );
}
