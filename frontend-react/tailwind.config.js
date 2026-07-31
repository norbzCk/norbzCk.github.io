/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['selector', '[data-theme="dark"]'],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        /* Colors are now managed via @theme in global.css using CSS
           variable references so dark mode works automatically.
           These are kept as fallbacks for any utility classes that
           might not resolve through @theme. */
        brand: "var(--brand)",
        "brand-strong": "var(--brand-strong)",
        "brand-light": "var(--brand-light)",
        accent: "var(--accent)",
        "accent-strong": "var(--accent-strong)",
        bg: "var(--bg)",
        text: "var(--text)",
        "text-muted": "var(--text-muted)",
        border: "var(--border)",
        danger: "var(--danger)",
        surface: "var(--surface)",
        "surface-soft": "var(--surface-soft)",
        "surface-strong": "var(--surface-strong)",
        "surface-bg": "var(--bg)",
        "dark-bg": "var(--dark-bg)",
        "dark-surface": "var(--dark-surface)",
        "dark-soft": "var(--dark-soft)",
      },
      fontFamily: {
        display: ['Sora', 'sans-serif'],
        sans: ['Inter', 'sans-serif'],
      },
      animation: {
        'soft-enter': 'page-soft-enter 420ms ease both',
        'pulse-btn': 'pulse-btn 2s infinite',
        'marquee': 'marquee 40s linear infinite',
      },
      keyframes: {
        'page-soft-enter': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-btn': {
          '0%, 100%': { boxShadow: '0 4px 16px rgba(15, 90, 166, 0.3)' },
          '50%': { boxShadow: '0 4px 24px rgba(15, 90, 166, 0.5)' },
        },
        marquee: {
          '0%': { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(-50%)' },
        },
      },
    },
  },
  plugins: [],
}
