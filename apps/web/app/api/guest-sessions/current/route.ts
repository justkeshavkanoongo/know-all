import { proxyBackendRequest } from "@/lib/backend-proxy";
export async function DELETE(request: Request) { return proxyBackendRequest("/api/guest-sessions/current", request); }
