import React, { useEffect, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

const COLORS = {
  artist: '#8f77dd',
  venue: '#ff6b6b',
  event: '#4ecdc4',
  promoter: '#ffe66d',
};

const SIZES = {
  artist: 8,
  venue: 10,
  event: 7,
  promoter: 9,
};

export default function NetworkGraph({ rawData }) {
  const fgRef = useRef();
  const [filter, setFilter] = useState('all');
  const [selected, setSelected] = useState(null);
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });

  // Initialize graph data when filter changes
  useEffect(() => {
    const filteredNodes = filter === 'all' 
      ? rawData.nodes 
      : rawData.nodes.filter(n => n.type === filter);

    const nodeIds = new Set(filteredNodes.map(n => n.id));
    const filteredLinks = rawData.edges.filter(
      e => nodeIds.has(e.s) && nodeIds.has(e.t)
    );

    setGraphData({
      nodes: filteredNodes,
      links: filteredLinks.map(e => ({
        source: e.s,
        target: e.t,
        value: e.w || 1,
      })),
    });

    setSelected(null);
  }, [filter, rawData]);

  // Configure force simulation
  useEffect(() => {
    if (!fgRef.current) return;

    fgRef.current
      .d3Force('charge')?.strength(-300);
    fgRef.current
      .d3Force('link')?.distance(90);
    fgRef.current
      .d3Force('center')?.strength(0.1);
  }, []);

  const handleNodeClick = (node) => {
    setSelected(selected?.id === node.id ? null : node);
    // Optionally center camera on selected node
    if (fgRef.current) {
      const distance = 40;
      const distRatio = 1 + distance / Math.hypot(node.x, node.y);
      fgRef.current.centerAt(node.x * distRatio, node.y * distRatio, 800);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', fontFamily: 'system-ui, sans-serif' }}>
      {/* Controls */}
      <div style={{
        padding: '16px 20px',
        background: '#f8f9fa',
        borderBottom: '1px solid #e0e0e0',
        display: 'flex',
        gap: '12px',
        alignItems: 'center',
        flexWrap: 'wrap',
      }}>
        <label style={{ fontWeight: 600, color: '#333' }}>Filter by type:</label>
        {['all', 'artist', 'venue', 'event', 'promoter'].map(type => (
          <button
            key={type}
            onClick={() => setFilter(type)}
            style={{
              padding: '8px 16px',
              border: filter === type ? '2px solid #8f77dd' : '1px solid #ddd',
              background: filter === type ? '#8f77dd' : '#fff',
              color: filter === type ? '#fff' : '#333',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: 500,
              transition: 'all 0.2s',
            }}
          >
            {type.charAt(0).toUpperCase() + type.slice(1)}
          </button>
        ))}
        {selected && (
          <div style={{
            marginLeft: 'auto',
            padding: '8px 12px',
            background: '#fffacd',
            borderRadius: '4px',
            fontSize: '14px',
            color: '#333',
          }}>
            Selected: <strong>{selected.label}</strong> ({selected.type})
          </div>
        )}
      </div>

      {/* Graph Canvas */}
      <div style={{ flex: 1, position: 'relative' }}>
        <ForceGraph2D
          ref={fgRef}
          graphData={graphData}
          nodeCanvasObject={(node, ctx, globalScale) => {
            const size = SIZES[node.type] || 8;
            const isSelected = selected?.id === node.id;
            const radius = isSelected ? size + 3 : size;

            // Draw node circle
            ctx.beginPath();
            ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
            ctx.fillStyle = COLORS[node.type] || '#888';
            ctx.globalAlpha = isSelected ? 1 : 0.85;
            ctx.fill();
            ctx.globalAlpha = 1;

            // Draw selection ring
            if (isSelected) {
              ctx.strokeStyle = '#fff';
              ctx.lineWidth = 2 / globalScale;
              ctx.stroke();
            }

            // Draw label for large/selected nodes
            if (isSelected || radius >= 12) {
              ctx.fillStyle = '#333';
              ctx.font = `${isSelected ? 500 : 400} 11px sans-serif`;
              ctx.textAlign = 'center';
              ctx.fillText(node.label, node.x, node.y + radius + 12);
            }
          }}
          linkCanvasObject={(link, ctx, globalScale) => {
            const isSelected = 
              selected?.id === link.source.id || 
              selected?.id === link.target.id;

            ctx.beginPath();
            ctx.moveTo(link.source.x, link.source.y);
            ctx.lineTo(link.target.x, link.target.y);
            ctx.strokeStyle = isSelected 
              ? 'rgba(127,119,221,0.6)' 
              : 'rgba(128,128,128,0.18)';
            ctx.lineWidth = (isSelected ? 1.5 : 0.8) * (link.value || 1) * 0.4;
            ctx.stroke();
          }}
          onNodeClick={handleNodeClick}
          onBackgroundClick={() => setSelected(null)}
          width={typeof window !== 'undefined' ? window.innerWidth : 800}
          height={typeof window !== 'undefined' ? window.innerHeight : 600}
          nodeColor={() => 'transparent'}
          linkDirectionalParticles={2}
          linkDirectionalParticleWidth={1.5}
        />
      </div>
    </div>
  );
}
