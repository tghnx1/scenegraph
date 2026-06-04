from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List
from psycopg import Connection
from app.db import get_db

router = APIRouter()


class Genre(BaseModel):
    name: str
    value: str


class GenresResponse(BaseModel):
    genres: List[Genre]


GENRES_SQL = """
SELECT DISTINCT
    extracted_genre AS name,
    lower(extracted_genre) AS value
FROM artist_extracted_genres
WHERE extracted_genre IS NOT NULL
ORDER BY name ASC;
"""


@router.get("", response_model=GenresResponse)
def get_genres(db: Connection = Depends(get_db)):
    with db.cursor() as cur:
        cur.execute(GENRES_SQL)
        rows = cur.fetchall()

    return GenresResponse(
        genres=[Genre(name=row["name"], value=row["value"]) for row in rows]
    )