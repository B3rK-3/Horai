import React, { useCallback, useEffect, useState } from 'react'
import { endpoints } from '../api' // uses your endpoints.calendarToken() and endpoints.login()

export default function Connections() {
  const userID = localStorage.getItem('userID')
  const [gisReady, setGisReady] = useState(false)
  const [googleStatus, setGoogleStatus] = useState('')
  const [canvasToken, setCanvasToken] = useState('')
  const [canvasStatus, setCanvasStatus] = useState('')
  const [busy, setBusy] = useState(false)

  // ensure GIS script is available
  useEffect(() => {
    const check = () => setGisReady(!!window.google?.accounts?.oauth2)
    check()
    const id = window.setInterval(check, 300)
    return () => window.clearInterval(id)
  }, [])

  const connectGoogle = useCallback(() => {
    if (!gisReady) {
      setGoogleStatus('Google Identity Services not loaded yet.')
      return
    }
    if (!userID) {
      setGoogleStatus('Missing userID.')
      return
    }
    try {
      const codeClient = window.google.accounts.oauth2.initCodeClient({
        client_id: "768428005792-vqg3ld0gfjlhn10o3e9a5s0avimusjit.apps.googleusercontent.com",
        scope: "openid email profile https://www.googleapis.com/auth/calendar.readonly",
        ux_mode: "popup",
        prompt: "consent",
        access_type: "offline",
        callback: async (resp) => {
          setBusy(true)
          setGoogleStatus('Exchanging code with backend...')
          try {
            const r = await fetch(endpoints.calendarToken(), {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ userID, code: resp.code }),
              credentials: 'include',
            })
            const data = await r.json().catch(() => ({}))
            if (r.ok) {
              setGoogleStatus('Google Calendar connected ✔')
            } else {
              setGoogleStatus(`Failed: ${data.error || r.statusText}`)
            }
          } catch (e) {
            setGoogleStatus('Network error while exchanging code.')
          } finally {
            setBusy(false)
          }
        },
      })
      codeClient.requestCode()
    } catch (e) {
      console.error(e)
      setGoogleStatus('Failed to initialize Google auth.')
    }
  }, [gisReady, userID])

  const saveCanvas = useCallback(async (e) => {
    e.preventDefault()
    if (!canvasToken.trim()) {
      setCanvasStatus('Please enter a token.')
      return
    }
    setBusy(true)
    setCanvasStatus('Saving token...')
    try {
      // your backend previously handled canvasToken via POST /canvasToken
      const resp = await fetch(endpoints.canvasToken(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userID, canvasToken: canvasToken.trim() }),
        credentials: 'include',
      })
      const data = await resp.json().catch(()=> ({}))
      if (resp.ok) {
        setCanvasStatus('Canvas token saved ✔')
        setCanvasToken('')
      } else {
        setCanvasStatus(`Error saving token: ${data.error || resp.statusText}`)
      }
    } catch (err) {
      setCanvasStatus('Network error during connection.')
    } finally {
      setBusy(false)
    }
  }, [canvasToken])

  return (
    <section className="integrations-card">
      <h3 className="section-title">Connect Your Accounts</h3>

      {/* Google Calendar */}
      <div className="integration-block">
        <div className="integration-head">
          <div>
            <div className="integration-title">Google Calendar</div>
            <div className="integration-subtitle">See your calendar in Horai.</div>
          </div>
          <button
            className="btn btn-google"
            onClick={connectGoogle}
            disabled={!gisReady || !userID || busy}
          >
            {gisReady ? 'Connect Google Calendar' : 'Loading...'}
          </button>
        </div>
        {googleStatus && (
          <p className={googleStatus.includes('✔') ? 'status-ok' : 'status-msg'}>
            {googleStatus}
          </p>
        )}
      </div>

      <hr className="integration-sep" />

      {/* Canvas Token */}
      <div className="integration-block">
        <div className="integration-title">Canvas LMS Token</div>
        <p className="integration-subtitle">Import assignments and due dates.</p>
        <form className="form" onSubmit={saveCanvas}>
          <label htmlFor="canvas-token-input" className="label">Canvas API Token</label>
          <input
            id="canvas-token-input"
            className="input"
            type="text"
            placeholder="Paste your Canvas token"
            value={canvasToken}
            onChange={(e) => setCanvasToken(e.target.value)}
            disabled={busy}
            autoComplete="off"
          />
          <div className="form-row">
            <button className="btn btn-primary" type="submit" disabled={busy}>
              Save Token
            </button>
          </div>
        </form>
        {canvasStatus && (
          <p className={canvasStatus.includes('✔') ? 'status-ok' : 'status-msg'}>
            {canvasStatus}
          </p>
        )}
      </div>
    </section>
  )
}
