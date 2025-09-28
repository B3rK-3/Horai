import React, { useEffect, useRef, useState } from 'react'

// Props:
// - backendBase: e.g. "https://horai-dun.vercel.app" or "http://localhost:3000"
// - initialOpen?: boolean
export default function ChatWidget({ backendBase, initialOpen = false }) {
const userID = localStorage.getItem('userID')
  const [open, setOpen] = useState(initialOpen)
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [conversation, setConversation] = useState([
    { role: 'model', parts: ['Hi! How can I help you with your schedule today?'] },
  ])
  const bodyRef = useRef(null)

  useEffect(() => {
    if (open && bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight
    }
  }, [open, conversation])

  const toggle = () => setOpen(o => !o)

  async function sendMessage() {
    const msg = input.trim()
    if (!msg || sending) return
    setError('')
    setSending(true)

    // 1) add user message locally
    const nextConversation = [
      ...conversation,
      { role: 'user', parts: [msg] },
    ]
    setConversation(nextConversation)
    setInput('')

    try {
      const res = await fetch(`${backendBase}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // backend expects: { convo: [{ role, parts: ['...'] }, ...] }
        body: JSON.stringify({ userID,convo: nextConversation }),
        credentials: 'include', // keep cookies if your backend uses them
      })

      if (!res.ok) {
        const txt = await safeText(res)
        throw new Error(`Chat failed (${res.status}): ${txt}`)
      }

      const data = await res.json().catch(() => ({}))

      // Expect backend returns something like { reply: "..." }
      // If your backend returns the full updated convo, adopt it instead.
      const botText =
        data.chatMessage ||
        'Done'

      setConversation(cur => [
        ...cur,
        { role: 'model', parts: [String(botText)] },
      ])

    } catch (e) {
      console.error('Chat error:', e)
      setError(e.message || 'Network error')
      // optionally add an error bot bubble
      setConversation(cur => [
        ...cur,
        { role: 'model', parts: ['Sorry—there was a problem reaching the server.'] },
      ])
    } finally {
      setSending(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <>
      {/* Floating toggle button */}
      <button
        className="chat-toggle-btn"
        aria-label={open ? 'Close chat' : 'Open chat'}
        onClick={toggle}
        id='chatBtn'
      >
        {open ? '×' : 'Chat'}
      </button>

      {/* Backdrop */}
      {open && <div className="chat-backdrop" onClick={toggle} />}

      {/* Panel */}
      <div className={`chat-panel ${open ? 'open' : ''}`} role="dialog" aria-modal="true" aria-label="Chatbot">
        <div className="chat-header">
          <div className="chat-title">Horai Chat</div>
          <button className="chat-close" onClick={toggle} aria-label="Close">×</button>
        </div>

        <div className="chat-body" ref={bodyRef}>
          {conversation.map((m, i) => (
            <div key={i} className={`chat-bubble ${m.role === 'user' ? 'from-user' : 'from-bot'}`}>
              {m.parts?.join('\n')}
            </div>
          ))}
          {sending && (
            <div className="chat-bubble from-bot">
              <span className="typing-dot" /> <span className="typing-dot" /> <span className="typing-dot" />
            </div>
          )}
        </div>

        {error && <div className="chat-error">{error}</div>}

        <div className="chat-input-row">
          <textarea
            className="chat-input"
            placeholder="Type a message… (Enter to send, Shift+Enter for newline)"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={sending}
            rows={2}
          />
          <button className="chat-send" onClick={sendMessage} disabled={sending || !input.trim()}>
            Send
          </button>
        </div>
      </div>
    </>
  )
}

async function safeText(res) {
  try { return await res.text() } catch { return '' }
}
