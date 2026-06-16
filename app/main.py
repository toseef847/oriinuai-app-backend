from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.v1.router import api_router
from app.core.config import settings
from app.utils.response import api_error, api_success


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Starting {settings.APP_NAME}...")
    yield
    print("Shutting down.")


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    version="1.0.0",
    description="African Sacred Science™ AI — Backend API",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Standardize HTTPException
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return api_error(
        message=exc.detail,
        status_code=exc.status_code
    )

# Standardize RequestValidationError (422)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    if errors:
        # Simplify to first error message
        first_error = errors[0]
        field = ".".join(str(loc) for loc in first_error.get("loc", []) if loc != "body")
        msg = first_error.get("msg", "Validation error")
        error_message = f"Field '{field}' {msg}" if field else msg
    else:
        error_message = "Validation error"
        
    return api_error(
        message=error_message,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        data=errors # Include full errors in data for debugging/advanced usage
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health():
    return api_success(
        data={"status": "ok", "service": settings.APP_NAME},
        message="Service is healthy"
    )
