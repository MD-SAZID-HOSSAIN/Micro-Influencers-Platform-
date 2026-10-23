/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Editorial duo-tone: a warm paper canvas, deep warm ink for type, one terracotta ("ember") accent.
        // The class names the screens already use (ink / mist / brand / nest) keep working; only their values changed.
        // ink   - warm neutrals, 50 is a tint and 900 near-black type.
        ink: {
          50:  '#F4F2EC',
          100: '#E8E4D9',
          200: '#CFC8B7',
          // 300 is for icons, separators and borders: 3.7:1 on the paper canvas (it was 2.5:1).
          300: '#8A816A',
          400: '#6B6452',
          500: '#3F3A2E',
          600: '#2A2620',
          700: '#1B1814',
          800: '#13110E',
          900: '#0B0A08',
        },
        // paper - the cream canvas. 50 is the page and the cards, 100 a soft fill, 200/300 hairlines.
        paper: {
          50:  '#FBF9F3',
          100: '#F4F0E6',
          200: '#E6DFCC',
          300: '#D2C8AC',
          400: '#B5A989',
        },
        // ember - the terracotta accent.
        ember: {
          50:  '#FBEEE6',
          100: '#F4D6C2',
          200: '#E9B294',
          300: '#DC8A66',
          400: '#CC6A42',
          500: '#B8502B',
          600: '#9A3F1F',
          700: '#7A311A',
        },
        // mist - the surface names the screens use. Same values as paper.
        mist: {
          50:  '#FBF9F3',
          100: '#F4F0E6',
          200: '#E6DFCC',
          300: '#D2C8AC',
          400: '#B5A989',
        },
        // brand - the accent the screens use. Same values as ember.
        brand: {
          50:  '#FBEEE6',
          100: '#F4D6C2',
          200: '#E9B294',
          300: '#DC8A66',
          400: '#CC6A42',
          500: '#B8502B',
          600: '#9A3F1F',
          700: '#7A311A',
        },
        // nest - the green for "verified" and other good news.
        nest: {
          50:  '#EAF4EE',
          100: '#CFE6D8',
          400: '#4C9A6F',
          500: '#2E8A5C',
          600: '#1F7A4D',
          700: '#175F3C',
        },
        success: '#1F7A4D',
        danger:  '#B23A48',
        warn:    '#C58A2E',
      },
      fontFamily: {
        display: ['"Fraunces"', 'ui-serif', 'Georgia', 'serif'],
        sans: ['"Inter"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 0 rgba(11,10,8,.04), 0 1px 2px rgba(11,10,8,.04)',
        pop:  '0 14px 40px -16px rgba(11,10,8,.18), 0 2px 6px rgba(11,10,8,.05)',
        ring: 'inset 0 0 0 1px rgba(11,10,8,.06)',
        'brand-glow': '0 0 0 3px rgba(184,80,43,.18)',
      },
      borderRadius: {
        xl:   '10px',
        '2xl':'14px',
        '3xl':'20px',
        '4xl':'28px',
      },
      backgroundImage: {
        'noise-soft':
          "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix values='0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 .04 0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
        'editorial-grid':
          'linear-gradient(to right, rgba(11,10,8,.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(11,10,8,.05) 1px, transparent 1px)',
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
        marquee: {
          '0%':   { transform: 'translateX(0)' },
          '100%': { transform: 'translateX(-50%)' },
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
        marquee:    'marquee 50s linear infinite',
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
