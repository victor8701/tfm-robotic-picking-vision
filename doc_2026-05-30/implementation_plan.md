# Plan de Implementación Final: Reestructuración de Documentación, Automatización de Sesiones y Reglas IA-IA

Este plan finaliza la arquitectura de archivos del proyecto, integra las reglas para la optimización de tokens durante la interacción y establece el protocolo de cierre de sesión ("me voy").

---

## 🔍 Decisiones Técnicas y de Diseño

1.  **Limpieza del repositorio:** Se eliminará por completo la carpeta `assets/`.
2.  **Entorno local:** El sistema correrá localmente en Windows con WSL y GPU NVIDIA GeForce GTX.
3.  **Objetivo de picking simplificado:** Se eliminan referencias a códigos QR y a la clasificación/ordenación de bolsas. El robot debe extraer las bolsas transparentes (todas idénticas) de la caja lo más rápido posible y apilarlas en un Destino B.
4.  **Ubicación de `solucion_deteccion_bolsas_plasticas.md`:** Será un único documento técnico de diseño que vivirá a la **raíz del proyecto**, al mismo nivel que `README.md` e `input.md`. Incluirá las descripciones de las imágenes reales `real1.jpg` a `real6.jpg` de `images/02Dic/`.
5.  **Ubicación de `input.md`:** Estará únicamente en la **raíz del proyecto** como punto de lectura e instrucciones.
6.  **Ubicación de `feedback.md`:** Se creará tanto en `doc/` (snapshot) como en `doc_YYYY-MM-DD/` (activo) para reportar el estado de avance del desarrollo.

---

## 📁 Arquitectura Definitiva de Archivos

```text
tfm-robotic-picking-vision/
├── doc/                        # SNAPSHOT ORIGINAL (De sólo lectura para la IA)
│   ├── implementation_plan.md
│   ├── plan_global.md
│   ├── feedback.md
│   └── bitacora_desarrollo.md
├── doc_2026-05-30/             # CARPETA ACTIVA (Donde escribe la IA hoy)
│   ├── implementation_plan.md
│   ├── plan_global.md
│   ├── feedback.md
│   └── bitacora_desarrollo.md
├── images/                     # Carpeta de datasets e imágenes de test
│   └── 02Dic/
│       └── real1.jpg ... real6.jpg
├── src/                        # Código fuente del pipeline actual
│   ├── main.py
│   ├── deteccion_bolsas.py
│   └── ...
├── README.md                   # Fichero global introductorio (Sólo lectura para la IA)
├── input.md                    # Canal de instrucciones del usuario a la IA (Raíz)
└── solucion_deteccion_bolsas_plasticas.md  # Propuesta técnica de diseño YOLO (Raíz)
```

---

## 🤖 Reglas de Operación e Interacción (Optimización de Tokens)

### 1. Reglas de Comunicación por Chat
*   **Comando "input":** Si el usuario escribe únicamente `"input"` en el chat, la IA leerá directamente `input.md` en la raíz, ejecutará la tarea indicada allí, actualizará el `feedback.md` activo y responderá en el chat de forma ultra-corta: *"feedback actualizado"*.
*   **Comando "readme":** Si el usuario escribe únicamente `"readme"`, la IA leerá el `README.md` de la raíz, se orientará y esperará nuevas instrucciones.
*   **Otros mensajes:** Si el usuario escribe cualquier otra frase, la IA responderá de forma normal.

### 2. Protocolo de Cierre ("me voy")
Cuando el usuario escribe `"me voy"` en el chat o en `input.md`, la IA ejecutará automáticamente las siguientes tareas antes de cerrar el turno:
1.  **Sincronización:** Copiar todos los archivos activos de `doc_YYYY-MM-DD/` a la carpeta original `doc/` para mantener el snapshot aprobado.
2.  **Limpieza:** Borrar cualquier archivo temporal creado durante la ejecución del código (como imágenes de depuración `debug_*`).
3.  **Handover Final:** Escribir un resumen breve en el `feedback.md` activo detallando:
    *   Tareas completadas en la sesión.
    *   Estado actual de los archivos de código.
    *   Siguiente paso inmediato para la siguiente sesión de IA.

### 3. Diario de Desarrollo Optimizado (`bitacora_desarrollo.md`)
Para ahorrar tokens, la bitácora de desarrollo se estructurará como una **tabla markdown compacta** en lugar de párrafos narrativos extensos:

| Fecha | Archivo modificado | Acción corta | Justificación / Test |
| :--- | :--- | :--- | :--- |
| YYYY-MM-DD | `src/main.py` | Modificada func X | Corrección de imports. Test OK. |

---

## 🛠️ Tareas de la Fase Inmediata (Documentación y Limpieza)

1.  **Limpieza:** Eliminar la carpeta `assets/` por completo.
2.  **Estructura de Directorios:** Crear las carpetas `doc/` y `doc_2026-05-30/`.
3.  **Movimiento y Ubicación de Archivos de Raíz:**
    *   Escribir el nuevo `README.md` en la raíz (con la guía para la IA, descripción de módulos y estructura).
    *   Escribir el nuevo `input.md` en la raíz (con las reglas y la sección de comandos).
    *   Mover y actualizar `solucion_deteccion_bolsas_plasticas.md` a la raíz, incluyendo la tabla de descripción de las imágenes reales (`real1` a `real6`).
4.  **Generación de la Documentación en `doc/` y `doc_2026-05-30/`:**
    *   Mover `implementation_plan.md` (este documento) a `doc/` y copiarlo a `doc_2026-05-30/`.
    *   Crear `plan_global.md` en ambas carpetas (con la hoja de ruta del TFM a largo plazo sin códigos QR ni separación de clases).
    *   Crear `feedback.md` en ambas carpetas con el estado inicial.
    *   Crear `bitacora_desarrollo.md` con la tabla compacta vacía.
