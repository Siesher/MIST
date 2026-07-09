import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ["var(--font-jetbrains-mono)", "JetBrains Mono", "ui-monospace", "monospace"],
        display: ["var(--font-space-grotesk)", "Space Grotesk", "system-ui", "sans-serif"],
      },
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        // Cyberpunk palette — direct access
        cyber: {
          bg0: "var(--bg-0)",
          bg1: "var(--bg-1)",
          bg2: "var(--bg-2)",
          bg3: "var(--bg-3)",
          surface: "var(--surface)",
          "surface-hi": "var(--surface-hi)",
          violet: "var(--violet)",
          "violet-bright": "var(--violet-bright)",
          "violet-deep": "var(--violet-deep)",
          yellow: "var(--yellow)",
          "yellow-soft": "var(--yellow-soft)",
          magenta: "var(--magenta)",
          cyan: "var(--cyan)",
          text: "var(--text)",
          "text-dim": "var(--text-dim)",
          "text-muted": "var(--text-muted)",
          "text-ghost": "var(--text-ghost)",
          success: "var(--success)",
          warn: "var(--warn)",
          error: "var(--error)",
          line: "var(--line)",
          "line-hi": "var(--line-hi)",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      boxShadow: {
        "glow-v": "0 0 var(--glow-size) rgba(165, 131, 255, 0.35)",
        "glow-y": "0 0 var(--glow-size) rgba(232, 198, 104, 0.28)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
export default config;
