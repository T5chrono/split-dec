import { useI18n } from "../lib/i18n";
import { SUPPORT_URL } from "../lib/support";

/** Link to the voluntary-support profile: our own button carrying the
 *  provider's cup.
 *
 *  **Nothing is fetched from buycoffee.to.** The embed code the platform hands
 *  out hotlinks its artwork from their server, which would make every render of
 *  the landing footer a request carrying the visitor's IP and visit time to a
 *  third party — undisclosed view tracking, and the same reason the
 *  transactional emails draw their logo in HTML instead of linking one. It also
 *  keeps `img-src 'self'` intact: needing a CSP change here would mean someone
 *  reverted to the embed.
 *
 *  The button itself is drawn here rather than taken from their panel, because
 *  their green (#00A862 / #1E3932) is not our teal and their artwork may not be
 *  recoloured — it is their mark. Their service rules carry no clause requiring
 *  the official button, which is what makes drawing our own available at all.
 *  The cup is theirs, unaltered: they publish it as a monochrome file in black
 *  and in white, so it sits on our teal without anyone repainting it.
 */
export type SupportVariant = "brand" | "quiet";

const SHELL =
  "inline-flex items-center gap-2 whitespace-nowrap rounded-full px-4 py-2 text-sm font-semibold transition hover:-translate-y-0.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-500";

const SKIN: Record<SupportVariant, string> = {
  brand:
    "bg-teal-600 text-white hover:bg-teal-700 dark:bg-teal-500 dark:text-slate-950 dark:hover:bg-teal-400",
  quiet:
    "border border-teal-600/40 text-teal-700 hover:border-teal-600 hover:bg-teal-50 dark:border-teal-400/40 dark:text-teal-300 dark:hover:bg-teal-950",
};

/** Which cup file each variant shows, light theme first. It follows the
 *  button's own text colour, so both themes work off one rule. */
const MARK: Record<SupportVariant, readonly [string, string]> = {
  brand: ["cup-white", "cup-black"],
  quiet: ["cup-black", "cup-white"],
};

export default function SupportLink({
  variant = "brand",
  className = "",
}: {
  variant?: SupportVariant;
  className?: string;
}) {
  const { t } = useI18n();
  const [markLight, markDark] = MARK[variant];

  return (
    <a
      href={SUPPORT_URL}
      target="_blank"
      rel="noopener noreferrer"
      title={t("supportTitle")}
      className={`${SHELL} ${SKIN[variant]} ${className}`}
    >
      {/* Both carry an empty alt: one of them is always `display:none`, so a
          name on it would be a name that disappears with the theme. The
          visible label names the link in either. */}
      <img
        src={`/buycoffee/${markLight}.png`}
        alt=""
        width={26}
        height={16}
        loading="lazy"
        decoding="async"
        className="block h-4 w-auto dark:hidden"
      />
      <img
        src={`/buycoffee/${markDark}.png`}
        alt=""
        width={26}
        height={16}
        loading="lazy"
        decoding="async"
        className="hidden h-4 w-auto dark:block"
      />
      {t("supportCta")}
    </a>
  );
}
