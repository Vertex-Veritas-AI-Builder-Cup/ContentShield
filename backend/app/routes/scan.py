from fastapi import APIRouter

from app.services.firestore_db import list_scans

router = APIRouter()


@router.get("/api/scans")
def get_scans():
    return {"scans": list_scans()}
