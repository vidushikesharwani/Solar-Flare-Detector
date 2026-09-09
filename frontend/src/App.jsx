import Timeline from "./pages/Timeline";
import Metrics from "./pages/Metrics";

function App() {
  const path = window.location.pathname;

  return (
    <div>
      <nav>
        <a href="/">Timeline</a>
        {" | "}
        <a href="/metrics">Metrics</a>
      </nav>

      {path === "/metrics" ? <Metrics /> : <Timeline />}
    </div>
  );
}

export default App;