import uuid

from fastapi import APIRouter, UploadFile

router = APIRouter()


@router.post("/uploads")
async def upload_file(file: UploadFile):
    set_id = str(uuid.uuid4())

    # Read file to consume the upload (no processing yet)
    await file.read()

    return {
        "setId": set_id,
        "fileName": file.filename,
        "status": "processing",
    }
