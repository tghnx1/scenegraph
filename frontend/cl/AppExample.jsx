// Usage example in your main App component

import NetworkGraph from './NetworkGraph';

// Mock data structure (matches your scraped data format)
const mockRawData = {
  nodes: [
    { id: '1', type: 'artist', label: 'Artist A' },
    { id: '2', type: 'artist', label: 'Artist B' },
    { id: '3', type: 'venue', label: 'Club X' },
    { id: '4', type: 'venue', label: 'Hall Y' },
    { id: '5', type: 'event', label: 'Festival 2024' },
    { id: '6', type: 'promoter', label: 'Promoter Z' },
    // ... more nodes
  ],
  edges: [
    { s: '1', t: '3', w: 1 },      // Artist A performs at Club X
    { s: '2', t: '3', w: 2 },      // Artist B performs at Club X (weight 2)
    { s: '3', t: '5', w: 1 },      // Club X hosts Festival
    { s: '6', t: '5', w: 1 },      // Promoter Z organizes Festival
    // ... more edges
  ],
};

export default function App() {
  return <NetworkGraph rawData={mockRawData} />;
}
