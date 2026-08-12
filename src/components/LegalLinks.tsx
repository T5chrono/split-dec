import { Link } from "react-router-dom";
import { useI18n } from "../lib/i18n";

/** Privacy Policy / Terms links. Reachable signed-out (the landing and login
 *  screens) as well as signed-in — Google's OAuth consent screen requires
 *  both documents to be publicly linked. */
export default function LegalLinks({ className = "" }: { className?: string }) {
  const { t } = useI18n();

  return (
    <nav className={`flex items-center gap-4 text-sm ${className}`}>
      <Link to="/privacy" className="hover:text-teal-700 hover:underline dark:hover:text-teal-300">
        {t("privacyPolicy")}
      </Link>
      <Link to="/terms" className="hover:text-teal-700 hover:underline dark:hover:text-teal-300">
        {t("termsOfService")}
      </Link>
    </nav>
  );
}
