#!/usr/bin/env python3
# utils/test_supabase_connection.py
# Iron Vault - Test Supabase Connection
#
# Purpose: Verify Supabase configuration and table access
# Usage: python utils/test_supabase_connection.py

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

try:
    from utils.supabase_client import supabase_client, test_supabase_connection
    SUPABASE_AVAILABLE = True
except (ImportError, ValueError, RuntimeError) as e:
    print(f"❌ FAILED: Could not import Supabase client: {e}")
    print("   → Check that SUPABASE_URL and SUPABASE_KEY are set")
    SUPABASE_AVAILABLE = False
    supabase_client = None

from datetime import datetime, timezone


def main():
    """Test Supabase connection and event insertion."""
    print("=" * 60)
    print("Iron Vault - Supabase Connection Test")
    print("=" * 60)
    print()
    
    # Test 1: Check client initialization
    print("Test 1: Checking Supabase client initialization...")
    if not SUPABASE_AVAILABLE or supabase_client is None:
        print("❌ FAILED: Supabase client not initialized")
        print("   → Check that SUPABASE_URL and SUPABASE_KEY are set")
        return False
    else:
        print("✅ SUCCESS: Supabase client initialized")
    print()
    
    # Test 2: Check table access
    print("Test 2: Checking table access...")
    table_ok = test_supabase_connection()
    
    if not table_ok:
        print("❌ FAILED: Cannot access raw_events table")
        print("   → Verify that table exists in Supabase")
        print("   → Run Docs/supabase_schema.sql to create the table")
        return False
    else:
        print("✅ SUCCESS: Table access verified")
    print()
    
    # Test 3: Insert test event (real insertion)
    print("Test 3: Inserting test event...")
    test_id = f"test_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    test_ticker = "TESTUSDT"
    inserted_id = None
    
    test_payload = {
        "secret": "test_secret",
        "ticker": test_ticker,
        "signal": "ON",
        "event_type": "daily_snapshot",
        "price": 50000.0,
        "sma50": 48000.0,
        "sma200": 45000.0,
        "time": datetime.now(timezone.utc).isoformat() + "Z"
    }
    
    try:
        insert_payload = {
            "payload": test_payload,
            "ticker": test_ticker,
            "source": "tradingview"
        }
        
        print(f"   → Inserting event with ticker: {test_ticker}")
        print(f"   → Test ID: {test_id}")
        
        response = supabase_client.from_("raw_events").insert(insert_payload).execute()
        
        if not response.data:
            print("❌ FAILED: Insert returned no data")
            return False
        
        inserted_id = response.data[0].get("id")
        print(f"✅ SUCCESS: Test event inserted (ID: {inserted_id})")
    except Exception as e:
        print(f"❌ FAILED: Could not insert test event: {e}")
        print(f"   → Error type: {type(e).__name__}")
        import traceback
        print(f"   → Traceback:\n{traceback.format_exc()}")
        return False
    print()
    
    # Test 4: Verify insertion success (query the inserted event)
    print("Test 4: Verifying insertion success...")
    try:
        # Query the event we just inserted (PostgREST uses .from_() instead of .table())
        query_response = supabase_client.from_("raw_events") \
            .select("*") \
            .eq("ticker", test_ticker) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
        
        if not query_response.data or len(query_response.data) == 0:
            print("❌ FAILED: Could not retrieve inserted event")
            print("   → Event was inserted but query returned no results")
            return False
        
        retrieved_event = query_response.data[0]
        
        # Verify the data matches
        if retrieved_event.get("ticker") != test_ticker:
            print(f"❌ FAILED: Ticker mismatch")
            print(f"   → Expected: {test_ticker}, Got: {retrieved_event.get('ticker')}")
            return False
        
        if retrieved_event.get("source") != "tradingview":
            print(f"❌ FAILED: Source mismatch")
            print(f"   → Expected: tradingview, Got: {retrieved_event.get('source')}")
            return False
        
        # Verify payload structure
        payload = retrieved_event.get("payload")
        if not payload:
            print("❌ FAILED: Payload is missing or null")
            return False
        
        if payload.get("ticker") != test_ticker:
            print(f"❌ FAILED: Payload ticker mismatch")
            return False
        
        if payload.get("price") != test_payload.get("price"):
            print(f"❌ FAILED: Payload price mismatch")
            return False
        
        print(f"✅ SUCCESS: Inserted event verified")
        print(f"   → Database ID: {retrieved_event.get('id')}")
        print(f"   → Ticker: {retrieved_event.get('ticker')}")
        print(f"   → Source: {retrieved_event.get('source')}")
        print(f"   → Created at: {retrieved_event.get('created_at')}")
        print(f"   → Payload ticker: {payload.get('ticker')}")
        print(f"   → Payload price: {payload.get('price')}")
        print(f"   → Payload signal: {payload.get('signal')}")
        
    except Exception as e:
        print(f"❌ FAILED: Could not verify insertion: {e}")
        print(f"   → Error type: {type(e).__name__}")
        import traceback
        print(f"   → Traceback:\n{traceback.format_exc()}")
        return False
    print()
    
    print("=" * 60)
    print("✅ All tests passed! Supabase is configured correctly.")
    print("=" * 60)
    print()
    print("📊 Test Summary:")
    print(f"   • Client initialized: ✅")
    print(f"   • Table access: ✅")
    print(f"   • Event insertion: ✅ (ID: {inserted_id})")
    print(f"   • Insertion verification: ✅")
    print()
    print(f"💡 Next steps:")
    print(f"   → Check Supabase Table Editor to see the test event")
    print(f"   → Look for ticker: {test_ticker}")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

