# utils/webhook_receiver.py
# v2.0.0 - Improved JSON parsing and error logging for TradingView alerts
#
# Deploy to Render with: python utils/webhook_receiver.py

from flask import Flask, request, jsonify, send_file
import json
import os
import sys
from datetime import datetime
import hashlib
import logging

# Configure logging to show in Render logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# SHARED SECRET - must match TradingView alerts
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "pyquant_shadow_2025_xyz123")

# Output directory - works both locally and on Render
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "Output/webhooks")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_event_id(data: dict) -> str:
    """Generate unique event ID for deduplication."""
    # Use ticker + event_type + date (not exact time) to allow 1 snapshot per day per asset
    today = datetime.utcnow().strftime("%Y-%m-%d")
    key = f"{data.get('ticker')}_{data.get('event_type')}_{today}_{data.get('signal')}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]

def load_events_today() -> set:
    """Load today's event IDs for deduplication."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    log_file = os.path.join(OUTPUT_DIR, f"events_{today}.json")
    
    if not os.path.exists(log_file):
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
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }), 200


# ============ WEBHOOK ENDPOINT ============
@app.route('/tradingview', methods=['POST'])
def tv_webhook():
    try:
        # 1. LOG RAW REQUEST (for debugging)
        raw_data = request.data.decode('utf-8')
        logger.info(f"[RAW] Content-Type: {request.content_type}")
        logger.info(f"[RAW] Body: {raw_data[:500]}")  # First 500 chars
        
        # 2. PARSE JSON (handle both application/json and text/plain)
        if request.is_json:
            data = request.json
        else:
            # TradingView sometimes sends as text/plain
            data = json.loads(raw_data)
        
        logger.info(f"[PARSED] {json.dumps(data)}")
        
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
            "received_at": datetime.utcnow().isoformat() + "Z"
        }
        
        # Parse numeric fields (price, sma50, sma200)
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
        
        # 6. SAVE EVENT
        today = datetime.utcnow().strftime("%Y-%m-%d")
        log_file = os.path.join(OUTPUT_DIR, f"events_{today}.json")
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(clean_data) + "\n")
        
        logger.info(f"[SAVED] {clean_data['event_type'].upper()}: {clean_data['ticker']} = {clean_data['signal']}")
        
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
    
    log_file = os.path.join(OUTPUT_DIR, f"events_{date}.json")
    
    if not os.path.exists(log_file):
        logger.warning(f"[404] Events file not found: {date}")
        return jsonify({"error": f"No events for {date}"}), 404
    
    logger.info(f"[DOWNLOAD] Events for {date}")
    return send_file(log_file, mimetype='application/json')


# ============ LIST EVENTS ENDPOINT ============
@app.route('/events', methods=['GET'])
def list_events():
    """List all available event dates."""
    files = [f for f in os.listdir(OUTPUT_DIR) if f.startswith('events_') and f.endswith('.json')]
    dates = sorted([f.replace('events_', '').replace('.json', '') for f in files], reverse=True)
    return jsonify({"available_dates": dates, "count": len(dates)}), 200


# ============ MAIN ============
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting PyQuant Webhook Receiver v2.0.0 on port {port}")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    app.run(host='0.0.0.0', port=port, debug=False)
