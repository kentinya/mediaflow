export interface CountItem {
  readonly label: string;
  readonly value: number;
}

export interface CountGridProps {
  readonly title: string;
  readonly counts: readonly CountItem[];
}

/** Shared presentation for bounded Dashboard count groups. */
export function CountGrid({ title, counts }: CountGridProps) {
  return (
    <section className="mf-count-section">
      <h3>{title}</h3>
      <ul className="mf-count-grid">
        {counts.map((item) => (
          <li key={item.label} className="mf-count-card">
            <span className="mf-count-value">{item.value}</span>
            <span className="mf-count-label">{item.label}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
