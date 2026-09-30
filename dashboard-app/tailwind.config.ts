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
        background: "#07090e",
        "bg-canvas": "#07090e",
        surface: "#0c1017",
        "surface-1": "#0c1017",
        "surface-2": "#111622",
        "surface-3": "#182030",
        "surface-dim": "#090d14",
        "surface-container": "#111622",
        border: "#1e2638",
        outline: "#1e2638",
        "outline-variant": "#2a364f",
        "border-main": "#1e2638",
        "border-subtle": "#161d2d",
        primary: "#6366f1",
        "primary-deep": "#4f46e5",
        "primary-bright": "#818cf8",
        "primary-pressed": "#4338ca",
        "primary-container": "#1e1b4b",
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
          400: "#818cf8",
          500: "#6366f1",
          900: "#1e1b4b",
        },
        "on-surface": "#f1f5f9",
        "on-surface-variant": "#94a3b8",
        "on-surface-faint": "#64748b",
        "on-background": "#f8fafc",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "Inter", "sans-serif"],
        display: ["var(--font-display)", "Space Grotesk", "sans-serif"],
        mono: ["var(--font-mono)", "JetBrains Mono", "monospace"],
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic": "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "hero-glow": "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(99, 102, 241, 0.25), rgba(6, 182, 212, 0.08), transparent 70%)",
        "card-glow": "radial-gradient(circle at 50% 0%, rgba(99, 102, 241, 0.12), transparent 70%)",
      },
      keyframes: {
        pulseGlow: {
          "0%, 100%": { opacity: "1", filter: "drop-shadow(0 0 12px rgba(99, 102, 241, 0.6))" },
          "50%": { opacity: "0.6", filter: "drop-shadow(0 0 4px rgba(99, 102, 241, 0.2))" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "pulse-glow": "pulseGlow 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        float: "float 5s ease-in-out infinite",
        shimmer: "shimmer 2s infinite",
      },
    },
  },
  plugins: [],
};
export default config;
