import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

function formatTime(timestamp) {
  if (!timestamp) return "—";

  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return String(timestamp);
  }

  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDateTime(timestamp) {
  if (!timestamp) return "—";

  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return String(timestamp);
  }

  return date.toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function prepareData(data) {
  if (!Array.isArray(data)) return [];

  const cleaned = data
    .map((point) => ({
      timestamp: point?.timestamp ?? null,
      displayTime: formatTime(point?.timestamp),
      solexs_flux:
        point?.solexs_flux === null || point?.solexs_flux === undefined
          ? null
          : Number(point.solexs_flux),
      hel1os_flux:
        point?.hel1os_flux === null || point?.hel1os_flux === undefined
          ? null
          : Number(point.hel1os_flux),
    }))
    .filter(
      (point) =>
        point.timestamp &&
        (Number.isFinite(point.solexs_flux) ||
          Number.isFinite(point.hel1os_flux))
    )
    .sort(
      (a, b) =>
        new Date(a.timestamp).getTime() -
        new Date(b.timestamp).getTime()
    );

  // Keep the chart responsive with very large datasets.
  if (cleaned.length <= 300) {
    return cleaned;
  }

  const step = Math.ceil(cleaned.length / 300);

  return cleaned.filter(
    (_, index) =>
      index % step === 0 || index === cleaned.length - 1
  );
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;

  const timestamp = payload[0]?.payload?.timestamp;

  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-time">
        {formatDateTime(timestamp)}
      </div>

      {payload.map((item) => {
        if (item.value === null || item.value === undefined) {
          return null;
        }

        return (
          <div className="chart-tooltip-row" key={item.dataKey}>
            <span>{item.name}</span>
            <strong>{Number(item.value).toExponential(3)}</strong>
          </div>
        );
      })}
    </div>
  );
}

export default function FluxChart({ data = [], loading = false }) {
  const chartData = prepareData(data);

  if (loading) {
    return (
      <div className="flux-chart-state">
        <span>Loading X-ray flux data...</span>
      </div>
    );
  }

  if (!chartData.length) {
    return (
      <div className="flux-chart-state">
        <span>No flux data available</span>
      </div>
    );
  }

  return (
    <div className="real-chart">
      <ResponsiveContainer width="100%" height={360}>
        <LineChart
          data={chartData}
          margin={{
            top: 10,
            right: 18,
            left: 0,
            bottom: 8,
          }}
        >
          <CartesianGrid
            strokeDasharray="3 5"
            vertical={false}
            opacity={0.16}
          />

          <XAxis
            dataKey="displayTime"
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            minTickGap={45}
            interval="preserveStartEnd"
          />

          <YAxis
            yAxisId="solexs"
            orientation="left"
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={55}
            tickFormatter={(value) =>
              Number(value).toExponential(1)
            }
          />

          <YAxis
            yAxisId="hel1os"
            orientation="right"
            tick={{ fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={55}
            tickFormatter={(value) =>
              Number(value).toExponential(1)
            }
          />

          <Tooltip
            content={<CustomTooltip />}
            cursor={{ opacity: 0.2 }}
          />

          <Line
            yAxisId="solexs"
            type="monotone"
            dataKey="solexs_flux"
            name="SoLEXS"
            stroke="#5b9cff"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
            connectNulls={false}
            isAnimationActive={false}
          />

          <Line
            yAxisId="hel1os"
            type="monotone"
            dataKey="hel1os_flux"
            name="HEL1OS"
            stroke="#a78bfa"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
            connectNulls={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>

      <div className="flux-chart-legend">
        <span>
          <i className="legend-dot solexs-dot" />
          SoLEXS
        </span>

        <span>
          <i className="legend-dot hel1os-dot" />
          HEL1OS
        </span>
      </div>
    </div>
  );
}