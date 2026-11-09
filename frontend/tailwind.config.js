/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "surface": "#080B12",
        "surface-canvas": "#080B12",
        "surface-sidebar": "#0B1019",
        "surface-container-lowest": "#070e1d",
        "surface-container-low": "#0d1424",
        "surface-container": "#111827",
        "surface-container-high": "#172235",
        "surface-container-highest": "#232f48",
        "surface-bright": "#2d3a56",
        "surface-dim": "#080B12",
        "on-surface": "#F5F7FB",
        "on-surface-variant": "#A2AEC0",
        "outline": "#475569",
        "outline-variant": "#243149",
        "primary": "#9B8CFF",
        "primary-container": "#9B8CFF",
        "on-primary": "#080B12",
        "on-primary-container": "#080B12",
        "secondary": "#51DCC8",
        "on-secondary": "#003731",
        "secondary-container": "#00b19f",
        "tertiary": "#6BCBFF",
        "on-tertiary": "#00344a",
        "tertiary-container": "#3ea5d7",
        "accent-amber": "#F4BF69",
        "accent-rose": "#FF7386",
        "error": "#FF7386",
        "error-container": "#93000a",
      },
      fontFamily: {
        sans: ["Geist", "Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        panel: "10px",
        control: "6px",
        badge: "4px",
      },
    },
  },
  plugins: [],
};


