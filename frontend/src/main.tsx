import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.tsx'
import './styles/base.css' //tokens, global reset, typography
import './styles/app.css' //app shell, navigation, footer
import './styles/graph.css' //graph page layout, graph canvas, filter controls
import './styles/dashboard.css' //dashboard and profile page shells and panels
import './styles/search.css' //search input, result cards, detail panel pieces
import './styles/mobile.css' //mobile overrides
import { applyStoredTheme } from './styles/colors'

applyStoredTheme()

const root = ReactDOM.createRoot(document.getElementById('root')!);
root.render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)
