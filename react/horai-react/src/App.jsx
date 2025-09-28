import React, { useEffect, useState } from 'react'
import Navbar from './components/Navbar'
import CalendarPage from './pages/CalendarPage'
import AuthGate from './pages/AuthGate'
import ChatWidget from './components/ChatWidget'
// ❌ remove this: import { serializeUseCacheCacheStore } from 'next/...'

export default function App() {
  const [userID, setUserID] = useState(null)

  useEffect(() => {
    if (userID) {
      // update the URL without reload
      window.history.replaceState({}, '', '/calendar')
    } else {
      window.history.replaceState({}, '', '/login')
    }
  }, [userID])

  if (!userID) return <AuthGate onAuth={setUserID} />

  return (
    <div id="app">
      <div id="main-app-container" style={{ display: 'block' }}>
        <ChatWidget backendBase="https://horai-dun.vercel.app"  userID={userID}/>
        <Navbar onLogout={() => { setUserID(null); }} />
        <div className="container" id="page-content">
          <CalendarPage userID={userID} />
        </div>
      </div>
    </div>
  )
}
