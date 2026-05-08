import { useAuthStore } from "@/store/authStore";

export function useCurrentTenant() {
  const tenantId = useAuthStore((s) => s.tenantId);
  const companySlug = useAuthStore((s) => s.companySlug);
  const setTenantId = useAuthStore((s) => s.setTenantId);
  const setCompanySlug = useAuthStore((s) => s.setCompanySlug);
  const currentUser = useAuthStore((s) => s.currentUser);

  // Build list of tenants the user has roles in
  const tenants = currentUser
    ? Array.from(new Set(currentUser.roles.map((r) => r.tenant_id))).filter(Boolean)
    : [];

  return {
    tenantId,
    companySlug,
    tenants,
    setTenantId,
    setCompanySlug,
  };
}
