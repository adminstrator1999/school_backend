"""School Accounting SaaS Platform - FastAPI Application."""

from fastapi import FastAPI

app = FastAPI(
    title="School Accounting API",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
