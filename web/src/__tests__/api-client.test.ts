import { describe, it, expect, vi, beforeEach } from "vitest";
import { ragFetch, ApiError } from "@/lib/api-client";

describe("api-client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("throws ApiError on non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        text: () => Promise.resolve("Unauthorized"),
      })
    );

    await expect(ragFetch("/test")).rejects.toThrow(ApiError);
    await expect(ragFetch("/test")).rejects.toMatchObject({
      status: 401,
      message: "Unauthorized",
    });
  });

  it("returns parsed JSON on success", async () => {
    const mockData = { total: 42 };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockData),
      })
    );

    const result = await ragFetch("/test");
    expect(result).toEqual(mockData);
  });

  it("sends X-API-Key header", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    });
    vi.stubGlobal("fetch", fetchMock);

    await ragFetch("/test");
    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers["X-API-Key"]).toBeDefined();
  });
});
