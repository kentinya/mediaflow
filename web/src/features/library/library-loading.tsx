/**
 * One coordinated waiting presentation for both library browse surfaces.
 *
 * The operator can tell the difference between "the library information has
 * not arrived yet", "this directory is being read" and a real empty library or
 * empty directory. The static status text is the accessible feedback; the
 * bars are a bounded visual placeholder that stops animating under
 * `prefers-reduced-motion`. It owns no read, no cache and no business rule, so
 * a fast/cached response simply renders real content instead of this panel.
 */

export function LibraryLoadingPanel({
  title,
  detail,
  variant = "rows",
}: {
  readonly title: string;
  readonly detail: string;
  /** `cards` while the library list is pending; `rows` for a directory read. */
  readonly variant?: "cards" | "rows";
}) {
  const placeholderCount = variant === "cards" ? 3 : 5;
  return (
    <section
      className={
        variant === "cards"
          ? "mf-library-loading mf-library-loading-cards"
          : "mf-library-loading mf-library-loading-rows"
      }
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
