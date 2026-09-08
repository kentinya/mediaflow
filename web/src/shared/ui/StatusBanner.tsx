import type { ReactNode } from "react";

export type StatusVariant = "info" | "success" | "warning" | "error";

export interface StatusBannerProps {
  readonly variant: StatusVariant;
  readonly title: string;
  readonly children?: ReactNode;
}

/**
 * Shared bounded status presentation for loading, empty, error,
 * unauthorized and forbidden states. Content is project-authored text;
 * it never renders raw exceptions, headers, tokens or provider payloads.
 */
export function StatusBanner({ variant, title, children }: StatusBannerProps) {
  return (
    <section
      className={`mf-status mf-status-${variant}`}
      role={variant === "error" ? "alert" : "status"}
    >
      <h2>{title}</h2>
      {children}
    </section>
  );
}
