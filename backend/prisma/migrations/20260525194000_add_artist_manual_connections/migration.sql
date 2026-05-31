CREATE TABLE artist_manual_connections (
    source_artist_id BIGINT NOT NULL,
    connected_artist_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT artist_manual_connections_pkey PRIMARY KEY (source_artist_id, connected_artist_id),
    CONSTRAINT artist_manual_connections_source_artist_id_fkey
        FOREIGN KEY (source_artist_id)
        REFERENCES artists(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT artist_manual_connections_connected_artist_id_fkey
        FOREIGN KEY (connected_artist_id)
        REFERENCES artists(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT artist_manual_connections_no_self_link
        CHECK (source_artist_id <> connected_artist_id)
);

CREATE INDEX artist_manual_connections_connected_artist_id_idx
    ON artist_manual_connections(connected_artist_id);
