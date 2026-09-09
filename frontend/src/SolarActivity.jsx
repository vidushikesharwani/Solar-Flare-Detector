function SolarActivity({ flareClass = "A" }) {
  const normalizedClass = String(flareClass).toUpperCase();

  let activityLevel = "quiet";

  if (normalizedClass === "X") {
    activityLevel = "extreme";
  } else if (normalizedClass === "M") {
    activityLevel = "high";
  } else if (normalizedClass === "C") {
    activityLevel = "active";
  }

  return (
    <div
      className={`sun-container ${activityLevel}`}
      aria-label={`Solar activity level ${normalizedClass}`}
    >
      <div className="sun-glow"></div>

      <div className="sun">
        <div className="sun-surface"></div>
        <div className="sun-spot sun-spot-one"></div>
        <div className="sun-spot sun-spot-two"></div>
        <div className="sun-spot sun-spot-three"></div>
      </div>

      <div className="solar-flare flare-one"></div>
      <div className="solar-flare flare-two"></div>

      <div className="orbit orbit-one"></div>
      <div className="orbit orbit-two"></div>
    </div>
  );
}

export default SolarActivity;