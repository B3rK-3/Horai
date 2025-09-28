import React from 'react'

export default function Navbar({ onLogout }) {
  return (
    <nav className="navbar">
      <div className="navbar-container">
        <a href="#" className="brand" onClick={(e)=>e.preventDefault()}>Horai</a>
        <ul className="nav-links">
          <li><a href="#" className="active" onClick={(e)=>e.preventDefault()}>Calendar</a></li>
          <li><a href="#" id="nav-logout" onClick={(e)=>{e.preventDefault(); onLogout?.()}}>Logout</a></li>
        </ul>
      </div>
    </nav>
  )
}
