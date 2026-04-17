import type { PredictRequestBody, PredictResponse, Race } from "./types";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export async function listRaces(year: number): Promise<Race[]> {
  const res = await fetch(`/api/races?year=${year}`);
  const data = await jsonOrThrow<{ races: Race[] }>(res);
  return data.races;
}

export async function runPrediction(body: PredictRequestBody): Promise<PredictResponse> {
  const res = await fetch("/api/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return jsonOrThrow<PredictResponse>(res);
}

export async function fetchFeatureColumns(): Promise<string[]> {
  const res = await fetch("/api/feature-columns");
  const data = await jsonOrThrow<{ features: string[] }>(res);
  return data.features;
}
