import React from "react";
import { useMsal } from "@azure/msal-react";
import { useQuery } from "@tanstack/react-query";
import { LogOut, ChevronDown, Building2 } from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Sidebar } from "./Sidebar";
import { useAuthStore } from "@/store/authStore";
import { apiGet } from "@/services/api";
import type { User, TenantOut } from "@/types";
import { cn } from "@/utils/cn";

function TenantSwitcher({ tenants }: { tenants: TenantOut[] }) {
  const tenantId = useAuthStore((s) => s.tenantId);
  const setTenantId = useAuthStore((s) => s.setTenantId);
  const setCompanySlug = useAuthStore((s) => s.setCompanySlug);

  if (tenants.length <= 1) return null;

  const current = tenants.find((t) => t.tenant_id === tenantId);

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button className="flex items-center gap-1.5 px-2 py-1.5 text-xs rounded-md hover:bg-accent transition-colors w-full">
          <Building2 className="h-3 w-3 shrink-0 text-muted-foreground" />
          <span className="flex-1 text-left truncate">
            {current?.company_name ?? "Select tenant"}
          </span>
          <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="start"
          sideOffset={4}
          className="z-50 min-w-[200px] bg-popover border rounded-md shadow-md p-1 text-sm"
        >
          {tenants.map((t) => (
            <DropdownMenu.Item
              key={t.tenant_id}
              onSelect={() => {
                setTenantId(t.tenant_id);
                setCompanySlug(t.company_slug);
              }}
              className={cn(
                "flex flex-col px-3 py-2 rounded cursor-pointer outline-none transition-colors",
                t.tenant_id === tenantId
                  ? "bg-primary/10 text-primary"
                  : "hover:bg-accent"
              )}
            >
              <span className="font-medium">{t.company_name}</span>
              <span className="text-xs text-muted-foreground">{t.enterprise_name}</span>
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

function UserMenu() {
  const { instance } = useMsal();
  const currentUser = useAuthStore((s) => s.currentUser);

  const initials = currentUser?.display_name
    ? currentUser.display_name
        .split(" ")
        .map((n) => n[0])
        .slice(0, 2)
        .join("")
        .toUpperCase()
    : "?";

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button className="flex items-center gap-2 px-2 py-1 rounded-md hover:bg-accent transition-colors">
          <span className="h-7 w-7 rounded-full bg-primary/20 text-primary text-xs font-semibold flex items-center justify-center shrink-0">
            {initials}
          </span>
          <span className="text-sm hidden sm:block max-w-[140px] truncate">
            {currentUser?.display_name ?? currentUser?.email ?? ""}
          </span>
          <ChevronDown className="h-3 w-3 text-muted-foreground" />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={4}
          className="z-50 min-w-[180px] bg-popover border rounded-md shadow-md p-1 text-sm"
        >
          {currentUser && (
            <div className="px-3 py-2 border-b mb-1">
              <p className="font-medium truncate">{currentUser.display_name}</p>
              <p className="text-xs text-muted-foreground truncate">{currentUser.email}</p>
            </div>
          )}
          <DropdownMenu.Item
            onSelect={() => instance.logoutRedirect()}
            className="flex items-center gap-2 px-3 py-2 rounded cursor-pointer hover:bg-accent outline-none text-red-600"
          >
            <LogOut className="h-4 w-4" />
            Sign Out
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const { accounts } = useMsal();
  const setCurrentUser = useAuthStore((s) => s.setCurrentUser);
  const setTenantId = useAuthStore((s) => s.setTenantId);
  const setCompanySlug = useAuthStore((s) => s.setCompanySlug);
  const tenantId = useAuthStore((s) => s.tenantId);

  // Bootstrap current user from /auth/me (includes backend-resolved permissions)
  useQuery({
    queryKey: ["me", accounts[0]?.homeAccountId],
    queryFn: async () => {
      const user = await apiGet<User>("/api/v1/auth/me");
      setCurrentUser(user);
      return user;
    },
    enabled: !!accounts.length,
    staleTime: 5 * 60 * 1000,
  });

  // Fetch tenant list to populate TenantSwitcher
  const { data: tenants = [] } = useQuery({
    queryKey: ["my-tenants", accounts[0]?.homeAccountId],
    queryFn: async () => {
      const list = await apiGet<TenantOut[]>("/api/v1/auth/tenants");
      // Auto-select first tenant if none chosen yet
      if (!tenantId && list.length > 0) {
        setTenantId(list[0].tenant_id);
        setCompanySlug(list[0].company_slug);
      }
      return list;
    },
    enabled: !!accounts.length,
    staleTime: 10 * 60 * 1000,
  });

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className="w-64 border-r bg-card flex flex-col shrink-0">
        <div className="p-5 border-b">
          <h1 className="text-lg font-bold text-primary">KAATS</h1>
          <p className="text-xs text-muted-foreground">KIU AI Automated Test System</p>
        </div>

        <Sidebar />

        {tenants.length > 1 && (
          <div className="p-3 border-t">
            <TenantSwitcher tenants={tenants} />
          </div>
        )}
      </aside>

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 border-b flex items-center justify-end px-6 gap-3 shrink-0">
          <UserMenu />
        </header>

        <main className="flex-1 overflow-auto">
          <div className="p-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
