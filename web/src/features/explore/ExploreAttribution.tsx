/**
 * The Explore attribution area (Slice 51 Task 51.1 / V2-EXPLORE-010).
 *
 * TMDB's attribution requirements ask for one of their approved logos plus
 * the exact notice "This product uses the TMDB API but is not endorsed or
 * certified by TMDB.", near the source information, less prominent than the
 * application's own mark, with a link back to https://www.themoviedb.org.
 *
 * The logo is the approved `blue_short` asset served from this origin
 * (`/ui-v2/tmdb-logo.svg`), so the fixed V2 `img-src` never widens and no
 * credential, provider host or proxy ever touches an image request. The same
 * area is reused inside the detail card (`compact`) beside the existing
 * source sentence, keeping the notice reachable from both journey points.
 */

const BASE = import.meta.env.BASE_URL;

/** Same-origin approved TMDB logo; never a remote or proxy image source. */
export const TMDB_LOGO_URL = `${BASE}tmdb-logo.svg`;
/** The required notice, verbatim. */
export const TMDB_ATTRIBUTION_NOTICE =
  "This product uses the TMDB API but is not endorsed or certified by TMDB.";
/** The required link-back target. */
export const TMDB_HOME_URL = "https://www.themoviedb.org";

export interface ExploreAttributionProps {
  /** Detail-card form: logo + notice only, next to the source sentence. */
  readonly compact?: boolean;
}

export function ExploreAttribution({
  compact = false,
}: ExploreAttributionProps) {
  return (
    <section
      className={`mf-explore-attribution${
        compact ? " mf-explore-attribution-compact" : ""
      }`}
      aria-label="数据来源与署名"
    >
      <a
        className="mf-explore-attribution-logo"
        href={TMDB_HOME_URL}
        target="_blank"
        rel="noreferrer noopener"
      >
        <img src={TMDB_LOGO_URL} alt="TMDB" />
      </a>
      <p className="mf-explore-attribution-notice">{TMDB_ATTRIBUTION_NOTICE}</p>
      {compact ? null : (
        <p className="mf-explore-attribution-note">
          作品数据与图片来自 TMDB,与本地媒体库无关,本页不表示该作品已入库。
        </p>
      )}
    </section>
  );
}
