export interface Genre { //separate interface if genres are their own entities in the db
  id:   string
  name: string
  slug: string //URL-safe name used for filtering (like techno or dub-techno).
}

export interface Artist { //should match the shape returned by GET /artists/:id from express (used in ArtistPage)
  id:             string //sg_id
  raId?:           string //ra's id maybe unnecessary
  name:           string
  genres:         Genre[] //array to display both name and use slug for filtering without extra lookups
  bio?:           string
  claimed:        boolean //if profile is claimed to be used later to show an "Edit profile" to real artist
  eventCount?:    number
  artistLinks?:   string[] //artists
}

export interface SimilarArtist { //used by GET /artists/:id/similar
  artist:       Artist
  sharedEvents: number
  sharedGenres: string[]
}