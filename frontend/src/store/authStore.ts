import { create } from "zustand";
import type { User } from "@/types";

interface AuthState {
  currentUser: User | null;
  setCurrentUser: (user: User | null) => void;
  hasPermission: (permission: string) => boolean;
}

const ROLE_PERMISSIONS: Record<string, string[]> = {
  GADM: ["*"],
  EADM: ["project:*", "user:*", "script:*", "cycle:*", "report:*"],
  CADM: ["project:*", "user:*", "script:*", "cycle:*", "report:*"],
  SM: ["project:*", "script:*", "cycle:*", "report:*"],
  VL: ["project:read", "script:*", "cycle:*", "execution:*", "report:*"],
  QA: ["project:read", "script:read", "cycle:read", "execution:*", "defect:*"],
  VT: ["project:read", "script:create", "script:read", "script:update", "execution:run"],
  BPO: ["project:read", "script:read", "script:approve", "report:read"],
};

export const useAuthStore = create<AuthState>((set, get) => ({
  currentUser: null,
  setCurrentUser: (user) => set({ currentUser: user }),
  hasPermission: (permission) => {
    const user = get().currentUser;
    if (!user) return false;
    const perms = ROLE_PERMISSIONS[user.role] || [];
    if (perms.includes("*")) return true;
    const [resource, action] = permission.split(":");
    return (
      perms.includes(permission) ||
      perms.includes(`${resource}:*`)
    );
  },
}));
