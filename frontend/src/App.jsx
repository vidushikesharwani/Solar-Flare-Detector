import Timeline from "./pages/Timeline";
import Metrics from "./pages/Metrics";
import HowItWorks from "./pages/HowItWorks";
import AboutMission from "./pages/AboutMission";

function App() {
  const path = window.location.pathname;

  return (
    <div>
      <nav>
        <a href="/">Timeline</a>
        {" | "}
        <a href="/metrics">Metrics</a>
        {" | "}
        <a href="/how-it-works">How It Works</a>
        {" | "}
        <a href="/about-mission">About Mission</a>
      </nav>

      {path === "/metrics" ? (
        <Metrics />
      ) : path === "/how-it-works" ? (
        <HowItWorks />
      ) : path === "/about-mission" ? (
        <AboutMission />
      ) : (
        <Timeline />
      )}
    </div>
  );
}

export default App;