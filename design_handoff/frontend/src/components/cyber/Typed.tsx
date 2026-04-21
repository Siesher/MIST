"use client";

import { useEffect, useState } from "react";

interface Props {
  text: string;
  speed?: number;
  className?: string;
  caret?: boolean;
  onDone?: () => void;
}

export function Typed({ text, speed = 14, className = "", caret = true, onDone }: Props) {
  const [n, setN] = useState(0);

  useEffect(() => {
    setN(0);
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      setN(i);
      if (i >= text.length) {
        clearInterval(id);
        onDone?.();
      }
    }, speed);
    return () => clearInterval(id);
  }, [text, speed, onDone]);

  const done = n >= text.length;
  return (
    <span className={className}>
      {text.slice(0, n)}
      {caret && !done && (
        <span style={{ color: "var(--yellow)", animation: "blink 1s steps(2) infinite" }}>▊</span>
      )}
    </span>
  );
}
