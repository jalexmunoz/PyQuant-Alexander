# ESTADO DEL PROYECTO: PyQuant Alexander

## 1. Misión Actual: "The Iron Vault"

Implementar persistencia inmutable en base de datos (Supabase) para todos los eventos de webhooks entrantes, eliminando la dependencia crítica de archivos JSON efímeros en Render.

## 2. Arquitectura del Sistema

- **Capa Base (Datos):** `utils/data_fetcher.py` (TradingView/Binance).

- **Capa Core (Lógica):** Pipeline de 4 fases (Data->Risk->Strategy->Portfolio).

- **Capa Ejecución:** `run_shadow_mode.py` (Principal).

- **Capa Servicios (Punto de Inserción):** `webhook_receiver.py` (Flask).

- **Capa Config/Output:** `config/portfolio.json`, `Output/`.

**Contexto Técnico:**
- Cliente DB: postgrest-py (directo)

## 3. Estado de Tareas

- [x] Inicializar contexto (_PROJECT_STATUS.md)

- [x] Instalar cliente Supabase (requirements.txt)

- [x] Configurar credenciales (secrets/env vars)

- [ ] Crear tabla `raw_events` en Supabase

- [x] Inyectar código de guardado en `webhook_receiver.py`

- [x] Crear db_provider para lectura

- [x] Mejorar herramienta de lectura (timezone-safe con `get_latest_events`)

- [x] Habilitar logs de debug en producción

- [x] Fix imports path para Render

- [x] Fix dependencies: Agregar Flask a requirements.txt

- [x] Fix: Sanitizar variables de entorno (.strip)

- [ ] Configurar variables en Dashboard de Render

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
- Función `get_events_by_date()`: Consulta por fecha específica
- Función `get_latest_events()`: Obtiene eventos más recientes (timezone-safe)
- Manejo robusto de errores (retorna lista vacía si falla)

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

## 6. Próximos Pasos (Manual)

1. **Instalar dependencias:**
   ```bash
   pip install postgrest
   ```

2. **Configurar credenciales en Render:**
   - `SUPABASE_URL`: URL de tu proyecto Supabase
   - `SUPABASE_KEY`: Service role key (para inserts)
   - Ver `Docs/IRON_VAULT_SETUP.md` para detalles

3. **Crear tabla en Supabase:**
   - Ejecutar `Docs/supabase_schema.sql` en el SQL Editor de Supabase

4. **Verificar funcionamiento:**
   ```bash
   python utils/test_supabase_connection.py
   ```

5. **Enviar webhook de prueba:**
   - Verificar que evento aparece en Supabase
   - Confirmar que archivo JSON sigue funcionando (compatibilidad)

## 7. Archivos Creados/Modificados

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
- `requirements.txt` - Agregado `postgrest` (cliente ligero para Supabase PostgREST)
- `utils/webhook_receiver.py` - Integración de persistencia dual (archivo + Supabase)
- `utils/supabase_client.py` - Reescrito para usar `SyncPostgrestClient` de `postgrest` directamente
- `utils/test_supabase_connection.py` - Actualizado para usar `.from_()` en lugar de `.table()`

