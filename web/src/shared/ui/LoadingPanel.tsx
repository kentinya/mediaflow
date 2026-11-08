/**
 * The shared content-shaped waiting state for one bounded read region.
 *
 * It renders a short heading, the read's own explanation and neutral
 * placeholder bars, so a slow response replaces a similarly shaped region
 * instead of a small banner that suddenly expands into a full table. The
 * placeholder is presentation only: it never claims data, never invents a
 * count and never gates a request or an animation.
 */
export function LoadingPanel({
  title,
  detail,
  variant = "rows",
}: {
  readonly title: string;
  readonly detail: string;
  /** `cards` while a library list is pending; `rows` for a bounded read. */
  readonly variant?: "cards" | "rows";
}) {
  const placeholderCount = variant === "cards" ? 3 : 5;
  return (
    <section
      className={[
        // Callers mount this only when the read is genuinely slow (see
        // useReadReveal), so its one appearance eases in instead of popping.
        "mf-wait-reveal",
        variant === "cards"
          ? "mf-library-loading mf-library-loading-cards"
          : "mf-library-loading mf-library-loading-rows",
      ].join(" ")}
      role="status"
      aria-label={title}
    >
      <div className="mf-library-loading-heading">
        <span className="mf-library-loading-pulse" aria-hidden="true" />
        <div>
          <h3>{title}</h3>
          <p>{detail}</p>
        </div>
      </div>
      <div className="mf-library-loading-placeholder" aria-hidden="true">
        {Array.from({ length: placeholderCount }, (_, index) => (
          <span key={index} className="mf-library-loading-bar" />
        ))}
      </div>
    </section>
  );
}
