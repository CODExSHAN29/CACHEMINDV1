import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
    "./context/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#070709",
        "bg-canvas": "#070709",
        surface: "#0c0e14",
        "surface-1": "#0c0e14",
        "surface-2": "#050608",
        "surface-3": "#0f121a",
        "surface-dim": "#050608",
        "surface-container": "#050608",
        border: "#1a2030",
        outline: "#1a2030",
        "outline-variant": "#2a334c",
        "border-main": "#1a2030",
        "border-subtle": "#171b25",
        primary: "#2563eb",
        "primary-deep": "#1d4ed8",
        "primary-bright": "#60a5fa",
        "primary-pressed": "#1e40af",
        "primary-container": "#102044",
        secondary: "#06b6d4",
        "secondary-container": "#083344",
        cyan: {
          400: "#22d3ee",
          500: "#06b6d4",
          900: "#083344",
        },
        emerald: {
          400: "#34d399",
          500: "#10b981",
          900: "#064e3b",
        },
        indigo: {
          400: "#60a5fa",
          500: "#2563eb",
          900: "#102044",
        },
        "on-surface": "#f1f5f9",
        "on-surface-variant": "#94a3b8",
        "on-surface-faint": "#818b9e",
        "on-background": "#f8fafc",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "Inter", "sans-serif"],
        display: ["var(--font-display)", "Space Grotesk", "sans-serif"],
        mono: ["var(--font-mono)", "JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
