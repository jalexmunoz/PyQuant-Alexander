# ESTADO DEL PROYECTO: PyQuant Alexander

## 1. Estado General del Proyecto

**Fase 2: "The Iron Vault" - ✅ COMPLETADA**

Persistencia inmutable en base de datos (Supabase) implementada y funcionando. Todos los eventos de webhooks se guardan automáticamente en Supabase y `run_shadow_mode.py` lee desde Iron Vault correctamente.

**Fase 3: Automatización - 🚀 EN PROGRESO**

Próximos pasos: Automatizar el flujo completo de webhook → Supabase → Shadow Mode → Decisiones.

## 2. Arquitectura del Sistema

- **Capa Base (Datos):** `utils/data_fetcher.py` (TradingView/Binance).

- **Capa Core (Lógica):** Pipeline de 4 fases (Data->Risk->Strategy->Portfolio).

- **Capa Ejecución:** `run_shadow_mode.py` (Principal).

- **Capa Servicios (Punto de Inserción):** `webhook_receiver.py` (Flask).

- **Capa Config/Output:** `config/portfolio.json`, `Output/`.

**Flujo de Datos:**
- **Ingesta:** Directa desde Supabase (DbProvider)

**Contexto Técnico:**
- Cliente DB: Raw HTTP requests (requests) - Python 3.13 compatible
- Antes: postgrest-py SDK (tenía conflictos con Python 3.13)

## 3. Estado de Tareas

### ✅ Fase 2: "The Iron Vault" - COMPLETADA

- [x] Inicializar contexto (_PROJECT_STATUS.md)

- [x] Instalar cliente Supabase (requirements.txt)

- [x] Configurar credenciales (secrets/env vars)

- [x] Crear tabla `raw_events` en Supabase

- [x] Inyectar código de guardado en `webhook_receiver.py`

- [x] Crear db_provider para lectura

- [x] Mejorar herramienta de lectura (timezone-safe con `get_latest_events`)

- [x] Habilitar logs de debug en producción

- [x] Fix imports path para Render

- [x] Fix dependencies: Agregar Flask a requirements.txt

- [x] Fix: Sanitizar variables de entorno (.strip)

- [x] Conectar run_shadow_mode a DB

- [x] Refactor db_provider a Raw HTTP (Python 3.13 compatibilidad)

- [x] Fix: Asegurar carga de .env en db_provider

- [x] Fix: Corregir variable params en db_provider

- [x] Configurar variables en Dashboard de Render

- [x] **PRUEBA END-TO-END EXITOSA:** Webhook → Supabase → Shadow Mode detecta cruces correctamente

### 🚀 Fase 3: Automatización - EN PROGRESO

- [ ] Automatizar ejecución diaria de `run_shadow_mode.py`
- [ ] Configurar scheduler/CRON para ejecución automática
- [ ] Notificaciones de decisiones importantes
- [ ] Dashboard de monitoreo de decisiones
- [ ] Alertas de errores críticos

## 5. Componentes Implementados

### 5.1. Módulo de Persistencia (`utils/supabase_client.py`)
- Cliente PostgREST (`SyncPostgrestClient`) inicializado y exportado a nivel de módulo
- Usa `postgrest-py` directamente (ligero, sin dependencias pesadas como `pyroaring`)
- URL construida como: `{SUPABASE_URL}/rest/v1` (maneja slash final automáticamente)
- Headers configurados: `{"apikey": key, "Authorization": f"Bearer {key}"}`
- Validación estricta de variables de entorno (`SUPABASE_URL`, `SUPABASE_KEY`)
- Lanza excepciones claras si faltan credenciales (fail-fast)
- Cliente disponible globalmente como `supabase_client`

### 5.2. Esquema de Base de Datos (`Docs/supabase_schema.sql`)
- Tabla `raw_events` con estructura simple:
  - `payload` (JSONB): Payload completo del webhook (inmutable)
  - `ticker` (VARCHAR): Asset extraído para indexación
  - `source` (VARCHAR): Fuente del evento (default: "tradingview")
  - `created_at` (TIMESTAMPTZ): Timestamp de inserción (auto)
- Índices GIN en JSONB payload para consultas eficientes
- Índices en ticker, source y created_at para filtrado

### 5.3. Integración en Webhook Receiver (`utils/webhook_receiver.py`)
- Import del cliente Supabase a nivel de módulo (fail-fast si no está configurado)
- Inserción en Supabase **ANTES** de cualquier lógica de negocio (paso 2.5)
- Estructura del insert: `{"payload": data, "ticker": ..., "source": "tradingview"}`
- Fail-safe: Try/except que no detiene el flujo si Supabase falla
- Persistencia dual: Supabase (Iron Vault) + archivo (compatibilidad)

### 5.4. Módulo de Consumo (`utils/db_provider.py`)
- Cliente consumidor para leer eventos desde Iron Vault
- **Implementación:** Raw HTTP requests usando `requests` (Python 3.13 compatible)
- Función `get_events_by_date()`: Consulta por fecha específica via PostgREST API
- Función `get_latest_events()`: Obtiene eventos más recientes (timezone-safe)
- Manejo robusto de errores (retorna lista vacía si falla)
- **Cambio:** Refactorizado desde `postgrest` SDK a `requests` para evitar conflictos de typing en Python 3.13

### 5.5. Script de Prueba (`utils/test_supabase_connection.py`)
- Script standalone para verificar configuración
- Prueba conexión, acceso a tabla e inserción de eventos
- Útil para debugging y validación

### 5.6. Script de Prueba de Consumo (`utils/test_fetch_db.py`)
- Script para probar lectura de eventos desde Iron Vault
- Usa `get_latest_events()` para evitar problemas de timezone
- Muestra eventos recientes con fecha y ticker de forma clara

### 5.7. Documentación (`Docs/IRON_VAULT_SETUP.md`)
- Guía completa de configuración paso a paso
- Troubleshooting y consultas útiles
- Ejemplos de uso

## 4. Reglas Técnicas

- **Atomicidad:** Cambios pequeños y verificables.

- **Persistencia:** Render es solo pasarela; Supabase es la bóveda.

- **Estructura:** Respetar la separación de capas existente.

## 6. Resumen de Fase 2: "The Iron Vault"

### ✅ Logros Completados

1. **Infraestructura de Persistencia:**
   - Tabla `raw_events` creada en Supabase
   - Cliente HTTP directo (Python 3.13 compatible)
   - Integración completa en `webhook_receiver.py`

2. **Integración End-to-End:**
   - Webhook → Supabase: ✅ Funcionando
   - Supabase → Shadow Mode: ✅ Funcionando
   - Detección de cruces: ✅ Funcionando
   - Generación de decisiones: ✅ Funcionando

3. **Validación Exitosa:**
   - Webhook de prueba enviado y recibido
   - Evento guardado en Supabase correctamente
   - `run_shadow_mode.py` detectó evento de cross ON
   - Decisión BUY generada para BTCUSDT
   - Estado de posición actualizado: OFF → ON

### 🔧 Configuración Técnica

- **Cliente DB:** Raw HTTP requests (`requests` library)
- **Compatibilidad:** Python 3.13+
- **Persistencia Dual:** Supabase (primario) + Archivos JSON (compatibilidad)
- **Fail-Safe:** Sistema continúa operando aunque Supabase falle temporalmente

## 7. Próximos Pasos (Fase 3: Automatización)

1. **Automatizar ejecución diaria:**
   - Configurar scheduler (Windows Task Scheduler / CRON) para ejecutar `run_shadow_mode.py` diariamente
   - Horario sugerido: 16:00 ET (después del cierre del mercado)

2. **Monitoreo y alertas:**
   - Sistema de notificaciones para decisiones importantes (BUY/SELL)
   - Dashboard para visualizar decisiones históricas
   - Alertas de errores críticos (fallos en Supabase, errores en webhooks)

3. **Optimizaciones:**
   - Cache de datos de mercado para reducir llamadas a APIs
   - Validación de señales antes de generar decisiones
   - Historial de rendimiento de decisiones

## 8. Archivos Creados/Modificados

### Nuevos Archivos
- `_PROJECT_STATUS.md` - Estado del proyecto (fuente de verdad)
- `utils/supabase_client.py` - Módulo de persistencia Supabase (PostgREST)
- `utils/db_provider.py` - Módulo de consumo para leer eventos (timezone-safe)
- `Docs/supabase_schema.sql` - Esquema de tabla `raw_events`
- `Docs/IRON_VAULT_SETUP.md` - Guía de configuración
- `utils/test_supabase_connection.py` - Script de prueba de conexión
- `utils/test_fetch_db.py` - Script de prueba de consumo (timezone-safe)
- `utils/check_supabase_env.py` - Script de diagnóstico de variables de entorno

### Archivos Modificados
- `requirements.txt` - Agregado `postgrest`, `requests`, `flask`, `gunicorn`, `python-dotenv`
- `utils/webhook_receiver.py` - Integración de persistencia dual (archivo + Supabase) con fail-safe
- `utils/supabase_client.py` - Cliente PostgREST para inserción de eventos
- `utils/db_provider.py` - Refactorizado a Raw HTTP (Python 3.13 compatible)
- `runners/run_shadow_mode.py` - Conectado a Supabase para lectura de eventos
- `utils/test_supabase_connection.py` - Script de validación de conexión
- `utils/test_production.py` - Script de prueba de webhooks en producción
- `utils/test_fetch_db.py` - Script de prueba de lectura desde Supabase

## 9. Estado Actual del Sistema

**✅ FUNCIONANDO:**
- Webhook receiver en Render recibe eventos de TradingView
- Eventos se guardan automáticamente en Supabase (Iron Vault)
- `run_shadow_mode.py` lee eventos desde Supabase correctamente
- Sistema detecta cruces de SMA (ON/OFF) y genera decisiones
- Decisiones se guardan en `Output/shadow/decisions_YYYY-MM-DD.json`
- Portfolio se actualiza según decisiones generadas

**📊 Métricas de Validación:**
- Webhooks recibidos: ✅
- Eventos guardados en Supabase: ✅
- Eventos leídos desde Supabase: ✅
- Cruces detectados: ✅
- Decisiones generadas: ✅

**🚀 Listo para:**
- Fase 3: Automatización diaria
- Integración con TradingView en producción
- Monitoreo continuo de señales

