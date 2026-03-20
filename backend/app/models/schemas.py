from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class MessageCreate(BaseModel):
    content: str
    conversation_id: Optional[str] = None
    folder_id: Optional[str] = None  # 新建对话时归入该文件夹
    enable_search: bool = True
    images: Optional[list[str]] = None  # base64 data URLs, e.g. "data:image/png;base64,..."


class Message(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    citations: Optional[list] = None
    created_at: datetime


class ConversationCreate(BaseModel):
    title: Optional[str] = None
    folder_id: Optional[str] = None


class Conversation(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    folder_id: Optional[str] = None


class FolderCreate(BaseModel):
    name: str
    parent_id: Optional[str] = None


class Citation(BaseModel):
    index: int
    title: str
    url: str
    content: str


class MemoryItem(BaseModel):
    id: str
    memory: str
    created_at: Optional[str] = None
