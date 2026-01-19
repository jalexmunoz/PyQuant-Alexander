# Iron Vault - Guía de Configuración Supabase

## Propósito

Implementar persistencia inmutable en Supabase para todos los eventos de webhooks, eliminando la dependencia crítica de archivos JSON efímeros en Render.

---

## Paso 1: Crear Proyecto en Supabase

1. Ve a [supabase.com](https://supabase.com)
2. Crea una cuenta o inicia sesión
3. Crea un nuevo proyecto
4. Anota:
   - **Project URL** (ej: `https://xxxxx.supabase.co`)
   - **Service Role Key** (en Settings → API)

---

## Paso 2: Crear Tabla `raw_events`

1. En Supabase Dashboard, ve a **SQL Editor**
2. Abre el archivo `Docs/supabase_schema.sql`
3. Copia y pega el contenido completo
4. Ejecuta el script (Run)
5. Verifica que la tabla se creó:
   - Ve a **Table Editor** → deberías ver `raw_events`

---

## Paso 3: Configurar Credenciales en Render

1. En tu servicio de Render (webhook_receiver), ve a **Environment**
2. Agrega las siguientes variables:

```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJhbGc... (service role key)
```

3. **Importante:** 
   - Usa la **Service Role Key**, NO la anon key
   - La Service Role Key tiene permisos para INSERT sin RLS
   - No expongas esta key públicamente

4. Guarda y redeploy el servicio

---

## Paso 4: Verificar Funcionamiento

### 4.1. Verificar que el cliente se inicializa

Revisa los logs de Render después del deploy:
```
[INFO] Supabase client initialized successfully
```

Si ves esto, Supabase está configurado correctamente.

Si ves:
```
[WARNING] Supabase credentials not found...
```
Las variables de entorno no están configuradas correctamente.

### 4.2. Enviar Webhook de Prueba

Envía un webhook de prueba desde TradingView (o usando curl):

```bash
curl -X POST https://your-webhook-service.onrender.com/tradingview \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "your_webhook_secret",
    "ticker": "BTCUSDT",
    "signal": "ON",
    "event_type": "daily_snapshot",
    "price": 50000.0,
    "sma50": 48000.0,
    "sma200": 45000.0
  }'
```

### 4.3. Verificar en Supabase

1. Ve a **Table Editor** → `raw_events`
2. Deberías ver el evento que acabas de enviar
3. Verifica los campos:
   - `event_id`: hash de 16 caracteres
   - `ticker`: "BTCUSDT"
   - `signal`: "ON"
   - `event_type`: "daily_snapshot"
   - `price`, `sma50`, `sma200`: valores numéricos
   - `received_at`: timestamp del evento
   - `created_at`: timestamp de inserción

### 4.4. Verificar en Archivos (Compatibilidad)

1. Verifica que el evento también se guardó en `Output/webhooks/events_YYYY-MM-DD.json`
2. Esto confirma que la persistencia dual está funcionando

---

## Paso 5: Monitoreo y Debugging

### Logs de Render

Busca estos mensajes en los logs:

**Éxito:**
```
[FILE] DAILY_SNAPSHOT: BTCUSDT = ON → events_2025-01-17.json
[SUPABASE] Event saved: abc123... (BTCUSDT daily_snapshot)
```

**Error (Supabase no disponible):**
```
[WARNING] Supabase credentials not found...
[FILE] DAILY_SNAPSHOT: BTCUSDT = ON → events_2025-01-17.json
[SUPABASE] Failed to save event abc123... to database (event still saved to file)
```

**Nota:** Si Supabase falla, el evento SIEMPRE se guarda en el archivo (compatibilidad garantizada).

---

## Estructura de Datos

### Evento de Ejemplo

```json
{
  "event_id": "a1b2c3d4e5f6g7h8",
  "ticker": "BTCUSDT",
  "signal": "ON",
  "event_type": "daily_snapshot",
  "price": 50000.0,
  "sma50": 48000.0,
  "sma200": 45000.0,
  "received_at": "2025-01-17T16:00:00Z",
  "created_at": "2025-01-17T16:00:05Z"
}
```

### Tipos de Eventos

- `daily_snapshot`: Snapshot diario con precio y SMAs
- `cross`: Evento de cruce de SMAs (puede no tener price/sma50/sma200)

---

## Consultas Útiles

### Ver últimos eventos

```sql
SELECT * FROM raw_events 
ORDER BY received_at DESC 
LIMIT 10;
```

### Eventos por ticker

```sql
SELECT * FROM raw_events 
WHERE ticker = 'BTCUSDT' 
ORDER BY received_at DESC;
```

### Eventos por fecha

```sql
SELECT * FROM raw_events 
WHERE DATE(received_at) = '2025-01-17'
ORDER BY received_at;
```

### Contar eventos por tipo

```sql
SELECT event_type, COUNT(*) 
FROM raw_events 
GROUP BY event_type;
```

---

## Troubleshooting

### Error: "Supabase client not available"

**Causa:** Módulo no instalado o import fallido.

**Solución:**
```bash
pip install supabase
```

### Error: "Supabase credentials not found"

**Causa:** Variables de entorno no configuradas.

**Solución:** Verifica que `SUPABASE_URL` y `SUPABASE_KEY` estén en Render Environment.

### Error: "Failed to save event to database"

**Causa:** Problema con la conexión o la tabla no existe.

**Solución:**
1. Verifica que la tabla `raw_events` existe en Supabase
2. Verifica que la Service Role Key es correcta
3. Revisa los logs de Supabase (Dashboard → Logs)

### Eventos no aparecen en Supabase pero sí en archivos

**Causa:** Supabase falla silenciosamente (diseñado así para no romper el flujo).

**Solución:** 
- Revisa los logs para ver el error específico
- Verifica que la tabla existe y tiene los campos correctos
- Prueba la conexión con `test_supabase_connection()`

---

## Seguridad

- **Service Role Key:** Tiene acceso total a la base de datos. NUNCA la expongas públicamente.
- **RLS (Row Level Security):** Opcional. Si lo habilitas, configura políticas apropiadas.
- **Deduplicación:** Los eventos se deduplican por `event_id` (constraint UNIQUE en la tabla).

---

## Arquitectura

```
TradingView Webhook
    ↓
webhook_receiver.py (Flask)
    ↓
    ├─→ Output/webhooks/events_YYYY-MM-DD.json (archivo)
    └─→ Supabase raw_events (base de datos)
```

**Persistencia Dual:**
- Archivos: Compatibilidad y backup local
- Supabase: Bóveda inmutable (Iron Vault)

---

## Estado del Proyecto

Ver `_PROJECT_STATUS.md` para el estado actual de implementación.

