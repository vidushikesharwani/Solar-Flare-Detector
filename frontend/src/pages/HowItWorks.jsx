import "./HowItWorks.css";

function HowItWorks() {
  return (
    <div className="education-page">
      <h1>How It Works</h1>

      <p className="education-intro">
        The Solar Flare Detector analyzes X-ray observations from
        Aditya-L1 to identify sudden increases in solar activity.
      </p>

      <div className="info-section">
        <h2>☀️ 1. What is X-ray Flux?</h2>
        <p>
          The Sun continuously emits X-rays. During a solar flare,
          the X-ray emission can suddenly increase. By monitoring
          this X-ray flux, we can identify periods of enhanced solar activity.
        </p>
      </div>

      <div className="info-section">
        <h2>📊 2. Finding the Baseline</h2>
        <p>
          The detector first estimates the normal background level
          of X-ray activity. A rolling baseline helps the system
          understand what the usual signal looks like over time.
        </p>
      </div>

      <div className="info-section">
        <h2>🔍 3. Detecting a Flare</h2>
        <p>
          When the observed X-ray flux rises significantly above
          the normal baseline, the system can identify it as a
          possible solar flare. A statistical threshold based on
          the baseline and its variation helps reduce false detections.
        </p>

        <div className="formula-box">
          Detection threshold = Baseline + k × Standard Deviation
        </div>
      </div>

      <div className="info-section">
        <h2>🌟 4. Classifying the Flare</h2>
        <p>
          Solar flares are commonly classified according to their
          peak X-ray intensity. The major classes are:
        </p>

        <ul>
          <li><strong>A-class:</strong> Very small flares</li>
          <li><strong>B-class:</strong> Small flares</li>
          <li><strong>C-class:</strong> Moderate flares</li>
          <li><strong>M-class:</strong> Strong flares</li>
          <li><strong>X-class:</strong> The strongest category</li>
        </ul>
      </div>

      <div className="info-section">
        <h2>📈 5. From Detection to Dashboard</h2>
        <p>
          Once a flare is detected, its start time, peak time,
          decay time, class, and instrument information can be
          displayed on the dashboard timeline.
        </p>
      </div>

      <div className="process-flow">
        <span>X-ray Data</span>
        <span>→</span>
        <span>Baseline</span>
        <span>→</span>
        <span>Detection</span>
        <span>→</span>
        <span>Classification</span>
        <span>→</span>
        <span>Dashboard</span>
      </div>
    </div>
  );
}

export default HowItWorks;