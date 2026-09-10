const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(endpoint) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`);

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json();
}

export function getFlux() {
  return request("/api/flux");
}

export function getEvents() {
  return request("/api/events");
}

export function getPredictions() {
  return request("/api/predictions");
}

export function getMetrics() {
  return request("/api/metrics");
}

export function getValidation() {
  return request("/api/validation");
}

export function getHealth() {
  return request("/health");
}