import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        paper: "#FFFFFF",
        ink: "#051230",
        cocoa: "#34454C",
        rose: "#D46D7A",
        rosedeep: "#051230",
        "rose-deep": "#051230",
        blush: "#D46D7A",
        sage: "#96D1AA",
        butter: "#F3A257",
        sky: "#97ACC8",
        kraft: "#B6BFC1",
      },
      borderRadius: {
        card: "20px",
      },
      boxShadow: {
        paper: "0 12px 28px rgba(5, 18, 48, 0.15)",
        tape: "0 3px 8px rgba(5, 18, 48, 0.15)",
      },
      fontFamily: {
        sans: ["var(--font-nunito)", "sans-serif"],
        hand: ["var(--font-caveat)", "cursive"],
      },
    },
  },
  plugins: [],
};

export default config;
