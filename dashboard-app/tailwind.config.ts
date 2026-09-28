import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-sans)", "Inter", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
        mono: ["var(--font-mono)", "JetBrains Mono", "SF Mono", "Menlo", "monospace"],
        display: ["var(--font-display)", "Space Grotesk", "sans-serif"],
      },
      colors: {
        carbon: {
          950: "#050608",
          900: "#090B0F",
          850: "#0E1117",
          800: "#131720",
          750: "#1A202C",
          700: "#222938",
          600: "#313B4E",
          500: "#48566E",
        },
        laser: {
          emerald: "#00F59B",
          cyan: "#00D2FF",
          amber: "#FFB800",
          crimson: "#FF3856",
        },
      },
      backgroundImage: {
        "grid-pattern": "linear-gradient(to right, rgba(255, 255, 255, 0.03) 1px, transparent 1px), linear-gradient(to bottom, rgba(255, 255, 255, 0.03) 1px, transparent 1px)",
        "dots-pattern": "radial-gradient(rgba(255, 255, 255, 0.08) 1px, transparent 1px)",
      },
    },
  },
  plugins: [],
};
export default config;
