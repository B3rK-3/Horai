import React, { useEffect, useMemo, useRef } from 'react'
import Calendar from '@toast-ui/react-calendar'
import '@toast-ui/calendar/dist/toastui-calendar.min.css'

// Map your events to Toast UI's event shape
function toTuiEvents(events = []) {
  return events
    .map((evt) => {
      const startStr = evt['start time'] || evt.startTime
      const endStr   = evt.endtime || evt.endTime
      const dueStr   = evt.duedate || evt.dueDate

      let start, end, isAllday = false
      if (startStr && endStr) {
        start = new Date(startStr)
        end   = new Date(endStr)
      } else if (dueStr) {
        // treat dueDate as a 9–10am block by default
        start = new Date(dueStr); start.setHours(9, 0, 0, 0)
        end   = new Date(start.getTime() + 60 * 60 * 1000)
      } else {
        return null
      }

      const id = evt.id || evt._id || `${evt.title}-${start.toISOString()}`
      const priority = (evt.priority || '').toLowerCase()

      // simple color by priority
      const colorMap = {
        high:   { bg: '#fdecea', border: '#d32f2f' },
        medium: { bg: '#e3f2fd', border: '#1976d2' },
        med:    { bg: '#e3f2fd', border: '#1976d2' },
        low:    { bg: '#e8f5e9', border: '#2e7d32' },
      }
      const c = colorMap[priority] || { bg: '#f3f3f3', border: '#999' }

      return {
        id,
        calendarId: 'default',
        title: evt.title || evt.summary || 'Untitled Event',
        start,
        end,
        isAllday,
        backgroundColor: c.bg,
        borderColor: c.border,
        raw: evt, // keep original around if you need it
      }
    })
    .filter(Boolean)
}

const calendars = [
  {
    id: 'default',
    name: 'Schedule',
    backgroundColor: '#1976d2',
    borderColor: '#0d47a1',
  },
]

export default function ToastCalendar({
  events,
  date,
  view = 'week',            // 'week' | 'month' | 'day'
  onViewChange,             // optional: (newView) => void
  onNavigate,               // (newDate: Date) => void
  onSelectEvent,            // (event) => void
}) {
  const ref = useRef(null)
  const tuiEvents = useMemo(() => toTuiEvents(events), [events])

  // keep Toast UI's internal date in sync when prop `date` changes
  useEffect(() => {
    const inst = ref.current?.getInstance?.()
    if (!inst) return
    inst.setDate(date)
  }, [date])

  // Toast UI emits events with a { event } shape on click
  const handleClick = (info) => {
    if (onSelectEvent) onSelectEvent(info?.event)
  }

  // When the calendar navigates (via built-in controls), reflect it upward
  const handleAfterRender = () => {
    const inst = ref.current?.getInstance?.()
    if (!inst || !onNavigate) return
    const currentDate = inst.getDate()
    onNavigate(new Date(currentDate))
  }

  return (
    <Calendar
      ref={ref}
      height="calc(100vh - 220px)"
      view={view}
      calendars={calendars}
      events={tuiEvents}
      usageStatistics={false}
      week={{taskView: false,
          eventView: true, startDayOfWeek: 0, hourStart: 0, hourEnd: 24 }}
      month={{ startDayOfWeek: 0 }}
      // handlers
      onClickEvent={handleClick}
      onAfterRenderEvent={handleAfterRender}
      // if you add a custom toolbar, call these:
      // inst.prev(), inst.next(), inst.today()
    />
  )
}

// Helpers to control navigation from outside:
// const inst = ref.current.getInstance()
// inst.prev(); inst.next(); inst.today(); inst.setDate(new Date())
