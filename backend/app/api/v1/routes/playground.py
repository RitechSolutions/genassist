"""
Playground routes for mocking APIs - no authentication or validations required.
Use this for testing and development purposes only.

Available endpoints:
- GET /api/v1/playground/ - Root endpoint
- GET /api/v1/playground/health - Health check
- GET/POST/PUT/DELETE/PATCH /api/v1/playground/mock/{endpoint} - Mock any endpoint
- POST /api/v1/playground/echo - Echo request data
- GET /api/v1/playground/sample-data - Return sample data
- POST /api/v1/playground/sample-response - Create sample response
- GET /api/v1/playground/error/{status_code} - Mock error responses
- GET /api/v1/playground/delay/{seconds} - Mock delayed responses
- GET /api/v1/playground/getParkings - Get Sample City parking zones by location
- POST /api/v1/playground/webhook - Mock webhook endpoint
"""

import logging
from typing import Any, Dict
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def playground_root():
    """Root playground endpoint."""
    return {"message": "Playground API - No auth required", "status": "active"}


@router.get("/health")
async def playground_health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "playground"}


@router.get("/mock/{endpoint}")
async def mock_get_endpoint(endpoint: str, request: Request):
    """Mock any GET endpoint - returns the endpoint name and query parameters."""
    query_params = dict(request.query_params)
    return {
        "endpoint": endpoint,
        "method": "GET",
        "query_params": query_params,
        "message": f"Mocked GET request to /{endpoint}"
    }


@router.post("/mock/{endpoint}")
async def mock_post_endpoint(endpoint: str, request: Request):
    """Mock any POST endpoint - returns the endpoint name and request body."""
    try:
        body = await request.json()
    except Exception:
        body = None
    return {
        "endpoint": endpoint,
        "method": "POST",
        "body": body,
        "message": f"Mocked POST request to /{endpoint}"
    }


@router.put("/mock/{endpoint}")
async def mock_put_endpoint(endpoint: str, request: Request):
    """Mock any PUT endpoint - returns the endpoint name and request body."""
    try:
        body = await request.json()
    except Exception:
        body = None
    return {
        "endpoint": endpoint,
        "method": "PUT",
        "body": body,
        "message": f"Mocked PUT request to /{endpoint}"
    }


@router.delete("/mock/{endpoint}")
async def mock_delete_endpoint(endpoint: str):
    """Mock any DELETE endpoint - returns the endpoint name."""
    return {
        "endpoint": endpoint,
        "method": "DELETE",
        "message": f"Mocked DELETE request to /{endpoint}"
    }


@router.patch("/mock/{endpoint}")
async def mock_patch_endpoint(endpoint: str, request: Request):
    """Mock any PATCH endpoint - returns the endpoint name and request body."""
    try:
        body = await request.json()
    except Exception:
        body = None
    return {
        "endpoint": endpoint,
        "method": "PATCH",
        "body": body,
        "message": f"Mocked PATCH request to /{endpoint}"
    }


@router.post("/echo")
async def echo_request(request: Request):
    """Echo back the request data."""
    try:
        body = await request.json()
    except Exception:
        body = None
    headers = dict(request.headers)
    query_params = dict(request.query_params)

    return {
        "method": request.method,
        "url": str(request.url),
        "headers": headers,
        "query_params": query_params,
        "body": body,
        "message": "Echoed request data"
    }


@router.get("/sample-data")
async def get_sample_data():
    """Return sample data for testing."""
    return {
        "users": [
            {"id": 1, "name": "John Doe", "email": "john@example.com"},
            {"id": 2, "name": "Jane Smith", "email": "jane@example.com"}
        ],
        "products": [
            {"id": 1, "name": "Product A", "price": 29.99},
            {"id": 2, "name": "Product B", "price": 49.99}
        ],
        "status": "success"
    }


@router.post("/sample-response")
async def create_sample_response(data: Dict[str, Any]):
    """Create a sample response with provided data."""
    return {
        "id": "mock-id-123",
        "created_at": "2024-01-01T00:00:00Z",
        "data": data,
        "status": "created",
        "message": "Sample response created successfully"
    }


@router.get("/error/{status_code}")
async def mock_error(status_code: int):
    """Mock different HTTP error responses."""
    if status_code == 400:
        return JSONResponse(
            status_code=400,
            content={"error": "Bad Request", "message": "Invalid input data"}
        )
    elif status_code == 401:
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized",
                     "message": "Authentication required"}
        )
    elif status_code == 403:
        return JSONResponse(
            status_code=403,
            content={"error": "Forbidden", "message": "Access denied"}
        )
    elif status_code == 404:
        return JSONResponse(
            status_code=404,
            content={"error": "Not Found", "message": "Resource not found"}
        )
    elif status_code == 500:
        return JSONResponse(
            status_code=500,
            content={"error": "Internal Server Error",
                     "message": "Something went wrong"}
        )
    else:
        return JSONResponse(
            status_code=status_code,
            content={"error": "Custom Error",
                     "message": f"Error with status {status_code}"}
        )


@router.get("/delay/{seconds}")
async def mock_delay(seconds: int):
    """Mock a delayed response."""
    import asyncio
    await asyncio.sleep(min(seconds, 30))  # Cap at 30 seconds
    return {
        "message": f"Response delayed by {seconds} seconds",
        "delay": seconds,
        "timestamp": "2024-01-01T00:00:00Z"
    }


@router.get("/getParkings")
async def get_parkings(
    latitude: float,
    longitude: float,
    radius: float = -1
):
    """Get Sample City parking zones filtered by location and radius."""
    # Sample Sample City parking zones data
    parking_zones = [
        {
            "id": "zone_001",
            "name": "Ivy Bellefonte Lot",
            "latitude": 40.4406,
            "longitude": -79.9959,
            "model_reference_id": "0199e3e9-feac-7d61-affe-b9c53eb7bd5e"
        },
        {
            "id": "zone_002",
            "name": "Forbes Shady Lot",
            "latitude": 40.4568,
            "longitude": -79.9784,
            "model_reference_id": "0199e431-c663-75f2-81fd-27b49be9715b"
        },
        {
            "id": "zone_003",
            "name": "Frendship Cedarville Lot",
            "latitude": 40.4684,
            "longitude": -79.9631,
            "model_reference_id": "0199e434-d242-7146-b63f-c0b0acd7569b"
        },
        {
            "id": "zone_004",
            "name": "JCC Forbes Lot",
            "latitude": 40.4568,
            "longitude": -79.9364,
            "model_reference_id": "0199e436-1975-78e6-87fb-cfff833c5c0f"
        },
        {
            "id": "zone_005",
            "name": "Downtown 1",
            "latitude": 40.4442,
            "longitude": -79.9606,
            "model_reference_id": "0199e437-328f-7603-8494-10fee129d865"
        },
        {
            "id": "zone_006",
            "name": "Downtown 2",
            "latitude": 40.4259,
            "longitude": -79.9784,
            "model_reference_id": "0199e437-d74f-7a32-90eb-98fcb78267bf"
        },
        {
            "id": "zone_007",
            "name": "Mount Washington",
            "latitude": 40.4259,
            "longitude": -80.0169,
            "model_reference_id": "0199e360-d2ee-726f-8a45-20f346b7f1ba"
        },
        {
            "id": "zone_008",
            "name": "Bloomfield",
            "latitude": 40.4568,
            "longitude": -79.9364,
            "model_reference_id": "0199e360-d2ee-726f-8a45-20f346b7f1ba"
        },
        {
            "id": "zone_009",
            "name": "Squirrel Hill",
            "latitude": 40.4442,
            "longitude": -79.9364,
            "model_reference_id": "0199e360-d2ee-726f-8a45-20f346b7f1ba"
        },
        {
            "id": "zone_010",
            "name": "East Liberty",
            "latitude": 40.4568,
            "longitude": -79.9364,
            "model_reference_id": "0199e360-d2ee-726f-8a45-20f346b7f1ba"
        }
    ]

    # If radius is -1 or not provided, return all zones
    if radius == -1:
        return {
            "parking_zones": parking_zones,
            "total_count": len(parking_zones),
            "search_params": {
                "latitude": latitude,
                "longitude": longitude,
                "radius": radius
            },
            "message": "All Sample City parking zones returned"
        }

    # Filter zones by radius (simple distance calculation)
    import math

    def calculate_distance(lat1, lon1, lat2, lon2):
        """Calculate distance between two points in kilometers."""
        R = 6371  # Earth's radius in kilometers
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat/2) * math.sin(dlat/2) +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon/2) * math.sin(dlon/2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    filtered_zones = []
    for zone in parking_zones:
        distance = calculate_distance(
            latitude, longitude,
            zone["latitude"], zone["longitude"]
        )
        if distance <= radius:
            zone_with_distance = zone.copy()
            zone_with_distance["distance_km"] = round(distance, 2)
            filtered_zones.append(zone_with_distance)

    return {
        "parking_zones": filtered_zones,
        "total_count": len(filtered_zones),
        "search_params": {
            "latitude": latitude,
            "longitude": longitude,
            "radius": radius
        },
        "message": f"Found {len(filtered_zones)} parking zones within {radius}km radius"
    }


@router.post("/webhook")
async def mock_webhook(request: Request):
    """Mock webhook endpoint."""
    try:
        body = await request.json()
    except Exception:
        body = None
    headers = dict(request.headers)

    return {
        "webhook_received": True,
        "headers": headers,
        "body": body,
        "message": "Webhook mock endpoint hit successfully"
    }
