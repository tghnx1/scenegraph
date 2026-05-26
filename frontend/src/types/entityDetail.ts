import type { ArtistDetail } from './artist'
import type { EventDetail } from './event'
import type { PromoterDetail } from './promoter'
import type { VenueDetail } from './venue'

export type EntityDetail =
  | ArtistDetail
  | EventDetail
  | PromoterDetail
  | VenueDetail
