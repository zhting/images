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
          DEFAULT: 'var(--surface)',       // page background  (#0f0f0f)
          raised:  'var(--surface-raised)', // cards           (#141414)
          sunken:  'var(--surface-sunken)', // tiles, inputs   (#1a1a1a)
          overlay: 'var(--surface-overlay)',// popovers, bars  (#1f1f1f)
          hover:   'var(--surface-hover)',  // hover fills     (#2a2a2a)
        },
        line: {
          DEFAULT: 'var(--line)',          // subtle borders   (#222)
          strong:  'var(--line-strong)',   // visible borders  (#333)
          stronger:'var(--line-stronger)', //                  (#3a3a3a)
        },
        content: {
          DEFAULT: 'var(--content)',       // primary text     (#ececec)
        },
      },
    },
  },
  plugins: [],
}
