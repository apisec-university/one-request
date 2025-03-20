from fastapi.responses import FileResponse
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

# Create a new router for the landing pages
router = APIRouter(include_in_schema=False)

# Setup templates directory - assuming templates are stored in a 'templates' folder
BASE_DIR = Path(__file__).parent
templates_dir = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(templates_dir))
postman_collection = BASE_DIR.parent.parent / "build" / "postman.json"


@router.get("/", response_class=HTMLResponse)
async def get_landing_page(request: Request):
    """
    Serves the main landing page for the One Request API
    """
    return templates.TemplateResponse("landing.html", {"request": request})


@router.get("/features", response_class=HTMLResponse)
async def get_features_page(request: Request):
    """
    Serves the features overview page
    """
    return templates.TemplateResponse("features.html", {"request": request})


@router.get("/developers", response_class=HTMLResponse)
async def get_developers_page(request: Request):
    """
    Serves the developers documentation page
    """
    return templates.TemplateResponse("developers.html", {"request": request})

@router.get("/challenges", response_class=HTMLResponse)
async def get_challenges_page(request: Request):
    """
    Serves the developers documentation page
    """
    return templates.TemplateResponse("challenges.html", {"request": request})

@router.get('/postman.json')
async def get_postman_collection():
    """
    Serves the Postman collection JSON file
    """
    if not postman_collection.is_file():
        raise HTTPException(status_code=404, detail="Postman collection file not found")

    return FileResponse(
        path=postman_collection,
        filename="postman.json",
        media_type="application/json"
    )
