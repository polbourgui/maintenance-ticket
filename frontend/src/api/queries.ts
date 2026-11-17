import { useQuery } from "@tanstack/react-query";

import { api, call } from "./client";

/** All sites visible to the current user (the API caps a page at 100). */
export function useSites() {
  return useQuery({
    queryKey: ["sites", "all"],
    queryFn: () => call(api.GET("/api/v1/sites", { params: { query: { limit: 100 } } })),
    select: (page) => page.items,
  });
}

export function useSiteMap() {
  const sites = useSites();
  return new Map((sites.data ?? []).map((site) => [site.id, site]));
}

export function useProviders(enabled: boolean, activeOnly = true) {
  return useQuery({
    queryKey: ["providers", { activeOnly }],
    queryFn: () =>
      call(api.GET("/api/v1/providers", { params: { query: { limit: 100, active_only: activeOnly } } })),
    select: (page) => page.items,
    enabled,
  });
}

export function useTechnicians(siteId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ["users", "technicians", siteId],
    queryFn: () =>
      call(
        api.GET("/api/v1/users", {
          params: { query: { role: "technician", site_id: siteId, limit: 100 } },
        }),
      ),
    select: (page) => page.items.filter((user) => user.is_active),
    enabled: enabled && Boolean(siteId),
  });
}
