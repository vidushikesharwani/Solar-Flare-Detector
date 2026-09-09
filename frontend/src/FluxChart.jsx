import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

function FluxChart({ data = [], loading = false }) {
  if (loading) {
    return (
      <div className="flux-chart-state">
        <span>Loading solar observations...</span>
        <small>Aditya-L1</small>
      </div>
    );
  }

  if (!data.length) {
    return (
      <div className="flux-chart-state">
        <span>Waiting for solar observation data</span>
        <small>SoLEXS + HEL1OS</small>
      </div>
    );
  }

  const step =
    data.length > 300
      ? Math.ceil(data.length / 300)
      : 1;

  const chartData = data
    .filter((_, index) => index % step === 0)
    .map((point) => ({
      time: new Date(point.timestamp).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
      solexs: point.solexs_flux,
      hel1os: point.hel1os_flux,
    }));

  return (
    <div className="real-chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={chartData}
          margin={{
            top: 10,
            right: 10,
            left: 0,
            bottom: 5,
          }}
        >
          <CartesianGrid
            stroke="rgba(130, 170, 210, 0.08)"
            vertical={false}
          />

          <XAxis
            dataKey="time"
            tick={{
              fill: "#71839a",
              fontSize: 10,
            }}
            axisLine={false}
            tickLine={false}
          />

          <YAxis
            yAxisId="solexs"
            tick={{
              fill: "#71839a",
              fontSize: 10,
            }}
            axisLine={false}
            tickLine={false}
            width={45}
          />

          <YAxis
            yAxisId="hel1os"
            orientation="right"
            tick={{
              fill: "#71839a",
              fontSize: 10,
            }}
            axisLine={false}
            tickLine={false}
            width={45}
          />

          <Tooltip
            contentStyle={{
              background: "#0b1a2d",
              border: "1px solid rgba(130, 170, 210, 0.18)",
              borderRadius: "10px",
              color: "#f2f6fb",
            }}
          />

          <Line
            yAxisId="solexs"
            type="monotone"
            dataKey="solexs"
            stroke="#4da3ff"
            strokeWidth={2}
            dot={false}
            name="SoLEXS"
            connectNulls={false}
          />

          <Line
            yAxisId="hel1os"
            type="monotone"
            dataKey="hel1os"
            stroke="#9b8cff"
            strokeWidth={2}
            dot={false}
            name="HEL1OS"
            connectNulls={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default FluxChart;