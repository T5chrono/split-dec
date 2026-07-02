import { Link, Outlet } from "react-router-dom";
import { LogOut, Split } from "lucide-react";
import { useAuth } from "../hooks/useAuth";

export default function Layout() {
  const { session, signOut } = useAuth();
  const meta = session?.user.user_metadata as
    | { full_name?: string; name?: string; avatar_url?: string; picture?: string }
    | undefined;
  const displayName = meta?.full_name ?? meta?.name ?? session?.user.email ?? "";
  const avatar = meta?.avatar_url ?? meta?.picture;

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <Link to="/" className="flex items-center gap-2 text-lg font-bold text-teal-700">
            <Split className="h-5 w-5" />
            SplitDec
          </Link>
          <div className="flex items-center gap-3">
            {avatar && (
              <img src={avatar} alt="" className="h-8 w-8 rounded-full" referrerPolicy="no-referrer" />
            )}
            <span className="hidden text-sm text-slate-600 sm:block">{displayName}</span>
            <button
              onClick={signOut}
              title="Sign out"
              className="rounded-md p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
