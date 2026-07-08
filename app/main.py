from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine, Base
from app.routers import health, search, check, admin

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name, debug=settings.debug, docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(health.router)
app.include_router(search.router)
app.include_router(check.router)
app.include_router(admin.router)


@app.get("/")
async def root():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "PanSou Python API", "docs": "/docs"}


@app.get("/admin.html")
async def admin_page():
    admin_file = static_dir / "admin.html"
    if admin_file.exists():
        return FileResponse(admin_file)
    raise HTTPException(status_code=404, detail="Admin page not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
