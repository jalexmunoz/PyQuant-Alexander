# utils/db_provider.py
# Iron Vault - Database Provider (Consumer)
#
# Purpose: Read events from Supabase raw_events table using raw HTTP requests
# Architecture: Consumer layer for local scripts to fetch events from Iron Vault
# Compatibility: Python 3.13+ (uses requests instead of postgrest SDK)

import logging
import os
import json
from typing import List, Dict, Any
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


def _get_supabase_config() -> tuple[str, dict] | None:
    """
    Get Supabase URL and headers for HTTP requests.
    
    Returns:
    --------
    tuple[str, dict] | None
        (base_url, headers) if configuration is valid, None otherwise
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        logger.warning("SUPABASE_URL or SUPABASE_KEY not configured")
        return None
    
    # Sanitize credentials (remove whitespace/newlines)
    url = url.strip().rstrip('/')
    key = key.strip()
    
    # Construct PostgREST endpoint
    base_url = f"{url}/rest/v1/raw_events"
    
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"  # Return data in response
    }
    
    return (base_url, headers)


def get_events_by_date(target_date: str) -> List[Dict[str, Any]]:
    """
    Fetch events from Supabase raw_events table for a specific date using raw HTTP.
    
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
        - Supabase credentials are not configured
        
    Examples:
    ---------
    >>> events = get_events_by_date("2025-01-17")
    >>> print(f"Found {len(events)} events")
    >>> if events:
    ...     print(f"First event ticker: {events[0].get('ticker')}")
    """
    
    # Get configuration
    config = _get_supabase_config()
    if not config:
        logger.error("Cannot fetch events: Supabase configuration not available")
        return []
    
    base_url, headers = config
    
    # Validate date format
    if not target_date or len(target_date) != 10 or target_date[4] != '-' or target_date[7] != '-':
        logger.error(f"Invalid date format: {target_date}. Expected YYYY-MM-DD")
        return []
    
    try:
        # Build date range for filtering (UTC timezone)
        date_start = f"{target_date}T00:00:00Z"
        date_end = f"{target_date}T23:59:59Z"
        
        logger.debug(f"Querying events for date: {target_date} ({date_start} to {date_end})")
        
        # Build PostgREST query parameters
        # PostgREST accepts multiple query params with same name for AND conditions
        # Build query string manually to handle multiple conditions on same field
        query_parts = [
            "select=payload",
            f"created_at=gte.{date_start}",
            f"created_at=lte.{date_end}",
            "order=created_at.asc"
        ]
        query_string = "&".join(query_parts)
        full_url = f"{base_url}?{query_string}"
        
        # Make HTTP GET request to Supabase PostgREST API
        response = requests.get(full_url, headers=headers, timeout=10)
        
        # Check response status
        if response.status_code != 200:
            logger.error(f"Failed to fetch events: HTTP {response.status_code}")
            logger.debug(f"Response: {response.text}")
            return []
        
        # Parse JSON response
        data = response.json()
        
        if not data or not isinstance(data, list):
            logger.debug(f"No events found for date: {target_date}")
            return []
        
        # Extract payload column from each row
        events = [row.get("payload") for row in data if row.get("payload")]
        
        logger.info(f"Retrieved {len(events)} events from Iron Vault for date: {target_date}")
        return events
        
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request failed for date {target_date}: {e}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching events for date {target_date}: {e}")
        logger.debug(f"Error type: {type(e).__name__}, Details: {str(e)}")
        return []


def get_latest_events(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Fetch the most recent events from Supabase raw_events table using raw HTTP.
    
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
        - Supabase credentials are not configured
        
    Examples:
    ---------
    >>> events = get_latest_events(5)
    >>> print(f"Found {len(events)} recent events")
    >>> for event in events:
    ...     print(f"{event['created_at']}: {event['payload'].get('ticker')}")
    """
    
    # Get configuration
    config = _get_supabase_config()
    if not config:
        logger.error("Cannot fetch events: Supabase configuration not available")
        return []
    
    base_url, headers = config
    
    # Validate limit
    if limit <= 0:
        logger.warning(f"Invalid limit: {limit}. Using default limit: 10")
        limit = 10
    
    try:
        logger.debug(f"Querying latest {limit} events from Iron Vault")
        
        # Build PostgREST query parameters
        params = {
            "select": "payload,created_at,ticker",
            "order": "created_at.desc",
            "limit": str(limit)
        }
        
        # Make HTTP GET request to Supabase PostgREST API
        response = requests.get(base_url, headers=headers, params=params, timeout=10)
        
        # Check response status
        if response.status_code != 200:
            logger.error(f"Failed to fetch latest events: HTTP {response.status_code}")
            logger.debug(f"Response: {response.text}")
            return []
        
        # Parse JSON response
        data = response.json()
        
        if not data or not isinstance(data, list):
            logger.debug("No events found in database")
            return []
        
        # Build list of events with payload and metadata
        events = []
        for row in data:
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
        
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP request failed for latest events: {e}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching latest events: {e}")
        logger.debug(f"Error type: {type(e).__name__}, Details: {str(e)}")
        return []
