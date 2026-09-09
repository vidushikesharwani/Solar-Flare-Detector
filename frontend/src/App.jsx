import "./App.css";
import { useEffect, useState } from "react";
import { getFlux, getEvents, getPredictions } from "./api";
import FluxChart from "./FluxChart";
import SolarActivity from "./SolarActivity";
import ThreatGauge from "./ThreatGauge";
import EventsPanel from "./EventsPanel";

function App() {
  const [fluxData, setFluxData] = useState([]);
  const [events, setEvents] = useState([]);
  const [predictions, setPredictions] = useState([]);

  const [loading, setLoading] = useState(true);
  const [backendConnected, setBackendConnected] = useState(false);

  useEffect(() => {
    async function loadDashboard() {
      const results = await Promise.allSettled([
        getFlux(),
        getEvents(),
        getPredictions(),
      ]);

      let connected = false;

      if (results[0].status === "fulfilled") {
        setFluxData(results[0].value.data || []);
        connected = true;
      }

      if (results[1].status === "fulfilled") {
        setEvents(results[1].value.events || []);
        connected = true;
      }

      if (results[2].status === "fulfilled") {
        setPredictions(results[2].value.predictions || []);
        connected = true;
      }

      setBackendConnected(connected);
      setLoading(false);
    }

    loadDashboard();
  }, []);

  const latestPrediction =
    predictions.length > 0
      ? predictions[predictions.length - 1]
      : null;

  const latestEvent =
    events.length > 0
      ? events[events.length - 1]
      : null;

  const flareClass =
    latestPrediction?.predicted_class ||
    latestEvent?.flare_class ||
    "A";

  const threatProbability =
    latestPrediction?.flare_probability ?? 0.12;

  const statusText =
    flareClass === "X"
      ? "Extreme solar activity detected"
      : flareClass === "M"
      ? "High solar activity detected"
      : flareClass === "C"
      ? "Active solar conditions"
      : "No significant flare activity";

  return (
    <div className="app">
      <div className="stars stars-one"></div>
      <div className="stars stars-two"></div>
      <div className="nebula"></div>

      <nav className="navbar">
        <div className="brand">
          <span className="brand-dot"></span>
          SOLAR FLARE DETECTOR
        </div>

        <div className="nav-links">
          <a href="#dashboard">Dashboard</a>
          <a href="#events">Events</a>
          <a href="#about">About</a>
        </div>

        <div className="live-status">
          <span className="status-dot"></span>
          {backendConnected ? "DATA CONNECTED" : "SYSTEM READY"}
        </div>
      </nav>

      <main id="dashboard">

        {/* HERO */}
        <section className="hero-section">
          <div className="hero-content">
            <p className="eyebrow">
              ADITYA-L1 • SOLAR OBSERVATION
            </p>

            <h1>
              Understanding
              <span> Our Sun</span>
            </h1>

            <p className="hero-description">
              Monitor solar activity and detect solar flares through
              observations from India's Aditya-L1 mission.
            </p>

            <button
              className="explore-button"
              onClick={() =>
                document
                  .getElementById("dashboard-monitoring")
                  ?.scrollIntoView({ behavior: "smooth" })
              }
            >
              Explore Dashboard
              <span>→</span>
            </button>
          </div>

          <SolarActivity flareClass={flareClass} />
        </section>

        {/* MONITORING */}
        <section
          className="activity-section"
          id="dashboard-monitoring"
        >
          <div className="section-heading">
            <div>
              <p className="eyebrow">LIVE MONITORING</p>
              <h2>Current Solar Activity</h2>
            </div>

            <div className="activity-state">
              <span></span>
              {loading ? "Loading" : "Monitoring"}
            </div>
          </div>

          <div className="dashboard-grid">

            {/* FLUX */}
            <div className="flux-card glass-card">
              <div className="card-header">
                <div>
                  <p className="card-label">SOLAR FLUX</p>
                  <h3>SoLEXS + HEL1OS</h3>
                </div>

                <span className="time-label">
                  {loading
                    ? "LOADING"
                    : backendConnected
                    ? "LIVE DATA"
                    : "WAITING"}
                </span>
              </div>

              <div className="chart-container">
                <FluxChart
                  data={fluxData}
                  loading={loading}
                />
              </div>

              <div className="chart-legend">
                <span>
                  <i className="legend-blue"></i>
                  SoLEXS
                </span>

                <span>
                  <i className="legend-violet"></i>
                  HEL1OS
                </span>
              </div>
            </div>

            {/* FLARE STATUS */}
            <div className="metric-card glass-card">
              <p className="card-label">FLARE STATUS</p>

              <div className={`flare-class flare-${flareClass}`}>
                {flareClass}
              </div>

              <p className="metric-description">
                {statusText}
              </p>

              {latestEvent && (
                <div className="small-data">
                  Latest detected event
                </div>
              )}
            </div>

            {/* THREAT */}
            <div className="metric-card glass-card">
              <p className="card-label">
                ML THREAT PROBABILITY
              </p>

              <ThreatGauge
                probability={threatProbability}
              />
            </div>
          </div>
        </section>

        {/* EVENTS */}
        <EventsPanel events={events} />

        {/* ABOUT */}
        <section className="about-section" id="about">
          <div className="section-heading">
            <div>
              <p className="eyebrow">THE MISSION</p>
              <h2>Observing Solar Activity</h2>
              <p className="section-description">
                Combining complementary X-ray observations with
                data-driven flare detection.
              </p>
            </div>
          </div>

          <div className="about-grid">
            <div className="about-card">
              <span className="about-number">01</span>

              <h3>SoLEXS</h3>

              <p>
                Soft X-ray observations used to study changes
                in solar activity and flare behaviour.
              </p>
            </div>

            <div className="about-card">
              <span className="about-number">02</span>

              <h3>HEL1OS</h3>

              <p>
                Hard X-ray observations provide complementary
                information about energetic solar activity.
              </p>
            </div>

            <div className="about-card">
              <span className="about-number">03</span>

              <h3>Machine Learning</h3>

              <p>
                XGBoost-based prediction estimates the probability
                of solar flare activity from extracted features.
              </p>
            </div>
          </div>
        </section>

      </main>

      <footer className="footer">
        <span>ADITYA-L1 • SOLAR FLARE DETECTOR</span>
        <span>Offline-first scientific visualization</span>
      </footer>
    </div>
  );
}

export default App;