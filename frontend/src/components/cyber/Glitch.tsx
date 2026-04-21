import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
  text?: string;
  className?: string;
  as?: keyof JSX.IntrinsicElements;
}

export function Glitch({ children, text, className = "", as: Tag = "span" }: Props) {
  const dataText =
    text ?? (typeof children === "string" ? children : "");
  const Comp = Tag as "span";
  return (
    <Comp className={`glitch ${className}`} data-text={dataText}>
      {children}
    </Comp>
  );
}
