// frontend/calendar.js

function mapEventsToCalendar(events) {
  return events.map((e) => ({
    title: `${e.event_type.toUpperCase()}: ${e.description}`,
    start: e.created_at,
    allDay: false,
  }));
}

function initCalendar(events) {
  const calendarEl = document.getElementById("calendar");
  if (!calendarEl) return;

  const mapped = mapEventsToCalendar(events);

  const calendar = new FullCalendar.Calendar(calendarEl, {
    initialView: "dayGridMonth",
    locale: "es",
    height: 500,
    events: mapped,
  });

  calendar.render();
}
