# input.md — Instrucciones Activas y Normas de Desarrollo (IA-IA)

Este archivo sirve como el canal principal de instrucciones del usuario hacia la IA. También define las reglas de desarrollo y el estado de entrega (handover) entre sesiones de la IA.

---

## 📜 Normas Permanentes para la IA (No Modificar)

1.  **Edición de README:** La IA **no** debe modificar el `README.md` raíz a menos que el usuario lo ordene explícitamente en el chat o en la sección de instrucciones activas.
2.  **Snapshot Histórico:** La IA **nunca** debe modificar archivos dentro del directorio `doc/` durante el desarrollo. Esta carpeta representa el historial o snapshot aprobado. La IA **solo** modificará la carpeta `doc/` al cerrar sesión, es decir, cuando el usuario ejecuta el comando `"me voy"`.
3.  **Directorio Activo Diario:** La IA siempre trabajará y modificará documentos en la carpeta `doc_YYYY-MM-DD/` (según la fecha local del sistema). Si la fecha cambia, la IA creará automáticamente un nuevo directorio `doc_NUEVA_FECHA/` copiando el contenido de la carpeta de la fecha anterior como punto de partida.
4.  **Bitácora de Desarrollo Obligatoria:** Cada cambio en el código o en los archivos de configuración, por mínimo que sea, debe documentarse inmediatamente en el archivo `bitacora_desarrollo.md` de la carpeta activa diaria utilizando el formato de tabla compacta. Al final del turno, la IA debe revisar si el objetivo instantáneo se ha completado e indicarlo explícitamente en la bitácora.
5.  **Actualización de Feedback Obligatorio:** Al finalizar cada turno de interacción, la IA debe actualizar siempre el archivo `feedback.md` de la carpeta activa diaria indicando el estado del proyecto, progresos y bloqueos.
6.  **Preservación de Código:** Mantener docstrings y comentarios existentes en el código que no estén relacionados con la lógica modificada.
7.  **Respuestas del chat ultra-cortas:** Si el usuario inicia su prompt con la palabra `"input"`, la IA procesará las tareas detalladas en la sección de **Instrucciones Activas** de este archivo, actualizará el `feedback.md` de la carpeta activa y responderá en el chat con una frase única: *"feedback actualizado"*. Si el usuario inicia con `"readme"`, la IA leerá el `README.md` de la raíz para orientarse y comenzará a trabajar en las instrucciones que tenga activas.
8. **Gestion de GitHub:** NUNCA se hara commit ni push si el usuario no lo pide explicitamente.
9. **Uso de acentos en .mds y scripts:** No se usaran nunca, si se ve alguno se debe corregir.
---

## 🤖 Protocolo "me voy" (Instrucciones Paso a Paso)

Cuando el usuario escribe `"me voy"` en el chat, la IA debe ejecutar estrictamente este flujo de cierre antes de terminar su ejecución:

1.  **Sincronización:** Copiar todos los archivos `.md` de la carpeta activa diaria (ej: `doc_2026-05-30/`) a la carpeta de snapshot `doc/` para asegurar que el historial maestro queda actualizado.
    *   *Comando:* `cp doc_2026-05-30/*.md doc/`
2.  **Limpieza de Temporales:** Buscar y eliminar todos los archivos resultantes de depuración o pruebas (como imágenes `debug_*` e imágenes de visualización temporales) en la raíz o en los directorios del proyecto para evitar ensuciar el git.
    *   *Comando:* `rm -f debug_*`
3.  **Actualización Final de Estado:**
    *   Asegurar que el `feedback.md` y la `bitacora_desarrollo.md` de la carpeta activa diaria (y ahora también su copia sincronizada en `doc/`) reflejen con precisión las últimas tareas realizadas, si se ha cumplido el objetivo instantáneo, y el resultado del desarrollo.
    *   Actualizar la sección **Estado de Entrega (Handover IA-IA)** de este archivo (`input.md` en la raíz) con el estado actual del repositorio.
4.  **Confirmación en Chat:** Responder con un mensaje único y ultra-corto: *"Sesión cerrada y sincronizada. Temporales eliminados y snapshot en doc/ actualizado."*

---

## 🔄 Estado de Entrega (Handover IA-IA)

*Este apartado lo edita la IA al final de su sesión para dejar constancia de lo que ha hecho y qué debe hacer la siguiente IA.*

*   **Fecha de cierre de sesión:** 2026-05-30
*   **Estado actual:** Reestructuración de documentación completada con éxito. El pipeline de CV clásico está totalmente documentado y listo.
*   **Siguiente paso recomendado para la IA:** Esperar instrucciones del usuario en la sección de "Instrucciones Activas" o en el chat.

---

## 📥 Instrucciones Activas (Usuario)

*Escribe aquí lo que deseas que la IA haga en esta sesión. Cuando termines, escribe en el chat: "input" o "readme".*

*   **Objetivo de la sesión:** [El usuario aún no ha definido tareas activas para esta sesión]
