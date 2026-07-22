from typing import Optional
from pydantic import BaseModel

class AssetMetadata(BaseModel):
    asset_id: str
    presentation_id: str
    asset_type: str  # presentation, video, image, notes, script
    storage_provider: str  # LOCAL, S3, AZURE, NAS
    storage_uri: str
    checksum: Optional[str] = None
    version: int = 1
