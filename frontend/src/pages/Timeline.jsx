import "./Timeline.css";
import { useState } from "react";
const events = [
  {
    id: 1,
    start: "10:30",
    peak: "10:42",
    decay: "11:05",
    flareClass: "M1.2",
    instrument: "SoLEXS",
  },
  {
    id: 2,
    start: "13:15",
    peak: "13:27",
    decay: "13:50",
    flareClass: "C3.5",
    instrument: "HEL1OS",
  },
  {
    id: 3,
    start: "16:40",
    peak: "16:52",
    decay: "17:20",
    flareClass: "B8.1",
    instrument: "SoLEXS",
  },
];

function Timeline() {
    const [selectedClass, setSelectedClass] = useState("All");

  const filteredEvents =
    selectedClass === "All"
      ? events
      : events.filter((event) => event.flareClass.startsWith(selectedClass));
  return (
    <div className="timeline-page">
      <h1>Solar Flare Timeline</h1>

      <p className="timeline-description">
        Chronological timeline of detected solar flare events.
      </p>

      <div className="timeline-list">
        {filteredEvents.map((event) => (
          <div className="event-card" key={event.id}>
            <div className="event-header">
              <h2>{event.flareClass}</h2>
              <span>{event.instrument}</span>
            </div>
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

            <div className="event-times">
              <div>
                <strong>Start</strong>
                <p>{event.start}</p>
              </div>

              <div>
                <strong>Peak</strong>
                <p>{event.peak}</p>
              </div>

              <div>
                <strong>Decay</strong>
                <p>{event.decay}</p>
              </div>
            </div>

            <button
  onClick={() =>
    (window.location.href = `/dashboard?event=${event.id}`)
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