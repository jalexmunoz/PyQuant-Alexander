# utils/supabase_client.py
# Iron Vault - Immutable event storage in Supabase
#
# Purpose: Persist all webhook events to Supabase database via PostgREST
# Architecture: Separate layer for persistence (not coupled to webhook receiver)
# Client: postgrest-py (direct, lightweight)

import os
import logging
from typing import Dict, Any

# Try to load .env file if it exists (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip

logger = logging.getLogger(__name__)

# Initialize PostgREST client at module level
try:
    from postgrest import SyncPostgrestClient
    
    # Read credentials from environment
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    
    # Validate credentials
    if not SUPABASE_URL:
        raise ValueError(
            "SUPABASE_URL environment variable is not set. "
            "Please configure it in your environment or Render service settings."
        )
    
    if not SUPABASE_KEY:
        raise ValueError(
            "SUPABASE_KEY environment variable is not set. "
            "Please configure it in your environment or Render service settings."
        )
    
    # Build PostgREST URL: ensure base URL doesn't end with slash, then append /rest/v1
    base_url = SUPABASE_URL.rstrip('/')
    postgrest_url = f"{base_url}/rest/v1"
    
    # Set headers for Supabase PostgREST API
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    
    # Create and export PostgREST client
    supabase_client = SyncPostgrestClient(
        base_url=postgrest_url,
        schema="public",
        headers=headers
    )
    
    logger.info(f"PostgREST client initialized successfully (URL: {postgrest_url[:30]}...)")
    
except ImportError as e:
    raise ImportError(
        "postgrest package is not installed. "
        "Please run: pip install postgrest"
    ) from e
except ValueError as e:
    # Re-raise ValueError for missing credentials
    raise
except Exception as e:
    raise RuntimeError(
        f"Failed to initialize PostgREST client: {e}. "
        "Please verify SUPABASE_URL and SUPABASE_KEY are correct."
    ) from e


def test_supabase_connection() -> bool:
    """
    Test Supabase connection and table access via PostgREST.
    
    Note: This function assumes supabase_client is already initialized.
    If credentials are missing, this will fail at import time.
    
    Returns:
        bool: True if connection and table are accessible
    """
    try:
        # Try to query the table (should return empty result if table exists)
        response = supabase_client.from_("raw_events").select("ticker").limit(1).execute()
        logger.info("PostgREST connection test: SUCCESS")
        return True
    except Exception as e:
        logger.error(f"PostgREST connection test: FAILED - {e}")
        return False
