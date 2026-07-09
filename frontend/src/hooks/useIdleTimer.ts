"use client";
import { useEffect, useRef } from "react";

export function useIdleTimer(onIdle: () => void, ms = 180_000, enabled = true) {
  const cb = useRef(onIdle);
  useEffect(() => {
    cb.current = onIdle;
  }, [onIdle]);
  useEffect(() => {
    if (!enabled) return;
    let timer: ReturnType<typeof setTimeout>;
    const reset = () => {
      clearTimeout(timer);
      timer = setTimeout(() => cb.current(), ms);
    };
    const evs = ["mousemove", "keydown", "pointerdown", "scroll"];
    evs.forEach((e) => window.addEventListener(e, reset, { passive: true }));
    reset();
    return () => {
      clearTimeout(timer);
      evs.forEach((e) => window.removeEventListener(e, reset));
    };
  }, [ms, enabled]);
}
