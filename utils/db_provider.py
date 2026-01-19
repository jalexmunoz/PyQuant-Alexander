# utils/db_provider.py
# Iron Vault - Database Provider (Consumer)
#
# Purpose: Read events from Supabase raw_events table
# Architecture: Consumer layer for local scripts to fetch events from Iron Vault

import logging
from typing import List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Import PostgREST client (fail gracefully if not available)
try:
    from utils.supabase_client import supabase_client
    DB_AVAILABLE = True
except (ImportError, ValueError, RuntimeError) as e:
    DB_AVAILABLE = False
    supabase_client = None
    logger.warning(f"Supabase client not available in db_provider: {e}")


def get_events_by_date(target_date: str) -> List[Dict[str, Any]]:
    """
    Fetch events from Supabase raw_events table for a specific date.
    
    This is the primary consumer interface for reading events from Iron Vault.
    Events are retrieved from the `payload` column (which contains the full webhook data).
    
    Parameters:
    -----------
    target_date : str
        Date in format "YYYY-MM-DD" (e.g., "2025-01-17")
        
    Returns:
    --------
    List[Dict[str, Any]]
        List of event payloads (raw webhook data). Each item is a dict from the payload JSONB column.
        Returns empty list if:
        - Database connection fails
        - No events found for the date
        - Database client is not available
        
    Examples:
    ---------
    >>> events = get_events_by_date("2025-01-17")
    >>> print(f"Found {len(events)} events")
    >>> if events:
    ...     print(f"First event ticker: {events[0].get('ticker')}")
    """
    
    if not DB_AVAILABLE or supabase_client is None:
        logger.error("Cannot fetch events: Supabase client not available")
        return []
    
    if not target_date or len(target_date) != 10 or target_date[4] != '-' or target_date[7] != '-':
        logger.error(f"Invalid date format: {target_date}. Expected YYYY-MM-DD")
        return []
    
    try:
        # Build date range for filtering
        # Use UTC timezone (Supabase stores created_at as TIMESTAMPTZ)
        date_start = f"{target_date}T00:00:00Z"
        date_end = f"{target_date}T23:59:59Z"
        
        logger.debug(f"Querying events for date: {target_date} ({date_start} to {date_end})")
        
        # Query raw_events table using PostgREST
        # Filter by created_at range and select only payload column
        response = supabase_client.from_("raw_events") \
            .select("payload") \
            .gte("created_at", date_start) \
            .lte("created_at", date_end) \
            .order("created_at", desc=False) \
            .execute()
        
        # Extract payloads from response
        if not response.data:
            logger.debug(f"No events found for date: {target_date}")
            return []
        
        # Extract payload column from each row
        events = [row.get("payload") for row in response.data if row.get("payload")]
        
        logger.info(f"Retrieved {len(events)} events from Iron Vault for date: {target_date}")
        return events
        
    except Exception as e:
        # Fail gracefully: log error and return empty list
        logger.error(f"Failed to fetch events from database for date {target_date}: {e}")
        logger.debug(f"Error type: {type(e).__name__}, Details: {str(e)}")
        return []


def get_latest_events(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch the most recent events from Supabase raw_events table.
    
    This function avoids timezone issues by simply ordering by created_at descending
    and taking the N most recent events, regardless of date.
    
    Parameters:
    -----------
    limit : int, optional
        Maximum number of events to retrieve (default: 10)
        
    Returns:
    --------
    List[Dict[str, Any]]
        List of event dictionaries, each containing:
        - payload: The raw webhook payload (dict)
        - created_at: Timestamp when the event was inserted (str, ISO format)
        - ticker: Asset ticker (str, extracted from row for convenience)
        
        Returns empty list if:
        - Database connection fails
        - No events found
        - Database client is not available
        
    Examples:
    ---------
    >>> events = get_latest_events(5)
    >>> print(f"Found {len(events)} recent events")
    >>> for event in events:
    ...     print(f"{event['created_at']}: {event['payload'].get('ticker')}")
    """
    
    if not DB_AVAILABLE or supabase_client is None:
        logger.error("Cannot fetch events: Supabase client not available")
        return []
    
    if limit <= 0:
        logger.warning(f"Invalid limit: {limit}. Using default limit: 10")
        limit = 10
    
    try:
        logger.debug(f"Querying latest {limit} events from Iron Vault")
        
        # Query raw_events table using PostgREST
        # Select payload and created_at, order by created_at descending, apply limit
        response = supabase_client.from_("raw_events") \
            .select("payload,created_at,ticker") \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        
        # Extract events from response
        if not response.data:
            logger.debug("No events found in database")
            return []
        
        # Build list of events with payload and metadata
        events = []
        for row in response.data:
            event = {
                "payload": row.get("payload"),
                "created_at": row.get("created_at"),
                "ticker": row.get("ticker")
            }
            # Only include if payload exists
            if event["payload"]:
                events.append(event)
        
        logger.info(f"Retrieved {len(events)} latest events from Iron Vault")
        return events
        
    except Exception as e:
        # Fail gracefully: log error and return empty list
        logger.error(f"Failed to fetch latest events from database: {e}")
        logger.debug(f"Error type: {type(e).__name__}, Details: {str(e)}")
        return []

