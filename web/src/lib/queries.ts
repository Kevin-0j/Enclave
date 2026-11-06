import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { useAuth } from "./auth";
import type { AuditEntry, Camera, Member, Page, Role, Site, StreamGrant } from "./types";

/** Query keys are scoped by tenant so a tenant switch can never show cached data from the last one. */
function useTenantKey(): string {
  return useAuth().session?.tenant?.id ?? "none";
}

export function useCameras() {
  const t = useTenantKey();
  return useQuery({
    queryKey: [t, "cameras"],
    queryFn: () => api<Page<Camera>>("/api/v1/cameras?limit=200").then((p) => p.items),
  });
}

export function useSites() {
  const t = useTenantKey();
  return useQuery({ queryKey: [t, "sites"], queryFn: () => api<Site[]>("/api/v1/sites") });
}

export function useMembers(enabled = true) {
  const t = useTenantKey();
  return useQuery({ queryKey: [t, "members"], queryFn: () => api<Member[]>("/api/v1/users"), enabled });
}

export function useAudit(enabled = true) {
  const t = useTenantKey();
  return useQuery({
    queryKey: [t, "audit"],
    queryFn: () => api<AuditEntry[]>("/api/v1/audit?limit=200"),
    enabled,
    refetchInterval: 15_000,
  });
}

export function requestStream(cameraId: string, variant: "main" | "sub"): Promise<StreamGrant> {
  return api<StreamGrant>(`/api/v1/cameras/${cameraId}/stream`, { method: "POST", body: { variant } });
}

export interface CameraInput {
  name?: string;
  site_id?: string | null;
  enabled?: boolean;
  main_url?: string;
  sub_url?: string | null;
}

export function useSaveCamera() {
  const qc = useQueryClient();
  const t = useTenantKey();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: CameraInput }) =>
      id
        ? api<Camera>(`/api/v1/cameras/${id}`, { method: "PATCH", body })
        : api<Camera>("/api/v1/cameras", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: [t] }),
  });
}

export function useDeleteCamera() {
  const qc = useQueryClient();
  const t = useTenantKey();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/api/v1/cameras/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: [t] }),
  });
}

export function useAddMember() {
  const qc = useQueryClient();
  const t = useTenantKey();
  return useMutation({
    mutationFn: (body: { email: string; name: string; role: Role; password: string }) =>
      api<Member>("/api/v1/users", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: [t] }),
  });
}

export function useUpdateMember() {
  const qc = useQueryClient();
  const t = useTenantKey();
  return useMutation({
    mutationFn: ({ id, role }: { id: string; role: Role }) => api<Member>(`/api/v1/users/${id}`, { method: "PATCH", body: { role } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: [t] }),
  });
}

export function useRemoveMember() {
  const qc = useQueryClient();
  const t = useTenantKey();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/api/v1/users/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: [t] }),
  });
}
