import { useMemo } from "react";

export default function SolarActivity({
  flareClass = "A",
}) {
  const activity = useMemo(() => {
    const level = String(flareClass)
      .trim()
      .toUpperCase();

    switch (level) {
      case "X":
        return {
          className: "solar-x",
          label: "EXTREME ACTIVITY",
          description:
            "Major solar flare activity detected",
        };

      case "M":
        return {
          className: "solar-m",
          label: "HIGH ACTIVITY",
          description:
            "Elevated solar flare activity detected",
        };

      case "C":
        return {
          className: "solar-c",
          label: "MODERATE ACTIVITY",
          description:
            "Moderate solar activity detected",
        };

      case "B":
        return {
          className: "solar-b",
          label: "LOW ACTIVITY",
          description:
            "Low-level solar activity detected",
        };

      default:
        return {
          className: "solar-a",
          label: "QUIET",
          description:
            "Solar activity currently quiet",
        };
    }
  }, [flareClass]);


  return (
    <div
      className={`solar-activity ${activity.className}`}
    >

      {/* ================================================
          CENTERED SOLAR VISUAL
      ================================================= */}

      <div className="solar-visual">

        <div className="solar-orbit solar-orbit-one" />

        <div className="solar-orbit solar-orbit-two" />

        <div className="solar-glow" />

        <div className="sun">

          <div className="sun-surface" />

          <div className="sun-flare sun-flare-one" />

          <div className="sun-flare sun-flare-two" />

          <div className="sun-flare sun-flare-three" />

        </div>

      </div>


      {/* ================================================
          ACTIVITY STATUS
      ================================================= */}

      <div className="solar-status">

        <span className="solar-status-dot" />

        <span>
          {activity.label}
        </span>

      </div>


      {/* ================================================
          DESCRIPTION
      ================================================= */}

      <p>
        {activity.description}
      </p>


      {/* ================================================
          CLASS
      ================================================= */}

      <div className="solar-class">

        CLASS

        <strong>
          {String(flareClass)
            .trim()
            .toUpperCase()}
        </strong>

      </div>

    </div>
  );
}