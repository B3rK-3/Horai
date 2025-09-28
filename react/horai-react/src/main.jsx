import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'   // ✅ import it
import App from './App.jsx'
import './index.css' // put your style.css here or adjust imports

createRoot(document.getElementById('root')).render(<BrowserRouter>
    <App />
  </BrowserRouter>)
