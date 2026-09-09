function formatTime(timestamp) {
  if (!timestamp) return "—";

  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return String(timestamp);
  }

  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDate(timestamp) {
  if (!timestamp) return "—";

  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return String(timestamp);
  }

  return date.toLocaleDateString([], {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function getFlareClass(event) {
  return (
    event?.flare_class ||
    event?.predicted_class ||
    "—"
  ).toString().toUpperCase();
}

function getClassStyle(flareClass) {
  switch (flareClass) {
    case "X":
      return "event-class-x";

    case "M":
      return "event-class-m";

    case "C":
      return "event-class-c";

    case "B":
      return "event-class-b";

    default:
      return "event-class-a";
  }
}

function PreviewEvents() {
  const previewEvents = [
    {
      id: "FLR-001",
      time: "14:32",
      flareClass: "M",
    },
    {
      id: "FLR-002",
      time: "16:07",
      flareClass: "C",
    },
    {
      id: "FLR-003",
      time: "18:41",
      flareClass: "X",
    },
  ];

  return (
    <div className="events-preview">
      {previewEvents.map((event) => (
        <div className="event-row" key={event.id}>
          <div className="event-marker" />

          <div className="event-main">
            <div className="event-id">
              {event.id}
            </div>

            <div className="event-meta">
              <span>{event.time}</span>

              <span
                className={`event-class-badge ${getClassStyle(
                  event.flareClass
                )}`}
              >
                {event.flareClass}
              </span>

              <span className="event-detected">
                Detected
              </span>
            </div>
          </div>

          <div className="event-state">
            DETECTED
          </div>
        </div>
      ))}

      <div className="events-preview-note">
        Displaying interface preview data until processed
        observations are available.
      </div>
    </div>
  );
}

export default function EventsPanel({ events = [] }) {
  const hasEvents =
    Array.isArray(events) && events.length > 0;

  return (
    <div className="events-panel">

      <div className="events-intro">
        <div>
          <span className="events-kicker">
            EVENT TIMELINE
          </span>

          <h3>Recent Solar Events</h3>

          <p>
            Detected solar flare activity from
            Aditya-L1 observations.
          </p>
        </div>
      </div>

      {hasEvents ? (
        <div className="events-list">
          {events.map((event, index) => {
            const flareClass =
              getFlareClass(event);

            return (
              <div
                className="event-row"
                key={
                  event?.event_id ||
                  `${event?.start_time}-${index}`
                }
              >
                <div className="event-marker" />

                <div className="event-main">
                  <div className="event-id">
                    {event?.event_id ||
                      `FLR-${String(index + 1).padStart(
                        3,
                        "0"
                      )}`}
                  </div>

                  <div className="event-meta">
                    <span>
                      {formatTime(event?.start_time)}
                    </span>

                    <span
                      className={`event-class-badge ${getClassStyle(
                        flareClass
                      )}`}
                    >
                      {flareClass}
                    </span>

                    <span className="event-detected">
                      Detected
                    </span>
                  </div>
                </div>

                <div className="event-details">
                  <span>
                    {formatDate(event?.start_time)}
                  </span>

                  <span>
                    {event?.instrument || "Aditya-L1"}
                  </span>
                </div>

                <div className="event-state">
                  DETECTED
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <PreviewEvents />
      )}

    </div>
  );
}