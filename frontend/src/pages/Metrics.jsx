import "./Metrics.css";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts";

// Demo data only.
// These values will later come from the backend API.
const trainingData = [
  { epoch: 1, accuracy: 0.72, loss: 0.65 },
  { epoch: 2, accuracy: 0.78, loss: 0.52 },
  { epoch: 3, accuracy: 0.83, loss: 0.41 },
  { epoch: 4, accuracy: 0.87, loss: 0.33 },
  { epoch: 5, accuracy: 0.90, loss: 0.27 },
];

const featureData = [
  { feature: "Peak Flux", importance: 0.85 },
  { feature: "Duration", importance: 0.68 },
  { feature: "Rise Time", importance: 0.56 },
  { feature: "Decay Time", importance: 0.43 },
  { feature: "Baseline", importance: 0.35 },
];

function Metrics() {
  return (
    <div className="metrics-page">

      <h1>Metrics & Accuracy</h1>

      <p className="metrics-description">
        Performance evaluation of the Solar Flare Detector.
      </p>

      <p className="demo-notice">
        ⚠️ Demo data shown — real model metrics will be loaded from the backend.
      </p>

      {/* Metric Cards */}
      <div className="metrics-cards">

        <div className="metric-card">
          <h3>Matched Detections</h3>
          <p>--</p>
        </div>

        <div className="metric-card">
          <h3>Precision</h3>
          <p>--</p>
        </div>

        <div className="metric-card">
          <h3>Recall</h3>
          <p>--</p>
        </div>

        <div className="metric-card">
          <h3>F1 Score</h3>
          <p>--</p>
        </div>

      </div>

      {/* Training Chart */}
      <div className="chart-container">

        <h2>Training Accuracy & Loss</h2>

        <ResponsiveContainer width="100%" height={350}>
          <LineChart data={trainingData}>

            <CartesianGrid strokeDasharray="3 3" />

            <XAxis
              dataKey="epoch"
              label={{
                value: "Epoch",
                position: "insideBottom",
                offset: -5,
              }}
            />

            <YAxis />

            <Tooltip />

            <Legend />

            <Line
              type="monotone"
              dataKey="accuracy"
              name="Accuracy"
              stroke="#4ade80"
              strokeWidth={3}
            />

            <Line
              type="monotone"
              dataKey="loss"
              name="Loss"
              stroke="#f87171"
              strokeWidth={3}
            />

          </LineChart>
        </ResponsiveContainer>

      </div>

      {/* Feature Importance Chart */}
      <div className="chart-container">

        <h2>Feature Importance</h2>

        <ResponsiveContainer width="100%" height={350}>
          <BarChart data={featureData}>

            <CartesianGrid strokeDasharray="3 3" />

            <XAxis dataKey="feature" />

            <YAxis />

            <Tooltip />

            <Bar
              dataKey="importance"
              name="Importance"
              fill="#60a5fa"
            />

          </BarChart>
        </ResponsiveContainer>

      </div>

    </div>
  );
}

export default Metrics;