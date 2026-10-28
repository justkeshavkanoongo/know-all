const API_BASE_URL = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

export async function proxyBackendRequest(path: string, request?: Request): Promise<Response> {
  try {
    const body = request ? await request.text() : undefined;
    const upstream = await fetch(`${API_BASE_URL}${path}`, {
      method: request?.method ?? "GET",
      cache: "no-store",
      headers: request ? { "content-type": "application/json" } : undefined,
      body,
    });
    const responseBody = await upstream.text();
    return new Response(responseBody, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return Response.json(
      { code: "learning_api_unavailable", message: "The learning service is temporarily unavailable." },
      { status: 502 },
    );
  }
}
