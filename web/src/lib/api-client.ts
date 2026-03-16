const RAG_API_URL = process.env.RAG_API_URL || "http://localhost:8080";
const RAG_API_KEY = process.env.RAG_INTERNAL_KEY || "dev-key";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

export async function ragFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${RAG_API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": RAG_API_KEY,
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new ApiError(res.status, errorText);
  }
  return res.json() as Promise<T>;
}
