from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="Berlin Scene Graph API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api")
async def root() -> dict[str, str]:
    return {"message": "Berlin Scene Graph backend is running."}
