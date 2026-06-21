import { z } from "zod";

import { ApiError, requestJson } from "./client";

describe("requestJson", () => {
  it("validates successful responses against the supplied schema", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: "ready" }), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      )
    );

    const result = await requestJson(
      "/api/example/",
      { method: "GET" },
      z.object({ status: z.literal("ready") })
    );

    expect(result).toEqual({ status: "ready" });
  });

  it("surfaces the backend error contract", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ code: "unsafe_transform", message: "Pattern rejected." }),
          { status: 400, headers: { "Content-Type": "application/json" } }
        )
      )
    );

    await expect(
      requestJson("/api/example/", { method: "POST" }, z.object({ ok: z.boolean() }))
    ).rejects.toEqual(expect.objectContaining<ApiError>({
      name: "ApiError",
      code: "unsafe_transform",
      message: "Pattern rejected."
    }));
  });

  it("rejects a successful response with an unexpected shape", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: "surprise" }), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        })
      )
    );

    await expect(
      requestJson(
        "/api/example/",
        { method: "GET" },
        z.object({ status: z.literal("ready") })
      )
    ).rejects.toThrow("unexpected response");
  });
});
