import { FormEvent, useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Users, 
  ShieldCheck, 
  ShieldAlert, 
  Plus, 
  X, 
  Search, 
  Mail, 
  Key, 
  ChevronRight, 
  Trash2, 
  Activity,
  Lock,
  Unlock,
  UserPlus
} from "lucide-react";
import { useAuth } from "../features/auth/AuthContext";
import { apiRequest } from "../lib/http";
import { EmptyState, PageIntro, SectionCard, StatCards } from "../components/ui/PageSections";
import type { AdminUser } from "../types/domain";

function RoleBadge({ role }: { role: string }) {
  const colors = {
    super_admin: "bg-brand text-white shadow-[0_0_10px_var(--brand-light)]",
    owner: "bg-emerald-500 text-white shadow-[0_0_10px_rgba(16,185,129,0.3)]",
    admin: "bg-blue-500/10 text-blue-500 border border-blue-500/20",
    user: "bg-surface-strong text-text-muted border border-border"
  };
  
  const normalizedRole = role.replace('_', ' ');
  const colorClass = colors[role as keyof typeof colors] || colors.user;

  return (
    <span className={`px-3 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest ${colorClass}`}>
      {normalizedRole}
    </span>
  );
}

export function UsersPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (["admin", "super_admin", "owner"].includes(String(user?.role || ""))) {
      void load();
    }
  }, [user?.role]);

  const roleOptions = useMemo(() => {
    const all = ["user", "admin", "super_admin", "owner"];
    if (["super_admin", "owner"].includes(String(user?.role || ""))) return all;
    return ["user", "admin"];
  }, [user?.role]);

  async function load() {
    setLoading(true);
    try {
      const data = await apiRequest<AdminUser[]>("/auth/users");
      setUsers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Platform synchronization failure");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Permanently remove this identity? This action cannot be undone.")) return;
    try {
      await apiRequest(`/auth/users/${id}`, { method: "DELETE" });
      setFlash("Identity removed successfully.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Identity removal failed");
    }
  }

  async function handleRoleChange(id: number, role: string) {
    try {
      await apiRequest(`/auth/users/${id}`, { method: "PATCH", body: { role } });
      setFlash("Access tier updated.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update access tier");
    }
  }

  async function handleToggleActive(id: number, isActive: boolean) {
    try {
      await apiRequest(`/auth/users/${id}`, { method: "PATCH", body: { is_active: !isActive } });
      setFlash("Node status updated.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update node status");
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = {
      name: String(form.get("name") || "").trim(),
      email: String(form.get("email") || "").trim().toLowerCase(),
      password: String(form.get("password") || ""),
      role: String(form.get("role") || "user"),
    };
    try {
      await apiRequest("/auth/users", { method: "POST", body: payload });
      event.currentTarget.reset();
      setFlash("Strategic node successfully provisioned.");
      setShowAddForm(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Identity creation protocol failed");
    }
  }

  const filteredUsers = users.filter(u => 
    u.name.toLowerCase().includes(search.toLowerCase()) || 
    u.email.toLowerCase().includes(search.toLowerCase())
  );

  if (!["admin", "super_admin", "owner"].includes(String(user?.role || ""))) {
    return (
      <div className="p-8">
        <PageIntro 
          eyebrow="Access Denied"
          title="Security Protocol"
          description="Your current identity level does not have clearance for the global user ledger."
        />
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      <PageIntro
        eyebrow="Platform Control"
        title="Identity Ledger"
        description="Comprehensive oversight of platform operators and internal stakeholders. Manage access levels and identity lifecycle protocols."
        actions={
          <button 
            onClick={() => setShowAddForm(!showAddForm)}
            className="btn-primary !h-12 !px-6 flex items-center gap-2"
          >
            {showAddForm ? <X size={16} /> : <UserPlus size={16} />}
            {showAddForm ? "Cancel Protocol" : "Provision Identity"}
          </button>
        }
      />

      <StatCards
        items={[
          { id: "all", label: "Global Node Count", value: users.length, icon: <Users size={18} />, note: "Platform identities" },
          { id: "active", label: "Enabled Nodes", value: users.filter((entry) => entry.is_active).length, icon: <Activity size={18} />, note: "Operational status" },
          { id: "admins", label: "Highest Privilege", value: users.filter((entry) => ["super_admin", "owner"].includes(entry.role)).length, icon: <ShieldCheck size={18} />, note: "Platform controllers" },
        ]}
      />

      {error && <div className="p-4 bg-danger/10 text-danger rounded-2xl font-bold border border-danger/20 text-xs animate-soft-enter">{error}</div>}
      {flash && <div className="p-4 bg-accent/10 text-accent rounded-2xl font-bold border border-accent/20 text-xs animate-soft-enter">{flash}</div>}

      <AnimatePresence>
        {showAddForm && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <SectionCard title="Provision New Identity" description="Define the operational parameters and clearance level for a new marketplace node.">
              <form className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6" onSubmit={handleSubmit}>
                <div className="space-y-2">
                  <label className="text-[10px] font-black uppercase tracking-widest text-text-muted ml-1">Legal Name</label>
                  <input className="modern-input" name="name" placeholder="Full Identity Name" required />
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-black uppercase tracking-widest text-text-muted ml-1">Secure Email</label>
                  <input className="modern-input" name="email" type="email" placeholder="name@platform.com" required />
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-black uppercase tracking-widest text-text-muted ml-1">Secure Key</label>
                  <div className="relative">
                    <input className="modern-input pr-10" name="password" type="password" minLength={8} placeholder="••••••••" required />
                    <Lock size={14} className="absolute right-4 top-1/2 -translate-y-1/2 text-text-muted" />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-black uppercase tracking-widest text-text-muted ml-1">Clearance Level</label>
                  <select className="modern-input cursor-pointer appearance-none" name="role" defaultValue="user">
                    {roleOptions.map((role) => <option key={role} value={role}>{role.replace('_', ' ')}</option>)}
                  </select>
                </div>
                <div className="lg:col-span-4 pt-4">
                  <button className="btn-primary w-full" type="submit">Synchronize Identity</button>
                </div>
              </form>
            </SectionCard>
          </motion.div>
        )}
      </AnimatePresence>

      <SectionCard 
        title="Directory Ledger" 
        description="Unified identity management with real-time status synchronization."
        action={
          <div className="relative group">
            <Search size={14} className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted group-focus-within:text-brand transition-colors" />
            <input 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search ledger..."
              className="pl-10 pr-4 py-2 bg-surface-soft border border-border rounded-xl outline-none font-bold text-[10px] w-64 focus:border-brand/30 transition-all"
            />
          </div>
        }
      >
        {loading ? (
          <div className="py-20 flex flex-col items-center justify-center gap-4">
            <div className="w-12 h-12 border-4 border-brand/10 border-t-brand rounded-full animate-spin" />
            <p className="text-[10px] font-black uppercase tracking-widest text-text-muted animate-pulse">Syncing Identity Matrix...</p>
          </div>
        ) : filteredUsers.length === 0 ? (
          <EmptyState
            title="No matching identities"
            description="The search protocol could not synchronize any records within the active ledger."
            icon={<ShieldAlert size={32} />}
          />
        ) : (
          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            {filteredUsers.map((entry) => (
              <motion.article 
                key={entry.id}
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className="glass-card p-6 flex flex-col group hover:border-brand/40"
              >
                <div className="flex items-start justify-between mb-6">
                  <div className="flex items-center gap-4 min-w-0">
                    <div className="w-12 h-12 rounded-[1.25rem] bg-surface-soft border border-border flex items-center justify-center text-brand font-black text-lg shrink-0 group-hover:bg-brand/10 group-hover:border-brand/20 transition-all">
                      {entry.name[0].toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <h3 className="font-display font-black text-lg text-text truncate group-hover:text-brand transition-colors leading-none">{entry.name}</h3>
                      <div className="flex items-center gap-2 mt-2">
                        <div className={`w-1.5 h-1.5 rounded-full ${entry.is_active ? 'bg-emerald-500 animate-pulse' : 'bg-danger'}`} />
                        <p className="text-[9px] font-bold text-text-muted uppercase tracking-widest">{entry.is_active ? "Live Session" : "Node Disabled"}</p>
                      </div>
                    </div>
                  </div>
                  <RoleBadge role={entry.role} />
                </div>
                
                 <div className="space-y-4 pt-6 border-t border-border mt-auto">
                  <div className="flex items-center gap-3 text-xs font-bold text-text-muted group/item cursor-pointer">
                    <Mail size={14} className="group-hover/item:text-brand transition-colors" />
                    <span className="truncate">{entry.email}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <div className="flex items-center gap-2">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider ${
                        entry.is_verified ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20'
                      }`}>
                        {entry.is_verified ? 'Confirmed' : 'Unconfirmed'}
                      </span>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider ${
                        entry.is_active ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-danger/10 text-danger border border-danger/20'
                      }`}>
                        {entry.is_active ? 'Active' : 'Disabled'}
                      </span>
                    </div>
                    <div className="flex gap-1">
                      <select
                        value={entry.role}
                        onChange={(e) => void handleRoleChange(entry.id, e.target.value)}
                        className="text-[9px] font-black uppercase tracking-wider bg-surface-soft border border-border rounded-lg px-2 py-1 outline-none focus:border-brand/40"
                      >
                        {roleOptions.map((role) => <option key={role} value={role}>{role.replace('_', ' ')}</option>)}
                      </select>
                      <button onClick={() => void handleToggleActive(entry.id, entry.is_active)} className={`p-2 rounded-lg transition-all ${entry.is_active ? 'bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500 hover:text-white' : 'bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500 hover:text-white'}`}>
                        {entry.is_active ? <Lock size={14} /> : <Unlock size={14} />}
                      </button>
                      <button onClick={() => void handleDelete(entry.id)} className="p-2 text-text-muted hover:text-danger transition-colors">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                </div>
              </motion.article>
            ))}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
