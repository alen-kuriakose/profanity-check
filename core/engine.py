from fastapi import APIRouter, UploadFile, File, Form
from core.config_manager import get_settings

router = APIRouter(prefix="/engine", tags=["Core Engine"])

@router.post("/upload")
async def upload_content(
    content_type: str = Form(...),
    file: UploadFile = File(...)
):
    # In real system: save file, create DB entry, dispatch to modules
    # For POC: just return info
    settings = get_settings()
    enabled_modules = [k for k, v in settings.modules.items() if v.get("enabled")]
    return {
        "filename": file.filename,
        "content_type": content_type,
        "modules_invoked": enabled_modules
    }

@router.get("/config")
def get_config():
    return get_settings().dict()
