function EventsPanel({ events = [] }) {
  const fallbackEvents = [
    {
      event_id: "FLR-001",
      peak_time: "14:32",
      flare_class: "M",
      instrument: "SoLEXS",
    },
    {
      event_id: "FLR-002",
      peak_time: "16:07",
      flare_class: "C",
      instrument: "HEL1OS",
    },
    {
      event_id: "FLR-003",
      peak_time: "18:41",
      flare_class: "X",
      instrument: "SoLEXS",
    },
  ];

  const displayEvents =
    events.length > 0
      ? events
      : fallbackEvents;

  function formatTime(value) {
    if (!value) return "--";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  return (
    <section
      className="events-section"
      id="events"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">EVENT TIMELINE</p>

          <h2>Recent Solar Events</h2>

          <p className="events-description">
            Detected solar flare activity from
            Aditya-L1 observations.
          </p>
        </div>
      </div>

      <div className="events-list">
        {displayEvents.map((event) => (
          <div
            className="event-row"
            key={event.event_id}
          >
            <div>
              <span className="event-id">
                {event.event_id}
              </span>

              <span className="event-instrument">
                {event.instrument || "Aditya-L1"}
              </span>
            </div>

            <span className="event-time">
              {formatTime(event.peak_time)}
            </span>

            <span
              className={`event-class class-${
                event.flare_class
              }`}
            >
              {event.flare_class || "A"}
            </span>

            <span className="event-status">
              Detected
            </span>
          </div>
        ))}
      </div>

      {events.length === 0 && (
        <p className="demo-note">
          Displaying interface preview data until
          processed observations are available.
        </p>
      )}
    </section>
  );
}

export default EventsPanel;