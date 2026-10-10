/**
 * Semantic colours are CSS variables (so light mode is a variable swap).
 * Tailwind cannot apply an opacity modifier to a bare var() — a class like
 * `bg-surface-overlay/95` silently generated no CSS at all, leaving toasts
 * and the selection bar with transparent backgrounds. color-mix() with
 * Tailwind's <alpha-value> placeholder makes every `/NN` modifier work.
 */
const token = (name) =>
  `color-mix(in srgb, var(--${name}) calc(<alpha-value> * 100%), transparent)`

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      // Semantic tokens backed by CSS variables — one definition per
      // concept, and light mode becomes a variable swap rather than a
      // 187-site find-and-replace.
      colors: {
        surface: {
          DEFAULT: token('surface'),       // page background  (#0f0f0f)
          raised:  token('surface-raised'), // cards           (#141414)
          sunken:  token('surface-sunken'), // tiles, inputs   (#1a1a1a)
          overlay: token('surface-overlay'),// popovers, bars  (#1f1f1f)
          hover:   token('surface-hover'),  // hover fills     (#2a2a2a)
        },
        line: {
          DEFAULT: token('line'),          // subtle borders   (#222)
          strong:  token('line-strong'),   // visible borders  (#333)
          stronger:token('line-stronger'), //                  (#3a3a3a)
        },
        content: {
          DEFAULT: token('content'),       // primary text     (#ececec)
        },
      },
    },
  },
  plugins: [],
}
