import { useEffect, useState } from "react";

// Paleta categórica validada (CVD-safe, ordem fixa — nunca reordenar).
const SERIES_LIGHT = [
  "#2a78d6", "#1baf7a", "#eda100", "#008300",
  "#4a3aa7", "#e34948", "#e87ba4", "#eb6834",
];
const SERIES_DARK = [
  "#3987e5", "#199e70", "#c98500", "#008300",
  "#9085e9", "#e66767", "#d55181", "#d95926",
];

export function useDark(): boolean {
  const [dark, setDark] = useState(
    () => window.matchMedia("(prefers-color-scheme: dark)").matches
  );
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const fn = (e: MediaQueryListEvent) => setDark(e.matches);
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, []);
  return dark;
}

export function chartTheme(dark: boolean) {
  return {
    series: dark ? SERIES_DARK : SERIES_LIGHT,
    accent: dark ? "#56bd8c" : "#1c5c43",
    grid: dark ? "#2a2718" : "#ece6d5",
    axis: "#898781",
    surface: dark ? "#1d1a11" : "#fdfcf7",
    negative: dark ? "#e2705f" : "#ab3a2c",
    positive: dark ? "#56bd8c" : "#1c6e4a",
  };
}

export const MESES_LONGOS = [
  "janeiro", "fevereiro", "março", "abril", "maio", "junho",
  "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
];

export function tooltipProps(dark: boolean) {
  return {
    contentStyle: {
      background: dark ? "#242116" : "#fdfcf7",
      border: `1px solid ${dark ? "#322e1f" : "#e4ddc9"}`,
      borderRadius: 10,
      fontSize: 12,
      boxShadow: "0 8px 24px rgba(0,0,0,.14)",
    },
    labelStyle: { color: dark ? "#a79e88" : "#6f6858", fontWeight: 600 },
    itemStyle: { color: dark ? "#f0ead9" : "#211d12" },
  } as const;
}

export const MESES_CURTOS = [
  "jan", "fev", "mar", "abr", "mai", "jun",
  "jul", "ago", "set", "out", "nov", "dez",
];

/** "2026-07" → "jul" */
export function mesCurto(m: string): string {
  return MESES_CURTOS[Number(m.slice(5, 7)) - 1] ?? m;
}

/** Eixo compacto: 1500 → "1,5k" */
export function brlCompacto(v: number): string {
  if (Math.abs(v) >= 1000) {
    return `${(v / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}k`;
  }
  return String(Math.round(v));
}
