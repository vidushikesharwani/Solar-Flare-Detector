import { useEffect, useState } from "react";
import { NavLink, Routes, Route } from "react-router-dom";

import FluxChart from "./FluxChart";
import SolarActivity from "./SolarActivity";
import ThreatGauge from "./ThreatGauge";
import EventsPanel from "./EventsPanel";
import Timeline from "./Timeline";
import Metrics from "./Metrics";


import {
  getFlux,
  getEvents,
  getPredictions,
} from "./api";

import "./App.css";


/* =========================================================
   MAIN DASHBOARD
========================================================= */

function Dashboard() {
  const [fluxData, setFluxData] = useState([]);
  const [events, setEvents] = useState([]);
  const [predictions, setPredictions] = useState([]);

  const [loading, setLoading] = useState(true);
  const [backendConnected, setBackendConnected] = useState(false);


  /*
   * =====================================================
   * LOAD / REFRESH DASHBOARD DATA
   * =====================================================
   */

  useEffect(() => {
    let mounted = true;

    async function loadDashboard() {
      const results = await Promise.allSettled([
        getFlux(),
        getEvents(),
        getPredictions(),
      ]);

      if (!mounted) return;

      const [
        fluxResult,
        eventsResult,
        predictionsResult,
      ] = results;

      let connected = false;


      /* -------------------------
         FLUX
      ------------------------- */

      if (fluxResult.status === "fulfilled") {
        connected = true;

        setFluxData(
          Array.isArray(fluxResult.value?.data)
            ? fluxResult.value.data
            : []
        );
      }


      /* -------------------------
         EVENTS
      ------------------------- */

      if (eventsResult.status === "fulfilled") {
        connected = true;

        setEvents(
          Array.isArray(eventsResult.value?.events)
            ? eventsResult.value.events
            : []
        );
      }


      /* -------------------------
         PREDICTIONS
      ------------------------- */

      if (predictionsResult.status === "fulfilled") {
        connected = true;

        setPredictions(
          Array.isArray(
            predictionsResult.value?.predictions
          )
            ? predictionsResult.value.predictions
            : []
        );
      }

      setBackendConnected(connected);
      setLoading(false);
    }


    /* Initial load */
    loadDashboard();


    /* Refresh every 3 seconds */
    const interval = setInterval(
      loadDashboard,
      3000
    );

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);


  /*
   * =====================================================
   * LATEST MODEL PREDICTION
   * =====================================================
   */

  const latestPrediction =
    predictions.length > 0
      ? predictions[predictions.length - 1]
      : null;


  /*
   * =====================================================
   * AUTOMATIC FLARE CLASS
   * =====================================================
   */

  const latestFlareClass =
    latestPrediction?.predicted_class
      ?.toString()
      .trim()
      .toUpperCase() || "A";


  /*
   * =====================================================
   * AUTOMATIC THREAT PROBABILITY
   * =====================================================
   */

  const latestProbability =
    typeof latestPrediction?.flare_probability ===
    "number"
      ? latestPrediction.flare_probability
      : 0.12;


  /*
   * =====================================================
   * THREAT LEVEL
   * =====================================================
   */

  const threatLevel =
    latestProbability >= 0.7
      ? "HIGH"
      : latestProbability >= 0.4
        ? "MODERATE"
        : "LOW";


  return (
    <main className="dashboard">

      {/* =================================================
          HERO
      ================================================= */}

      <section className="hero-section">

        <div className="hero-content">

          <div className="eyebrow">
            ADITYA-L1 • X-RAY MONITORING
          </div>

          <h1>
            Solar Activity
            <span>Intelligence</span>
          </h1>

          <p>
            Real-time analysis of solar X-ray
            observations using SoLEXS and HEL1OS data.
          </p>

          <div className="hero-status">

            <span className="live-indicator" />

            {backendConnected
              ? "LIVE DATA STREAM"
              : "MONITORING SYSTEM READY"}

          </div>

        </div>


        <div className="hero-decoration">

          <div className="hero-ring hero-ring-one" />
          <div className="hero-ring hero-ring-two" />
          <div className="hero-ring hero-ring-three" />

        </div>

      </section>


      {/* =================================================
          SOLAR + THREAT
      ================================================= */}

      <section className="monitoring-grid">

        {/* SOLAR MONITOR */}

        <div className="dashboard-card solar-card">

          <div className="card-header">

            <div>

              <span className="card-kicker">
                SOLAR ACTIVITY
              </span>

              <h2>
                Sun Monitor
              </h2>

            </div>

            <span className="card-badge">
              {latestFlareClass} CLASS
            </span>

          </div>

          <SolarActivity
            flareClass={latestFlareClass}
          />

        </div>


        {/* THREAT GAUGE */}

        <div className="dashboard-card threat-card">

          <div className="card-header">

            <div>

              <span className="card-kicker">
                MACHINE LEARNING
              </span>

              <h2>
                Threat Probability
              </h2>

            </div>

            <span className="card-badge">
              XGBOOST
            </span>

          </div>

          <ThreatGauge
            probability={latestProbability}
          />

          <div className="threat-summary">

            <div className="threat-summary-label">
              CURRENT THREAT
            </div>

            <div className="threat-summary-value">
              {threatLevel}
            </div>

            <div className="threat-summary-detail">
              Predicted class:{" "}
              <strong>
                {latestFlareClass}
              </strong>
            </div>

          </div>

        </div>

      </section>


      {/* =================================================
          FLUX CHART
      ================================================= */}

      <section className="dashboard-card flux-section">

        <div className="card-header">

          <div>

            <span className="card-kicker">
              X-RAY OBSERVATIONS
            </span>

            <h2>
              Solar X-Ray Flux
            </h2>

            <p className="card-description">
              Aligned SoLEXS and HEL1OS observations
            </p>

          </div>

          <div className="flux-live-status">

            <span className="status-dot" />

            {backendConnected
              ? "LIVE DATA"
              : "WAITING FOR DATA"}

          </div>

        </div>

        <FluxChart
          data={fluxData}
          loading={loading}
        />

      </section>


      {/* =================================================
          EVENTS
      ================================================= */}

      <section className="dashboard-card events-section">

        <div className="card-header">

          <div>

            <span className="card-kicker">
              DETECTION ENGINE
            </span>

            <h2>
              Detected Events
            </h2>

            <p className="card-description">
              Solar flare events identified by the
              detection pipeline
            </p>

          </div>

          <div className="event-count">
            {events.length}
          </div>

        </div>

        <EventsPanel
          events={events}
        />

      </section>


      {/* =================================================
          ABOUT
      ================================================= */}

      <section className="about-section">

        <div className="about-content">

          <span className="card-kicker">
            ABOUT THE SYSTEM
          </span>

          <h2>
            Understanding Solar Activity
          </h2>

          <p>
            The Solar Flare Detector analyses X-ray
            observations from the Aditya-L1 mission to
            identify changes in solar activity. SoLEXS
            provides soft X-ray observations while HEL1OS
            captures higher-energy X-ray activity.
          </p>

          <p>
            Statistical detection and machine-learning
            predictions work together to identify and
            classify potential solar flare events.
          </p>

        </div>


        <div className="about-stats">

          <div className="about-stat">
            <strong>2</strong>
            <span>INSTRUMENTS</span>
          </div>

          <div className="about-stat">
            <strong>5</strong>
            <span>FLARE CLASSES</span>
          </div>

          <div className="about-stat">
            <strong>AI</strong>
            <span>XGBOOST MODEL</span>
          </div>

        </div>

      </section>

    </main>
  );
}


/* =========================================================
   APP
========================================================= */

function App() {
  const [backendConnected, setBackendConnected] = useState(false);

  /*
   * Lightweight health check for navbar status.
   */
  useEffect(() => {
    let mounted = true;

    async function checkBackend() {
      try {
        const response = await fetch(
          "http://localhost:8000/health"
        );

        if (mounted && response.ok) {
          setBackendConnected(true);
        }
      } catch {
        if (mounted) {
          setBackendConnected(false);
        }
      }
    }

    checkBackend();

    const interval = setInterval(
      checkBackend,
      3000
    );

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);


  return (
    <div className="app">

      {/* =================================================
          BACKGROUND
      ================================================= */}

      <div className="space-background">

        <div className="stars stars-one" />
        <div className="stars stars-two" />

        <div className="nebula nebula-one" />
        <div className="nebula nebula-two" />

      </div>


      {/* =================================================
          NAVBAR
      ================================================= */}

      <nav className="navbar">

        <NavLink
          to="/"
          className="nav-brand"
        >

          <div className="brand-orbit">
            <span />
          </div>

          <div>

            <div className="brand-title">
              SOLAR FLARE
            </div>

            <div className="brand-subtitle">
              DETECTION SYSTEM
            </div>

          </div>

        </NavLink>


        {/* NAVIGATION TABS */}

        <div className="nav-links">

          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `nav-link ${
                isActive ? "active" : ""
              }`
            }
          >
            Dashboard
          </NavLink>

          <NavLink
            to="/timeline"
            className={({ isActive }) =>
              `nav-link ${
                isActive ? "active" : ""
              }`
            }
          >
            Timeline
          </NavLink>

          <NavLink
            to="/metrics"
            className={({ isActive }) =>
              `nav-link ${
                isActive ? "active" : ""
              }`
            }
          >
            Metrics
          </NavLink>

        </div>


        <div className="nav-status">

          <span className="status-dot" />

          {backendConnected
            ? "DATA CONNECTED"
            : "SYSTEM READY"}

        </div>

      </nav>


      {/* =================================================
          PAGE ROUTES
      ================================================= */}

      <Routes>

        <Route
          path="/"
          element={<Dashboard />}
        />
        <Route path="/timeline" element={<Timeline />} />
          <Route path="/metrics" element={<Metrics />} />

      
      </Routes>


      {/* =================================================
          FOOTER
      ================================================= */}

      <footer className="footer">

        <div>
          SOLAR FLARE DETECTOR
        </div>

        <div>
          ADITYA-L1 • SoLEXS • HEL1OS
        </div>

      </footer>

    </div>
  );
}

export default App;