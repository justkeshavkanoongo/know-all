import { proxyBackendRequest } from "@/lib/backend-proxy";
export async function POST(request: Request) { return proxyBackendRequest("/api/quest-invitations/redeem", request); }
