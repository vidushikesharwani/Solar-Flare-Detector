import "./Timeline.css";
import { useEffect, useState } from "react";

function Timeline() {
  const [events, setEvents] = useState([]);
  const [selectedClass, setSelectedClass] = useState("All");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("http://localhost:8000/api/events")
      .then((response) => {
        if (!response.ok) {
          throw new Error("Event data is not available.");
        }

        return response.json();
      })
      .then((data) => {
        setEvents(data.events || []);
        setLoading(false);
      })
      .catch((error) => {
        console.error("Failed to load events:", error);
        setError("Event data is currently unavailable.");
        setLoading(false);
      });
  }, []);

  const filteredEvents =
    selectedClass === "All"
      ? events
      : events.filter(
          (event) =>
            event.flare_class?.toUpperCase() === selectedClass
        );

  return (
    <div className="timeline-page">
      <h1>Solar Flare Timeline</h1>

      <p className="timeline-description">
        Chronological timeline of detected solar flare events.
      </p>

      {/* Flare class filters */}
      <div className="filter-buttons">
        {["All", "A", "B", "C", "M", "X"].map((flareClass) => (
          <button
            key={flareClass}
            onClick={() => setSelectedClass(flareClass)}
            className={selectedClass === flareClass ? "active" : ""}
          >
            {flareClass}
          </button>
        ))}
      </div>

      {/* Loading state */}
      {loading && (
        <p className="status-message">
          Loading detected flare events...
        </p>
      )}

      {/* Error / backend unavailable */}
      {!loading && error && (
  <div className="empty-state">
    <h2>Waiting for Detection Data</h2>

    <p>
      The Solar Flare Detector is connected to the backend,
      but no processed flare events are available yet.
    </p>

    <p>
      Once the detection pipeline generates event data,
      the timeline will automatically display it here.
    </p>
  </div>
)}

      {/* No events */}
      {!loading && !error && filteredEvents.length === 0 && (
        <p className="status-message">
          No flare events found for this class.
        </p>
      )}

      {/* Event list */}
      <div className="timeline-list">
        {!loading &&
          !error &&
          filteredEvents.map((event) => (
            <div className="event-card" key={event.event_id}>
              
              <div className="event-header">
                <h2>{event.flare_class}</h2>
                <span>{event.instrument}</span>
              </div>

              <div className="event-times">
                <div>
                  <strong>Start</strong>
                  <p>{event.start_time}</p>
                </div>

                <div>
                  <strong>Peak</strong>
                  <p>{event.peak_time}</p>
                </div>

                <div>
                  <strong>Decay</strong>
                  <p>{event.end_time}</p>
                </div>
              </div>

              <button
                onClick={() =>
                  (window.location.href = `/dashboard?event=${event.event_id}`)
                }
              >
                View on Dashboard
              </button>

            </div>
          ))}
      </div>
    </div>
  );
}

export default Timeline;