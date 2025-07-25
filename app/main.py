from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from contextlib import asynccontextmanager
import uvicorn

from app.database import create_db, engine
from app.api import (
    auth_router,
    files_router,
    expose_router,
    access_router,
    approve_router,
    health_router,
    premium_router
)

security = HTTPBearer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    create_db()
    print("Database tables created successfully")
    
    yield
    
    engine.dispose()
    print("Database connections closed")


app = FastAPI(
    title="Drive File Sharing API",
    description="A secure file sharing platform with phone-based authentication",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "drive-api"}

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Drive File Sharing API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

app.include_router(auth_router)
app.include_router(files_router)
app.include_router(expose_router)
app.include_router(access_router)
app.include_router(approve_router)
app.include_router(health_router)
app.include_router(premium_router)


@app.exception_handler(500)
async def internal_server_error(request, exc):
    return HTTPException(
        status_code=500,
        detail="Internal server error occurred"
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )