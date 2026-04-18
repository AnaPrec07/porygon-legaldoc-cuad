# MCP Server Imports

import json
from typing import Any, Dict, Optional

from fastmcp import FastMCP
import httpx
from geopy.geocoders import Nominatim
from mcp_server.core.mask_sensitive_data import MaskSensitiveData
from mcp_server.integration.gcp.documentai import process_document
import os
import uvicorn

# Initialize FastMCP server
mcp = FastMCP("weather")


# --- Configuration & Constants ---
BASE_URL = ""
USER_AGENT = ""
REQUEST_TIMEOUT = 20.0
GEOCODE_TIMEOUT = 10.0  # Timeout for geocoding requests

# --- Shared HTTP Client ---
http_client = httpx.AsyncClient(
    base_url=BASE_URL,
    headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"},
    timeout=REQUEST_TIMEOUT,
    follow_redirects=True,
)

# --- Geocoding Setup ---
# Initialize the geocoder (Nominatim requires a unique user_agent)
# geolocator = Nominatim(user_agent=USER_AGENT)

# --- MCP Tools ---
@mcp.tool()
async def get_masked_text(document: bytes)->str:
    """
    Get the masked text for a document.

    Args:
        document (bytes): PDF object in bytes.
    """
    masker = MaskSensitiveData()

    # Perform OCR
    result = process_document(document = document)

    # Mask content
    masked = masker.deidentify_text(result.text)

    return masked

# --- Server Execution & Shutdown ---
async def shutdown_event():
    """Gracefully close the httpx client."""
    await http_client.aclose()

# Expose the ASGI app at module level so uvicorn can import it directly.
# mcp.run() is convenient for local dev but Cloud Run needs the app object
# so the process manager (uvicorn) controls the lifecycle.
app = mcp.http_app(transport="streamable-http")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)


