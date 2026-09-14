import { proxyPlanning } from "@/api/proxy.server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<Response> {
  return proxyPlanning(request);
}
