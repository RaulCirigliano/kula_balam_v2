# Guía de Exportación y Descarga en Ubuntu (Git)

Esta guía explica cómo transferir o descargar **únicamente la carpeta `modulo_tres_velas/`** hacia tu computadora con **Ubuntu**, manteniendo la arquitectura desacoplada y sin mezclar código con el resto del proyecto.

---

## 📌 Método 1: Rama Dedicada en Git (Recomendado y más limpio)

Si sincronizas mediante el repositorio Git existente:

### 1. En esta máquina (cuando apruebes subirlo):
```bash
# Crear y cambiar a la rama de la funcionalidad
git checkout -b feature/modulo-tres-velas

# Añadir únicamente la carpeta del módulo
git add modulo_tres_velas/

# Guardar el commit
git commit -m "feat: módulo tres velas con 3 temporalidades y estrategia Wyckoff-Bulkowski"

# Subir la rama al remoto
git push -u origin feature/modulo-tres-velas
```

### 2. En tu PC de Ubuntu:
Puedes optar por descargar **solamente esta carpeta** en tu proyecto de Ubuntu sin necesidad de cambiar toda tu rama principal:

```bash
# Actualizar las referencias remotas
git fetch origin

# Descargar ÚNICAMENTE la carpeta modulo_tres_velas hacia tu rama actual:
git checkout origin/feature/modulo-tres-velas -- modulo_tres_velas/

# Verificar que los archivos llegaron intactos:
ls -la modulo_tres_velas/
```

---

## 📌 Método 2: Git Sparse-Checkout (Bajar Solo Esa Carpeta)

Si en Ubuntu solo quieres tener esta funcionalidad específica sin el resto del repositorio:

```bash
# En Ubuntu: Clonar con sparse-checkout activado
git clone --filter=blob:none --no-checkout <URL_DE_TU_REPOSITORIO> tres_velas_ubuntu
cd tres_velas_ubuntu

# Configurar para que descargue únicamente modulo_tres_velas
git sparse-checkout init --cone
git sparse-checkout set modulo_tres_velas

# Traer los archivos
git checkout feature/modulo-tres-velas
```

---

## 📌 Método 3: Exportación Rápida Directa (Tarball / SCP)

Si prefieres pasar la carpeta directamente por red local o SSH a Ubuntu:

### En Windows (PowerShell):
```powershell
Compress-Archive -Path modulo_tres_velas -DestinationPath modulo_tres_velas.zip
# Enviar por scp a Ubuntu:
scp modulo_tres_velas.zip usuario@ip_ubuntu:~/proyectos/
```

### En Ubuntu:
```bash
unzip modulo_tres_velas.zip -d ~/proyectos/
cd ~/proyectos/modulo_tres_velas
# Abrir directamente en el navegador de Ubuntu:
google-chrome index.html
# o si usas Firefox:
firefox index.html
```

---

## 🧩 Cómo Probarlo en Ubuntu

1. Abre `index.html` en cualquier navegador web moderno (Chrome, Firefox o Brave). Funciona de forma 100% offline y autónoma.
2. Para vincular la estrategia en Python con el backend de `trading_ollama` en Ubuntu:
   - Copia `estrategia_tres_velas.py` a `backend/estrategias/`.
   - Agrégala a `STRATEGY_REGISTRY` en `backend/estrategias/registry.py`.
