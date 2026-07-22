import type { NodeType } from '../../types/graph.ts'

export const GRAPH_NODE_TYPES: NodeType[] = ['venue', 'artist', 'promoter', 'event']

export const GRAPH_NODE_TYPE_ITEMS = [
  {
    type: 'venue',
    label: 'Venue',
    shapeClass: 'bg-[var(--venue)] [clip-path:polygon(50%_0,100%_100%,0_100%)]',
  },
  {
    type: 'artist',
    label: 'Artist',
    shapeClass: 'bg-[var(--artist)] [clip-path:polygon(25%_6%,75%_6%,100%_50%,75%_94%,25%_94%,0_50%)]',
  },
  {
    type: 'promoter',
    label: 'Promoter',
    shapeClass: 'bg-[var(--promoter)]',
  },
  {
    type: 'event',
    label: 'Event',
    shapeClass: 'rounded-full bg-[var(--event)]',
  },
] satisfies Array<{
  type: NodeType
  label: string
  shapeClass: string
}>
