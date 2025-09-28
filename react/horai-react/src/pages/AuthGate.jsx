import React, { useState } from 'react'
import { endpoints } from '../api'

export default function AuthGate({ onAuth }) {
  const [mode, setMode] = useState('login') // 'login' | 'register'
  const [status, setStatus] = useState('')
  const [canvasStatus, setCanvasStatus] = useState('')
  const [canvasToken, setCanvasToken] = useState('')

  async function handleLogin(e) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    try {
      const resp = await fetch(endpoints.login(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: form.get('email'), password: form.get('password') })
      })
      if (resp.ok) {
        const data = await resp.json()
        console.log(data)
        onAuth(data.userID)
      } else setStatus('Login failed. Check your credentials.')
    } catch (err) {
      console.error(err); setStatus('Network error during login.')
    }
  }

  async function handleRegister(e) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    try {
      const resp = await fetch(endpoints.register(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: form.get('email'), password: form.get('password') })
      })
      if (resp.ok) {
        const data = await resp.json()
        console.log(data)
        onAuth(data.userID)
      } else setStatus('Registration failed. The email might already be in use.')
    } catch (err) {
      console.error(err); setStatus('Network error during registration.')
    }
  }

  async function saveCanvasToken(e) {
    e.preventDefault()
    if (!canvasToken.trim()) {
      setCanvasStatus('Please enter a token.')
      return
    }
    try {
      const resp = await fetch(endpoints.login(), { // your backend expects /login for that in your code
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ canvasToken })
      })
      const data = await resp.json().catch(()=>({}))
      if (resp.ok) {
        setCanvasStatus('Canvas Token Saved Successfully!')
        setCanvasToken('')
      } else {
        setCanvasStatus(`Error saving token: ${data.error || 'Server error.'}`)
      }
    } catch (err) {
      console.error(err); setCanvasStatus('Network error during connection.')
    }
  }

  return (
    <div className="container login-register-container" id="login-container" style={{ display: 'block' }}>
      {mode === 'login' ? (
        <>
          <h1>Welcome to Horai</h1>
          <p>Let the goddesses of time guide your day.</p>
          <form onSubmit={handleLogin}>
            <input name="email" type="email" placeholder="Email" required />
            <input name="password" type="password" placeholder="Password" required />
            <button type="submit">Log In</button>
          </form>
          {status && <p style={{color:'red'}}>{status}</p>}
          <p>Don't have an account? <a href="#" id="show-register" onClick={(e)=>{e.preventDefault();setMode('register')}}>Register here</a></p>

          <hr />
          <div className="lms-connect-section">
            <h3>Canvas LMS Token</h3>
            <form onSubmit={saveCanvasToken} className="event-form">
              <label htmlFor="canvas-token-input">Canvas API Token</label>
              <input id="canvas-token-input" type="text" value={canvasToken} onChange={e=>setCanvasToken(e.target.value)} placeholder="Paste your generated Canvas token here" />
              <button type="submit">Save Canvas Token</button>
            </form>
            {canvasStatus && <p className="status-message" id="canvas-status">{canvasStatus}</p>}
          </div>
        </>
      ) : (
        <>
          <h1>Create Your Account</h1>
          <form onSubmit={handleRegister}>
            <input name="name" type="text" placeholder="Name" required />
            <input name="email" type="email" placeholder="Email" required />
            <input name="password" type="password" placeholder="Password" required />
            <button type="submit">Register</button>
          </form>
          {status && <p style={{color:'red'}}>{status}</p>}
          <p>Already have an account? <a href="#" id="show-login" onClick={(e)=>{e.preventDefault();setMode('login')}}>Log in here</a></p>
        </>
      )}
    </div>
  )
}
