import { proxyServices } from "@/api/proxy.server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: Request): Promise<Response> {
  return proxyServices(request);
}
