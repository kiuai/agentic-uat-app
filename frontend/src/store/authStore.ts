import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User, UserRole } from "@/types";

// Mirror of backend Permission enum values
const ALL_PERMISSIONS = [
  "tenant:read", "tenant:create", "tenant:update", "tenant:delete",
  "user:read", "user:create", "user:update", "user:delete", "user:assign_role",
  "project:read", "project:create", "project:update", "project:delete",
  "environment:read", "environment:manage",
  "requirement:read", "requirement:create", "requirement:update", "requirement:delete",
  "script:read", "script:create", "script:update", "script:delete",
  "script:approve", "script:export", "script:import",
  "cycle:read", "cycle:create", "cycle:update", "cycle:delete",
  "assignment:create", "assignment:update",
  "result:create", "result:update", "result:read",
  "crawler:read", "crawler:create", "crawler:cancel",
  "ai:generate", "ai:configure",
  "report:read", "report:export",
  "admin:global", "admin:enterprise", "admin:company",
  "audit_log:read",
] as const;

type Permission = (typeof ALL_PERMISSIONS)[number];

const ROLE_PERMISSIONS: Record<UserRole, Permission[]> = {
  GADM: [...ALL_PERMISSIONS],
  EADM: ALL_PERMISSIONS.filter((p) => p !== "admin:global"),
  CADM: ALL_PERMISSIONS.filter(
    (p) => !["admin:global", "admin:enterprise", "tenant:create", "tenant:delete"].includes(p)
  ),
  SM: [
    "project:read", "project:create", "project:update", "project:delete",
    "environment:read", "environment:manage",
    "requirement:read", "requirement:create", "requirement:update", "requirement:delete",
    "script:read", "script:create", "script:update", "script:delete",
    "script:import", "script:export",
    "cycle:read", "cycle:create", "cycle:update", "cycle:delete",
    "assignment:create", "assignment:update",
    "result:read",
    "crawler:read", "crawler:create", "crawler:cancel",
    "ai:generate", "ai:configure",
    "report:read", "report:export",
    "user:read",
    "audit_log:read",
  ],
  VL: [
    "project:read", "environment:read",
    "cycle:read", "cycle:create", "cycle:update", "cycle:delete",
    "assignment:create", "assignment:update",
    "script:read", "script:create", "script:update", "script:approve", "script:export",
    "requirement:read", "requirement:create", "requirement:update",
    "result:read",
    "report:read", "report:export",
    "crawler:read", "crawler:create",
    "ai:generate",
    "audit_log:read",
  ],
  QA: [
    "project:read", "environment:read",
    "requirement:read",
    "script:read", "script:export",
    "cycle:read",
    "assignment:update",
    "result:create", "result:update", "result:read",
    "crawler:read",
    "report:read",
  ],
  VT: [
    "project:read", "environment:read",
    "requirement:read",
    "script:read", "script:create", "script:update", "script:export",
    "cycle:read",
    "assignment:update",
    "result:create", "result:read",
    "report:read",
  ],
  BPO: [
    "project:read", "environment:read",
    "requirement:read",
    "script:read", "script:approve",
    "cycle:read",
    "result:read",
    "report:read", "report:export",
  ],
};

interface AuthState {
  currentUser: User | null;
  tenantId: string | null;
  companySlug: string | null;
  /** Effective permissions union for all roles the user holds in current tenant */
  permissions: Set<Permission>;

  setCurrentUser: (user: User | null) => void;
  setTenantId: (id: string | null) => void;
  setCompanySlug: (slug: string | null) => void;
  hasPermission: (permission: string) => boolean;
  /** Compute permissions from the user's RoleAssignment list */
  refreshPermissions: () => void;
}

function computePermissions(user: User | null, tenantId: string | null): Set<Permission> {
  if (!user) return new Set();

  // Collect all roles (tenant-scoped or global admin)
  const roles = user.is_global_admin
    ? (["GADM"] as UserRole[])
    : user.roles
        .filter((ra) => !tenantId || ra.tenant_id === tenantId)
        .map((ra) => ra.role);

  const perms = new Set<Permission>();
  for (const role of roles) {
    for (const p of ROLE_PERMISSIONS[role] ?? []) {
      perms.add(p);
    }
  }
  return perms;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      currentUser: null,
      tenantId: null,
      companySlug: null,
      permissions: new Set(),

      setCurrentUser: (user) => {
        const permissions = computePermissions(user, get().tenantId);
        set({ currentUser: user, permissions });
      },

      setTenantId: (id) => {
        const permissions = computePermissions(get().currentUser, id);
        set({ tenantId: id, permissions });
      },

      setCompanySlug: (slug) => set({ companySlug: slug }),

      hasPermission: (permission) => {
        return (get().permissions as Set<string>).has(permission);
      },

      refreshPermissions: () => {
        const { currentUser, tenantId } = get();
        const permissions = computePermissions(currentUser, tenantId);
        set({ permissions });
      },
    }),
    {
      name: "kaats-auth",
      // Only persist tenant selection, not the full user object (re-fetched on mount)
      partialize: (state) => ({
        tenantId: state.tenantId,
        companySlug: state.companySlug,
      }),
    }
  )
);
