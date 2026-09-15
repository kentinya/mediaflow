import type { SVGProps } from "react";

export type IconName =
  | "home"
  | "folder"
  | "library"
  | "storage"
  | "rules"
  | "automation"
  | "operations"
  | "notification"
  | "settings"
  | "search"
  | "bell"
  | "chevron-down"
  | "chevron-right"
  | "info"
  | "refresh"
  | "list"
  | "grid"
  | "file"
  | "image"
  | "video"
  | "trash"
  | "more";

export interface IconProps extends SVGProps<SVGSVGElement> {
  readonly name: IconName;
}

/** Small inline icons keep the V2 shell and Files page asset-free and deterministic. */
export function Icon({ name, ...props }: IconProps) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    strokeWidth: 1.8,
    ...props,
  };
  switch (name) {
    case "home":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <path d="m3.5 10.8 8.5-7 8.5 7" />
          <path d="M5.5 9.8v10h13v-10M9.5 19.8v-5h5v5" />
        </svg>
      );
    case "folder":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <path d="M3.5 6.5h6l2 2h9v9.8a1.7 1.7 0 0 1-1.7 1.7H5.2a1.7 1.7 0 0 1-1.7-1.7z" />
          <path d="M3.5 9h17" />
        </svg>
      );
    case "library":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <path d="M4 5.5h16v13H4zM7.5 5.5v13M16.5 5.5v13" />
          <path d="M9.8 8.5h4.4M9.8 12h4.4M9.8 15.5h4.4" />
        </svg>
      );
    case "storage":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <rect x="4" y="4" width="16" height="16" rx="2" />
          <path d="M4 9h16M4 15h16M8 6.5h.01M8 12h.01M8 18h.01" />
        </svg>
      );
    case "rules":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <path d="M12 3.5v17M3.5 12h17" />
          <circle cx="12" cy="12" r="7.2" />
          <path d="m8.5 8.5 7 7M15.5 8.5l-7 7" />
        </svg>
      );
    case "automation":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <circle cx="12" cy="12" r="7.2" />
          <path d="M12 8v4l2.8 1.8M12 3.5v1.3M20.5 12h-1.3M12 19.2v1.3M4.8 12H3.5" />
        </svg>
      );
    case "operations":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <rect x="4" y="4" width="16" height="16" rx="3" />
          <path d="M8 8h8M8 12h5M8 16h8M16 11.5v4.5M13.8 14.2 16 16l2.2-2.2" />
        </svg>
      );
    case "notification":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <path d="M6 17.5h12l-1.2-2v-4.2a4.8 4.8 0 0 0-9.6 0v4.2z" />
          <path d="M10 20.2h4M12 3.3v1" />
        </svg>
      );
    case "settings":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1-1.5 1.5-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5v.2h-2.1v-.2a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1-1.5-1.5.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H6v-2.1h.2a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1 1.5-1.5.1.1a1.6 1.6 0 0 0 1.8.3 1.6 1.6 0 0 0 1-1.5V6h2.1v.2a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1 1.5 1.5-.1.1a1.6 1.6 0 0 0-.3 1.8 1.6 1.6 0 0 0 1.5 1h.2v2.1h-.2a1.6 1.6 0 0 0-1.5 1z" />
        </svg>
      );
    case "search":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <circle cx="10.8" cy="10.8" r="5.8" />
          <path d="m15.2 15.2 5 5" />
        </svg>
      );
    case "bell":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <path d="M6.2 17.4h11.6l-1.3-2.1v-3.9a4.5 4.5 0 0 0-9 0v3.9z" />
          <path d="M10 19.5h4M12 3.2v1" />
        </svg>
      );
    case "chevron-down":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <path d="m6.5 9 5.5 5.5L17.5 9" />
        </svg>
      );
    case "chevron-right":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <path d="m9 6.5 5.5 5.5L9 17.5" />
        </svg>
      );
    case "info":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <circle cx="12" cy="12" r="8.5" />
          <path d="M12 10.5v5M12 7.5h.01" />
        </svg>
      );
    case "refresh":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <path d="M19 10a7 7 0 0 0-12.5-2L5 10M5 10V6.5M5 10h3.5M5 14a7 7 0 0 0 12.5 2l1.5-2M19 14v3.5M19 14h-3.5" />
        </svg>
      );
    case "list":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <path d="M8 6h11M8 12h11M8 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01" />
        </svg>
      );
    case "grid":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <rect x="4.5" y="4.5" width="6" height="6" rx=".5" />
          <rect x="13.5" y="4.5" width="6" height="6" rx=".5" />
          <rect x="4.5" y="13.5" width="6" height="6" rx=".5" />
          <rect x="13.5" y="13.5" width="6" height="6" rx=".5" />
        </svg>
      );
    case "file":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <path d="M6 3.8h8l4 4v12.4H6zM14 3.8v4h4M9 12h6M9 15.5h6" />
        </svg>
      );
    case "image":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <rect x="4" y="5" width="16" height="14" rx="1.5" />
          <circle cx="9" cy="9.5" r="1.2" />
          <path d="m5.5 17 4.2-4 2.8 2.5 2.2-2 3.8 3.5" />
        </svg>
      );
    case "video":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <rect x="4" y="5" width="16" height="14" rx="1.5" />
          <path d="m10 9 5 3-5 3z" />
        </svg>
      );
    case "more":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <circle cx="5" cy="12" r="1" fill="currentColor" stroke="none" />
          <circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" />
          <circle cx="19" cy="12" r="1" fill="currentColor" stroke="none" />
        </svg>
      );
    case "trash":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
          <path d="M4.5 6.5h15M9.5 6.5V4.8h5v1.7M6.5 6.5l.9 12.2a1.6 1.6 0 0 0 1.6 1.5h6a1.6 1.6 0 0 0 1.6-1.5l.9-12.2" />
          <path d="M10 10.5v6M14 10.5v6" />
        </svg>
      );
  }
}
