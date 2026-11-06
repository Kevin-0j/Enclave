import { useCallback, useSyncExternalStore } from "react";

export type Theme = "dark" | "light" | "system";
export type GridSize = 1 | 4 | 9;
interface Settings {
  theme: Theme;
  grid: GridSize;
}

const KEY = "enclave.settings.v1";
const DEFAULTS: Settings = { theme: "dark", grid: 4 };
const subs = new Set<() => void>();
let cache: Settings | null = null;

function read(): Settings {
  if (cache) return cache;
  try {
    cache = { ...DEFAULTS, ...(JSON.parse(localStorage.getItem(KEY) ?? "{}") as Partial<Settings>) };
  } catch {
    cache = DEFAULTS;
  }
  return cache;
}

export function applyTheme(theme: Theme): void {
  const dark = theme === "dark" || (theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#070b11" : "#f3f4f6");
}

export function useSettings(): [Settings, (patch: Partial<Settings>) => void] {
  const value = useSyncExternalStore(
    (cb) => {
      subs.add(cb);
      return () => subs.delete(cb);
    },
    read,
    () => DEFAULTS,
  );
  const update = useCallback((patch: Partial<Settings>) => {
    cache = { ...read(), ...patch };
    try {
      localStorage.setItem(KEY, JSON.stringify(cache));
    } catch {
      /* private mode: keep in memory */
    }
    if (patch.theme) applyTheme(patch.theme);
    subs.forEach((s) => s());
  }, []);
  return [value, update];
}
