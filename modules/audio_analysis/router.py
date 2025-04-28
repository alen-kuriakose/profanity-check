from fastapi import APIRouter

router = APIRouter(prefix="/audio-analysis", tags=["Audio Analysis"])

@router.get("/health")
def health():
    return {"status": "healthy"}
