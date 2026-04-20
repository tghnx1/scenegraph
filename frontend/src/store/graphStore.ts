import { create } from 'zustand'
import type { GraphNode } from '../types/graph'

interface GraphStore {
  //state
  activeGenre:  string | null
  selectedNode: GraphNode | null

  //actions
  setGenre:     (genre: string | null) => void
  setSelected:  (node: GraphNode | null) => void
  clearAll:     () => void
}

export const useGraphStore = create<GraphStore>((set) => ({
  activeGenre:  null,
  selectedNode: null,

  setGenre:    (activeGenre)  => set({ activeGenre }),
  setSelected: (selectedNode) => set({ selectedNode }),
  clearAll:    ()             => set({ activeGenre: null, selectedNode: null }),
}))