export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
  timestamp: string;
}

const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/health`, { signal });
  if (!res.ok) {
    throw new Error(`Health check failed with HTTP ${res.status}`);
  }
  return res.json() as Promise<HealthResponse>;
}

