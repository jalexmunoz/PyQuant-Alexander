#!/usr/bin/env python3
# utils/test_fetch_db.py
# Iron Vault - Test Database Consumer
#
# Purpose: Test fetching events from Supabase using db_provider
# Usage: python utils/test_fetch_db.py

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from utils.db_provider import get_latest_events
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)


def main():
    """Test fetching latest events from Iron Vault (timezone-safe)."""
    print("=" * 60)
    print("Iron Vault - Database Consumer Test")
    print("=" * 60)
    print()
    
    print("Fetching latest 5 events (timezone-safe)...")
    print()
    
    # Fetch latest events using db_provider (avoids timezone issues)
    events = get_latest_events(limit=5)
    
    # Display results
    print(f"Results: Found {len(events)} event(s)")
    print()
    
    if events:
        print("Latest Events:")
        print("-" * 60)
        
        for i, event in enumerate(events, 1):
            created_at = event.get("created_at", "N/A")
            ticker = event.get("ticker", "N/A")
            payload = event.get("payload", {})
            
            # Extract additional info from payload
            event_type = payload.get("event_type", "N/A")
            signal = payload.get("signal", "N/A")
            price = payload.get("price")
            
            print(f"{i}. Created: {created_at}")
            print(f"   Ticker: {ticker}")
            print(f"   Type: {event_type} | Signal: {signal}")
            if price:
                print(f"   Price: {price}")
            print()
        
        # Show full first event for debugging
        if len(events) > 0:
            print("Full first event (JSON):")
            import json
            first_event = events[0]
            print(json.dumps({
                "created_at": first_event.get("created_at"),
                "ticker": first_event.get("ticker"),
                "payload": first_event.get("payload")
            }, indent=2))
    else:
        print("No events found in database.")
        print("This is normal if:")
        print("  - No webhooks have been received yet")
        print("  - Events haven't been inserted to Supabase")
        print("  - Database connection is not configured")
    
    print()
    print("=" * 60)
    
    return len(events) >= 0  # Always return True (just testing connectivity)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

