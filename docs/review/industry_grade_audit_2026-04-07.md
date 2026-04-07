# Auditoría Industry-Grade PyME - 2026-04-07

## Estado actual

La auditoría ya produjo hallazgos accionables y parte de ellos ya se empezó a implementar.

### Quick wins ya implementados

1. [I-1] Pre-chequeo de inventario antes de editar ventas.
2. [I-2] Hardening de backups con limpieza previa y validación de espacio libre mínimo.
3. [I-3] Evento operativo `backup_skipped` cuando se omite un backup por falta de espacio.
4. [I-4] Alerta visible en UI para `backup_skipped` en la ventana principal.
5. [I-5] Mejora UX en ventas para clientes eliminados y ayuda de atajos con `F1`.
6. [I-6] Soft-delete y restauración para clientes y productos.
7. [I-7] Audit log persistente para ventas, compras, inventario, clientes y productos.
8. [I-8] Visor y exportación CSV de audit log en UI.

## Hallazgos principales de auditoría

### Confiabilidad operativa

1. [R-1] El flujo de actualización de ventas podía fallar tarde dentro de la transacción cuando el nuevo stock no alcanzaba.
2. [R-2] El sistema de backups no prevenía explícitamente la creación de respaldo con disco insuficiente.
3. [R-3] La omisión de backups por condiciones operativas no llegaba a la UI; dependía de logs.
4. [R-4] Persisten áreas largas y complejas en servicios y UI crítica, especialmente ventas.

### UX / operación diaria

1. [U-1] La vista de ventas tenía tratamiento poco claro para ventas históricas con cliente eliminado.
2. [U-2] Los atajos de teclado existían, pero no eran fácilmente descubribles por caja.
3. [U-3] El flujo de devoluciones sigue ausente como experiencia dedicada.

### Seguridad / compliance intermedio

1. [C-1] Sigue faltando autenticación básica por usuario/PIN.
2. [C-2] Sigue faltando asociar actor autenticado al audit log para trazabilidad por usuario.
3. [C-3] Sigue faltando trazabilidad persistente de fallos operativos relevantes.

## Evidencia y archivos relevantes

### Implementación aplicada

1. [services/sale_service.py](services/sale_service.py)
2. [services/backup_service.py](services/backup_service.py)
3. [utils/system/event_system.py](utils/system/event_system.py)
4. [ui/main_window.py](ui/main_window.py)
5. [ui/sale_view.py](ui/sale_view.py)
6. [services/customer_service.py](services/customer_service.py)
7. [services/product_service.py](services/product_service.py)
8. [ui/customer_view.py](ui/customer_view.py)
9. [ui/product_view.py](ui/product_view.py)
10. [schema.sql](schema.sql)
11. [database/migrations.py](database/migrations.py)
12. [services/audit_service.py](services/audit_service.py)
13. [ui/audit_log_view.py](ui/audit_log_view.py)

### Pruebas agregadas o extendidas

1. [tests/test_services/test_sale_service.py](tests/test_services/test_sale_service.py)
2. [tests/test_backup_service.py](tests/test_backup_service.py)
3. [tests/test_ui/test_sale_view_helpers.py](tests/test_ui/test_sale_view_helpers.py)
4. [tests/test_ui/test_main_window_helpers.py](tests/test_ui/test_main_window_helpers.py)
5. [tests/test_services/test_customer_service.py](tests/test_services/test_customer_service.py)
6. [tests/test_services/test_product_service.py](tests/test_services/test_product_service.py)
7. [tests/test_ui/test_customer_view.py](tests/test_ui/test_customer_view.py)
8. [tests/test_ui/test_product_view.py](tests/test_ui/test_product_view.py)
9. [tests/test_critical_backend_flows.py](tests/test_critical_backend_flows.py)
10. [tests/test_ui/test_audit_log_view.py](tests/test_ui/test_audit_log_view.py)

### Auditorías previas consultadas

1. [docs/review/db_findings.md](docs/review/db_findings.md)
2. [docs/review/perf.md](docs/review/perf.md)
3. [docs/review/security_findings.md](docs/review/security_findings.md)
4. [docs/review/ux_findings.md](docs/review/ux_findings.md)

## Qué falta

### Pendientes de mayor impacto

1. [P-1] Autenticación básica para acceso a la app.
2. [P-2] Flujo dedicado de devoluciones/reembolsos.
3. [P-3] Vista o widget de salud operativa en dashboard.
4. [P-4] Soft-delete consistente para entidades de negocio relevantes.
5. [P-5] Asociar actor autenticado al audit log y exponer filtros por usuario.

### Pendientes técnicos importantes

1. [T-1] Reducir complejidad y tamaño de [ui/sale_view.py](ui/sale_view.py).
2. [T-2] Reducir complejidad y tamaño de [services/sale_service.py](services/sale_service.py).
3. [T-3] Llevar alertas operativas de backup al dashboard, no solo a status bar.
4. [T-4] Agregar más pruebas cross-domain para flujos de eventos, caché y recuperación.
5. [T-5] Consolidar un documento de roadmap de 30 días dentro del repo si se quiere seguimiento formal.

## 5 quick wins priorizados

1. [Q-1] Autenticación básica por PIN o usuario local.
2. [Q-2] Indicador de salud de backups en dashboard.
3. [Q-3] Refactor parcial de ventas para bajar complejidad.
4. [Q-4] Mensajes y labels de ventas más consistentes en español operativo.
5. [Q-5] Filtros por actor autenticado en la bitácora.

## 5 features de mayor valor para nivel industry-grade PyME

1. [F-1] Devoluciones/reembolsos con flujo dedicado.
2. [F-2] Control de acceso por rol básico.
3. [F-3] Bitácora de operaciones y acciones sensibles.
4. [F-4] Alertas de stock bajo integradas en ventas/dashboard.
5. [F-5] Soft-delete y restauración para clientes/productos. Estado: implementado en esta etapa.

## Estado de validación ejecutado

1. Análisis Codacy ejecutado sobre todos los archivos editados en esta etapa.
2. Pruebas focalizadas ejecutadas con éxito para ventas, soft-delete de clientes/productos, audit log y helpers de UI.

## Resumen ejecutivo

La auditoría ya generó resultados concretos y el proyecto ya mejoró en confiabilidad operativa. Sin embargo, todavía no está en nivel industry-grade para PyME desde el punto de vista de control operativo y compliance intermedio. El mayor gap restante ya no es estabilidad básica, sino control: autenticación, trazabilidad y workflows de negocio más completos.

## Backlog ejecutable

Para continuar implementación en otra conversación sin reanalizar el repo completo, usar:

1. [docs/audit/industry_grade_backlog.md](../audit/industry_grade_backlog.md)

## Convención de IDs

1. `I-n`: implementado en esta etapa.
2. `R-n`: hallazgo de confiabilidad.
3. `U-n`: hallazgo de UX/operación.
4. `C-n`: hallazgo de compliance/control.
5. `P-n`: pendiente de mayor impacto.
6. `T-n`: pendiente técnico.
7. `Q-n`: quick win priorizado.
8. `F-n`: feature priorizada.