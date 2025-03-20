from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(tags=["Application"])


class LiveZ(BaseModel):
    ok: bool = True


@router.get("/livez", response_model=LiveZ, status_code=200)
def livez() -> LiveZ:
    """
    Check if Server is running.
    """
    return LiveZ()


@router.get("/healthz", response_model=LiveZ, status_code=200)
def healthz() -> LiveZ:
    """
    Check if Server is running and services are available.
    """
    return LiveZ()

@router.post("/solvez")
def solvez(auth: Annotated[str | None, Header()] = None) -> JSONResponse:
    """
    Check if challenge is solvable
    """
    from scripts.solve import main
    if auth != "Papyrus-Angled-Salvation-Valley7-Festive-Getaway":
        raise HTTPException(status_code=403, detail="Unauthorized")

    result = main()
    status = 200
    if not result["flag"]:
        status = 400
    result["flag"] = bool(result["flag"])

    return JSONResponse(content=result, status_code=status)
