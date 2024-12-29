# app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from loguru import logger
from starlette.responses import JSONResponse

from .core.logging import logger_manager
from .core.exceptions import AppException, app_exception_handler, NotFoundError
from .core.config import get_settings
from .core.database import engine, Base, get_db
from .api.v1.api import api_router
from .services.llama_service import LlamaService
import time

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI
    
    Handles startup and shutdown events properly:
    - Sets up logging
    - Creates database tables
    - Initializes LlamaService
    - Cleans up resources on shutdown
    """
    # Startup
    try:
        # Setup logging
        logger.info("Setting up logging...")
        logger_manager.setup_logging()
        logger.info("Logging setup complete")
        logger.info(f"Application environment: {settings.APP_ENV}")
        logger.info(f"Log level: {settings.LOG_LEVEL}")
        
        # Create database tables
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        # Initialize services
        db = next(get_db())
        logger.info("Initializing LlamaService...")
        llama_service = LlamaService(db)
        llama_service.initialize()
        logger.info("LlamaService initialized successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise
        
    finally:
        # Shutdown
        logger.info("Shutting down application...")
        # Add any cleanup code here if needed


app = FastAPI(
    title="Prompt Management API",
    description="API for managing prompts and their versions",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(NotFoundError, app_exception_handler)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_details = []
    for error in exc.errors():
        error_details.append({
            'loc': error['loc'],
            'msg': error['msg'],
            'type': error['type']
        })
    
    logger.error(
        "Request validation failed",
        extra={
            'path': request.url.path,
            'method': request.method,
            'validation_errors': error_details
        }
    )
    
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": error_details
            }
        }
    )

# Include API router
app.include_router(api_router, prefix="/api/v1")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    logger.info(
        f"Request started",
        extra={
            "path": request.url.path,
            "method": request.method,
            "query_params": str(request.query_params),
            "client_host": request.client.host if request.client else None,
            "headers": dict(request.headers)
        }
    )
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        logger.info(
            f"Request completed",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "process_time_ms": round(process_time * 1000, 2)
            }
        )
        return response
    except Exception as e:
        logger.error(
            f"Request failed",
            extra={
                "path": request.url.path,
                "method": request.method,
                "error": str(e)
            }
        )
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    logger.info("Health check endpoint called")
    return {"status": "healthy"}


@app.get("/test-error")
async def test_error():
    """Test error handling"""
    raise NotFoundError("This is a test error")