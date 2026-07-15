// Brand assets from the SplitDec design system: the split-coin mark and the
// two-tone lowercase wordmark. Coin halves pair light-lead / deep-follow and
// shift one ramp step lighter on dark surfaces.

export function CoinMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden>
      <path
        d="M29 10 A 21 21 0 0 0 29 52 L 29 10 Z"
        className="fill-teal-600 dark:fill-teal-400"
      />
      <path
        d="M35 12 A 21 21 0 0 1 35 54 L 35 12 Z"
        className="fill-teal-700 dark:fill-teal-600"
      />
    </svg>
  );
}

// App-icon tile (fixed dark tile regardless of theme, per the design system).
export function TileMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} role="img" aria-label="SplitDec">
      <rect width="64" height="64" rx="15" fill="#0f172a" />
      <rect
        x="1.5"
        y="1.5"
        width="61"
        height="61"
        rx="13.5"
        fill="none"
        stroke="#134e4a"
        strokeWidth="3"
      />
      <path d="M29 12 A 20 20 0 0 0 29 52 L 29 12 Z" fill="#2dd4bf" />
      <path d="M35 15 A 20 20 0 0 1 35 55 L 35 15 Z" fill="#0d9488" />
    </svg>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`font-extrabold lowercase tracking-[-0.02em] ${className}`}>
      <span className="text-slate-900 dark:text-slate-100">split</span>
      <span className="text-teal-600 dark:text-teal-400">dec</span>
    </span>
  );
}
