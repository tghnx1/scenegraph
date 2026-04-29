export type NodeType = 'artist' | 'venue' | 'promoter' | 'event' //NodeType union

export interface GraphNode { //GraphNode interface
  id:             string //sg_id
  type:           NodeType
  label:          string
  lat?:           number //venues
  lng?:           number //venues
  eventCount?:    number //venues
  address?:       string //venues
  genres?:        string[] //events amnd artists
  interestCount?: number //events
  date?:          string //events
  content?:       string //events
  eventLinks?:      string //events
  bio?:           string //artists
  
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
