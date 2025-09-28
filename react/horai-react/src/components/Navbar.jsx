import React from 'react'
import { NavLink } from 'react-router-dom'

export default function Navbar({ onLogout }) {
  return (
    <nav className="navbar">
      <div className="navbar-container">
        <NavLink to="/calendar" className="brand">Horai</NavLink>
        <ul className="nav-links">
          <li>
            <NavLink
              to="/calendar"
              className={({ isActive }) => isActive ? 'active' : undefined}
            >
              Calendar
            </NavLink>
          </li>
          <li>
            <NavLink
              to="/connections"
              className={({ isActive }) => isActive ? 'active' : undefined}
            >
              Connections
            </NavLink>
          </li>
          <li>
            <a href="#" id="nav-logout" onClick={(e)=>{ e.preventDefault(); onLogout?.() }}>
              Logout
            </a>
          </li>
        </ul>
      </div>
    </nav>
  )
}
