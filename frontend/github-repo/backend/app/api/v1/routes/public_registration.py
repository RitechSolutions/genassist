import os
import uuid
import logging
from fastapi import APIRouter, HTTPException
from app.core.project_path import DATA_VOLUME

router = APIRouter()

logger = logging.getLogger(__name__)
FILE_NAME = "registration_id.txt"
FILE_PATH = os.path.join(DATA_VOLUME, FILE_NAME)


@router.get("/registration-id")
async def get_registration_id():
    # Ensure directory exists
    os.makedirs(DATA_VOLUME, exist_ok=True)
     
    # Check if the file already exists
    if os.path.exists(FILE_PATH):
        try:
            with open(FILE_PATH, "r") as f:
                registration_id = f.read().strip()
                logger.info(f"Read existing registration ID: {registration_id}")
                if str(os.environ.get("START_WIZARD")).lower() == "true":
                    logger.debug(f"Registration ID from file: {registration_id} - allways starting wizard")
                    return {"registration_id": registration_id, "is_new": True}
            return {"registration_id": registration_id, "is_new": False}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading file: {e}")

    # Create a new GUID and write it
    try:
        registration_id = str(uuid.uuid4())
        with open(FILE_PATH, "w") as f:
            f.write(registration_id)
            logger.info(f"Generated and saved new registration ID: {registration_id}")
        return {"registration_id": registration_id, "is_new": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error writing file: {e}")
