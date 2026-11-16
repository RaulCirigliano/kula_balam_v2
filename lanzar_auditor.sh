#!/bin/bash
# Lanzador automático del Auditor SQLite para Kula Balam
cd "/home/raul/Escritorio/proyectos/kula_balam"
./venv/bin/python auditar_sqlite.py || python3 auditar_sqlite.py

echo ""
echo "==========================================================================="
echo "🌐 Abriendo automáticamente el Auditor Visual en tu navegador..."
echo "📋 El reporte está copiado en tu portapapeles (Ctrl + V para cualquier IA)."
echo "📁 Archivo directo: ~/Escritorio/ultimo_reporte_boveda.txt"
echo "🗂️  Histórico guardado en: ~/Escritorio/informes_auditoria/"
echo "==========================================================================="
echo ""

# Abrir automáticamente el HTML en el navegador sin preguntar
(google-chrome "http://127.0.0.1:18087/auditor_visual.html" 2>/dev/null || xdg-open "http://127.0.0.1:18087/auditor_visual.html" 2>/dev/null) &

echo "Presiona [ENTER] cuando quieras cerrar esta ventana de terminal..."
read -r
