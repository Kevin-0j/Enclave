import { Plus, Trash2, Users } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button, IconButton } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { SelectField, TextField } from "@/components/ui/Field";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ROLE_HINT, ROLE_LABEL } from "@/lib/labels";
import { useAddMember, useMembers, useRemoveMember, useUpdateMember } from "@/lib/queries";
import type { Role } from "@/lib/types";

const ROLES: Role[] = ["tenant_admin", "operator", "viewer"];

export function PeoplePage() {
  const { session, can } = useAuth();
  const manage = can("users:manage");
  const { data: members, isLoading } = useMembers();
  const update = useUpdateMember();
  const remove = useRemoveMember();
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onRole = (id: string, role: Role) =>
    update.mutate({ id, role }, { onError: (e) => setError(e instanceof ApiError ? e.message : "Couldn't change the role.") });

  return (
    <div className="mx-auto max-w-[980px] px-4 pt-5 sm:px-6 sm:pt-7">
      <PageHeader
        eyebrow={session?.tenant?.name}
        title="People"
        actions={manage && <Button variant="cta" icon={<Plus aria-hidden className="size-4" />} onClick={() => setAdding(true)}>Add person</Button>}
      >
        Admins see every camera. Operators and viewers see only the cameras they're given.
      </PageHeader>
      {error && (
        <p role="alert" className="mt-4 rounded-[10px] bg-danger-soft px-3 py-2.5 text-[13.5px] text-danger">
          {error}
        </p>
      )}
      <div className="mt-6">
        {isLoading ? (
          <div className="card h-40 skeleton" />
        ) : !members?.length ? (
          <EmptyState icon={Users} title="Nobody here yet" />
        ) : (
          <ul className="card divide-y divide-border">
            {members.map((m) => {
              const self = m.user_id === session?.user.id;
              return (
                <li key={m.user_id} className="flex flex-wrap items-center gap-3 px-4 py-3.5 sm:px-5">
                  <span aria-hidden className="grid size-9 shrink-0 place-items-center rounded-full bg-ink text-[13px] font-semibold text-amber">
                    {(m.name || m.email).slice(0, 1).toUpperCase()}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">
                      {m.name || m.email} {self && <span className="text-muted">(you)</span>}
                    </p>
                    <p className="truncate text-[12.5px] text-muted">{m.email}</p>
                  </div>
                  {manage && !self ? (
                    <div className="flex items-center gap-1">
                      <label className="sr-only" htmlFor={`role-${m.user_id}`}>
                        Role for {m.email}
                      </label>
                      <select
                        id={`role-${m.user_id}`}
                        value={m.role}
                        onChange={(e) => onRole(m.user_id, e.target.value as Role)}
                        className="h-9 rounded-full border border-border bg-surface px-3 text-[13px] hover:border-border-strong"
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>
                            {ROLE_LABEL[r]}
                          </option>
                        ))}
                      </select>
                      <IconButton label={`Remove ${m.email}`} size="sm" variant="danger-ghost" onClick={() => remove.mutate(m.user_id)}>
                        <Trash2 aria-hidden className="size-4" />
                      </IconButton>
                    </div>
                  ) : (
                    <Badge tone={m.role === "tenant_admin" ? "accent" : "muted"}>{ROLE_LABEL[m.role]}</Badge>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
      {adding && <AddPersonDialog onClose={() => setAdding(false)} />}
    </div>
  );
}

function AddPersonDialog({ onClose }: { onClose: () => void }) {
  const add = useAddMember();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("viewer");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await add.mutateAsync({ email, name, role, password });
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? (err.problem?.errors?.[0]?.msg ?? err.message) : "Couldn't add this person.");
    }
  };

  return (
    <Dialog
      open
      onOpenChange={(o) => !o && onClose()}
      title="Add a person"
      description="Email invitations arrive with notifications. For now, share the starting password with them in person."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="person-form" variant="cta" loading={add.isPending} disabled={!email || password.length < 12}>
            Add person
          </Button>
        </>
      }
    >
      <form id="person-form" onSubmit={submit} className="flex flex-col gap-4">
        <TextField label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} />
        <SelectField label="Role" value={role} onChange={(e) => setRole(e.target.value as Role)} hint={ROLE_HINT[role]}>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {ROLE_LABEL[r]}
            </option>
          ))}
        </SelectField>
        <TextField
          label="Starting password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          hint="At least 12 characters. If they already have an Enclave account, their own password is kept."
        />
        {error && (
          <p role="alert" className="rounded-[10px] bg-danger-soft px-3 py-2.5 text-[13.5px] text-danger">
            {error}
          </p>
        )}
      </form>
    </Dialog>
  );
}
