import { proxyBackendRequest } from "@/lib/backend-proxy";
export async function POST(request: Request) { return proxyBackendRequest("/api/guest-sessions/rotate", request); }
