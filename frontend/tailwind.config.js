/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Palette taken from the CollabNest logo: navy lettering, a blue → teal arc.
        // ink   — navy-tinted neutrals. 700 is the logo navy (#212F41), 500 the tagline slate.
        ink: {
          50:  '#F4F7FA',
          100: '#E9EEF4',
          200: '#D5DDE7',
          300: '#AAB6C5',
          400: '#7A8798',
          500: '#4E5868',
          600: '#364255',
          700: '#212F41',
          800: '#16212F',
          900: '#0E1826',
        },
        // mist  — cool surfaces. 50 is a card, 100 the page canvas, 200/300 are hairlines.
        mist: {
          50:  '#FFFFFF',
          100: '#F4F7FA',
          200: '#E3E9F0',
          300: '#CBD5E1',
          400: '#A3B1C2',
        },
        // brand — the blue of the arc. 500 passes 4.5:1 against white for text and buttons;
        // 400 is the logo's own blue and is for large decorative fills only.
        brand: {
          50:  '#EAF5FD',
          100: '#CFE8FA',
          200: '#9FD2F5',
          300: '#5DB6EE',
          400: '#0DA0FD',
          500: '#0A78C8',
          600: '#0866A9',
          700: '#064F86',
        },
        // nest  — the teal at the start of the arc. Used sparingly: gradients and "verified".
        nest: {
          50:  '#E6FAF7',
          100: '#C2F3EC',
          400: '#06CAB5',
          500: '#08B3A1',
          600: '#0B8A7E',
          700: '#0A6E65',
        },
        success: '#13795B',
        danger:  '#C23B4B',
        warn:    '#B7791F',
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        sans: ['"Figtree"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(14,24,38,.05), 0 1px 1px rgba(14,24,38,.03)',
        pop:  '0 16px 40px -16px rgba(14,24,38,.22), 0 2px 6px rgba(14,24,38,.06)',
        ring: 'inset 0 0 0 1px rgba(14,24,38,.06)',
        'brand-glow': '0 0 0 3px rgba(10,120,200,.18)',
      },
      borderRadius: {
        xl:   '12px',
        '2xl':'16px',
        '3xl':'20px',
        '4xl':'28px',
      },
      transitionTimingFunction: {
        'out-quint':  'cubic-bezier(0.22, 1, 0.36, 1)',
        'out-expo':   'cubic-bezier(0.16, 1, 0.3, 1)',
        'in-out-quad':'cubic-bezier(0.45, 0, 0.55, 1)',
      },
      keyframes: {
        'fade-up': {
          '0%':   { opacity: '0', transform: 'translateY(14px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'pop-in': {
          '0%':   { opacity: '0', transform: 'translateY(-4px) scale(.98)' },
          '100%': { opacity: '1', transform: 'translateY(0)    scale(1)' },
        },
        'pop-out': {
          '0%':   { opacity: '1', transform: 'translateY(0)    scale(1)' },
          '100%': { opacity: '0', transform: 'translateY(-4px) scale(.98)' },
        },
        'item-in': {
          '0%':   { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '.6' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '.25' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200px 0' },
          '100%': { backgroundPosition: '200px 0' },
        },
        'arc-draw': {
          '0%':   { strokeDashoffset: '1' },
          '100%': { strokeDashoffset: '0' },
        },
        'bird-land': {
          '0%':   { opacity: '0', transform: 'translate(-14px, 10px)' },
          '100%': { opacity: '1', transform: 'translate(0, 0)' },
        },
      },
      animation: {
        'fade-up':  'fade-up .9s cubic-bezier(0.22, 1, 0.36, 1) both',
        'fade-in':  'fade-in 1.2s ease both',
        'pop-in':   'pop-in 160ms cubic-bezier(0.22, 1, 0.36, 1) both',
        'pop-out':  'pop-out 140ms cubic-bezier(0.22, 1, 0.36, 1) both',
        'item-in':  'item-in .5s cubic-bezier(0.22, 1, 0.36, 1) both',
        'pulse-soft': 'pulse-soft 2.4s ease-in-out infinite',
        blink:      'blink 1.6s ease-in-out infinite',
        shimmer:    'shimmer 1.4s linear infinite',
        'arc-draw': 'arc-draw 1.6s cubic-bezier(0.22, 1, 0.36, 1) .25s both',
        'bird-land': 'bird-land .7s cubic-bezier(0.22, 1, 0.36, 1) 1.5s both',
      },
    },
  },
  plugins: [],
};
