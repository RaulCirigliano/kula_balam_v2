/** Configuración de build de Tailwind (v3.4). Reemplaza al CDN de desarrollo (cdn.tailwindcss.com).
 *  Las clases se extraen del HTML y de los JS (hay clases construidas en strings de JS). */
module.exports = {
  content: ['./index.html', './js/**/*.js'],
  theme: { extend: {} },
  plugins: [],
};
