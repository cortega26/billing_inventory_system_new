# Industry-Grade Backlog
> Basado en la auditoría consolidada del 2026-04-07
> Documento fuente: [docs/review/industry_grade_audit_2026-04-07.md](../review/industry_grade_audit_2026-04-07.md)

---

## Cómo usar este backlog

Este backlog está preparado para retomar implementación en una conversación nueva sin re-auditar el repo.

Usa prompts como:

1. `Implementa Phase IG-1 de docs/audit/industry_grade_backlog.md`
2. `Implementa solo IG-2.1 y IG-2.2 de docs/audit/industry_grade_backlog.md`
3. `Haz review de lo implementado para IG-1`

Reglas de ejecución:

1. Implementar por fase o por item, no mezclar bloques grandes si no hace falta.
2. Mantener invariantes del repo descritos en [AGENTS.md](../../AGENTS.md).
3. Priorizar confiabilidad operativa y compliance intermedio antes de features grandes.

---

## Ya implementado en esta etapa

### [D-1] Pre-chequeo de inventario antes de editar ventas
- Estado: completado
- Evidencia: [services/sale_service.py](../../services/sale_service.py), [tests/test_services/test_sale_service.py](../../tests/test_services/test_sale_service.py)

### [D-2] Hardening de backup por espacio libre mínimo y limpieza previa
- Estado: completado
- Evidencia: [services/backup_service.py](../../services/backup_service.py), [tests/test_backup_service.py](../../tests/test_backup_service.py)

### [D-3] Evento `backup_skipped` + alerta visible en UI principal
- Estado: completado
- Evidencia: [utils/system/event_system.py](../../utils/system/event_system.py), [ui/main_window.py](../../ui/main_window.py), [tests/test_ui/test_main_window_helpers.py](../../tests/test_ui/test_main_window_helpers.py)

### [D-4] UX de ventas para cliente eliminado + ayuda F1 de atajos
- Estado: completado
- Evidencia: [ui/sale_view.py](../../ui/sale_view.py), [tests/test_ui/test_sale_view_helpers.py](../../tests/test_ui/test_sale_view_helpers.py)

### [D-5] Soft-delete y restauración para clientes/productos
- Estado: completado
- Evidencia: [services/customer_service.py](../../services/customer_service.py), [services/product_service.py](../../services/product_service.py), [ui/customer_view.py](../../ui/customer_view.py), [ui/product_view.py](../../ui/product_view.py)

### [D-6] Audit log persistente para mutaciones críticas
- Estado: completado
- Evidencia: [services/audit_service.py](../../services/audit_service.py), [services/sale_service.py](../../services/sale_service.py), [services/purchase_service.py](../../services/purchase_service.py), [services/inventory_service.py](../../services/inventory_service.py), [services/customer_service.py](../../services/customer_service.py), [services/product_service.py](../../services/product_service.py), [ui/audit_log_view.py](../../ui/audit_log_view.py), [tests/test_ui/test_audit_log_view.py](../../tests/test_ui/test_audit_log_view.py)

---

## PHASE IG-1 — Compliance intermedio mínimo

Objetivo: dejar la app con control básico de acceso y trazabilidad mínima.

### [IG-1.1] Autenticación básica por PIN o usuario local
- Prioridad: crítica
- Esfuerzo: M
- Qué cambiar:
  1. Agregar una pantalla o diálogo de acceso antes de habilitar la UI principal.
  2. Guardar configuración mínima de credenciales en `config.py` o una tabla dedicada si se elige implementación persistente.
  3. Bloquear apertura completa de [ui/main_window.py](../../ui/main_window.py) hasta autenticar.
- Archivos candidatos:
  1. [ui/main_window.py](../../ui/main_window.py)
  2. [config.py](../../config.py)
  3. [tests/test_system/test_config.py](../../tests/test_system/test_config.py)
- Aceptación:
  1. La app no permite operar sin autenticación.
  2. Existe al menos una prueba de flujo feliz y una de rechazo.

### [IG-1.2] Audit log persistente para operaciones críticas
- Prioridad: crítica
- Esfuerzo: M/L
- Estado: completado
- Qué cambiar:
  1. Crear tabla `audit_log` con tipo de operación, entidad, entidad_id, fecha, payload resumido y actor si existe.
  2. Registrar ventas, compras, ajustes de inventario, borrados y cancelaciones.
  3. Mantener escritura dentro de la misma transacción del flujo cuando corresponda.
- Archivos candidatos:
  1. [schema.sql](../../schema.sql)
  2. [database/migrations.py](../../database/migrations.py)
  3. [services/sale_service.py](../../services/sale_service.py)
  4. [services/purchase_service.py](../../services/purchase_service.py)
  5. [services/inventory_service.py](../../services/inventory_service.py)
- Aceptación:
  1. Cada mutación crítica deja registro persistente.
  2. Hay pruebas que validan escritura y rollback consistente.
  3. Existe visor/export operativo para consultar la bitácora sin depender de SQL manual.

### [IG-1.3] Exponer estado de backup en dashboard
- Prioridad: alta
- Esfuerzo: M
- Qué cambiar:
  1. Mostrar último backup exitoso y último backup omitido/fallido.
  2. Reusar evento `backup_skipped` para señalizar estado visible.
  3. Evitar depender solo de la barra de estado.
- Archivos candidatos:
  1. [ui/dashboard_view.py](../../ui/dashboard_view.py)
  2. [services/backup_service.py](../../services/backup_service.py)
  3. [ui/main_window.py](../../ui/main_window.py)
- Aceptación:
  1. Dashboard refleja estado operativo de backups.
  2. El usuario puede detectar riesgo sin leer logs.

---

## PHASE IG-2 — Robustez de operación diaria

Objetivo: reducir fricción y deuda en la operación de ventas.

### [IG-2.1] Flujo dedicado de devoluciones/reembolsos
- Prioridad: alta
- Esfuerzo: L
- Qué cambiar:
  1. Crear workflow explícito desde ventas históricas o modo devolución.
  2. Restaurar inventario una vez y preservar trazabilidad.
  3. Reusar reglas actuales de cancelación/borrado solo si respetan ledger.
- Archivos candidatos:
  1. [ui/sale_view.py](../../ui/sale_view.py)
  2. [services/sale_service.py](../../services/sale_service.py)
  3. [tests/test_services/test_sale_service.py](../../tests/test_services/test_sale_service.py)
  4. [tests/test_critical_backend_flows.py](../../tests/test_critical_backend_flows.py)
- Aceptación:
  1. Existe flujo de devolución entendible para usuario final.
  2. Inventario y trazabilidad quedan correctos.

### [IG-2.2] Alertas de stock bajo visibles en ventas
- Prioridad: alta
- Esfuerzo: S/M
- Qué cambiar:
  1. Mostrar aviso al agregar items con stock por debajo del umbral.
  2. Reusar la lógica de inventario de stock bajo existente si ya está disponible.
- Archivos candidatos:
  1. [ui/sale_view.py](../../ui/sale_view.py)
  2. [services/inventory_service.py](../../services/inventory_service.py)
  3. [tests/test_services/test_ux_features.py](../../tests/test_services/test_ux_features.py)
- Aceptación:
  1. El cajero ve una alerta antes de quedar sin stock.

### [IG-2.3] Limpiar complejidad de ventas
- Prioridad: media/alta
- Esfuerzo: M
- Qué cambiar:
  1. Extraer helpers/métodos de [ui/sale_view.py](../../ui/sale_view.py).
  2. Extraer validaciones y finalización de mutaciones de [services/sale_service.py](../../services/sale_service.py).
  3. Atacar warnings estructurales de Lizard más críticos.
- Aceptación:
  1. Menor complejidad ciclomática y NLOC en áreas de ventas.
  2. Sin regresión funcional.

---

## PHASE IG-3 — Gestión segura de entidades

Objetivo: preservar historial sin destruir datos de negocio relevantes.

### [IG-3.1] Soft-delete para clientes
- Prioridad: alta
- Esfuerzo: M
- Estado: completado
- Qué cambiar:
  1. Reemplazar borrado destructivo por marca lógica cuando aplique.
  2. Mantener visibilidad histórica consistente en ventas.
- Archivos candidatos:
  1. [schema.sql](../../schema.sql)
  2. [database/migrations.py](../../database/migrations.py)
  3. [services/customer_service.py](../../services/customer_service.py)
  4. [ui/customer_view.py](../../ui/customer_view.py)
- Aceptación:
  1. Las ventas históricas conservan contexto suficiente.
  2. El usuario puede distinguir registro activo vs archivado.

### [IG-3.2] Soft-delete para productos con historial
- Prioridad: alta
- Esfuerzo: M
- Estado: completado
- Qué cambiar:
  1. Archivar productos en lugar de intentar eliminarlos cuando hay ledger.
  2. Excluirlos de búsquedas operativas normales, pero mantener referencia histórica.
- Archivos candidatos:
  1. [services/product_service.py](../../services/product_service.py)
  2. [ui/product_view.py](../../ui/product_view.py)
  3. [tests/test_services/test_product_service.py](../../tests/test_services/test_product_service.py)
- Aceptación:
  1. No se rompe historial de ventas/compras.
  2. UI distingue archivado vs activo.

---

## PHASE IG-4 — Roadmap de features de valor

Objetivo: completar la evolución hacia una app PyME más competitiva.

### [IG-4.1] Recibos más completos: preview + impresión más integrada
- Prioridad: media
- Esfuerzo: M

### [IG-4.2] Roles básicos de usuario
- Prioridad: media/alta
- Esfuerzo: M/L

### [IG-4.3] Dashboard operativo consolidado
- Prioridad: media
- Esfuerzo: M

### [IG-4.4] Mejoras de consistencia de lenguaje en ventas
- Prioridad: media
- Esfuerzo: S/M

### [IG-4.5] Exportes operativos y reportes de auditoría
- Prioridad: media
- Esfuerzo: M

---

## Orden sugerido de implementación

1. IG-1.1
2. IG-1.3
3. IG-2.1
4. IG-2.2
5. IG-2.1
6. IG-3.1
7. IG-3.2
8. IG-2.3

---

## Estado de reanudación rápida

Si se retoma en otra conversación, no hace falta re-auditar el repo completo. Para continuar, basta con usar:

1. [docs/review/industry_grade_audit_2026-04-07.md](../review/industry_grade_audit_2026-04-07.md)
2. [docs/audit/industry_grade_backlog.md](industry_grade_backlog.md)
3. [AGENTS.md](../../AGENTS.md)

Y pedir directamente una fase o item de backlog.

## Convención de IDs

1. `D-n`: implementado.
2. `IG-x.y`: item pendiente del backlog industry-grade.
3. `R-n`, `U-n`, `C-n`, `P-n`, `T-n`, `Q-n`, `F-n`: referencias al informe de auditoría en [docs/review/industry_grade_audit_2026-04-07.md](../review/industry_grade_audit_2026-04-07.md).
