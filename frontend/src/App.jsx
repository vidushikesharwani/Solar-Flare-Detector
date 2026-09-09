function App() {
  return (
    <div>
      <h1>Solar Flare Detector</h1>
      <p>Aditya-L1 Solar Flare Monitoring Dashboard</p>

      <hr />

      <h2>Navigation</h2>

      <button>Dashboard</button>
      <button>Timeline</button>
      <button>Metrics</button>
      <button>How It Works</button>
      <button>About Mission</button>

      <hr />

      <h2>Solar Flare Timeline</h2>

      <p>
        Detected solar flare events from Aditya-L1 X-ray observations will
        appear here.
      </p>

      <div>
        <h3>Sample Event</h3>
        <p>Flare Class: M1.2</p>
        <p>Instrument: SoLEXS</p>
        <p>Start: 2026-09-08 10:30</p>
        <p>Peak: 2026-09-08 10:42</p>
        <p>Decay: 2026-09-08 11:05</p>
      </div>
    </div>
  );
}

export default App;