from fastapi import APIRouter, HTTPException

from app.services.firestore_db import delete_clip, get_clip, list_clips

router = APIRouter()


@router.get("/api/clips")
def get_clips():
    return {"clips": list_clips()}


@router.get("/api/clips/{clip_id}")
def get_clip_by_id(clip_id: str):
    clip = get_clip(clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found")
    return clip


@router.delete("/api/clips/{clip_id}")
def remove_clip(clip_id: str):
    if not delete_clip(clip_id):
        raise HTTPException(status_code=404, detail="Clip not found")
    return {"deleted": clip_id}
