import asyncio
import random
import uuid
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

class HealthResponse(BaseModel):
    status: str
    version: str

class LibraryNodeModel(BaseModel):
    id: str
    name: str
    path: str
    type: str
    parentId: Optional[str] = None
    children: Optional[List] = []
    memoryCount: int = 0
    memorySize: int = 0
    createdAt: str
    updatedAt: str

class MemoryModel(BaseModel):
    id: str
    content: str
    summary: Optional[str] = None
    category: str
    tags: List[str] = []
    importance: int = 3
    embeddingStatus: str = "completed"
    embeddingScore: Optional[float] = None
    filePath: str
    createdAt: str
    updatedAt: str
    accessCount: int = 0
