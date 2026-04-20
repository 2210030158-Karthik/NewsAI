import React from 'react'
import ReactDOM from 'react-dom/client'
// Fix: Use './' because App.jsx and index.css are in the SAME 'src' folder
import App from './App.jsx'
import './index.css' // Import our global stylesheet

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

