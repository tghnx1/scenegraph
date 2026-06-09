export interface DashboardStatus {
  events: number
  artists: number
  venues: number
  promoters: number
  genres: number
  artists_no_bio: number
  artists_no_bio_percent?: number | null
  artists_no_genre?: number
  artists_no_genre_percent?: number | null
  first_event_date?: string | null
  last_event_date?: string | null
  artists_with_extracted_tags?: number
  artists_with_extracted_tags_percent?: number | null
  artists_with_extracted_genres?: number
  artists_with_extracted_genres_percent?: number | null
  events_without_description?: number
  events_without_description_percent?: number | null
  events_no_desc?: number
  events_no_desc_percent?: number | null
  events_without_genres?: number
  events_without_genres_percent?: number | null
  events_no_genres?: number
  events_no_genres_percent?: number | null
  events_without_artists?: number
  events_without_artists_percent?: number | null
  events_without_promoters?: number
  events_without_promoters_percent?: number | null
  events_without_venues?: number
  events_without_venues_percent?: number | null
  avg_artists_per_event?: number
  median_artists_per_event?: number
  avg_promoters_per_event?: number
  avg_genres_per_event?: number
  artist_embeddings?: number
  artist_embeddings_percent?: number | null
  event_embeddings?: number
  event_embeddings_percent?: number | null
  events_with_extracted_tags?: number
  events_with_extracted_tags_percent?: number | null
  events_with_extracted_genres?: number
  events_with_extracted_genres_percent?: number | null
  recommendation_feedback_rows?: number
  recommendation_feedback_rows_percent?: number | null
  top_ra_genres?: DashboardTopListItem[]
  top_extracted_genres?: DashboardTopListItem[]
  top_venues?: DashboardTopListItem[]
  top_promoters?: DashboardTopListItem[]
}

export interface DashboardTopListItem {
  name: string
  value: number
}
