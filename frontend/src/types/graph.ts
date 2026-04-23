export type NodeType = 'artist' | 'venue' | 'promoter' //NodeType union

export interface GraphNode { //GraphNode interface
  id:         string
  type:       NodeType //can only be artist/venue/promoter
  label:      string
  genres:     string[]
  eventCount: number
  lat?:       number //with ? --> optional, only for venue (if necessary)
  lng?:       number
  raVenueId?: string
}

export interface GraphEdge { //GraphEdge interface, shape of every line in the force graph
  source: string //node id
  target: string //node id
  weight: number //line thickness
}

export interface GraphData { //shape of the API response from GET /graph (what useApi returns and what ForceGraph2D receives)
  nodes: GraphNode[]
  links: GraphEdge[] //react-force-graph-2d expects "links" not "edges", dunno how this will work later (hopefully express return "links" too)
}
