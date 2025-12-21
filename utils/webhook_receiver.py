from flask import Flask, request, jsonify, send_file
import json
import os
from pathlib import Path
from datetime import datetime
import hashlib

app = Flask(__name__)

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "pyquant_shadow_2025_xyz123")

# Get absolute path to project root (parent of utils/)
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "Output" / "webhooks"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
(PROJECT_ROOT / "Output" / "shadow").mkdir(parents=True, exist_ok=True)

def get_event_id(data):
    key = f"{data.get('ticker')}_{data.get('time')}_{data.get('signal')}"
    return hashlib.sha1(key.encode()).hexdigest()

def load_events_today():
    today = datetime.now().date()
    log_file = OUTPUT_DIR / f"events_{today}.json"
    if not log_file.exists():
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

@app.route('/', methods=['GET', 'HEAD'])
def health_check():
    return jsonify({"status": "ok", "service": "pyquant-webhooks", "version": "1.0.0"}), 200

@app.route('/tradingview', methods=['POST'])
def tv_webhook():
    try:
        # Parse JSON
        if request.is_json:
            data = request.json
        else:
            data = json.loads(request.data.decode('utf-8'))
        
        print(f"[RECEIVED] {data}")
        
        # Validar secret
        if data.get('secret') != WEBHOOK_SECRET:
            print(f"[REJECT] Invalid secret")
            return jsonify({"error": "Unauthorized"}), 403
        
        # Deduplicación
        event_id = get_event_id(data)
        today_events = load_events_today()
        
        if event_id in today_events:
            print(f"[SKIP] Duplicate: {event_id}")
            return jsonify({"status": "duplicate"}), 200
        
        # Clean data
        clean_data = {
            "ticker": data.get('ticker'),
            "signal": data.get('signal'),
            "event_type": data.get('event_type', 'cross'),
            "time": data.get('time'),
            "event_id": event_id,
            "received_at": datetime.now().isoformat()
        }
        
        for field in ['price', 'sma50', 'sma200']:
            value = data.get(field)
            if value and value != 'na':
                try:
                    clean_data[field] = float(value)
                except:
                    clean_data[field] = None
            else:
                clean_data[field] = None
        
        # Log evento
        today = datetime.now().date()
        log_file = OUTPUT_DIR / f"events_{today}.json"
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(clean_data) + "\n")
        
        print(f"[WEBHOOK] {clean_data['event_type'].upper()}: {clean_data['ticker']} = {clean_data.get('signal')}")
        
        return jsonify({"status": "ok", "event_id": event_id}), 200
        
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/events/<date>', methods=['GET'])
def download_events(date):
    """
    Download events file for specific date.
    
    Args:
        date (str): Date in YYYY-MM-DD format
        
    Returns:
        JSON file if exists, 404 error if not found
    """
    # Validate date format (basic check)
    if len(date) != 10 or date[4] != '-' or date[7] != '-':
        print(f"[ERROR] Invalid date format requested: {date}")
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
    
    # Construct filepath
    filepath = OUTPUT_DIR / f"events_{date}.json"
    
    # Check if file exists
    if not filepath.exists():
        print(f"[INFO] Events file not found: {filepath}")
        return jsonify({"error": f"Events not found for date: {date}"}), 404
    
    # Return file
    print(f"[INFO] Serving events file: {filepath}")
    return send_file(filepath, mimetype='application/json', as_attachment=True, download_name=f"events_{date}.json")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)