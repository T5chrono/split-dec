/** The voluntary-support destination.
 *
 *  One constant because three places name it: `SupportLink`, the Terms clause
 *  in `legal.ts` ("What SplitDec costs") and the Privacy Policy's note about
 *  leaving the site. A second copy of this string is a second thing to forget.
 *
 *  Deliberately the profile itself rather than `?tab=subs`: a recurring pledge
 *  is a larger ask than the first click should carry, and the tab is one
 *  control away once someone is there.
 */
export const SUPPORT_URL = "https://buycoffee.to/split-dec";

/** Host shown in prose, so the documents and the link cannot drift apart. */
export const SUPPORT_PROVIDER = "buycoffee.to";
