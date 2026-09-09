function ThreatGauge({ probability = 0 }) {
  const safeProbability = Math.min(
    1,
    Math.max(0, Number(probability) || 0)
  );

  const percentage = Math.round(
    safeProbability * 100
  );

  let level = "LOW";

  if (percentage >= 70) {
    level = "HIGH";
  } else if (percentage >= 40) {
    level = "MODERATE";
  }

  const rotation = `${percentage * 3.6}deg`;

  return (
    <div className="threat-gauge">
      <div
        className="gauge-circle"
        style={{
          "--gauge-angle": rotation,
        }}
      >
        <div className="gauge-inner">
          <span className="gauge-value">
            {percentage}%
          </span>

          <span className="gauge-label">
            {level}
          </span>
        </div>
      </div>

      <p className="metric-description">
        ML-estimated flare threat
      </p>
    </div>
  );
}

export default ThreatGauge;