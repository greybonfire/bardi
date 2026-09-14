import "server-only";
import { cache } from "react";
import { getServices } from "@/api/services.server";

// React cache deduplicates metadata/page reads within ONE server render only.
// The API client and routes remain no-store across requests.
export const servicesForPage = cache(getServices);
