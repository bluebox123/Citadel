import type { Config } from "tailwindcss";
import defaultTheme from "tailwindcss/defaultTheme";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Gilded Noir: Deep obsidian void black
        "noir": {
          "0": "#000000",
          "50": "#0a0a0a",
          "100": "#0f0f0f",
          "200": "#1a1a1a",
          "300": "#2d2d2d",
          "400": "#404040",
          "500": "#525252",
          "600": "#666666",
          "700": "#808080",
        },
        // Neon accents: Warnings (amber) & crypto success (cyan/emerald)
        "accent": {
          "amber": {
            "DEFAULT": "#FCD34D",
            "50": "#FFFBEB",
            "100": "#FEF3C7",
            "200": "#FDE68A",
            "300": "#FCD34D",
            "400": "#FBBF24",
            "500": "#F59E0B",
            "600": "#D97706",
            "700": "#B45309",
            "800": "#92400E",
            "900": "#78350F",
          },
          "cyan": {
            "DEFAULT": "#06B6D4",
            "50": "#ECFDF5",
            "100": "#CFFAFE",
            "200": "#A5F3FC",
            "300": "#67E8F9",
            "400": "#22D3EE",
            "500": "#06B6D4",
            "600": "#0891B2",
            "700": "#0E7490",
            "800": "#155E75",
            "900": "#164E63",
          },
          "emerald": {
            "DEFAULT": "#10B981",
            "50": "#F0FDF4",
            "100": "#DCFCE7",
            "200": "#BBF7D0",
            "300": "#86EFAC",
            "400": "#4ADE80",
            "500": "#22C55E",
            "600": "#16A34A",
            "700": "#15803D",
            "800": "#166534",
            "900": "#145231",
          },
          "neon-cyan": "#0CFFFF",
          "neon-amber": "#FFD700",
        },
        // Subtle grays for hierarchy
        "gray-custom": {
          "dark": "#1a1a1a",
          "mid": "#2d2d2d",
          "light": "#404040",
        },
        // Background
        "bg": {
          "primary": "#0a0a0a",
          "secondary": "#0f0f0f",
          "tertiary": "#1a1a1a",
        },
      },
      fontFamily: {
        // Brutalist sans-serif for headers
        "sans-brutalist": [
          "Space Grotesk",
          "Courier Prime",
          ...defaultTheme.fontFamily.mono,
        ],
        // Strict monospace for crypto data
        "mono-strict": [
          "IBM Plex Mono",
          "JetBrains Mono",
          "Courier New",
          ...defaultTheme.fontFamily.mono,
        ],
        // Default serif for body
        "sans": ["Inter", ...defaultTheme.fontFamily.sans],
      },
      fontSize: {
        // Oversized headers (brutalist scale)
        "xs": ["0.75rem", { lineHeight: "1rem" }],
        "sm": ["0.875rem", { lineHeight: "1.25rem" }],
        "base": ["1rem", { lineHeight: "1.5rem" }],
        "lg": ["1.125rem", { lineHeight: "1.75rem" }],
        "xl": ["1.25rem", { lineHeight: "1.75rem" }],
        "2xl": ["1.5rem", { lineHeight: "2rem" }],
        "3xl": ["1.875rem", { lineHeight: "2.25rem" }],
        "4xl": ["2.25rem", { lineHeight: "2.5rem" }],
        "5xl": ["3rem", { lineHeight: "1" }],
        "6xl": ["3.75rem", { lineHeight: "1" }],
        "7xl": ["4.5rem", { lineHeight: "1" }],
        "8xl": ["6rem", { lineHeight: "1" }],
        "9xl": ["8rem", { lineHeight: "1" }],
      },
      animation: {
        // Subtle, slow animations for depth
        "data-grid": "data-grid 20s linear infinite",
        "fog-drift": "fog-drift 15s ease-in-out infinite",
        "pulse-neon": "pulse-neon 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "glow-amber": "glow-amber 2s ease-in-out infinite",
        "glow-cyan": "glow-cyan 2s ease-in-out infinite",
        "glow-emerald": "glow-emerald 2s ease-in-out infinite",
      },
      keyframes: {
        // Subtle data-grid: faint horizontal lines moving vertically
        "data-grid": {
          "0%": { "background-position": "0 0" },
          "100%": { "background-position": "0 100px" },
        },
        // Fog drift: slow fade in/out for atmospheric depth
        "fog-drift": {
          "0%, 100%": { opacity: "0.05" },
          "50%": { opacity: "0.15" },
        },
        // Neon pulse: strong glow effect
        "pulse-neon": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.7" },
        },
        // Amber glow for warnings
        "glow-amber": {
          "0%, 100%": {
            "text-shadow": "0 0 10px rgba(253, 211, 77, 0.5)",
          },
          "50%": {
            "text-shadow": "0 0 20px rgba(253, 211, 77, 0.8)",
          },
        },
        // Cyan glow for crypto success
        "glow-cyan": {
          "0%, 100%": {
            "text-shadow": "0 0 10px rgba(6, 182, 212, 0.5)",
          },
          "50%": {
            "text-shadow": "0 0 20px rgba(6, 182, 212, 0.8)",
          },
        },
        // Emerald glow for crypto success
        "glow-emerald": {
          "0%, 100%": {
            "text-shadow": "0 0 10px rgba(16, 185, 129, 0.5)",
          },
          "50%": {
            "text-shadow": "0 0 20px rgba(16, 185, 129, 0.8)",
          },
        },
      },
      backgroundImage: {
        // Subtle data grid overlay
        "grid-noir": `linear-gradient(
          0deg,
          rgba(12, 255, 255, 0.03) 1px,
          transparent 1px,
          transparent 50px
        )`,
        // Faint particulate fog
        "fog-overlay": `radial-gradient(
          circle at 20% 50%,
          rgba(6, 182, 212, 0.1) 0%,
          transparent 50%
        ),
        radial-gradient(
          circle at 80% 80%,
          rgba(253, 211, 77, 0.05) 0%,
          transparent 50%
        )`,
      },
      boxShadow: {
        // Neon glows for depth
        "glow-amber": "0 0 20px rgba(253, 211, 77, 0.5)",
        "glow-amber-strong": "0 0 40px rgba(253, 211, 77, 0.7)",
        "glow-cyan": "0 0 20px rgba(6, 182, 212, 0.5)",
        "glow-cyan-strong": "0 0 40px rgba(6, 182, 212, 0.7)",
        "glow-emerald": "0 0 20px rgba(16, 185, 129, 0.5)",
        "glow-emerald-strong": "0 0 40px rgba(16, 185, 129, 0.7)",
      },
      opacity: {
        "5": "0.05",
        "10": "0.1",
        "15": "0.15",
        "20": "0.2",
      },
    },
  },
  plugins: [],
};

export default config;
