/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // ── Editorial theme (FILE 1): cream paper · white cards · black borders ──
        // Values mirror src/styles/tokens.css. Legacy utility names are kept so
        // existing components adopt the new palette without mass edits.
        "bg-base":        "#F3EEE3",   // cream paper canvas
        "bg-panel":       "#FFFFFF",   // white cards
        "bg-panel-alt":   "#F8F3E7",   // cream-tinted surface
        "bg-panel-hover": "#EFE8D8",   // hover wash
        "border-subtle":  "#141414",   // solid black borders
        "border-strong":  "#141414",
        "border-hairline":"#D9D2C0",
        "text-primary":   "#141414",
        "text-secondary": "#45413A",
        "text-muted":     "#837D6E",

        // Legacy accent names — remapped to the editorial palette.
        "accent-cyan":    "#F0503C",   // primary coral red
        "accent-emerald": "#16A34A",   // success green
        "accent-violet":  "#B45309",   // amber (was violet; kept for rare debug text)
        "accent-amber":   "#B45309",   // warning amber, text-safe on cream
        "accent-rose":    "#DC2626",   // danger red

        // ── Legacy gold scale → cream washes / coral accent ──
        "gold-50":  "#F8F3E7",
        "gold-100": "#EFE6D2",
        "gold-300": "#E0D2B4",
        "gold-500": "#F0503C",
        "gold-600": "#D8432F",
        "gold-700": "#B23A2A",

        // ── Success green scale ──
        "green-50":  "#EAF7EF",
        "green-100": "#D5EDDE",
        "green-300": "#7ACD9E",
        "green-500": "#16A34A",
        "green-600": "#15803D",
        "green-700": "#166534",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      fontSize: {
        "2xs": ["10px", { lineHeight: "1.4" }],
      },
      boxShadow: {
        // Hard offset shadows — no soft blur anywhere.
        sm:   "2px 2px 0 #141414",
        md:   "3px 3px 0 #141414",
        lg:   "6px 6px 0 #141414",
        hard: "4px 4px 0 #141414",
        gold: "4px 4px 0 #141414",
        green:"4px 4px 0 #141414",
        none: "0 0 0 #141414",
      },
      borderRadius: {
        sm: "6px",
        md: "8px",
        lg: "12px",
      },
    },
  },
  plugins: [],
};
