import { NextRequest, NextResponse } from "next/server";

const RAG_API_URL = process.env.RAG_API_URL || "http://localhost:8080";
const RAG_API_KEY = process.env.RAG_INTERNAL_KEY || "dev-key";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const page = searchParams.get("page") ?? "1";
  const pageSize = searchParams.get("page_size") ?? "50";
  const action = searchParams.get("action") ?? "";

  const params = new URLSearchParams({ page, page_size: pageSize });
  if (action) params.set("action", action);

  const res = await fetch(`${RAG_API_URL}/api/v1/audit?${params}`, {
    headers: {
      ...(RAG_API_KEY ? { "X-API-Key": RAG_API_KEY } : {}),
    },
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
