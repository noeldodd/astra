// tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // JARVIS status colors
        status: {
          idle: '#6B7280',
          active: '#3B82F6',
          success: '#10B981',
          error: '#EF4444',
          warning: '#F59E0B',
          planning: '#8B5CF6',
          executing: '#3B82F6',
          waiting: '#F59E0B',
          searching: '#06B6D4',
          cached: '#10B981',
          classifying: '#8B5CF6',
          routing: '#3B82F6',
        },
        // Dark theme
        dark: {
          900: '#0F172A',
          800: '#1E293B',
          700: '#334155',
          600: '#475569',
        }
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [],
}