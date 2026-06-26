/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        pilot: {
          50: '#f0faf5',
          100: '#d4ede1',
          200: '#a8dcc4',
          300: '#6fbf98',
          400: '#1a8a52',
          500: '#005931',
          600: '#004927',
          700: '#003d21',
          800: '#002e19',
          900: '#001f11',
        },
      },
    },
  },
  plugins: [],
};
