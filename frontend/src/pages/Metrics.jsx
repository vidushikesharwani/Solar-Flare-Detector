
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
  const [validation, setValidation] = useState(null);

  const [loading, setLoading] = useState(true);
  const [validationLoading, setValidationLoading] = useState(true);

  const [error, setError] = useState("");
  const [validationError, setValidationError] = useState("");

  useEffect(() => {
    // Load model metrics
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

    // Load GOES validation data
    fetch("http://localhost:8000/api/validation")
      .then((response) => {
        if (!response.ok) {
          throw new Error("Validation data is not available.");
        }
        return response.json();
      })
      .then((data) => {
        setValidation(data);
        setValidationLoading(false);
      })
      .catch((error) => {
        console.error("Failed to load validation:", error);
        setValidationError("GOES validation data is currently unavailable.");
        setValidationLoading(false);
      });
  }, []);

  const formatMetric = (value) => {
    if (value === null || value === undefined) {
      return "--";
    }

    return `${(value * 100).toFixed(1)}%`;
  };

  // Loading state for metrics
  if (loading) {
    return (
      <div className="metrics-page">
        <h1>Metrics & Accuracy</h1>

        <p className="metrics-description">
          Performance evaluation of the Solar Flare Detector.
        </p>

        <div className="empty-state">
          <h2>Loading Model Metrics...</h2>
          <p>
            Please wait while the metrics are loaded from the backend.
          </p>
        </div>
      </div>
    );
  }

  // Metrics unavailable
  if (error) {
    return (
      <div className="metrics-page">
        <h1>Metrics & Accuracy</h1>

        <p className="metrics-description">
          Performance evaluation of the Solar Flare Detector.
        </p>

        <div className="empty-state">
          <h2>Metrics Not Available</h2>

          <p>{error}</p>

          <p>
            Once the model metrics are available, they will be displayed here.
          </p>
        </div>

        {/* Validation may still be available */}
        {!validationLoading && validation && (
          <div className="chart-container">
            <h2>GOES Validation</h2>

            <div className="validation-cards">
              <div className="validation-card">
                <h3>Total Detections</h3>
                <p>{validation.total_events}</p>
              </div>

              <div className="validation-card">
                <h3>Matched</h3>
                <p>{validation.matched}</p>
              </div>

              <div className="validation-card">
                <h3>Unmatched</h3>
                <p>{validation.unmatched}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  const perClassMetrics = metrics?.per_class_metrics || [];
  const trainingData = metrics?.training_curve || [];
  const featureImportance = metrics?.feature_importance || [];

  return (
    <div className="metrics-page">
      <h1>Metrics & Accuracy</h1>

      <p className="metrics-description">
        Performance evaluation of the Solar Flare Detector.
      </p>

      {/* Overall Metrics */}
      <div className="metrics-cards">
        <div className="metric-card">
          <h3>Overall Accuracy</h3>
          <p>{formatMetric(metrics?.overall_accuracy)}</p>
        </div>

        <div className="metric-card">
          <h3>Model Version</h3>
          <p>{metrics?.model_version || "--"}</p>
        </div>

        <div className="metric-card">
          <h3>Trained At</h3>
          <p>{metrics?.trained_at || "--"}</p>
        </div>
      </div>

      {/* Per-Class Metrics */}
      <div className="chart-container">
        <h2>Per-Class Performance</h2>

        <p>
          Precision, recall, F1 score, and support for each solar flare class.
        </p>

        {perClassMetrics.length > 0 ? (
          <div className="metrics-table-wrapper">
            <table className="metrics-table">
              <thead>
                <tr>
                  <th>Flare Class</th>
                  <th>Precision</th>
                  <th>Recall</th>
                  <th>F1 Score</th>
                  <th>Support</th>
                </tr>
              </thead>

              <tbody>
                {perClassMetrics.map((item) => (
                  <tr key={item.flare_class}>
                    <td>{item.flare_class}</td>
                    <td>{formatMetric(item.precision)}</td>
                    <td>{formatMetric(item.recall)}</td>
                    <td>{formatMetric(item.f1)}</td>
                    <td>{item.support ?? "--"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="table-empty-state">
            <p>Per-class metrics are not available yet.</p>
          </div>
        )}
      </div>

      {/* Training Curve */}
      <div className="chart-container">
        <h2>Training Accuracy & Loss</h2>

        <p>
          Model training performance across epochs.
        </p>

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
                dataKey="train_accuracy"
                name="Training Accuracy"
                stroke="#4ade80"
                strokeWidth={3}
              />

              <Line
                type="monotone"
                dataKey="val_accuracy"
                name="Validation Accuracy"
                stroke="#60a5fa"
                strokeWidth={3}
              />

              <Line
                type="monotone"
                dataKey="train_loss"
                name="Training Loss"
                stroke="#f87171"
                strokeWidth={3}
              />

              <Line
                type="monotone"
                dataKey="val_loss"
                name="Validation Loss"
                stroke="#fbbf24"
                strokeWidth={3}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="table-empty-state">
            <p>Training curve data is not available yet.</p>
          </div>
        )}
      </div>

      {/* Feature Importance */}
      <div className="chart-container">
        <h2>Feature Importance</h2>

        <p>
          Relative importance of features used by the machine-learning model.
        </p>

        {featureImportance.length > 0 ? (
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={featureImportance}>
              <CartesianGrid strokeDasharray="3 3" />

              <XAxis dataKey="feature" />

              <YAxis />

              <Tooltip />

              <Legend />

              <Bar
                dataKey="importance"
                name="Importance"
                fill="#60a5fa"
              />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="table-empty-state">
            <p>Feature importance data is not available yet.</p>
          </div>
        )}

        {featureImportance.length > 0 && (
          <div className="metrics-table-wrapper">
            <table className="metrics-table">
              <thead>
                <tr>
                  <th>Feature</th>
                  <th>Importance</th>
                  <th>Instrument</th>
                </tr>
              </thead>

              <tbody>
                {featureImportance.map((item, index) => (
                  <tr key={`${item.feature}-${index}`}>
                    <td>{item.feature}</td>
                    <td>{item.importance.toFixed(3)}</td>
                    <td>{item.instrument}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* GOES Validation */}
      <div className="chart-container">
        <h2>GOES Validation</h2>

        <p>
          Comparison of detected solar flares against the local NOAA GOES
          flare catalog.
        </p>

        {validationLoading ? (
          <div className="table-empty-state">
            <p>Loading GOES validation data...</p>
          </div>
        ) : validationError ? (
          <div className="table-empty-state">
            <p>{validationError}</p>
          </div>
        ) : validation ? (
          <>
            <div className="validation-cards">
              <div className="validation-card">
                <h3>Total Detections</h3>
                <p>{validation.total_events}</p>
              </div>

              <div className="validation-card">
                <h3>Matched</h3>
                <p>{validation.matched}</p>
              </div>

              <div className="validation-card">
                <h3>Unmatched</h3>
                <p>{validation.unmatched}</p>
              </div>
            </div>

            {validation.results?.length > 0 && (
              <div className="metrics-table-wrapper">
                <table className="metrics-table">
                  <thead>
                    <tr>
                      <th>Event ID</th>
                      <th>GOES Match</th>
                      <th>GOES Class</th>
                      <th>Time Difference</th>
                    </tr>
                  </thead>

                  <tbody>
                    {validation.results.map((result) => (
                      <tr key={result.event_id}>
                        <td>{result.event_id}</td>

                        <td>
                          {result.goes_match ? "Matched" : "No Match"}
                        </td>

                        <td>{result.goes_class || "--"}</td>

                        <td>
                          {result.time_diff_minutes !== null &&
                          result.time_diff_minutes !== undefined
                            ? `${result.time_diff_minutes} min`
                            : "--"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : (
          <div className="table-empty-state">
            <p>GOES validation data is not available yet.</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default Metrics;
