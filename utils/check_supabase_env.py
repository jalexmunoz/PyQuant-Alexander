#!/usr/bin/env python3
# utils/check_supabase_env.py
# Quick check for Supabase environment variables

import os

print("=" * 60)
print("Supabase Environment Check")
print("=" * 60)
print()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

print("Environment Variables:")
print(f"  SUPABASE_URL: {'✅ SET' if SUPABASE_URL else '❌ NOT SET'}")
if SUPABASE_URL:
    print(f"    Value: {SUPABASE_URL[:30]}...")
else:
    print("    → Configure this variable in Render or your .env file")

print(f"  SUPABASE_KEY: {'✅ SET' if SUPABASE_KEY else '❌ NOT SET'}")
if SUPABASE_KEY:
    print(f"    Value: {SUPABASE_KEY[:20]}...")
else:
    print("    → Configure this variable in Render or your .env file")

print()

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ CREDENTIALS MISSING")
    print()
    print("To configure:")
    print("1. In Render: Go to your service → Environment → Add:")
    print("   SUPABASE_URL=https://xxxxx.supabase.co")
    print("   SUPABASE_KEY=eyJhbGc... (service role key)")
    print()
    print("2. Or locally, create a .env file:")
    print("   SUPABASE_URL=https://xxxxx.supabase.co")
    print("   SUPABASE_KEY=eyJhbGc...")
    print()
    print("   Then load it: python -m pip install python-dotenv")
    print("   And in code: from dotenv import load_dotenv; load_dotenv()")
else:
    print("✅ Credentials are configured!")
    print()
    print("Next steps:")
    print("1. Install supabase package (requires Visual C++ Build Tools on Windows)")
    print("   OR use a pre-built wheel if available")
    print("2. Run: python utils/test_supabase_connection.py")

print("=" * 60)

