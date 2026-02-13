from pydantic import BaseModel


class DocumentCreateResponse(BaseModel):
    documentId: str
    setId: str
    jobId: str
    status: str
