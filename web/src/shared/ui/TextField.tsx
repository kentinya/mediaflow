import type { InputHTMLAttributes, ReactNode } from "react";

export interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  readonly id: string;
  readonly label: string;
  readonly hint?: ReactNode;
}

/** Shared labeled text field; never carries or renders token material. */
export function TextField({ id, label, hint, ...rest }: TextFieldProps) {
  return (
    <div className="mf-field">
      <label htmlFor={id}>{label}</label>
      <input id={id} name={id} {...rest} />
      {hint !== undefined ? <p className="mf-field-hint">{hint}</p> : null}
    </div>
  );
}
