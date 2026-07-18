import { ApiError, authedGet, authedRequest } from "@/lib/api";
import type { DashboardLayoutV2 } from "@/features/my-metrics/dashboard-layout";

export type DashboardPreferenceResponse = {
  layout: DashboardLayoutV2;
  updated_at: string;
};

export async function getDashboardPreference(
  token: string,
  tenantId: string,
): Promise<DashboardPreferenceResponse | null> {
  try {
    return await authedGet<DashboardPreferenceResponse>(
      `/api/v1/tenants/${tenantId}/dashboard-preference`,
      token,
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function putDashboardPreference(
  token: string,
  tenantId: string,
  layout: DashboardLayoutV2,
): Promise<DashboardPreferenceResponse> {
  return authedRequest<DashboardPreferenceResponse>(
    "PUT",
    `/api/v1/tenants/${tenantId}/dashboard-preference`,
    token,
    { layout },
  );
}
