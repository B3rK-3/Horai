import React, { useMemo } from "react"
import { Calendar, Views, dateFnsLocalizer } from "react-big-calendar"
import { format, parse, startOfWeek, getDay } from "date-fns"
import enUS from "date-fns/locale/en-US"
import "react-big-calendar/lib/css/react-big-calendar.css"

const locales = { "en-US": enUS }
const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: () => startOfWeek(new Date(), { weekStartsOn: 0 }),
  getDay,
  locales,
})

function normalizeToRbcEvents(events = []) {
  return events
    .map((evt) => {
      const startStr = evt["start time"] || evt.startTime
      const endStr   = evt.endtime || evt.endTime
      const dueStr   = evt.duedate || evt.dueDate

      let start, end
      if (startStr && endStr) {
        start = new Date(startStr)
        end   = new Date(endStr)
      } else if (dueStr) {
        start = new Date(dueStr); start.setHours(9,0,0,0)
        end   = new Date(start.getTime() + 60*60*1000)
      } else {
        return null
      }

      return {
        id: evt.id || evt._id || `${evt.title}-${start.toISOString()}`,
        title: evt.title || evt.summary || "Untitled Event",
        start,
        end,
        raw: evt,
      }
    })
    .filter(Boolean)
}

function eventPropGetter(event) {
  const priority = (event.raw?.priority || "").toLowerCase()
  let style = {}
  if (priority === "high") {
    style = { borderLeft: "4px solid #d32f2f", background: "#fdecea" }
  } else if (priority === "medium" || priority === "med") {
    style = { borderLeft: "4px solid #1976d2", background: "#e3f2fd" }
  } else if (priority === "low") {
    style = { borderLeft: "4px solid #2e7d32", background: "#e8f5e9" }
  }
  return { style }
}

export default function BigCalendar({
  events,
  date,
  onNavigate,
  defaultView = Views.WEEK,
  onSelectEvent,
  onSelectSlot,
}) {
  const rbcEvents = useMemo(() => normalizeToRbcEvents(events), [events])

  return (
    <Calendar
      localizer={localizer}
      events={rbcEvents}
      date={date}
      defaultView={defaultView}
      onNavigate={onNavigate}
      startAccessor="start"
      endAccessor="end"
      selectable
      popup
      step={30}
      timeslots={2}
      defaultDate={new Date()}
      eventPropGetter={eventPropGetter}
      onSelectEvent={onSelectEvent}
      onSelectSlot={onSelectSlot}
      style={{ height: "calc(100vh - 220px)" }}
    />
  )
}
