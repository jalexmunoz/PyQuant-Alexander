# utils/webhook_receiver.py
# v2.1.0 - Fixed paths and timezone for Render deployment
#
# Deploy to Render with: python utils/webhook_receiver.py

from flask import Flask, request, jsonify, send_file
import json
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import hashlib
import logging

# Configure logging first (before Supabase import)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# --- LÓGICA DE IMPORTACIÓN ROBUSTA ---
print("🔍 INICIANDO SISTEMA... Verificando dependencias...")
print(f"📂 Directorio actual: {os.getcwd()}")
print(f"🐍 Sys Path: {sys.path}")

SUPABASE_AVAILABLE = False
supabase_client = None

try:
    # Intento 1: Importación absoluta (funciona en local/tests cuando se ejecuta desde raíz)
    print("🔄 Intento 1: Importación absoluta (from utils.supabase_client)...")
    from utils.supabase_client import supabase_client
    SUPABASE_AVAILABLE = True
    print("✅ ÉXITO: Supabase Client importado correctamente (ruta absoluta).")
    logger.info("Supabase client loaded successfully (absolute import)")
except ImportError as e1:
    print(f"⚠️ Intento 1 falló: {e1}")
    try:
        # Intento 2: Importación relativa/directa (funciona en Render cuando se ejecuta dentro de utils/)
        print("🔄 Intento 2: Importación relativa (from supabase_client)...")
        from supabase_client import supabase_client
        SUPABASE_AVAILABLE = True
        print("✅ ÉXITO: Supabase Client importado correctamente (ruta relativa).")
        logger.info("Supabase client loaded successfully (relative import)")
    except ImportError as e2:
        SUPABASE_AVAILABLE = False
        supabase_client = None
        print(f"🛑 ERROR CRÍTICO DE IMPORTACIÓN: Ambos intentos fallaron")
        print(f"   Intento 1 (absoluto): {e1}")
        print(f"   Intento 2 (relativo): {e2}")
        logger.warning(f"Supabase client not available (Iron Vault disabled). Import errors: {e1}, {e2}")
except (ValueError, RuntimeError) as e:
    SUPABASE_AVAILABLE = False
    supabase_client = None
    print(f"🛑 ERROR CRÍTICO: Error al inicializar Supabase Client. Causa: {e}")
    logger.warning(f"Supabase client not available (Iron Vault disabled): {e}")
except Exception as e:
    SUPABASE_AVAILABLE = False
    supabase_client = None
    print(f"🛑 ERROR DESCONOCIDO al importar: {e}")
    logger.warning(f"Supabase client not available (Iron Vault disabled): {e}")
# -------------------------------------

app = Flask(__name__)

# SHARED SECRET
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "pyquant_shadow_2025_xyz123")

# TIMEZONE
APP_TZ = ZoneInfo("America/New_York")

# OUTPUT DIRECTORY - Anchored to repo root (not relative to utils/)
BASE_DIR = Path(__file__).resolve().parents[1]  # Go up from utils/ to repo root
OUTPUT_DIR = BASE_DIR / "Output" / "webhooks"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logger.info(f"Base directory: {BASE_DIR}")
logger.info(f"Output directory: {OUTPUT_DIR}")


def get_local_date_key(dt_utc: datetime) -> str:
    """Convert UTC datetime to America/New_York date string (YYYY-MM-DD)."""
    return dt_utc.astimezone(APP_TZ).date().isoformat()


def get_events_file(date_str: str) -> Path:
    """Get path to events file for given date."""
    return OUTPUT_DIR / f"events_{date_str}.json"


def get_event_id(data: dict) -> str:
    """Generate unique event ID for deduplication."""
    today = get_local_date_key(datetime.now(timezone.utc))
    key = f"{data.get('ticker')}_{data.get('event_type')}_{today}_{data.get('signal')}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def load_events_today() -> set:
    """Load today's event IDs for deduplication."""
    today = get_local_date_key(datetime.now(timezone.utc))
    log_file = get_events_file(today)
    
    if not log_file.exists():
        return set()
    
    events = set()
    try:
        with open(log_file, 'r') as f:
            for line in f:
                if line.strip():
                    event = json.loads(line)
                    events.add(event.get('event_id'))
    except Exception as e:
        logger.warning(f"Error loading events: {e}")
    
    return events


# ============ HEALTH CHECK ============
@app.route('/', methods=['GET', 'HEAD'])
def health_check():
    """Health check endpoint for Render."""
    return jsonify({
        "status": "ok",
        "service": "pyquant-webhooks",
        "version": "2.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(OUTPUT_DIR)
    }), 200


# ============ WEBHOOK ENDPOINT ============
@app.route('/tradingview', methods=['POST'])
def tv_webhook():
    try:
        # 1. LOG RAW REQUEST
        raw_data = request.data.decode('utf-8')
        logger.info(f"[RAW] Content-Type: {request.content_type}")
        logger.info(f"[RAW] Body: {raw_data[:500]}")
        
        # 2. PARSE JSON
        if request.is_json:
            data = request.json
        else:
            data = json.loads(raw_data)
        
        logger.info(f"[PARSED] {json.dumps(data)}")
        
        # 2.5. IRON VAULT: Save to Supabase BEFORE business logic (fail-safe)
        # DEBUG: Check credentials availability
        print(f"DEBUG: Supabase URL configured: {bool(os.environ.get('SUPABASE_URL'))}")
        print(f"DEBUG: Supabase KEY configured: {bool(os.environ.get('SUPABASE_KEY'))}")
        print(f"DEBUG: SUPABASE_AVAILABLE: {SUPABASE_AVAILABLE}")
        print(f"DEBUG: supabase_client is None: {supabase_client is None}")
        
        if SUPABASE_AVAILABLE and supabase_client is not None:
            try:
                # Structure as specified: payload + ticker + source
                insert_payload = {
                    "payload": data,  # Full raw payload
                    "ticker": data.get("ticker", "UNKNOWN"),
                    "source": "tradingview"
                }
                
                print(f"DEBUG: Intentando insertar payload en raw_events...")
                print(f"DEBUG: Payload ticker: {insert_payload.get('ticker')}")
                print(f"DEBUG: Payload source: {insert_payload.get('source')}")
                
                # Insert into raw_events table (PostgREST uses .from_() instead of .table())
                supabase_client.from_("raw_events").insert(insert_payload).execute()
                
                print(f"DEBUG: ✅ Inserción en Supabase completada exitosamente")
                logger.info(f"[SUPABASE] Event saved to Iron Vault: {data.get('ticker', 'UNKNOWN')}")
                
            except Exception as e:
                # Fail-safe: log error but don't stop webhook processing
                print(f"🛑 ERROR CRÍTICO SUPABASE: {str(e)}")
                print(f"Tipo de error: {type(e)}")
                print(f"Exception args: {e.args if hasattr(e, 'args') else 'N/A'}")
                logger.error(f"[SUPABASE] Failed to save event to database: {e}")
                logger.debug(f"[SUPABASE] Error details: {type(e).__name__}: {str(e)}")
                # Continue with normal flow even if Supabase fails
        else:
            logger.error("⚠️ ALERTA: Se recibió evento pero Supabase está DESACTIVADO por error de inicio.")
            print(f"DEBUG: ⚠️ Supabase NO disponible - saltando inserción en base de datos")
            print(f"DEBUG: SUPABASE_AVAILABLE={SUPABASE_AVAILABLE}, supabase_client={supabase_client}")
        
        # 3. VALIDATE SECRET
        received_secret = data.get('secret', '')
        if received_secret != WEBHOOK_SECRET:
            logger.warning(f"[REJECT] Invalid secret: {received_secret[:10]}...")
            return jsonify({"error": "Unauthorized"}), 403
        
        # 4. DEDUPLICATION
        event_id = get_event_id(data)
        today_events = load_events_today()
        
        if event_id in today_events:
            logger.info(f"[SKIP] Duplicate: {data.get('ticker')} {data.get('event_type')}")
            return jsonify({"status": "duplicate", "event_id": event_id}), 200
        
        # 5. CLEAN & VALIDATE DATA
        clean_data = {
            "event_id": event_id,
            "ticker": data.get('ticker', 'UNKNOWN'),
            "signal": data.get('signal', 'UNKNOWN'),
            "event_type": data.get('event_type', 'cross'),
            "received_at": datetime.now(timezone.utc).isoformat() + "Z"
        }
        
        # Parse numeric fields
        for field in ['price', 'sma50', 'sma200']:
            value = data.get(field)
            if value is not None:
                if isinstance(value, (int, float)):
                    clean_data[field] = float(value)
                elif isinstance(value, str) and value.lower() not in ['na', 'nan', '']:
                    try:
                        clean_data[field] = float(value)
                    except ValueError:
                        clean_data[field] = None
                else:
                    clean_data[field] = None
            else:
                clean_data[field] = None
        
        # 6. SAVE EVENT TO FILE (non-critical, preserved for compatibility)
        # Note: File writing is non-critical - if it fails, webhook still succeeds
        # Supabase (Iron Vault) is the primary persistence layer
        try:
            today = get_local_date_key(datetime.now(timezone.utc))
            log_file = get_events_file(today)
            
            with open(log_file, 'a') as f:
                f.write(json.dumps(clean_data) + "\n")
            
            logger.info(f"[FILE] {clean_data['event_type'].upper()}: {clean_data['ticker']} = {clean_data['signal']} → {log_file.name}")
        except Exception as e:
            # Non-critical: log warning but don't fail the webhook
            logger.warning(f"[FILE] Failed to save event to file (non-critical): {e}")
            # Continue - Supabase is the primary storage
        
        return jsonify({
            "status": "ok", 
            "event_id": event_id,
            "message": f"Received {clean_data['event_type']} for {clean_data['ticker']}"
        }), 200
        
    except json.JSONDecodeError as e:
        logger.error(f"[ERROR] Invalid JSON: {e}")
        logger.error(f"[ERROR] Raw data: {request.data.decode('utf-8')[:200]}")
        return jsonify({"error": "Invalid JSON", "details": str(e)}), 400
        
    except Exception as e:
        logger.error(f"[ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============ GET EVENTS ENDPOINT ============
@app.route('/events/<date>', methods=['GET'])
def get_events(date: str):
    """Download events file for a specific date (YYYY-MM-DD)."""
    # Validate date format
    if len(date) != 10 or date[4] != '-' or date[7] != '-':
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
    
    log_file = get_events_file(date)
    
    if not log_file.exists():
        logger.warning(f"[404] Events file not found: {date} (looked in {log_file})")
        # Return empty array instead of 404 for better compatibility
        return jsonify([]), 200
    
    logger.info(f"[DOWNLOAD] Events for {date} from {log_file}")
    return send_file(log_file, mimetype='application/json')


# ============ LIST EVENTS ENDPOINT ============
@app.route('/events', methods=['GET'])
def list_events():
    """List all available event dates."""
    files = [f.name for f in OUTPUT_DIR.glob('events_*.json')]
    dates = sorted([f.replace('events_', '').replace('.json', '') for f in files], reverse=True)
    return jsonify({"available_dates": dates, "count": len(dates)}), 200


# ============ MAIN ============
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting PyQuant Webhook Receiver v2.1.0 on port {port}")
    logger.info(f"Timezone: {APP_TZ}")
    app.run(host='0.0.0.0', port=port, debug=False)