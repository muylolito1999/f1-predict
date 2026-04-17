import { useEffect, useState } from "react";

/** Minimal zero-dep hash router. Returns the current `location.hash` without
 *  the leading '#'. Listens to `hashchange` and updates on the fly. */
export function useHashRoute(): [string, (next: string) => void] {
  const [route, setRoute] = useState<string>(() =>
    typeof window !== "undefined"
      ? window.location.hash.replace(/^#\/?/, "")
      : "",
  );

  useEffect(() => {
    const handler = () =>
      setRoute(window.location.hash.replace(/^#\/?/, ""));
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);

  const go = (next: string) => {
    window.location.hash = next ? `#/${next}` : "";
  };

  return [route, go];
}
