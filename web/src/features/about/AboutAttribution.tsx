import {
  useModalCardExit,
  useModalLayer,
  ModalCardShell,
} from "../../shared/ui/modal-card";

const BASE = import.meta.env.BASE_URL;

/** Same-origin approved TMDB logo; never a remote or proxy image source. */
export const TMDB_LOGO_URL = `${BASE}tmdb-logo.svg`;
/** The required notice, verbatim. */
export const TMDB_ATTRIBUTION_NOTICE =
  "This product uses the TMDB API but is not endorsed or certified by TMDB.";
/** The required link-back target. */
export const TMDB_HOME_URL = "https://www.themoviedb.org";

export interface AboutAttributionCardProps {
  readonly onClose: () => void;
}

/**
 * The one static attribution surface (PATCH-20261108-1 / V2-EXPLORE-010).
 *
 * The ordinary Explore list and detail card no longer repeat a full notice
 * block. The sidebar's "关于与鸣谢" entry opens this shared card instead. It
 * reads no configuration or Provider, starts no request, and reuses the
 * existing card shell for focus, scroll locking and reduced motion.
 */
export function AboutAttributionCard({ onClose }: AboutAttributionCardProps) {
  const exit = useModalCardExit();
  const requestClose = () => exit.beginClose(onClose);
  const layer = useModalLayer({
    onEscape: requestClose,
    fallbackFocusId: "about-attribution-entry",
  });

  return (
    <ModalCardShell
      layerRef={layer.layerRef}
      closing={exit.closing}
      busy={false}
      title="关于与鸣谢"
      titleId="about-attribution-title"
      description="MediaFlow 的产品身份与数据来源"
      closeLabel="关闭关于与鸣谢"
      closeDisabled={exit.closing}
      onRequestClose={requestClose}
      size="detail"
      cardClassName="mf-about-card"
      bodyClassName="mf-about-body"
    >
      <section className="mf-about" aria-label="数据来源与署名">
        <p className="mf-about-product">MediaFlow</p>
        <p className="mf-about-source">
          探索中的作品数据与图片来自 TMDB。TMDB 是外部元数据来源，
          此页不表示作品已入库、已订阅或拥有对应的本地文件。
        </p>
        <a
          className="mf-about-tmdb"
          href={TMDB_HOME_URL}
          target="_blank"
          rel="noreferrer noopener"
        >
          <img src={TMDB_LOGO_URL} alt="TMDB" />
          <span>访问 TMDB 首页 ↗</span>
        </a>
        <p className="mf-about-notice">{TMDB_ATTRIBUTION_NOTICE}</p>
      </section>
    </ModalCardShell>
  );
}
