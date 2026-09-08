import type { ButtonHTMLAttributes, ReactNode } from "react";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  readonly variant?: "primary" | "secondary";
  readonly children: ReactNode;
}

export function Button({
  variant = "primary",
  children,
  ...rest
}: ButtonProps) {
  return (
    <button className={`mf-button mf-button-${variant}`} {...rest}>
      {children}
    </button>
  );
}
