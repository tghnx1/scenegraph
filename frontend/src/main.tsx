import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.tsx'
import './styles/base.css' //tokens, global reset, typography
import './styles/graph.css' //graph page layout, graph canvas, filter controls
import './styles/search-results.css' //search input, result cards, detail panel pieces
import './styles/responsive.css' //mobile overrides
import { applyCssVars } from './styles/colors'

//apply ts defined palette to css vars before app mounts
applyCssVars()

const root = ReactDOM.createRoot(document.getElementById('root')!);
root.render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)
