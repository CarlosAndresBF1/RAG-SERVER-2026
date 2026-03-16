import { NextRequest, NextResponse } from "next/server";

const RAG_API_URL = process.env.RAG_API_URL || "http://localhost:8080";
const RAG_API_KEY = process.env.RAG_INTERNAL_KEY || "dev-key";

export async function POST(req: NextRequest) {
  const body = await req.json();

  const res = await fetch(`${RAG_API_URL}/api/v1/ingest`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(RAG_API_KEY ? { "X-API-Key": RAG_API_KEY } : {}),
    },
    body: JSON.stringify(body),
  });

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
