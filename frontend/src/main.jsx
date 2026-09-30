import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// Self-hosted, so the page carries no third-party font request and no
// render-blocking link to a font CDN.
import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import '@fontsource-variable/source-serif-4'

import App from './App.jsx'
import './styles/app.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)