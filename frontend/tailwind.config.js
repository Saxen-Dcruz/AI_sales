/** @type {import('tailwindcss').Config} */
/* ============================================================
 * NexusAI — daisyUI abyss-light migration
 * Drop-in replacement for AI_SALES/frontend/tailwind.config.js
 *
 * What changed vs the original:
 *  - `primary` ramp re-mapped to the daisyUI purple
 *    (oklch(70% .183 293)) with a 50→900 ramp built around it.
 *  - New `accent` is the daisyUI cyan (oklch(74% .16 232)).
 *  - `dark` ramp removed — light theme only.
 *  - `surface.*` repurposed for light-theme elevation
 *    (matches base-100 / base-200 / base-300 + white).
 *  - `arc` palette dropped — wasn't used by the live UI.
 *  - boxShadow.glow* re-tinted to the new primary.
 *  - borderRadius scale updated to match the daisyUI shape tokens
 *    (selector 0 / field .25rem / box 2rem).
 *  - borderWidth.DEFAULT bumped to 2px to match `--border: 2px`.
 * ============================================================ */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // daisyUI primary (purple) — oklch(70% .183 293)
        primary: {
          50:  '#f6f1ff',
          100: '#ede2ff',
          200: '#dac6ff',
          300: '#bea0ff',
          400: '#a378ff',
          500: '#8b54f7',  // <-- the brand primary (≈ oklch 70% .183 293)
          600: '#7639e0',
          700: '#5f2bbf',
          800: '#4d2599',
          900: '#3e1f7a',
        },
        // daisyUI accent (cyan) — oklch(74% .16 232)
        accent: {
          50:  '#ecfbff',
          100: '#d1f4ff',
          200: '#a4e9ff',
          300: '#6dd9ff',
          400: '#36c5f5',  // <-- the brand accent (≈ oklch 74% .16 232)
          500: '#1aa8db',
          600: '#0c8bba',
          700: '#0e7095',
          800: '#125b78',
          900: '#114a64',
          // legacy named accents (still used in stat-card chips) — re-map to brand
          blue:   '#36c5f5',
          purple: '#8b54f7',
          cyan:   '#36c5f5',
          green:  '#16a34a',  // oklch 62% .194 149
          orange: '#d97706',  // oklch 68% .162 75
          red:    '#dc2626',  // oklch 57% .245 27
          pink:   '#8b54f7',  // alias to primary purple — pink isn't in the daisy theme
        },
        // Light-theme elevation surfaces — replaces the old dark surface.* set
        surface: {
          DEFAULT: '#f9fbff',  // base-100
          1:       '#f9fbff',
          2:       '#f1f4f9',  // base-200
          3:       '#e6ebf2',  // base-300
          4:       '#d4dae3',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        // daisyUI shape tokens
        selector: '0px',         // checkboxes/toggles — sharp
        field:    '0.25rem',     // buttons / inputs / badges — slight
        box:      '2rem',        // cards / modals — very round
        // keep Tailwind's defaults useful too
        '2xl': '1rem',
        '3xl': '2rem',
      },
      borderWidth: {
        DEFAULT: '2px',          // matches --border: 2px
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
      },
      boxShadow: {
        // re-tinted to the new primary
        'glow':       '0 0 24px rgba(139, 84, 247, 0.30)',
        'glow-lg':    '0 0 48px rgba(139, 84, 247, 0.40)',
        'glow-cyan':  '0 0 24px rgba(54, 197, 245, 0.30)',
        'glow-green': '0 0 24px rgba(22, 163, 74, 0.30)',
        'glow-red':   '0 0 24px rgba(220, 38, 38, 0.30)',
        // light-theme card shadows (cool tint)
        'card':       '0 4px 14px rgba(40, 30, 80, 0.06)',
        'card-hover': '0 8px 28px rgba(40, 30, 80, 0.08)',
      },
      animation: {
        'float': 'float 6s ease-in-out infinite',
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'spin-slow': 'spin 8s linear infinite',
        'gradient': 'gradient 8s ease infinite',
        'shimmer': 'shimmer 2s linear infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        gradient: { 
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
    },
  },
  plugins: [],
}
