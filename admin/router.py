from fastapi import APIRouter

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/dashboard")
def dashboard():
    # Dummy admin dashboard endpoint
    return {"message": "Admin dashboard (POC)"}
