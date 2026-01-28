from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from app.config import get_settings

settings = get_settings()

# Define the API key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)):
    """
    Dependency to verify API key from request header.

    Usage in endpoints:
        @app.get("/endpoint", dependencies=[Depends(verify_api_key)])
    """
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key",
            headers={"WWW-Authenticate": "X-API-Key"},
        )

    if api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key",
        )

    return api_key
