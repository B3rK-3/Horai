import React, { useEffect, useState, useCallback } from 'react'
import { endpoints } from '../api'
import BigCalendar from '../components/BigCalendar'
import ToastCalendar from '../components/ToastCalendar'

export default function CalendarPage() {
  const [events, setEvents] = useState([])
  const [date, setDate] = useState(new Date())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const userID = localStorage.getItem('userID')
  const load = useCallback(async (signal) => {
    if (!userID) return
    setLoading(true)
    setError('')
    try {
      const res = await fetch(endpoints.eventsUnified(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userID }),
        signal,
      })
      if (!res.ok) {
        const msg = await safeText(res)
        throw new Error(`Failed to fetch unified schedule (${res.status}): ${msg}`)
      }
      const data = await res.json()
      console.log(data)
      setEvents(data.tasks || [])
    } catch (e) {
      if (e.name !== 'AbortError') {
        console.error('Fetch /getTasks error:', e)
        setError(e.message || 'Network error fetching events')
      }
    } finally {
      setLoading(false)
    }
  }, [userID])

  useEffect(() => {
    const ac = new AbortController()
    load(ac.signal)
    return () => ac.abort()
  }, [load])

  return (
    <div id="calendar-page" className="page" style={{ display: 'block' }}>
      <div id="calendar-header" style={{ display:'flex', alignItems:'center', gap:8 }}>
        <button onClick={() => setDate(d => new Date(d.getFullYear(), d.getMonth(), d.getDate() - 7))}>&lt;</button>
        <h2 style={{ margin: 0 }}>{formatHeaderRange(date)}</h2>
        <button onClick={() => setDate(d => new Date(d.getFullYear(), d.getMonth(), d.getDate() + 7))}>&gt;</button>
        <button style={{ marginLeft: 'auto' }} onClick={() => load()}>Refresh</button>
      </div>

      {loading && <p style={{marginTop:8}}>Loading events…</p>}
      {error && <p style={{marginTop:8,color:'crimson'}}>{error}</p>}

      <div className="schedule-grid-container">
        <ToastCalendar
          events={events}
          date={date}
          onNavigate={setDate}
          onSelectEvent={(evt) => console.log('selected event', evt)}
          onSelectSlot={(slot) => console.log('selected slot', slot)}
    
        />
      </div>
    </div>
  )
}

function formatHeaderRange(date) {
  const start = new Date(date)
  const end = new Date(date); end.setDate(end.getDate() + 6)
  const m = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  const s = `${m[start.getMonth()]} ${start.getDate()}`
  const e = `${m[end.getMonth()]} ${end.getDate()}, ${end.getFullYear()}`
  return `${s} - ${e}`
}

async function safeText(res) {
  try { return await res.text() } catch { return '' }
}
