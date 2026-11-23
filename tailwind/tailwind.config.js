/** نفس إعدادات Tailwind التي كانت داخل base.html */
module.exports = {
  content: ["../templates/**/*.html", "../app.py"],
  theme: {
    extend: {
      fontFamily: { sans: ['Cairo', 'sans-serif'] },
      colors: { ocean: '#0B4F6C', leaf: '#2E8B57', mint: '#88D498', app: '#F4F7F6' },
      boxShadow: {
        soft: '0 10px 40px -10px rgba(0,0,0,0.08)',
        glow: '0 0 20px rgba(46,139,87,0.3)'
      }
    }
  }
};