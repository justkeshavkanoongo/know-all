const API_BASE_URL = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

export async function proxyBackendRequest(path: string, request?: Request): Promise<Response> {
  try {
    const method = request?.method ?? "GET";
    const body = request && method !== "GET" && method !== "HEAD" ? await request.text() : undefined;
    const headers = new Headers();
    if (body !== undefined) headers.set("content-type", request?.headers.get("content-type") ?? "application/json");
    for (const name of ["cookie", "origin", "idempotency-key", "accept"]) {
      const value = request?.headers.get(name);
      if (value) headers.set(name, value);
    }
    const upstream = await fetch(`${API_BASE_URL}${path}`, {
      method,
      cache: "no-store",
      headers,
      body,
    });
    const responseBody = await upstream.text();
    const responseHeaders = new Headers();
    const contentType = upstream.headers.get("content-type");
    if (contentType) responseHeaders.set("content-type", contentType);
    for (const cookie of upstream.headers.getSetCookie()) responseHeaders.append("set-cookie", cookie);
    return new Response(responseBody || null, { status: upstream.status, headers: responseHeaders });
  } catch {
    return Response.json(
      { code: "learning_api_unavailable", message: "The learning service is temporarily unavailable." },
      { status: 502 },
    );
  }
}
