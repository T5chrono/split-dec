import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
} from "react";
import {
  ArrowRight,
  Check,
  Coins,
  Hotel,
  Languages,
  Lock,
  MonitorSmartphone,
  Moon,
  Percent,
  Route,
  ShieldCheck,
  ShoppingCart,
  Sun,
  TrainFront,
  UsersRound,
  UtensilsCrossed,
  type LucideIcon,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useTheme } from "../hooks/useTheme";
import { useI18n, type TKey } from "../lib/i18n";
import { formatMoney } from "../lib/currency";
import { CoinMark, Wordmark } from "../components/Logo";
import GoogleIcon from "../components/GoogleIcon";

/** Fades content in from below the first time it scrolls into view. */
function Reveal({
  children,
  className = "",
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          io.disconnect();
        }
      },
      { threshold: 0.15 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={`reveal ${visible ? "is-visible" : ""} ${className}`}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </div>
  );
}

/** Pointer-following 3D tilt for the hero mockup; inert under reduced motion. */
function useTilt() {
  const ref = useRef<HTMLDivElement>(null);

  const onMouseMove = useCallback((e: ReactMouseEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const rect = el.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width - 0.5;
    const py = (e.clientY - rect.top) / rect.height - 0.5;
    el.style.transform = `perspective(1100px) rotateY(${(px * 8).toFixed(2)}deg) rotateX(${(py * -8).toFixed(2)}deg)`;
  }, []);

  const onMouseLeave = useCallback(() => {
    if (ref.current) ref.current.style.transform = "";
  }, []);

  return { ref, onMouseMove, onMouseLeave };
}

function AuroraBackdrop() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute -left-32 -top-40 h-[34rem] w-[34rem] rounded-full bg-teal-400/30 blur-3xl animate-blob-a dark:bg-teal-500/15" />
      <div className="absolute -right-40 top-1/3 h-[30rem] w-[30rem] rounded-full bg-emerald-300/30 blur-3xl animate-blob-b dark:bg-emerald-400/10" />
      <div className="absolute -bottom-48 left-1/4 h-[36rem] w-[36rem] rounded-full bg-cyan-300/25 blur-3xl animate-blob-c dark:bg-cyan-400/10" />
      <div className="absolute inset-0 [background-image:radial-gradient(circle,rgb(13_148_136/0.18)_1px,transparent_1px)] [background-size:26px_26px] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_40%,black,transparent)]" />
    </div>
  );
}

function DemoAvatar({ initial, className }: { initial: string; className: string }) {
  return (
    <span
      className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ring-2 ring-white dark:ring-slate-900 ${className}`}
    >
      {initial}
    </span>
  );
}

function FloatingChip({
  className,
  animation,
  children,
}: {
  className: string;
  animation: string;
  children: ReactNode;
}) {
  return (
    <div aria-hidden className={`absolute [transform:translateZ(50px)] ${className}`}>
      <div className={animation}>{children}</div>
    </div>
  );
}

/** Static mockup of the app in a desktop browser window — SplitDec is a
 *  web app first, so the hero shows it the way laptops see it. */
function DemoWindow() {
  const { t, membersLabel } = useI18n();
  const tilt = useTilt();

  const rows: Array<{
    icon: LucideIcon;
    desc: string;
    payer: string;
    amount: string;
  }> = [
    { icon: UtensilsCrossed, desc: t("descriptionPlaceholder"), payer: "Ala", amount: "245.0000" },
    { icon: Hotel, desc: t("demoExpenseHotel"), payer: "Ala", amount: "320.0000" },
    { icon: TrainFront, desc: t("demoExpenseCable"), payer: "Tomek", amount: "180.0000" },
    { icon: ShoppingCart, desc: t("demoExpenseGroceries"), payer: "Kuba", amount: "96.5000" },
  ];

  const tabs: TKey[] = ["tabExpenses", "tabBalances", "tabSettlements", "tabMembers"];

  const badge =
    "rounded-xl border border-slate-200/80 bg-white/90 px-3 py-1.5 text-sm font-bold text-teal-700 shadow-lg backdrop-blur dark:border-slate-700 dark:bg-slate-800/90 dark:text-teal-300";

  return (
    <div
      ref={tilt.ref}
      onMouseMove={tilt.onMouseMove}
      onMouseLeave={tilt.onMouseLeave}
      className="relative transition-transform duration-200 ease-out [transform-style:preserve-3d]"
    >
      <FloatingChip animation="animate-float" className="-left-4 -top-5 sm:-left-8">
        <span className={badge}>zł PLN</span>
      </FloatingChip>
      <FloatingChip animation="animate-float-late" className="-right-3 top-40 sm:-right-7">
        <span className={badge}>€ EUR</span>
      </FloatingChip>
      <FloatingChip animation="animate-float-later" className="-bottom-6 -right-2 sm:-right-5">
        <span className={badge}>¥ JPY</span>
      </FloatingChip>
      <FloatingChip animation="animate-float-late" className="-bottom-7 left-8">
        <span className="flex items-center gap-2 rounded-xl bg-teal-600 px-3.5 py-2 text-sm font-semibold text-white shadow-xl shadow-teal-600/30">
          <Check className="h-4 w-4" />
          {t("demoToast")}
        </span>
      </FloatingChip>

      <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white/85 shadow-2xl shadow-teal-900/10 backdrop-blur dark:border-slate-700/80 dark:bg-slate-900/85 dark:shadow-black/40">
        {/* Browser chrome: this is the product's native habitat. */}
        <div className="flex items-center gap-3 border-b border-slate-200/80 bg-slate-100/80 px-4 py-2.5 dark:border-slate-800 dark:bg-slate-950/50">
          <span className="flex gap-1.5">
            <span className="h-3 w-3 rounded-full bg-rose-400/90" />
            <span className="h-3 w-3 rounded-full bg-amber-400/90" />
            <span className="h-3 w-3 rounded-full bg-emerald-400/90" />
          </span>
          <span className="mx-auto flex items-center gap-1.5 whitespace-nowrap rounded-md border border-slate-200 bg-white px-3 py-1 text-xs text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
            <Lock className="h-3 w-3" />
            split-dec.vercel.app
          </span>
          <span aria-hidden className="w-12" />
        </div>

        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-2.5 dark:border-slate-800">
          <span className="flex items-center gap-1.5 text-sm">
            <CoinMark className="h-4.5 w-4.5" />
            <Wordmark />
          </span>
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-teal-100 text-[0.65rem] font-bold text-teal-700 dark:bg-teal-900 dark:text-teal-200">
            T
          </span>
        </div>

        <div className="px-5 pt-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-lg font-bold">{t("groupNamePlaceholder")}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">{membersLabel(3)}</p>
            </div>
            <div className="flex -space-x-2">
              <DemoAvatar initial="A" className="bg-rose-100 text-rose-700 dark:bg-rose-900 dark:text-rose-200" />
              <DemoAvatar initial="T" className="bg-teal-100 text-teal-700 dark:bg-teal-900 dark:text-teal-200" />
              <DemoAvatar initial="K" className="bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-200" />
            </div>
          </div>
          <div className="mt-3 flex gap-1 overflow-x-auto border-b border-slate-100 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden dark:border-slate-800">
            {tabs.map((tab, i) => (
              <span
                key={tab}
                className={`whitespace-nowrap px-2.5 pb-2 text-xs font-semibold sm:px-3 sm:text-sm ${
                  i === 0
                    ? "border-b-2 border-teal-600 text-teal-700 dark:border-teal-400 dark:text-teal-300"
                    : "text-slate-500 dark:text-slate-400"
                }`}
              >
                {t(tab)}
              </span>
            ))}
          </div>
        </div>

        <ul className="divide-y divide-slate-100 dark:divide-slate-800">
          {rows.map(({ icon: Icon, desc, payer, amount }) => (
            <li key={desc} className="flex items-center gap-3 px-5 py-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-teal-600/10 text-teal-700 dark:bg-teal-400/10 dark:text-teal-300">
                <Icon className="h-4.5 w-4.5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold">{desc}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {payer} {t("paidVerb")}
                </p>
              </div>
              <span className="text-sm font-bold tabular-nums">{formatMoney(amount, "PLN")}</span>
            </li>
          ))}
        </ul>

        <div className="border-t border-slate-100 bg-slate-50/80 px-5 py-4 dark:border-slate-800 dark:bg-slate-950/40">
          <p className="mb-2 text-[0.65rem] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
            {t("tabBalances")}
          </p>
          <div className="flex items-center gap-2 text-sm">
            <span className="font-semibold">Kuba</span>
            <ArrowRight className="h-4 w-4 text-slate-400" />
            <span className="font-semibold">Ala</span>
            <span className="ml-auto font-bold tabular-nums text-teal-700 dark:text-teal-300">
              {formatMoney("120.5000", "PLN")}
            </span>
            <span className="rounded-md bg-teal-600 px-2.5 py-1 text-xs font-semibold text-white">
              {t("settle")}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

const MARQUEE_ITEMS = [
  "€ EUR", "$ USD", "zł PLN", "£ GBP", "¥ JPY", "₣ CHF", "Kč CZK", "kr SEK",
  "kr NOK", "kr DKK", "Ft HUF", "$ AUD", "$ CAD", "₴ UAH", "د.ك KWD",
];

function CurrencyMarquee() {
  return (
    <div
      aria-hidden
      className="overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_15%,black_85%,transparent)]"
    >
      <div className="flex w-max animate-marquee">
        {[...MARQUEE_ITEMS, ...MARQUEE_ITEMS].map((item, i) => (
          <span
            key={i}
            className="whitespace-nowrap px-6 text-sm font-semibold tracking-widest text-slate-400 dark:text-slate-600"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

const FEATURES: Array<{ icon: LucideIcon; title: TKey; body: TKey }> = [
  { icon: UsersRound, title: "featGroupsTitle", body: "featGroupsBody" },
  { icon: Coins, title: "featCurrencyTitle", body: "featCurrencyBody" },
  { icon: Route, title: "featSimplifyTitle", body: "featSimplifyBody" },
  { icon: Percent, title: "featSplitTitle", body: "featSplitBody" },
  { icon: MonitorSmartphone, title: "featPwaTitle", body: "featPwaBody" },
  { icon: ShieldCheck, title: "featPrivateTitle", body: "featPrivateBody" },
];

const STEPS: Array<{ title: TKey; body: TKey }> = [
  { title: "landingStep1Title", body: "landingStep1Body" },
  { title: "landingStep2Title", body: "landingStep2Body" },
  { title: "landingStep3Title", body: "landingStep3Body" },
];

export default function LandingPage() {
  const { signInWithGoogle } = useAuth();
  const { theme, toggle } = useTheme();
  const { t, lang, setLang } = useI18n();
  const navigate = useNavigate();

  return (
    <div className="landing relative">
      <header className="fixed inset-x-0 top-0 z-40 border-b border-slate-200/60 bg-white/70 backdrop-blur-md dark:border-slate-800/60 dark:bg-slate-950/60">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <span className="flex items-center gap-1.5 text-lg">
            <CoinMark className="h-6 w-6" />
            <Wordmark />
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setLang(lang === "en" ? "pl" : "en")}
              title={t("language")}
              className="flex items-center gap-1 rounded-md px-2 py-2 text-xs font-semibold uppercase text-slate-500 hover:bg-slate-100 hover:text-slate-800 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            >
              <Languages className="h-4 w-4" />
              {lang === "en" ? "PL" : "EN"}
            </button>
            <button
              onClick={toggle}
              title={theme === "dark" ? t("lightMode") : t("darkMode")}
              className="rounded-md p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <button
              onClick={() => navigate("/login")}
              className="ml-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-700"
            >
              {t("signIn")}
            </button>
          </div>
        </div>
      </header>

      <section className="relative overflow-hidden pb-16 pt-32 sm:pt-40">
        <AuroraBackdrop />
        <div className="mx-auto grid max-w-7xl items-center gap-16 px-4 lg:grid-cols-[1fr_1.2fr] lg:gap-12 xl:gap-16">
          <div>
            <h1
              className="animate-fade-up text-5xl font-extrabold leading-[1.05] tracking-tight sm:text-6xl"
              style={{ animationDelay: "80ms" }}
            >
              {t("landingHeadline1")}
              <br />
              <span className="text-shimmer animate-shimmer">{t("landingHeadline2")}</span>
            </h1>
            <p
              className="mt-6 max-w-xl animate-fade-up text-lg text-slate-600 xl:text-xl dark:text-slate-300"
              style={{ animationDelay: "220ms" }}
            >
              {t("landingSub")}
            </p>
            <div
              className="mt-9 flex animate-fade-up flex-wrap items-center gap-4"
              style={{ animationDelay: "360ms" }}
            >
              <button
                onClick={signInWithGoogle}
                className="group flex items-center gap-3 rounded-xl bg-slate-900 px-6 py-3.5 font-semibold text-white shadow-lg shadow-slate-900/20 transition hover:-translate-y-0.5 hover:shadow-xl dark:bg-white dark:text-slate-900 dark:shadow-white/10"
              >
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white">
                  <GoogleIcon className="h-4 w-4" />
                </span>
                {t("continueWithGoogle")}
                <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
              </button>
              <a
                href="#how"
                className="rounded-xl border border-slate-300 px-6 py-3.5 font-semibold text-slate-700 transition hover:border-teal-500 hover:text-teal-700 dark:border-slate-700 dark:text-slate-200 dark:hover:border-teal-400 dark:hover:text-teal-300"
              >
                {t("landingSeeHow")}
              </a>
            </div>
            <div className="mt-4 animate-fade-up" style={{ animationDelay: "420ms" }}>
              <button
                onClick={() => navigate("/login")}
                className="text-sm font-medium text-teal-700 hover:underline dark:text-teal-300"
              >
                {t("signInWithEmail")}
              </button>
            </div>
            <p
              className="mt-6 animate-fade-up text-sm text-slate-500 dark:text-slate-400"
              style={{ animationDelay: "480ms" }}
            >
              {t("landingTrust")}
            </p>
          </div>

          <div
            aria-hidden
            className="mx-auto w-full min-w-0 max-w-lg animate-fade-up px-4 sm:px-0 lg:max-w-none"
            style={{ animationDelay: "300ms" }}
          >
            <DemoWindow />
          </div>
        </div>
        <div className="mx-auto mt-20 max-w-6xl px-4">
          <CurrencyMarquee />
        </div>
      </section>

      <section id="features" className="py-20 sm:py-28">
        <div className="mx-auto max-w-7xl px-4">
          <Reveal className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-bold uppercase tracking-widest text-teal-600 dark:text-teal-400">
              {t("landingFeaturesKicker")}
            </p>
            <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
              {t("landingFeaturesTitle")}
            </h2>
          </Reveal>
          <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ icon: Icon, title, body }, i) => (
              <Reveal key={title} delay={(i % 3) * 90}>
                <div className="group relative h-full overflow-hidden rounded-2xl border border-slate-200/80 bg-white/70 p-6 backdrop-blur transition duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-teal-500/10 dark:border-slate-800 dark:bg-slate-900/60">
                  <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-teal-500/70 to-transparent opacity-0 transition duration-300 group-hover:opacity-100" />
                  <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-teal-600/10 text-teal-700 ring-1 ring-inset ring-teal-600/20 dark:bg-teal-400/10 dark:text-teal-300 dark:ring-teal-400/20">
                    <Icon className="h-5 w-5" />
                  </span>
                  <h3 className="mt-4 font-bold">{t(title)}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                    {t(body)}
                  </p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section id="how" className="scroll-mt-24 py-20 sm:py-28">
        <div className="mx-auto max-w-7xl px-4">
          <Reveal className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-bold uppercase tracking-widest text-teal-600 dark:text-teal-400">
              {t("landingHowKicker")}
            </p>
            <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
              {t("landingHowTitle")}
            </h2>
          </Reveal>
          <div className="relative mt-14 grid gap-12 md:grid-cols-3 md:gap-8">
            <div
              aria-hidden
              className="absolute left-[16.7%] right-[16.7%] top-7 hidden border-t-2 border-dashed border-teal-600/25 md:block dark:border-teal-400/20"
            />
            {STEPS.map(({ title, body }, i) => (
              <Reveal key={title} delay={i * 120} className="relative text-center">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-teal-600 text-lg font-extrabold text-white shadow-lg shadow-teal-600/30">
                  {i + 1}
                </div>
                <h3 className="mt-5 text-lg font-bold">{t(title)}</h3>
                <p className="mx-auto mt-2 max-w-xs text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                  {t(body)}
                </p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="pb-24 pt-4">
        <div className="mx-auto max-w-7xl px-4">
          <Reveal>
            <div className="relative overflow-hidden rounded-3xl bg-slate-900 px-6 py-16 text-center sm:px-16 dark:bg-slate-900">
              <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
                <div className="absolute -left-24 -top-32 h-80 w-80 rounded-full bg-teal-500/30 blur-3xl animate-blob-a" />
                <div className="absolute -bottom-32 -right-24 h-80 w-80 rounded-full bg-emerald-400/20 blur-3xl animate-blob-b" />
              </div>
              <div className="relative">
                <h2 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
                  {t("landingCtaTitle")}
                </h2>
                <p className="mx-auto mt-4 max-w-xl text-slate-300">{t("landingCtaBody")}</p>
                <button
                  onClick={signInWithGoogle}
                  className="group mx-auto mt-8 flex items-center gap-3 rounded-xl bg-white px-6 py-3.5 font-semibold text-slate-900 shadow-lg transition hover:-translate-y-0.5 hover:bg-slate-100"
                >
                  <GoogleIcon />
                  {t("continueWithGoogle")}
                  <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
                </button>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <footer className="border-t border-slate-200 py-10 dark:border-slate-800">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-4 sm:flex-row">
          <span className="flex items-center gap-1.5">
            <CoinMark className="h-5 w-5" />
            <Wordmark />
          </span>
          <p className="text-sm text-slate-500 dark:text-slate-400">{t("landingFooterTag")}</p>
          <p className="text-sm text-slate-400 dark:text-slate-500">
            © {new Date().getFullYear()} SplitDec
          </p>
        </div>
      </footer>
    </div>
  );
}
