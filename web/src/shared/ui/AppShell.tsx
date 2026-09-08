import type { ReactNode } from "react";
import { AuthControls } from "../auth/AuthControls";

export interface AppShellProps {
  readonly children: ReactNode;
}

/** Shared V2 shell: brand header, memory-only auth state and main content. */
export function AppShell({ children }: AppShellProps) {
  return (
    <div className="mf-shell">
      <header className="mf-shell-header">
        <div>
          <span className="mf-eyebrow">MEDIAFLOW</span>
          <h1>V2 migration preview</h1>
        </div>
        <AuthControls />
      </header>
      <main className="mf-shell-main">{children}</main>
    </div>
  );
}
