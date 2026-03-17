/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // OKLCH Color System - Warm Neutrals
        amber: {
          50: 'oklch(97% 0.005 60)',
          100: 'oklch(93% 0.006 60)',
          400: 'oklch(73% 0.16 85)',
          500: 'oklch(66% 0.19 85)',
          600: 'oklch(59% 0.18 85)',
        },
        gray: {
          50: 'oklch(97% 0.005 60)',
          100: 'oklch(93% 0.006 60)',
          200: 'oklch(88% 0.007 60)',
          300: 'oklch(78% 0.008 60)',
          500: 'oklch(64% 0.009 60)',
          700: 'oklch(45% 0.008 60)',
          800: 'oklch(38% 0.007 60)',
          900: 'oklch(32% 0.007 60)',
        },
        // Status colors
        status: {
          open: '#3b82f6',      // blue
          blocked: '#f59e0b',   // amber
          escalated: '#ef4444', // red
          closed: '#22c55e',    // green
        }
      },
    },
  },
  plugins: [],
};
