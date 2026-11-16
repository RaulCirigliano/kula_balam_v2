# Índice de Prompts para Auditorías Externas (Audit-Fix Cycle)

Esta carpeta centraliza los contratos y especificaciones de auditoría técnica utilizados para someter el proyecto a revisión cruzada por modelos de frontera (Claude 3.5 Sonnet, OpenAI o1, Sora, etc.), cumpliendo con el **Protocolo de Auditorías Externas** documentado en [`GEMINI.md`](../../GEMINI.md).

---

## 📌 Documento Central de Auditorías (VIVO Y OBLIGATORIO)

> 👉 **[`GUIA_Y_REGISTRO_DE_AUDITORIAS.md`](./GUIA_Y_REGISTRO_DE_AUDITORIAS.md)**: **Guía Maestra y Bitácora Histórica Unificada**. Contiene el checklist cuantitativo de 6 puntos ciegos y el registro cronológico de todas las intervenciones realizadas (Argon, Antigravity, Claude, Sora). **Es obligatorio mantenerlo actualizado tras cada auditoría.**

---

## 📋 Catálogo de Prompts de Auditoría Externa

| Archivo | Objetivo Principal | Destinatario Recomendado |
| :--- | :--- | :--- |
| **[`GUIA_Y_REGISTRO_DE_AUDITORIAS.md`](./GUIA_Y_REGISTRO_DE_AUDITORIAS.md)** | **Bitácora histórica oficial y Guía Maestra de Inspección Cuantitativa.** | Todo Agente / Desarrollador |
| **[`CLAUDE_SONNET_AUDITOR_PROMPT.md`](./CLAUDE_SONNET_AUDITOR_PROMPT.md)** | Auditoría técnica integral de seguridad financiera, concurrencia, saneamiento de entradas y arquitectura JIT / Cuentas Ómnibus. | Claude 3.5 Sonnet |
| **[`CLAUDE_SONNET_CONTRA_REVISION_PROMPT.md`](./CLAUDE_SONNET_CONTRA_REVISION_PROMPT.md)** | Contra-revisión de cierre de ciclo: verifica que los parches implementados no hayan introducido regresiones ni código roto. | Claude 3.5 Sonnet |
| **[`AUDITORIA_ESTRATEGIAS_Y_ORQUESTADOR_PROMPT.md`](./AUDITORIA_ESTRATEGIAS_Y_ORQUESTADOR_PROMPT.md)** | Auditoría especializada en la Trinchera cuantitativa, filtros ATR, desconexión de Kelly y régimen de comisiones. | Claude / GPT-4o / o1 |
| **[`SORA_AUDITOR_PROMPT.md`](./SORA_AUDITOR_PROMPT.md)** | Auditoría de resiliencia de satélites, contratos de API y robustez de brokers. | Sora / Modelos de Razonamiento |
| **[`CLAUDE_AUDITOR_PROMPT.md`](./CLAUDE_AUDITOR_PROMPT.md)** | Prompt de auditoría general base y verificación de estructura de directorios. | Claude |

---

## 🔄 Protocolo de Uso (Regla GEMINI.md)

1. **Envío:** Copiar íntegramente el prompt correspondiente y enviarlo al modelo auditor externo.
2. **Matriz de Trazabilidad:** Al recibir el diagnóstico, tabular los hallazgos en `[Implementado / Parcial / No implementado / Descartado]`.
3. **Cierre de Ciclo:** Tras implementar las correcciones en el código, ejecutar el prompt de **contra-revisión** para certificar la estabilidad antes de dar por cerrado el hito.
