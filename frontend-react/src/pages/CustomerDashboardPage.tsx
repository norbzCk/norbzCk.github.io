import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { 
  ShoppingBag, 
  Clock, 
  CheckCircle2, 
  Truck, 
  Zap, 
  ArrowRight, 
  Package,
  Search,
  ChevronRight,
  TrendingUp,
  MapPin,
  X,
  CreditCard,
  ShieldCheck,
  Star
} from "lucide-react";
import { useAuth } from "../features/auth/AuthContext";
import { useCart } from "../features/auth/CartContext";
import { StatCards, PageIntro } from "../components/ui/PageSections";
import { apiRequest } from "../lib/http";
import type { Order } from "../types/domain";

const lifecycleSteps = ["Pending", "Confirmed", "Processing", "Dispatched", "In Transit", "Delivery Failed", "Delivered"] as const;

function formatMoney(value?: number) {
  return `TZS ${Number(value || 0).toLocaleString()}`;
}

function normalizeStatus(value?: string | null) {
  const status = String(value || "").trim().toLowerCase();
  if (status.includes("delivery failed")) return "Delivery Failed";
  if (status === "confirmed") return "Confirmed";
  if (status === "processing" || status === "packed" || status === "ready for shipping") return "Processing";
  if (status === "dispatched" || status === "shipped") return "Dispatched";
  if (status === "in transit" || status === "on the way") return "In Transit";
  if (status === "delivered" || status === "received") return "Delivered";
  if (status === "cancelled" || status === "canceled") return "Cancelled";
  return "Pending";
}

function statusColor(status: string) {
  if (status === "Delivered") return "text-emerald-500 bg-emerald-500/10";
  if (status === "Delivery Failed") return "text-danger bg-danger/10";
  if (status === "Cancelled") return "text-danger bg-danger/10";
  if (status === "Pending") return "text-amber-500 bg-amber-500/10";
  return "text-brand bg-brand/10";
}

function progressPercent(status: string) {
  if (status === "Cancelled") return 8;
  const index = lifecycleSteps.indexOf(status as (typeof lifecycleSteps)[number]);
  return index >= 0 ? Math.max(12, Math.round(((index + 1) / lifecycleSteps.length) * 100)) : 12;
}

export function CustomerDashboardPage() {
  const { user } = useAuth();
  const { cartCount, cartTotal } = useCart();
  const navigate = useNavigate();
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");
  const [loading, setLoading] = useState(false);
  const [filterKeyword, setFilterKeyword] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("All");
  const deferredFilterKeyword = useDeferredValue(filterKeyword);

  useEffect(() => {
    if (user?.role === "user") void load();
  }, [user?.role]);

  async function load() {
    try {
      setLoading(true);
      setError("");
      const data = await apiRequest<Order[]>("/orders/");
      setOrders(Array.isArray(data) ? data : []);
    } catch (err) {
      setOrders([]);
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }

  const summary = useMemo(() => {
    const active = orders.filter(o => !["Delivered", "Cancelled"].includes(normalizeStatus(o.status))).length;
    const spend = orders.reduce((sum, o) => sum + (o.total || (Number(o.unit_price) * Number(o.quantity))), 0);
    return { active, total: orders.length, spend };
  }, [orders]);

  const statItems = useMemo(() => [
    { id: "active", label: "Active Orders", value: summary.active, icon: <Truck size={18} />, note: "Moving through fulfillment" },
    { id: "spend", label: "Account Spend", value: formatMoney(summary.spend), icon: <Zap size={18} /> },
    { id: "cart", label: "Cart Value", value: formatMoney(cartTotal), icon: <ShoppingBag size={18} />, note: `${cartCount} items drafted` },
    { id: "total", label: "Order History", value: summary.total, icon: <Package size={18} /> },
  ], [summary, cartCount, cartTotal]);

  const currentOrder = useMemo(() => {
    return [...orders]
      .sort((a, b) => new Date(b.order_date || 0).getTime() - new Date(a.order_date || 0).getTime())
      .find(o => !["Delivered", "Cancelled"].includes(normalizeStatus(o.status))) || orders[0] || null;
  }, [orders]);

  const filteredOrders = useMemo(() => {
    const kw = deferredFilterKeyword.toLowerCase();
    return orders.filter(o => 
      (selectedCategory === "All" || o.category === selectedCategory) &&
      (!kw || `${o.product} ${o.provider_name}`.toLowerCase().includes(kw))
    ).slice(0, 5);
  }, [deferredFilterKeyword, orders, selectedCategory]);

  const categories = useMemo(() => ["All", ...Array.from(new Set(orders.map(o => o.category || "General"))).sort()], [orders]);

  async function handleCancel(id: number) {
    try {
      await apiRequest(`/orders/${id}/cancel`, { method: "POST" });
      setFlash("Order successfully cancelled.");
      await load();
    } catch (err) {
      setError("Cancellation failed.");
    }
  }

  return (
    <div className="space-y-10 max-w-7xl mx-auto">
      <PageIntro 
        eyebrow="Marketplace Command"
        title={`Welcome, ${user?.name?.split(' ')[0] || "Partner"}`}
        description="Monitor your active orders, manage your procurement drafts, and discover verified suppliers."
        actions={
          <button onClick={() => navigate("/app/products")} className="btn-primary flex items-center gap-2">
            Explore Marketplace
            <ArrowRight size={18} />
          </button>
        }
      />

      <StatCards items={statItems} />

      {error && <div className="p-4 bg-danger/10 text-danger rounded-2xl font-bold border border-danger/20">{error}</div>}
      {flash && <div className="p-4 bg-accent/10 text-accent rounded-2xl font-bold border border-accent/20">{flash}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Active Shipment Tracking */}
        <div className="lg:col-span-2 space-y-8">
          <article className="glass-card p-8 md:p-10 space-y-10 relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-10 opacity-5 group-hover:rotate-12 transition-transform duration-700">
              <Truck size={120} />
            </div>
            
            <div className="flex justify-between items-start relative z-10">
              <div className="space-y-1">
                <span className="text-[10px] font-black uppercase tracking-[0.2em] text-brand">Live Fulfillment Tracking</span>
                <h3 className="text-3xl font-display font-black text-text tracking-tight">Active Shipment</h3>
              </div>
              {currentOrder && (
                <span className={`px-4 py-2 rounded-full text-xs font-black uppercase tracking-widest ${statusColor(normalizeStatus(currentOrder.status))}`}>
                  {normalizeStatus(currentOrder.status)}
                </span>
              )}
            </div>

            {currentOrder ? (
              <div className="space-y-10 relative z-10">
                <div className="flex items-center gap-6">
                  <div className="w-20 h-20 rounded-[2rem] bg-surface-soft border border-border flex items-center justify-center text-brand shadow-sm">
                    <Package size={32} />
                  </div>
                  <div>
                    <h4 className="text-2xl font-display font-black text-text">{currentOrder.product}</h4>
                    <p className="text-sm font-bold text-text-muted">Dispatched by <span className="text-text">{currentOrder.provider_name || "Verified Merchant"}</span></p>
                  </div>
                </div>

                <div className="relative pt-4">
                  <div className="absolute top-6 left-0 w-full h-1.5 bg-surface-soft rounded-full" />
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: `${progressPercent(normalizeStatus(currentOrder.status))}%` }}
                    transition={{ duration: 1.5, ease: "easeOut" }}
                    className="absolute top-6 left-0 h-1.5 bg-brand rounded-full shadow-[0_0_15px_rgba(59,130,246,0.5)]"
                  />
                  <div className="relative flex justify-between">
                    {lifecycleSteps.map((step) => {
                      const currentIndex = lifecycleSteps.indexOf(normalizeStatus(currentOrder.status) as (typeof lifecycleSteps)[number]);
                      const done = currentIndex >= 0 && lifecycleSteps.indexOf(step) <= currentIndex;
                      return (
                        <div key={step} className="flex flex-col items-center gap-4">
                          <div className={`w-6 h-6 rounded-full border-4 border-surface shadow-md z-10 transition-colors duration-500 ${done ? 'bg-brand' : 'bg-surface-strong'}`} />
                          <span className={`text-[10px] font-black uppercase tracking-widest hidden sm:block ${done ? 'text-text' : 'text-text-muted/50'}`}>{step}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
                
                <div className="pt-6 flex flex-wrap gap-6 border-t border-border">
                  <div className="flex items-center gap-3">
                    <MapPin size={18} className="text-brand" />
                    <span className="text-sm font-bold text-text truncate max-w-[200px]">{currentOrder.delivery_address}</span>
                  </div>
                  <div className="ml-auto">
                    <Link to="/app/orders" className="text-xs font-black uppercase tracking-widest text-brand hover:text-brand-strong flex items-center gap-2">
                      View Full Timeline <ChevronRight size={14} />
                    </Link>
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-16 text-center space-y-4 opacity-40">
                <div className="w-16 h-16 bg-surface-soft rounded-full flex items-center justify-center mx-auto"><ShoppingBag size={32} /></div>
                <p className="font-bold">No active shipments to track</p>
              </div>
            )}
          </article>

          {/* Recent Activity Ledger */}
          <article className="glass-card overflow-hidden">
            <div className="p-8 border-b border-border flex flex-col md:flex-row justify-between items-center gap-6">
              <div>
                <h3 className="text-2xl font-display font-black text-text tracking-tight">Recent Orders</h3>
                <p className="text-sm font-medium text-text-muted">Your latest marketplace transactions.</p>
              </div>
              <div className="flex items-center gap-3 w-full md:w-auto">
                <div className="relative flex-1">
                  <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted" />
                  <input 
                    value={filterKeyword}
                    onChange={(e) => setFilterKeyword(e.target.value)}
                    placeholder="Search ledger..."
                    className="w-full pl-10 pr-4 py-2 bg-surface-soft rounded-xl outline-none font-bold text-xs"
                  />
                </div>
                <select 
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  className="bg-surface-soft border-none rounded-xl px-4 py-2 text-xs font-black uppercase tracking-widest outline-none cursor-pointer"
                >
                  {categories.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
            </div>

            <div className="divide-y divide-border">
              {filteredOrders.map((order) => {
                const status = normalizeStatus(order.status);
                const total = order.total || (Number(order.unit_price) * Number(order.quantity));
                return (
                  <div key={order.id} className="p-6 md:p-8 flex flex-col md:flex-row justify-between items-start md:items-center gap-6 hover:bg-surface-soft/30 transition-colors group">
                    <div className="flex gap-6">
                      <div className="w-14 h-14 rounded-2xl bg-surface-soft border border-border flex items-center justify-center text-text-muted font-black text-xs group-hover:bg-brand/10 group-hover:text-brand transition-all">
                        #{order.id.toString().slice(-3)}
                      </div>
                      <div className="min-w-0">
                        <h4 className="text-lg font-display font-black text-text truncate group-hover:text-brand transition-colors">{order.product}</h4>
                        <p className="text-xs font-bold text-text-muted mt-1">{order.provider_name} • {new Date(order.order_date || '').toLocaleDateString()}</p>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-4 w-full md:w-auto">
                      <div className="text-right mr-4">
                        <span className="text-[9px] font-black uppercase tracking-widest text-text-muted block">Amount</span>
                        <span className="font-display font-black text-lg text-text">{formatMoney(total)}</span>
                      </div>
                      <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest ${statusColor(status)}`}>
                        {status}
                      </span>
                      <div className="flex items-center gap-2">
                        {status === 'Confirmed' && (
                          <button 
                            onClick={() => navigate(`/app/payments?order_id=${order.id}&amount=${total}`)}
                            className="px-4 py-2 bg-brand text-white text-[10px] font-black uppercase tracking-widest rounded-xl shadow-lg shadow-brand/20 hover:bg-brand-strong transition-all"
                          >
                            Pay Now
                          </button>
                        )}
                        {["Pending", "Confirmed"].includes(status) && (
                          <button onClick={() => void handleCancel(order.id)} className="p-2 text-text-muted hover:text-danger transition-colors">
                            <X size={18} />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
              {filteredOrders.length === 0 && (
                <div className="p-16 text-center text-text-muted font-bold">No transactions found.</div>
              )}
            </div>
            <div className="p-6 bg-surface-soft/30 text-center border-t border-border">
              <Link to="/app/orders" className="text-xs font-black uppercase tracking-widest text-brand hover:text-brand-strong transition-colors">View Full Order History</Link>
            </div>
          </article>
        </div>

        {/* Intelligence Sidebar */}
        <aside className="space-y-8">
          <article className="glass-card p-8 bg-dark-bg text-white border-none shadow-2xl relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-6 opacity-10 group-hover:scale-110 transition-transform duration-700">
              <ShieldCheck size={80} />
            </div>
            <div className="relative z-10 space-y-8">
              <div className="space-y-2">
                <span className="text-[10px] font-black uppercase tracking-[0.2em] text-white/40">Network Insights</span>
                <h3 className="text-2xl font-display font-black tracking-tight">Trust Summary</h3>
                <p className="text-white/60 text-sm font-medium leading-relaxed">Verified account standing and procurement metrics.</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-md">
                  <span className="text-[9px] font-black uppercase tracking-widest text-white/40">Success Rate</span>
                  <strong className="mt-2 block text-2xl font-display font-black">98.2%</strong>
                </div>
                <div className="p-4 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-md">
                  <span className="text-[9px] font-black uppercase tracking-widest text-white/40">Pro Points</span>
                  <strong className="mt-2 block text-2xl font-display font-black">2.4k</strong>
                </div>
              </div>

              <div className="space-y-3">
                <button onClick={() => navigate("/app/payments")} className="w-full h-14 bg-brand text-white font-black text-xs uppercase tracking-widest rounded-2xl flex items-center justify-center gap-3 hover:bg-brand-strong transition-all shadow-xl shadow-brand/20">
                  <CreditCard size={18} />
                  Settlement Hub
                </button>
                <button onClick={() => navigate("/app/profile")} className="w-full h-14 bg-white/5 text-white font-black text-xs uppercase tracking-widest rounded-2xl flex items-center justify-center hover:bg-white/10 transition-all border border-white/10">
                  Profile Settings
                </button>
              </div>
            </div>
          </article>

          <article className="glass-card p-8 space-y-8">
            <div className="space-y-1">
              <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">Procurement Engine</span>
              <h3 className="text-xl font-display font-black text-text tracking-tight">Smart Discovery</h3>
            </div>

            <div className="space-y-4">
              {[
                { label: "Verified Electronics", detail: "Browse 24 verified suppliers", to: "/app/products?category=Electronics" },
                { label: "Solar Energy Hub", detail: "New bulk deals available", to: "/app/products?category=Energy" },
                { label: "Top Rated Sellers", detail: "Performance-based selection", to: "/app/products?sort=rating" }
              ].map((item, i) => (
                <Link key={i} to={item.to} className="block p-5 rounded-[1.75rem] bg-surface-soft border border-transparent hover:border-brand/30 hover:bg-white transition-all group">
                  <div className="flex justify-between items-center mb-1">
                    <strong className="text-sm font-black text-text group-hover:text-brand transition-colors">{item.label}</strong>
                    <ArrowRight size={14} className="text-text-muted opacity-0 group-hover:opacity-100 transition-all -translate-x-2 group-hover:translate-x-0" />
                  </div>
                  <p className="text-[10px] font-bold text-text-muted uppercase tracking-wider">{item.detail}</p>
                </Link>
              ))}
            </div>

            <button onClick={() => navigate("/app/products")} className="w-full py-4 border-2 border-dashed border-border rounded-[1.75rem] text-[10px] font-black uppercase tracking-widest text-text-muted hover:border-brand/40 hover:text-brand transition-all">
              Explore All Categories
            </button>
          </article>
        </aside>
      </div>
    </div>
  );
}
