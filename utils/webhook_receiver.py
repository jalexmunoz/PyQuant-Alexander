# utils/webhook_receiver.py (VERSIÓN PRODUCTION-READY)

from flask import Flask, request, jsonify
import json
import os
from datetime import datetime
import hashlib

app = Flask(__name__)

# SHARED SECRET
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "pyquant_shadow_2025_xyz123")

# Asegurar directorios
os.makedirs("Output/webhooks", exist_ok=True)
os.makedirs("Output/shadow", exist_ok=True)

def get_event_id(data):
    """Generate unique event ID for deduplication"""
    key = f"{data.get('ticker')}_{data.get('time')}_{data.get('signal')}"
    return hashlib.sha1(key.encode()).hexdigest()

def load_events_today():
    """Load today's events for deduplication"""
    today = datetime.now().date()
    log_file = f"Output/webhooks/events_{today}.json"
    
    if not os.path.exists(log_file):
        return set()
    
    events = set()
    with open(log_file, 'r') as f:
        for line in f:
            try:
                event = json.loads(line)
                events.add(event.get('event_id'))
            except:
                pass
    return events

# ============ HEALTH CHECK (NUEVO) ============
@app.route('/', methods=['GET', 'HEAD'])
def health_check():
    """Health check endpoint for Render"""
    return jsonify({
        "status": "ok",
        "service": "pyquant-webhooks",
        "version": "1.0.0"
    }), 200

# ============ WEBHOOK ENDPOINT ============
@app.route('/tradingview', methods=['POST'])
def tv_webhook():
    try:
        # LOG REQUEST
        print(f"[DEBUG] Content-Type: {request.content_type}")
        print(f"[DEBUG] Raw data: {request.data.decode('utf-8')}")
        
        # PARSE JSON (tolerante a diferentes content types)
        if request.is_json:
            data = request.json
        else:
            # TradingView a veces manda text/plain si JSON tiene errores
            data = json.loads(request.data.decode('utf-8'))
        
        print(f"[DEBUG] Parsed data: {data}")
        
        # 1. VALIDAR SECRET
        if data.get('secret') != WEBHOOK_SECRET:
            print(f"[REJECT] Invalid secret")
            return jsonify({"error": "Unauthorized"}), 403
        
        # 2. DEDUPLICACIÓN
        event_id = get_event_id(data)
        today_events = load_events_today()
        
        if event_id in today_events:
            print(f"[SKIP] Duplicate event: {event_id}")
            return jsonify({"status": "duplicate"}), 200
        
        # 3. PARSE & CLEAN
        clean_data = {
            "ticker": data.get('ticker'),
            "signal": data.get('signal'),
            "event_type": data.get('event_type', 'cross'),
            "time": data.get('time'),
            "event_id": event_id,
            "received_at": datetime.now().isoformat()
        }
        
        # Convert price/SMAs from string, handle 'na'
        for field in ['price', 'sma50', 'sma200']:
            value = data.get(field)
            if value and value != 'na':
                try:
                    clean_data[field] = float(value)
                except:
                    clean_data[field] = None
            else:
                clean_data[field] = None
        
        # Si es snapshot, calcular señal real
        if clean_data['event_type'] == 'snapshot':
            sma50 = clean_data.get('sma50')
            sma200 = clean_data.get('sma200')
            if sma50 and sma200:
                clean_data['signal'] = 'ON' if sma50 > sma200 else 'OFF'
        
        # 4. LOG EVENTO
        today = datetime.now().date()
        log_file = f"Output/webhooks/events_{today}.json"
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(clean_data) + "\n")
        
        print(f"[WEBHOOK] {clean_data['event_type'].upper()}: {clean_data['ticker']} = {clean_data.get('signal', 'snapshot')}")
        
        return jsonify({"status": "ok", "event_id": event_id}), 200
        
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON: {e}")
        print(f"[ERROR] Raw data was: {request.data}")
        return jsonify({"error": "Invalid JSON"}), 400
        
    except Exception as e:
        print(f"[ERROR] Exception: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Obtener puerto de environment variable (Render lo pasa)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)