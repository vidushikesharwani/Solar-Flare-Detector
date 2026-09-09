import "./AboutMission.css";

function AboutMission() {
  return (
    <div className="mission-page">
      <h1>About Aditya-L1</h1>

      <p className="mission-intro">
        Aditya-L1 is India's first space-based solar observatory,
        designed to study the Sun continuously from space.
      </p>

      <div className="mission-section">
        <h2>🚀 Aditya-L1 Mission</h2>
        <p>
          Aditya-L1 was launched by the Indian Space Research Organisation
          (ISRO) on 2 September 2023. The spacecraft operates around the
          Sun-Earth L1 point, about 1.5 million kilometres from Earth in
          the direction of the Sun.
        </p>
      </div>

      <div className="mission-section">
        <h2>☀️ Why L1?</h2>
        <p>
          The L1 point provides a useful location for continuously observing
          the Sun without the Earth blocking the view. This makes it valuable
          for monitoring solar activity and studying solar eruptions.
        </p>
      </div>

      <div className="mission-section">
        <h2>📡 SoLEXS</h2>
        <p>
          SoLEXS is the Solar Low Energy X-ray Spectrometer onboard
          Aditya-L1. It observes the Sun in soft X-rays and helps scientists
          study solar flares and their X-ray emission.
        </p>
      </div>

      <div className="mission-section">
        <h2>⚡ HEL1OS</h2>
        <p>
          HEL1OS is the High Energy L1 Orbiting X-ray Spectrometer.
          It observes higher-energy X-rays from solar activity and provides
          observations that complement the measurements from SoLEXS.
        </p>
      </div>

      <div className="mission-section">
        <h2>🔬 Connection to This Project</h2>
        <p>
          Our Solar Flare Detector uses X-ray observations from Aditya-L1
          to identify and classify solar flare events. The detected events
          can then be displayed through the timeline and dashboard.
        </p>
      </div>

      <div className="mission-highlight">
        <h2>Aditya-L1 → X-ray Observations → Flare Detection → Dashboard</h2>
      </div>
    </div>
  );
}

export default AboutMission;