/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
        mono: ['"Fira Code"', 'monospace'],
      },
      colors: {
        crick: {
          bg: 'var(--bg-primary)',
          surface: 'var(--bg-surface)',
          'text-primary': 'var(--text-primary)',
          'text-secondary': 'var(--text-secondary)',
          accent: '#1a73e8', // Classic Google Blue
          neon: '#4285f4',   // Softer neon blue for glows
          'neon-bright': '#00F0FF', // Brighter cyan for highlights
          'btn-primary-bg': 'var(--btn-primary-bg)',
          'btn-primary-text': 'var(--btn-primary-text)',
        }
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.5s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        }
      }
    },
  },
  plugins: [],
}