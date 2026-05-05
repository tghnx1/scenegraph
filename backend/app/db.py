import os
from collections.abc import Generator

import psycopg
from psycopg.rows import dict_row


DATABASE_URL = os.environ["DATABASE_URL"]


def get_connection() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def get_db() -> Generator[psycopg.Connection, None, None]:
    with get_connection() as connection:
        yield connection


def initialize_database() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            sample_venues = [
                ("OHM", "Mitte", "Techno and leftfield club nights"),
                ("Club Ost", "Friedrichshain", "Peak-time techno and warehouse events"),
                ("RSO.BERLIN", "Schoneweide", "Large-format techno and house programming"),
            ]
            sample_artists = [
                ("mkokorev", "techno"),
                ("Phase Fatale", "techno"),
                ("Volvox", "techno"),
                ("Cinthie", "house"),
            ]
            sample_events = [
                ("42 Techno Night Berlin", "2025-03-15", "techno", "OHM"),
                ("Friedrichshain Pressure", "2025-06-07", "techno", "Club Ost"),
                ("Sunday House Session", "2025-09-21", "house", "RSO.BERLIN"),
            ]
            sample_event_artists = [
                ("42 Techno Night Berlin", "mkokorev"),
                ("42 Techno Night Berlin", "Phase Fatale"),
                ("Friedrichshain Pressure", "mkokorev"),
                ("Friedrichshain Pressure", "Volvox"),
                ("Sunday House Session", "Cinthie"),
            ]

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS venues (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    district TEXT NOT NULL,
                    scene_focus TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS artists (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    genre TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    event_date DATE NOT NULL,
                    genre TEXT NOT NULL,
                    venue_id INTEGER NOT NULL REFERENCES venues(id) ON DELETE CASCADE
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS event_artists (
                    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
                    artist_id INTEGER NOT NULL REFERENCES artists(id) ON DELETE CASCADE,
                    PRIMARY KEY (event_id, artist_id)
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_events_event_date
                ON events (event_date)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_event_artists_artist_id
                ON event_artists (artist_id)
                """
            )

            cursor.execute("SELECT id, name FROM venues")
            venues_by_name = {row["name"]: row["id"] for row in cursor.fetchall()}

            for name, district, scene_focus in sample_venues:
                if name in venues_by_name:
                    continue

                cursor.execute(
                    """
                    INSERT INTO venues (name, district, scene_focus)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (name, district, scene_focus),
                )
                venues_by_name[name] = cursor.fetchone()["id"]

            cursor.execute("SELECT id, name FROM artists")
            artists_by_name = {row["name"]: row["id"] for row in cursor.fetchall()}

            for name, genre in sample_artists:
                if name in artists_by_name:
                    continue

                cursor.execute(
                    """
                    INSERT INTO artists (name, genre)
                    VALUES (%s, %s)
                    RETURNING id
                    """,
                    (name, genre),
                )
                artists_by_name[name] = cursor.fetchone()["id"]

            cursor.execute("SELECT id, title FROM events")
            events_by_title = {row["title"]: row["id"] for row in cursor.fetchall()}

            for title, event_date, genre, venue_name in sample_events:
                if title in events_by_title:
                    continue

                cursor.execute(
                    """
                    INSERT INTO events (title, event_date, genre, venue_id)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (title, event_date, genre, venues_by_name[venue_name]),
                )
                events_by_title[title] = cursor.fetchone()["id"]

            cursor.execute("SELECT event_id, artist_id FROM event_artists")
            existing_event_artists = {
                (row["event_id"], row["artist_id"]) for row in cursor.fetchall()
            }

            for event_title, artist_name in sample_event_artists:
                edge = (events_by_title[event_title], artists_by_name[artist_name])
                if edge in existing_event_artists:
                    continue

                cursor.execute(
                    """
                    INSERT INTO event_artists (event_id, artist_id)
                    VALUES (%s, %s)
                    """,
                    edge,
                )
                existing_event_artists.add(edge)

        connection.commit()
