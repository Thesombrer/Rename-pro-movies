# 🎬 Rename Movies

**Organizador y renombrador inteligente de películas y subtítulos basado en TMDb**

---

## 📌 Descripción

**Rename Movies** es una potente aplicación con interfaz gráfica para Windows que te permite organizar y renombrar automáticamente tus películas y archivos de subtítulos. Utiliza información oficial de **TMDb (The Movie Database)** para validar, corregir y estandarizar nombres, años de estreno y más.

Incluye detección automática de coincidencias, renombrado masivo, control por colores según nivel de confianza y un modo de revisión manual para evitar errores.

---

## 🧑 Autor

**Thesombrer**

---

## 🛠️ Funcionalidades principales

- 🔍 Escaneo automático de carpetas con detección de todos los archivos de video.
- 🧠 Renombrado inteligente según título y año usando TMDb.
- ✅ Ajuste automático de subtítulos (`.srt`, `.ass`, etc.) al nuevo nombre de película.
- 📂 Compatible con archivos en múltiples carpetas y subcarpetas.
- 🧩 Clasificación por colores según nivel de coincidencia:
  - 🟢 Alta confianza
  - 🟡 Media confianza
  - 🔴 No encontrada
  - 🔵 Confirmado manualmente
- 📚 Historial de renombrado para no repetir tareas.
- 🪟 Selector visual cuando hay múltiples coincidencias (elige cuál es tu película).
- 🗃 Interfaz moderna con soporte para múltiples directorios de destino.
- 🔧 Totalmente configurable y libre para modificar.

---
💻 Compatibilidad
✅ Windows (probado)

✅ Código portable para Linux, macOS (requiere adaptar empaquetado y paths)

✅ Ejecutable .py libre para correr en cualquier sistema operativo

## 📦 Requisitos para editar o ejecutar fuera de windws

El programa necesita Python 3.9+ y estas dependencias instaladas:

 pip install tmdbsimple pillow requests langdetect