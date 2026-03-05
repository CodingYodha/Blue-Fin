/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#05080f",
        surface: "#0b1120",
        surface2: "#101828",
        border: "#1e2d45",
        accent: "#00d4ff",
        accent2: "#7c3aed",
        accent3: "#10b981",
        warn: "#f59e0b",
        danger: "#ef4444",
        muted: "#64748b",
        textprimary: "#e2e8f0",
      },
      fontFamily: {
        mono: ["IBM Plex Mono", "monospace"],
        sans: ["Space Grotesk", "sans-serif"],
      },
    },
  },
  plugins: [],
};
