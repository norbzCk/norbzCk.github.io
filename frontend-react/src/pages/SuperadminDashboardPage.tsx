import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { 
  ShieldCheck, 
  TrendingUp, 
  Users, 
  ShoppingBag, 
  Truck, 
  AlertTriangle, 
  Zap, 
  Search,
  Plus,
  Trash2,
  CheckCircle2,
  X,
  ChevronRight,
  LogOut,
  LayoutDashboard,
  Box,
  BarChart3,
  Globe,
  PieChart,
  Calendar,
  Activity,
  ArrowUpRight,
  Clock,
  MessageSquare
} from "lucide-react";
import { useAuth } from "../features/auth/AuthContext";
import { apiRequest } from "../lib/http";
import { PageIntro, StatCards, SectionCard } from "../components/ui/PageSections";
import type { SuperadminOverview, VerificationBusinessman, VerificationLogistics, VerificationUser } from "../types/domain";
import { env } from "../config/env";

interface Businessman {
  id: number;
  business_name: string;
  owner_name: string;
  email: string;
  phone: string;
  verification_status?: string;
  created_at?: string;
}

interface Customer {
  id: number;
  name: string;
  email: string;
  phone: string;
  created_at?: string;
  is_verified?: boolean;
  is_active?: boolean;
}

interface LogisticsUser {
  id: number;
  name: string;
  email: string;
  phone: string;
  account_type: string;
  verification_status?: string;
  created_at?: string;
}

interface Dispute {
  id: number;
  sale_id: number;
  buyer_id: number;
  seller_id: number;
  logistics_id: number | null;
  status: string;
  resolution_details: string | null;
  created_at: string;
  resolved_at: string | null;
}

interface GlobalAnalytics {
  graphs: {
    revenueByProduct: string | null;
    revenueOverTime: string | null;
  };
}

type ActiveTab = "businessmen" | "customers" | "logistics";

function formatMoney(value?: number) {
  return `TZS ${Number(value || 0).toLocaleString()}`;
}

function compactMoney(value?: number) {
  return `TZS ${Number(value || 0).toLocaleString(undefined, {
    notation: "compact",
    maximumFractionDigits: 1,
  })}`;
}

export function SuperadminDashboardPage() {
  const navigate = useNavigate();
  const [overview, setOverview] = useState<SuperadminOverview | null>(null);
  const [analytics, setAnalytics] = useState<GlobalAnalytics | null>(null);
  const [businessmen, setBusinessmen] = useState<Businessman[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [logistics, setLogistics] = useState<LogisticsUser[]>([]);
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<ActiveTab>("businessmen");
  const [showAddModal, setShowAddModal] = useState(false);
  const [verificationTab, setVerificationTab] = useState<"businessmen" | "logistics" | "users">("businessmen");
  const [verificationData, setVerificationData] = useState<{
    businessmen: VerificationBusinessman[];
    logistics: VerificationLogistics[];
    users: VerificationUser[];
  }>({ businessmen: [], logistics: [], users: [] });

  useEffect(() => {
    void loadData();
  }, []);

   async function loadData() {
     setLoading(true);
     setError("");
     try {
       const [overviewData, businessmenData, customersData, logisticsData, analyticsData, disputesData] = await Promise.all([
         apiRequest<SuperadminOverview>("/superadmin/stats"),
         apiRequest<Businessman[]>("/superadmin/businessmen"),
         apiRequest<Customer[]>("/superadmin/customers"),
         apiRequest<LogisticsUser[]>("/superadmin/logistics"),
         apiRequest<GlobalAnalytics>("/dashboard/analytics"),
         apiRequest<Dispute[]>("/disputes"),
       ]);
        const verifications = await apiRequest<{
          businessmen: VerificationBusinessman[];
          logistics: VerificationLogistics[];
          users: VerificationUser[];
        }>("/superadmin/verifications");
       setOverview(overviewData);
       setBusinessmen(businessmenData);
       setCustomers(customersData);
       setLogistics(logisticsData);
       setDisputes(disputesData);
       setVerificationData(verifications);
       setAnalytics(analyticsData);
     } catch (err) {
       setError(err instanceof Error ? err.message : "Failed to load superadmin overview");
     } finally {
       setLoading(false);
     }
   }

  async function updateVerification(kind: "businessmen" | "logistics" | "users", id: number, status: string) {
    try {
      const endpoint = kind === "users"
        ? `/superadmin/customers/${id}/verification`
        : `/superadmin/${kind}/${id}/verification`;
      await apiRequest(endpoint, {
        method: "PATCH",
        body: { status },
      });
      setSuccess(`${kind === "businessmen" ? "Seller" : kind === "logistics" ? "Logistics" : "Customer"} verification updated.`);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update verification");
    }
  }

  async function deleteEntity(kind: "businessmen" | "customers" | "logistics", id: number) {
    if (!confirm("Permanently remove this entity? This action cannot be undone.")) return;
    try {
      const endpoint = `/superadmin/${kind}/${id}`;
      await apiRequest(endpoint, { method: "DELETE" });
      setSuccess("Entity removed successfully.");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete entity");
    }
  }

  const statItems = useMemo(() => {
    if (!overview) return [];
    return [
      { id: "rev", label: "Global Revenue", value: formatMoney(overview.total_revenue), icon: <Zap size={18} />, note: `${overview.completed_orders} orders` },
      { id: "sellers", label: "Active Sellers", value: overview.active_businessmen, icon: <ShoppingBag size={18} />, note: `${overview.total_businessmen} registered` },
      { id: "transit", label: "In Transit", value: overview.in_transit_orders, icon: <Truck size={18} />, note: "Active deliveries" },
      { id: "stock", label: "Inventory Risk", value: overview.low_stock_products, icon: <AlertTriangle size={18} />, note: "Low stock items" },
      { id: "pending-users", label: "Pending Users", value: overview.pending_user_verifications, icon: <Users size={18} />, note: "Awaiting confirmation" },
    ];
  }, [overview]);

  const currentData = activeTab === "businessmen" ? businessmen : activeTab === "customers" ? customers : logistics;

  function resolveGraphUrl(path?: string | null) {
    if (!path) return "";
    return `${env.apiBase}${path}?t=${Date.now()}`;
  }

  if (loading) {
    return (
      <div className="h-96 flex flex-col items-center justify-center gap-6">
        <div className="w-16 h-16 border-4 border-brand/10 border-t-brand rounded-full animate-spin" />
        <p className="font-black text-[10px] uppercase tracking-[0.3em] text-text-muted animate-pulse">Syncing Platform Intelligence...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      <PageIntro 
        eyebrow="Platform Command Center"
        title="Global Intelligence"
        description="Unified oversight of the smart marketplace network. Manage entities, verify trust levels, and monitor economic trajectory."
        actions={
          <div className="flex gap-3">
            <button onClick={() => setShowAddModal(true)} className="btn-primary !h-12 !px-6 flex items-center gap-2">
              <Plus size={16} />
              Register Entity
            </button>
            <button onClick={() => void loadData()} className="btn-secondary !h-12 !px-4 flex items-center justify-center">
              <Activity size={16} />
            </button>
          </div>
        }
      />

       <StatCards items={statItems} />
       
       {/* Dispute Resolution Center */}
       <motion.article 
         initial={{ opacity: 0, y: 20 }}
         animate={{ opacity: 1, y: 0 }}
         className="lg:col-span-1 glass-card p-8 space-y-6"
       >
         <div className="flex items-center justify-between">
           <div className="space-y-1">
             <h3 className="text-xl font-display font-black text-text tracking-tight flex items-center gap-2">
               <ShieldCheck size={20} className="text-danger" />
               Dispute Resolution
             </h3>
             <p className="text-xs text-text-muted font-medium">Monitor and resolve transaction disputes between buyers and sellers.</p>
           </div>
           <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-danger/10 text-danger text-[10px] font-black uppercase tracking-widest border border-danger/20">
             <AlertTriangle size={14} />
             Active Disputes
           </div>
         </div>
         
         <div className="space-y-4 max-h-[300px] overflow-y-auto no-scrollbar pr-2">
           {disputes.length === 0 ? (
             <p className="py-8 text-center text-text-muted text-[10px] font-black uppercase tracking-widest opacity-40">
               No disputes found
             </p>
           ) : (
             disputes.map((dispute) => (
               <div key={dispute.id} className="p-4 rounded-xl bg-surface-soft/50 border border-border flex items-center justify-between group hover:border-brand/40 transition-all">
                 <div className="min-w-0">
                   <strong className="text-text font-bold block truncate text-sm">Order #{dispute.sale_id}</strong>
                   <p className="text-[9px] font-bold text-text-muted uppercase tracking-wider mt-1">
                     Buyer: {dispute.buyer_id} | Seller: {dispute.seller_id}
                   </p>
                 </div>
                 <div className="flex gap-2">
                   <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase 
                     ${dispute.status === 'open' ? 'bg-yellow-100 text-yellow-800' :
                       dispute.status === 'resolved_seller' ? 'bg-emerald-100 text-emerald-800' :
                       dispute.status === 'resolved_buyer' ? 'bg-blue-100 text-blue-800' :
                       dispute.status === 'resolved_mutual' ? 'bg-purple-100 text-purple-800' :
                       'bg-red-100 text-red-800'}`}>
                   {dispute.status.replace('_', ' ').toUpperCase()}
                   </span>
                 </div>
               </div>
             ))
           )}
         </div>
         
         <button className="w-full mt-4 py-3 rounded-xl border border-dashed border-border text-[9px] font-black uppercase tracking-[0.2em] text-text-muted hover:text-brand hover:border-brand/40 transition-all">
           View All Disputes
         </button>
       </motion.article>

      {error && <div className="p-4 bg-danger/10 text-danger rounded-2xl font-bold border border-danger/20 animate-soft-enter text-xs">{error}</div>}
      {success && <div className="p-4 bg-accent/10 text-accent rounded-2xl font-bold border border-accent/20 animate-soft-enter text-xs">{success}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Trend Analysis - Graph Section */}
        <motion.article 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="lg:col-span-2 glass-card p-8 space-y-8"
        >
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <h3 className="text-xl font-display font-black text-text tracking-tight flex items-center gap-2">
                <TrendingUp size={20} className="text-brand" />
                Economic Trajectory
              </h3>
              <p className="text-xs text-text-muted font-medium">Real-time revenue synchronization across the network.</p>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-500 text-[10px] font-black uppercase tracking-widest border border-emerald-500/20">
              <ArrowUpRight size={14} />
              +14.2% Growth
            </div>
          </div>
          
          <div className="aspect-[21/9] w-full rounded-2xl overflow-hidden bg-surface-soft/50 border border-border flex items-center justify-center">
            {analytics?.graphs.revenueOverTime ? (
              <img 
                src={resolveGraphUrl(analytics.graphs.revenueOverTime)} 
                alt="Revenue Trend" 
                className="w-full h-full object-contain filter dark:invert dark:brightness-90 dark:contrast-125 dark:opacity-90"
              />
            ) : (
              <div className="flex flex-col items-center gap-4 opacity-30">
                <BarChart3 size={48} />
                <p className="text-[10px] font-black uppercase tracking-widest">Aggregating protocol data...</p>
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {overview?.category_performance?.slice(0, 4).map(item => (
              <div key={item.category} className="p-4 rounded-xl bg-surface-soft border border-border">
                <span className="text-[9px] font-black text-text-muted uppercase tracking-widest block mb-1">{item.category}</span>
                <strong className="text-sm font-black text-text">{compactMoney(item.revenue)}</strong>
              </div>
            ))}
          </div>
        </motion.article>

        {/* Verification Center */}
        <SectionCard 
          title="Trust Protocols" 
          description="Entity verification & risk management."
          action={
            <div className="flex bg-surface-soft p-1 rounded-xl border border-border">
              <button 
                onClick={() => setVerificationTab("businessmen")}
                className={`px-3 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${verificationTab === 'businessmen' ? 'bg-surface text-brand shadow-sm' : 'text-text-muted hover:text-text'}`}
              >
                Sellers
              </button>
              <button 
                onClick={() => setVerificationTab("logistics")}
                className={`px-3 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${verificationTab === 'logistics' ? 'bg-surface text-brand shadow-sm' : 'text-text-muted hover:text-text'}`}
              >
                Nodes
              </button>
              <button 
                onClick={() => setVerificationTab("users")}
                className={`px-3 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${verificationTab === 'users' ? 'bg-surface text-brand shadow-sm' : 'text-text-muted hover:text-text'}`}
              >
                Users
              </button>
            </div>
          }
        >
          <div className="space-y-4 max-h-[400px] overflow-y-auto no-scrollbar pr-2">
            <AnimatePresence mode="wait">
              {verificationTab === "businessmen" ? (
                <motion.div key="v-biz" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-3">
                  {verificationData.businessmen.filter(i => i.verification_status !== 'verified').length === 0 ? <p className="py-10 text-center text-text-muted text-[10px] font-black uppercase tracking-widest opacity-40">All seller nodes verified.</p> : null}
                  {verificationData.businessmen.filter(i => i.verification_status !== 'verified').map(item => (
                    <div key={item.id} className="p-4 rounded-xl bg-surface-soft/50 border border-border flex items-center justify-between group hover:border-brand/40 transition-all">
                      <div className="min-w-0">
                        <strong className="text-text font-bold block truncate text-sm">{item.business_name}</strong>
                        <p className="text-[9px] font-bold text-text-muted uppercase tracking-wider mt-1">{item.area || "Remote"}</p>
                      </div>
                      <div className="flex gap-2">
                        <button onClick={() => updateVerification("businessmen", item.id, "verified")} className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-500 flex items-center justify-center hover:bg-emerald-500 hover:text-white transition-all shadow-sm"><CheckCircle2 size={14} /></button>
                        <button onClick={() => updateVerification("businessmen", item.id, "rejected")} className="w-8 h-8 rounded-lg bg-danger/10 text-danger flex items-center justify-center hover:bg-danger hover:text-white transition-all shadow-sm"><X size={14} /></button>
                      </div>
                    </div>
                  ))}
                </motion.div>
              ) : verificationTab === "logistics" ? (
                <motion.div key="v-log" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-3">
                  {verificationData.logistics.filter(i => i.verification_status !== 'verified').length === 0 ? <p className="py-10 text-center text-text-muted text-[10px] font-black uppercase tracking-widest opacity-40">All logistics nodes verified.</p> : null}
                  {verificationData.logistics.filter(i => i.verification_status !== 'verified').map(item => (
                    <div key={item.id} className="p-4 rounded-xl bg-surface-soft/50 border border-border flex items-center justify-between group hover:border-brand/40 transition-all">
                      <div className="min-w-0">
                        <strong className="text-text font-bold block truncate text-sm">{item.name}</strong>
                        <p className="text-[9px] font-bold text-text-muted uppercase tracking-wider mt-1">{item.base_area}</p>
                      </div>
                      <div className="flex gap-2">
                        <button onClick={() => updateVerification("logistics", item.id, "verified")} className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-500 flex items-center justify-center hover:bg-emerald-500 hover:text-white transition-all shadow-sm"><CheckCircle2 size={14} /></button>
                        <button onClick={() => updateVerification("logistics", item.id, "rejected")} className="w-8 h-8 rounded-lg bg-danger/10 text-danger flex items-center justify-center hover:bg-danger hover:text-white transition-all shadow-sm"><X size={14} /></button>
                      </div>
                    </div>
                  ))}
                </motion.div>
              ) : (
                <motion.div key="v-users" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-3">
                  {verificationData.users.length === 0 ? <p className="py-10 text-center text-text-muted text-[10px] font-black uppercase tracking-widest opacity-40">All user emails confirmed.</p> : null}
                  {verificationData.users.map(item => (
                    <div key={item.id} className="p-4 rounded-xl bg-surface-soft/50 border border-border flex items-center justify-between group hover:border-brand/40 transition-all">
                      <div className="min-w-0">
                        <strong className="text-text font-bold block truncate text-sm">{item.name}</strong>
                        <p className="text-[9px] font-bold text-text-muted uppercase tracking-wider mt-1">{item.email}</p>
                      </div>
                      <div className="flex gap-2">
                        <button onClick={() => updateVerification("users", item.id, "verified")} className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-500 flex items-center justify-center hover:bg-emerald-500 hover:text-white transition-all shadow-sm"><CheckCircle2 size={14} /></button>
                      </div>
                    </div>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
          <button className="w-full mt-6 py-3 rounded-xl border border-dashed border-border text-[9px] font-black uppercase tracking-[0.2em] text-text-muted hover:text-brand hover:border-brand/40 transition-all">
            Full Audit Logs
          </button>
        </SectionCard>
      </div>

      {/* Main Directory Ledger */}
      <SectionCard 
        title="Account Ledger" 
        description="Comprehensive control of platform participants."
        action={
          <div className="flex bg-surface-soft p-1 rounded-xl border border-border shadow-inner">
            {(['businessmen', 'customers', 'logistics'] as const).map(tab => (
              <button 
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${activeTab === tab ? 'bg-brand text-white shadow-lg' : 'text-text-muted hover:text-text'}`}
              >
                {tab}
              </button>
            ))}
          </div>
        }
      >
        <div className="overflow-x-auto no-scrollbar">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-border">
                <th className="pb-4 text-[9px] font-black uppercase tracking-[0.2em] text-text-muted">Protocol ID</th>
                <th className="pb-4 text-[9px] font-black uppercase tracking-[0.2em] text-text-muted">Account Identity</th>
                <th className="pb-4 text-[9px] font-black uppercase tracking-[0.2em] text-text-muted">Communication</th>
                <th className="pb-4 text-[9px] font-black uppercase tracking-[0.2em] text-text-muted">Status</th>
                <th className="pb-4 text-right text-[9px] font-black uppercase tracking-[0.2em] text-text-muted">Ops</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {currentData.map((item) => (
                <tr key={item.id} className="group hover:bg-surface-soft/40 transition-colors">
                  <td className="py-4 pr-4">
                    <span className="inline-flex items-center justify-center px-2 py-1 rounded-lg bg-surface-soft border border-border font-black text-[10px] text-brand">
                      {item.id.toString().padStart(4, '0')}
                    </span>
                  </td>
                  <td className="py-4 pr-4">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-brand/10 border border-brand/20 flex items-center justify-center text-brand font-black text-xs">
                        {('business_name' in item ? item.business_name : item.name)[0].toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <strong className="text-sm font-black text-text block truncate">{'business_name' in item ? item.business_name : item.name}</strong>
                        <p className="text-[9px] font-bold text-text-muted uppercase tracking-wider mt-0.5">{('owner_name' in item ? item.owner_name : activeTab === 'customers' ? 'Buyer Account' : 'Standard Access')}</p>
                      </div>
                    </div>
                  </td>
                  <td className="py-4 pr-4">
                    <div className="space-y-0.5">
                      <p className="text-xs font-bold text-text truncate max-w-[180px]">{item.email}</p>
                      <p className="text-[9px] font-medium text-text-muted tracking-wide">{item.phone}</p>
                    </div>
                  </td>
                  <td className="py-4 pr-4">
                    <div className="flex flex-col gap-1">
                      {activeTab === 'customers' && (
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider w-fit ${
                          item.is_verified ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20'
                        }`}>
                          {item.is_verified ? 'Confirmed' : 'Unconfirmed'}
                        </span>
                      )}
                      {activeTab === 'businessmen' && (
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider w-fit ${
                          item.verification_status === 'verified' ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20'
                        }`}>
                          {item.verification_status || 'pending'}
                        </span>
                      )}
                      {activeTab === 'logistics' && (
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider w-fit ${
                          item.verification_status === 'verified' ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20'
                        }`}>
                          {item.verification_status || 'pending'}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="py-4 text-right">
                    <button onClick={() => void deleteEntity(activeTab, item.id)} className="w-8 h-8 rounded-lg bg-danger/5 text-danger flex items-center justify-center ml-auto hover:bg-danger hover:text-white transition-all opacity-0 group-hover:opacity-100">
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {currentData.length === 0 && <div className="py-20 text-center text-text-muted text-[10px] font-black uppercase tracking-[0.3em] opacity-40">Ledger synchronization pending...</div>}
        </div>
      </SectionCard>

      {overview?.recent_orders && overview.recent_orders.length > 0 && (
        <SectionCard title="Recent Orders" description="Latest transactions across the marketplace network.">
          <div className="overflow-x-auto no-scrollbar">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-border">
                  <th className="pb-4 text-[9px] font-black uppercase tracking-[0.2em] text-text-muted">Order ID</th>
                  <th className="pb-4 text-[9px] font-black uppercase tracking-[0.2em] text-text-muted">Product</th>
                  <th className="pb-4 text-[9px] font-black uppercase tracking-[0.2em] text-text-muted">Status</th>
                  <th className="pb-4 text-[9px] font-black uppercase tracking-[0.2em] text-text-muted">Qty</th>
                  <th className="pb-4 text-right text-[9px] font-black uppercase tracking-[0.2em] text-text-muted">Revenue</th>
                  <th className="pb-4 text-right text-[9px] font-black uppercase tracking-[0.2em] text-text-muted">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {overview.recent_orders.map((order) => (
                  <tr key={order.id} className="group hover:bg-surface-soft/40 transition-colors">
                    <td className="py-3 pr-4">
                      <span className="inline-flex items-center justify-center px-2 py-1 rounded-lg bg-surface-soft border border-border font-black text-[10px] text-brand">
                        #{order.id}
                      </span>
                    </td>
                    <td className="py-3 pr-4">
                      <strong className="text-xs font-bold text-text block truncate max-w-[200px]">{order.product || "—"}</strong>
                      <p className="text-[9px] font-medium text-text-muted">{order.category || ""}</p>
                    </td>
                    <td className="py-3 pr-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider ${
                        order.status === 'Received' || order.status === 'Delivered' ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' :
                        order.status === 'Pending' ? 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20' :
                        'bg-slate-500/10 text-slate-500 border border-slate-500/20'
                      }`}>
                        {order.status || "pending"}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-xs font-bold text-text">{order.quantity || 0}</td>
                    <td className="py-3 pr-4 text-right text-xs font-bold text-text">TZS {(order.revenue || 0).toLocaleString()}</td>
                    <td className="py-3 text-right text-[10px] font-medium text-text-muted">{order.date ? new Date(order.date).toLocaleDateString() : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {overview?.seller_leaderboard && overview.seller_leaderboard.length > 0 && (
          <SectionCard title="Seller Leaderboard" description="Top performing marketplace nodes." className="lg:col-span-2">
            <div className="space-y-3">
              {overview.seller_leaderboard.map((seller, idx) => (
                <div key={seller.id} className="flex items-center gap-4 p-4 rounded-xl bg-surface-soft/50 border border-border hover:border-brand/40 transition-all">
                  <span className="text-lg font-black text-text-muted w-8 text-center">#{idx + 1}</span>
                  <div className="flex-1 min-w-0">
                    <strong className="text-sm font-black text-text block truncate">{seller.business_name}</strong>
                    <p className="text-[9px] font-bold text-text-muted uppercase tracking-wider">{seller.region} • {seller.area}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-black text-text">TZS {Number(seller.total_revenue || 0).toLocaleString()}</p>
                    <p className="text-[9px] font-bold text-text-muted uppercase tracking-wider">{seller.total_sales || 0} sales • {Number(seller.rating || 0).toFixed(1)} rating</p>
                  </div>
                </div>
              ))}
            </div>
          </SectionCard>
        )}

        {overview?.insights && overview.insights.length > 0 && (
          <SectionCard title="Platform Insights" description="AI-generated operational intelligence.">
            <div className="space-y-4">
              {overview.insights.map((insight) => (
                <div key={insight.id} className="p-4 rounded-xl bg-surface-soft/50 border border-border">
                  <h4 className="text-xs font-black text-text uppercase tracking-wider mb-1">{insight.title}</h4>
                  <p className="text-[11px] font-medium text-text-muted leading-relaxed">{insight.message}</p>
                </div>
              ))}
            </div>
          </SectionCard>
        )}
      </div>

      {overview?.inventory_watch && overview.inventory_watch.length > 0 && (
        <SectionCard title="Inventory Watch" description="Products nearing stock-out across the network.">
          <div className="overflow-x-auto no-scrollbar">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-border">
                  <th className="pb-4 text-[9px] font-black uppercase tracking-[0.2em] text-text-muted">Product</th>
                  <th className="pb-4 text-[9px] font-black uppercase tracking-[0.2em] text-text-muted">Seller</th>
                  <th className="pb-4 text-[9px] font-black uppercase tracking-[0.2em] text-text-muted">Area</th>
                  <th className="pb-4 text-right text-[9px] font-black uppercase tracking-[0.2em] text-text-muted">Stock</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {overview.inventory_watch.map((item) => (
                  <tr key={item.product_id} className="group hover:bg-surface-soft/40 transition-colors">
                    <td className="py-3 pr-4">
                      <strong className="text-xs font-bold text-text block truncate max-w-[200px]">{item.product_name}</strong>
                    </td>
                    <td className="py-3 pr-4 text-xs font-medium text-text-muted">{item.seller_name}</td>
                    <td className="py-3 pr-4 text-xs font-medium text-text-muted">{item.seller_area || "—"}</td>
                    <td className="py-3 text-right">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider ${
                        item.stock === 0 ? 'bg-danger/10 text-danger border border-danger/20' :
                        item.stock < 3 ? 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20' :
                        'bg-orange-500/10 text-orange-500 border border-orange-500/20'
                      }`}>
                        {item.stock} left
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      <AnimatePresence>
        {showAddModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setShowAddModal(false)} className="absolute inset-0 bg-dark-bg/60 backdrop-blur-md" />
            <motion.div initial={{ scale: 0.98, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.98, opacity: 0 }} className="relative w-full max-w-xl glass-card border border-white/10 shadow-[0_50px_100px_rgba(0,0,0,0.4)] overflow-hidden">
              <div className="p-8 border-b border-border flex items-center justify-between bg-surface/50">
                <div>
                  <h3 className="text-xl font-display font-black text-text uppercase tracking-tight">Onboard Entity</h3>
                  <p className="text-[10px] font-bold text-text-muted uppercase tracking-widest mt-1">Registration protocol active.</p>
                </div>
                <button onClick={() => setShowAddModal(false)} className="w-10 h-10 rounded-xl bg-surface-soft flex items-center justify-center hover:bg-surface-strong transition-all"><X size={18} /></button>
              </div>
              <div className="p-10 text-center space-y-6">
                <div className="w-20 h-20 rounded-[2.5rem] bg-brand/10 text-brand flex items-center justify-center mx-auto border-2 border-dashed border-brand/30">
                  <Globe size={40} className="animate-pulse" />
                </div>
                <p className="text-sm font-medium text-text-muted max-w-xs mx-auto leading-relaxed">Systematic registration of new marketplace entities requires identity validation.</p>
              </div>
              <div className="p-8 bg-surface-soft/80 border-t border-border flex justify-end gap-3">
                <button onClick={() => setShowAddModal(false)} className="h-12 px-6 rounded-xl text-[10px] font-black uppercase tracking-widest text-text-muted hover:text-text transition-all">Cancel</button>
                <button className="h-12 px-8 bg-brand text-white rounded-xl text-[10px] font-black uppercase tracking-widest shadow-lg shadow-brand/20 hover:bg-brand-strong transition-all">Confirm Protocol</button>
              </div>
            </motion.div>
          </div>
         )}
       </AnimatePresence>
     </div>
   );
 }
