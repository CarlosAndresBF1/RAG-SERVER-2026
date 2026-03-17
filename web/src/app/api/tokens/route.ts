import { NextRequest, NextResponse } from "next/server";

const RAG_API_URL = process.env.RAG_API_URL || "http://localhost:8080";
const RAG_API_KEY = process.env.RAG_INTERNAL_KEY || "dev-key";

const headers = {
  "Content-Type": "application/json",
  ...(RAG_API_KEY ? { "X-API-Key": RAG_API_KEY } : {}),
};

export async function GET() {
  const res = await fetch(`${RAG_API_URL}/api/v1/tokens`, { headers });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function POST(req: NextRequest) {
  const body = await req.json();

  // issued_by is resolved server-side by the backend if not provided
  // The middleware already ensures the user is authenticated

  try {
    const res = await fetch(`${RAG_API_URL}/api/v1/tokens`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { detail: "Could not connect to the RAG API" },
      { status: 502 },
    );
  }
}
