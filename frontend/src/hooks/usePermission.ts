import { useAuthStore } from "@/store/authStore";

/** Returns true if the current user has the given backend permission string. */
export function usePermission(permission: string): boolean {
  return useAuthStore((s) => s.hasPermission(permission));
}

/** Returns a function to imperatively check permissions without subscribing. */
export function usePermissionCheck() {
  return useAuthStore((s) => s.hasPermission);
}
