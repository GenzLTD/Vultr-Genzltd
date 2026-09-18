/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx,js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        // T 空间品牌色 — 从 tokens.css 对齐
        't-primary': 'var(--color-primary)',
        't-primary-hover': 'var(--color-primary-hover)',
        't-primary-light': 'var(--color-primary-light)',
        't-bg': 'var(--color-bg-primary)',
        't-bg-secondary': 'var(--color-bg-secondary)',
        't-text': 'var(--color-text-primary)',
        't-text-secondary': 'var(--color-text-secondary)',
        't-text-muted': 'var(--color-text-muted)',
        't-border': 'var(--color-border)',
        't-accent': 'var(--color-accent)',
        // 辅助色
        't-orange': 'var(--color-orange)',
        't-green': 'var(--color-green)',
        't-yellow': 'var(--color-yellow)',
        't-purple': 'var(--color-purple)',
      },
      fontFamily: {
        sans: ['Inter', 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', 'system-ui', 'sans-serif'],
        mono: ['SF Mono', 'Fira Code', 'JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        'xs': '4px',
        'sm': '6px',
        'md': '8px',
        'lg': '12px',
        'xl': '16px',
      },
      boxShadow: {
        'xs': '0 1px 2px rgba(15, 23, 42, 0.04)',
        'sm': '0 1px 3px rgba(15, 23, 42, 0.06)',
        'md': '0 4px 6px rgba(15, 23, 42, 0.05)',
        'lg': '0 10px 15px rgba(15, 23, 42, 0.06)',
        'xl': '0 20px 25px rgba(15, 23, 42, 0.08)',
        'focus': '0 0 0 3px rgba(20, 94, 255, 0.15)',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
