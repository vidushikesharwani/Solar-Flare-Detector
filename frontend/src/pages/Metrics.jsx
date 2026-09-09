import "./Metrics.css";

import { useEffect, useState } from "react";

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

function Metrics() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("http://localhost:8000/api/metrics")
      .then((response) => {
        if (!response.ok) {
          throw new Error("Metrics data is not available.");
        }

        return response.json();
      })
      .then((data) => {
        setMetrics(data);
        setLoading(false);
      })
      .catch((error) => {
        console.error("Failed to load metrics:", error);
        setError("Model metrics are currently unavailable.");
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="metrics-page">
        <h1>Metrics & Accuracy</h1>
        <p className="metrics-description">
          Performance evaluation of the Solar Flare Detector.
        </p>

        <div className="empty-state">
          <h2>Loading Model Metrics...</h2>
          <p>Please wait while the metrics are loaded from the backend.</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="metrics-page">
        <h1>Metrics & Accuracy</h1>
        <p className="metrics-description">
          Performance evaluation of the Solar Flare Detector.
        </p>

        <div className="empty-state">
          <h2>Metrics Not Available</h2>
          <p>
            {error}
          </p>
          <p>
            Once the model metrics are available, they will be displayed here.
          </p>
        </div>
      </div>
    );
  }

  /*
    The backend may contain different metric formats.
    We keep the data coming from the API and safely handle
    missing values instead of inventing numbers.
  */

  const perClassMetrics = metrics?.per_class_metrics || {};

  const classMetrics = Object.values(perClassMetrics);

  const averagePrecision =
    classMetrics.length > 0
      ? classMetrics.reduce(
          (sum, item) => sum + (item.precision || 0),
          0
        ) / classMetrics.length
      : null;

  const averageRecall =
    classMetrics.length > 0
      ? classMetrics.reduce(
          (sum, item) => sum + (item.recall || 0),
          0
        ) / classMetrics.length
      : null;

  const averageF1 =
    classMetrics.length > 0
      ? classMetrics.reduce(
          (sum, item) => sum + (item.f1 || 0),
          0
        ) / classMetrics.length
      : null;

  const trainingData = metrics?.training_curve || [];

  const featureImportance = metrics?.feature_importance || [];

  const formatMetric = (value) => {
    if (value === null || value === undefined) {
      return "--";
    }

    return `${(value * 100).toFixed(1)}%`;
  };

  return (
    <div className="metrics-page">

      <h1>Metrics & Accuracy</h1>

      <p className="metrics-description">
        Performance evaluation of the Solar Flare Detector.
      </p>

      {/* Metric Cards */}

      <div className="metrics-cards">

        <div className="metric-card">
          <h3>Overall Accuracy</h3>
          <p>
            {formatMetric(metrics?.overall_accuracy)}
          </p>
        </div>

        <div className="metric-card">
          <h3>Precision</h3>
          <p>
            {formatMetric(averagePrecision)}
          </p>
        </div>

        <div className="metric-card">
          <h3>Recall</h3>
          <p>
            {formatMetric(averageRecall)}
          </p>
        </div>

        <div className="metric-card">
          <h3>F1 Score</h3>
          <p>
            {formatMetric(averageF1)}
          </p>
        </div>

      </div>

      {/* Per-Class Metrics */}

<div className="chart-container">

  <h2>Per-Class Performance</h2>

  <p>
    Precision, recall, and F1 score for each solar flare class.
  </p>

  {classMetrics.length > 0 ? (
    <div className="metrics-table-wrapper">
      <table className="metrics-table">
        <thead>
          <tr>
            <th>Flare Class</th>
            <th>Precision</th>
            <th>Recall</th>
            <th>F1 Score</th>
          </tr>
        </thead>

        <tbody>
          {Object.entries(perClassMetrics).map(
            ([flareClass, values]) => (
              <tr key={flareClass}>
                <td>{flareClass}</td>

                <td>
                  {formatMetric(values.precision)}
                </td>

                <td>
                  {formatMetric(values.recall)}
                </td>

                <td>
                  {formatMetric(values.f1)}
                </td>
              </tr>
            )
          )}
        </tbody>
      </table>
    </div>
  ) : (
    <div className="table-empty-state">
      <p>
        Per-class metrics are not available yet.
      </p>
    </div>
  )}

</div>

      {/* Training Chart */}

      <div className="chart-container">

        <h2>Training Accuracy & Loss</h2>

        {trainingData.length > 0 ? (
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
        ) : (
          <p>No training curve data available.</p>
        )}

      </div>

      {/* Feature Importance Chart */}

      <div className="chart-container">

        <h2>Feature Importance</h2>

        {featureImportance.length > 0 ? (
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={featureImportance}>

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
        ) : (
          <p>No feature importance data available.</p>
        )}

      </div>

    </div>
  );
}

export default Metrics;