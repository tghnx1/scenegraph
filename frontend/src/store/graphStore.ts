import { create } from 'zustand'
import type { GraphNode } from '../types/graph'

interface GraphStore {
  //state
  selectedNode: GraphNode | null

  //actions
  setSelected:  (node: GraphNode | null) => void
}

export const useGraphStore = create<GraphStore>((set) => ({
  selectedNode: null,

  setSelected: (selectedNode) => set({ selectedNode }),
}))
