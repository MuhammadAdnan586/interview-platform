"""
main.py
--------
Application entry point. Creates DB tables on startup (SQLite — no
migrations needed for a project at this scale), wires up every router,
and serves the static frontend.

Run with: uvicorn app.main:app --reload
Then open: http://localhost:8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import Base, engine
from app.routers import auth_routes, cv_routes, interview_routes, admin_routes, report_routes, directory_routes

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Interview Readiness Platform")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(cv_routes.router)
app.include_router(interview_routes.router)
app.include_router(admin_routes.router)
app.include_router(report_routes.router)
app.include_router(directory_routes.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


def _page(filename: str):
    def handler():
        return FileResponse(f"app/static/{filename}")
    return handler


app.get("/")(_page("index.html"))
app.get("/login")(_page("login.html"))
app.get("/candidate")(_page("candidate_dashboard.html"))
app.get("/interview")(_page("interview.html"))
app.get("/report")(_page("report.html"))
app.get("/admin")(_page("admin_dashboard.html"))


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
