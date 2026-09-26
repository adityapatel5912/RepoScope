/**
 * useKeyboard.ts
 * Global keyboard-shortcut hook. Normalizes Ctrl (Win/Linux) and Cmd (Mac)
 * to "Mod". Example: useKeyboard({ "Mod+k": focus, "Escape": clear }).
 */
import { useEffect, useRef } from "react";

export function useKeyboard(handlers: Record<string, () => void>) {
  // Keep latest handlers without re-binding the listener
  const ref = useRef(handlers);
  ref.current = handlers;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const combo = [
        e.metaKey || e.ctrlKey ? "Mod" : "",
        e.shiftKey ? "Shift" : "",
        e.key.length === 1 ? e.key.toLowerCase() : e.key,
      ].filter(Boolean).join("+");

      // Don't hijack typing — except Mod-combos and Escape
      const el = e.target as HTMLElement | null;
      const typing =
        el?.tagName === "INPUT" || el?.tagName === "TEXTAREA" || el?.isContentEditable;
      if (typing && !combo.startsWith("Mod") && e.key !== "Escape") return;

      const handler = ref.current[combo] ?? ref.current[e.key];
      if (handler) {
        e.preventDefault();
        handler();
      }
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
