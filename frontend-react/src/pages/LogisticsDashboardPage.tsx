import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Truck, 
  MapPin, 
  CheckCircle2, 
  X, 
  MessageSquare, 
  Navigation, 
  Star, 
  ChevronRight, 
  ShieldCheck, 
  Activity,
  User as UserIcon,
  Phone,
  Package,
  ArrowRight,
  Clock
} from "lucide-react";
import { useAuth } from "../features/auth/AuthContext";
import { getStoredToken } from "../features/auth/authStorage";
import { PageIntro, StatCards, SectionCard } from "../components/ui/PageSections";
import { env } from "../config/env";
import { apiRequest } from "../lib/http";
import type { LogisticsDelivery } from "../types/domain";
import { useDeliverySocket } from "../features/logistics/useDeliverySocket";
import { LiveTrackingMap } from "../features/logistics/LiveTrackingMap";
import { DeliveryChat } from "../features/logistics/DeliveryChat";

interface LogisticsProfile {
  id: number;
  role?: string;
  name?: string;
  phone?: string;
  email?: string | null;
  account_type?: string;
  vehicle_type?: string | null;
  plate_number?: string | null;
  license_number?: string | null;
  base_area?: string | null;
  coverage_areas?: string | null;
  status?: string;
  availability?: string;
  profile_photo?: string | null;
  verification_status?: string;
  metrics?: {
    rating?: number;
    total_deliveries?: number;
    success_rate?: number;
    cancel_rate?: number;
  };
}

function formatMoney(value?: number | null) {
  return `TZS ${Number(value || 0).toLocaleString()}`;
}

function resolveImageUrl(url?: string | null) {
  const raw = String(url || "").trim();
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith("data:")) return raw;
  if (raw.startsWith("/")) return `${env.apiBase}${raw}`;
  return `${env.apiBase}/${raw.replace(/^\/+/, "")}`;
}

function ActiveDeliveryManager({ delivery, currentUserId, onStatusUpdate }: { delivery: LogisticsDelivery, currentUserId: number | undefined, onStatusUpdate: () => void }) {
  const token = getStoredToken();
  const { messages, sendChat, sendLocation, sendTyping, isConnected, isOtherPartyTyping } = useDeliverySocket(delivery.order_id as number, token);
  const [showChat, setShowChat] = useState(false);
  const [etaCountdown, setEtaCountdown] = useState(() => {
    // Estimate ETA based on distance: ~2.5 min per km, min 12 minutes
    const km = delivery.estimated_distance_km || 10;
    return Math.max(12, Math.round(km * 2.5));
  });

  useEffect(() => {
    if (delivery.status !== "in_transit") return;
    const timer = setInterval(() => {
      setEtaCountdown(prev => Math.max(0, prev - 1));
    }, 60000); // decrement every minute
    return () => clearInterval(timer);
  }, [delivery.status]);

  useEffect(() => {
    if (delivery.status !== "in_transit" || !isConnected) return;
    const watchId = navigator.geolocation.watchPosition(
      (pos) => sendLocation(pos.coords.latitude, pos.coords.longitude),
      (err) => console.warn("GPS tracking error:", err),
      { enableHighAccuracy: true }
    );
    return () => navigator.geolocation.clearWatch(watchId);
  }, [delivery.status, isConnected, sendLocation]);

  const pickupCoords: [number, number] | null = delivery.pickup_lat && delivery.pickup_lng ? [delivery.pickup_lat, delivery.pickup_lng] : null;
  const destCoords: [number, number] | null = delivery.destination_lat && delivery.destination_lng ? [delivery.destination_lat, delivery.destination_lng] : null;
  const currentCoords: [number, number] | null = delivery.current_lat && delivery.current_lng ? [delivery.current_lat, delivery.current_lng] : null;

  return (
    <article className="glass-card overflow-hidden border-brand/20 shadow-xl">
      <div className="p-6 bg-brand-strong text-white flex justify-between items-center">
        <div>
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-white/50">Active Operation</span>
          <h3 className="text-xl font-display font-black tracking-tight">Deployment #{delivery.order_id}</h3>
        </div>
        <div className="flex items-center gap-3">
          {delivery.status === "in_transit" && etaCountdown > 0 && (
            <div className="flex items-center gap-2 rounded-full bg-amber-500/20 px-3 py-1.5 text-amber-100 text-sm font-bold border border-amber-400/50">
              <Clock size={14} />
              ETA: {etaCountdown}m
            </div>
          )}
          <button 
            onClick={() => setShowChat(!showChat)}
            className="h-10 px-5 bg-white/10 hover:bg-white/20 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all flex items-center gap-2 border border-white/10"
          >
            <MessageSquare size={14} />
            {showChat ? 'Close Comms' : 'Sync Buyer'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-px bg-border">
        <div className="bg-surface p-8 space-y-8">
          <div className="grid grid-cols-2 gap-8">
            <div className="space-y-1.5">
              <span className="text-[9px] font-black uppercase tracking-[0.2em] text-text-muted">Origin Node</span>
              <p className="text-sm font-bold text-text leading-tight">{delivery.pickup_location}</p>
            </div>
            <div className="space-y-1.5">
              <span className="text-[9px] font-black uppercase tracking-[0.2em] text-text-muted">Target Node</span>
              <p className="text-sm font-bold text-text leading-tight">{delivery.delivery_location}</p>
            </div>
          </div>

          <div className="pt-6 flex flex-col gap-3 border-t border-border">
             {delivery.status === "assigned" && (
                <button onClick={() => onStatusUpdate()} className="btn-primary w-full !h-14">Confirm Pickup Protocol</button>
             )}
             {delivery.status === "picked_up" && (
                <button onClick={() => onStatusUpdate()} className="btn-primary w-full !h-14 !bg-orange-500 hover:!bg-orange-600">Initiate Transit</button>
             )}
             {delivery.status === "in_transit" && (
                <button onClick={() => onStatusUpdate()} className="btn-primary w-full !h-14 !bg-emerald-600 hover:!bg-emerald-700">Verify Final Receipt</button>
             )}
          </div>
        </div>

        <div className="bg-surface-soft min-h-[300px]">
          {showChat ? (
            <DeliveryChat 
              messages={messages} 
              onSend={sendChat} 
              onTyping={sendTyping}
              currentUserId={currentUserId} 
              otherPartyName="Buyer" 
              isConnected={isConnected}
              isOtherPartyTyping={isOtherPartyTyping}
            />
          ) : (
            <LiveTrackingMap 
              currentLocation={currentCoords}
              destination={destCoords}
              pickup={pickupCoords}
            />
          )}
        </div>
      </div>
    </article>
  );
}

export function LogisticsDashboardPage() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<LogisticsProfile | null>(null);
  const [deliveries, setDeliveries] = useState<LogisticsDelivery[]>([]);
  const [statusFilter, setStatusFilter] = useState("all");
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");
  const [loading, setLoading] = useState(false);
  const [showProofModal, setShowProofModal] = useState(false);
  const [selectedProofDelivery, setSelectedProofDelivery] = useState<LogisticsDelivery | null>(null);

  const metrics = profile?.metrics || {};
  const deliverySummary = useMemo(() => {
    const assigned = deliveries.filter((item) => item.status === "assigned").length;
    const inTransit = deliveries.filter((item) => item.status === "picked_up" || item.status === "in_transit").length;
    const completed = deliveries.filter((item) => item.status === "delivered").length;
    const failed = deliveries.filter((item) => item.status === "failed").length;
    return { assigned, inTransit, completed, failed };
  }, [deliveries]);
  
  const visibleDeliveries = useMemo(() => {
    if (statusFilter === "all") return deliveries;
    return deliveries.filter((item) => item.status === statusFilter);
  }, [deliveries, statusFilter]);

  const activeDelivery = deliveries.find(d => ["assigned", "picked_up", "in_transit"].includes(d.status));

  // Helper functions
  function isStaleAssignment(created_at?: string | null): boolean {
    if (!created_at) return false;
    const created = new Date(created_at).getTime();
    const hours = (Date.now() - created) / (1000 * 60 * 60);
    return hours > 2; // stale if assigned > 2 hours
  }

  // Multi-drop route optimization for assigned deliveries
  const routeOptimization = useMemo((): { deliveries: LogisticsDelivery[]; totalDistance: number; stops: number } | null => {
    const assigned = deliveries.filter(d => d.status === "assigned");
    if (assigned.length <= 1) return null;

    function haversineDist(p1: [number, number] | null, p2: [number, number] | null): number {
      if (!p1 || !p2) return Infinity;
      const R = 6371;
      const toRad = (deg: number) => deg * Math.PI / 180;
      const lat1 = toRad(p1[0]), lon1 = toRad(p1[1]);
      const lat2 = toRad(p2[0]), lon2 = toRad(p2[1]);
      const dLat = lat2 - lat1, dLon = lon2 - lon1;
      const a = Math.sin(dLat/2)**2 + Math.cos(lat1)*Math.cos(lat2)*Math.sin(dLon/2)**2;
      const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
      return R * c;
    }

    type DeliveryWithScore = { delivery: LogisticsDelivery; score: number };
    const withScores = assigned.map(d => {
      const pickup: [number, number] | null = (d.pickup_lat != null && d.pickup_lng != null) ? [d.pickup_lat, d.pickup_lng] as [number, number] : null;
      const dest: [number, number] | null = (d.destination_lat != null && d.destination_lng != null) ? [d.destination_lat, d.destination_lng] as [number, number] : null;
      const direct = pickup && dest ? haversineDist(pickup, dest) : 50;
      const score = (pickup ? 0 : 50) + (dest ? 0 : 50) + direct;
      return { delivery: d, score };
    });

    withScores.sort((a, b) => a.score - b.score);

    let total = 0;
    const sorted: LogisticsDelivery[] = [];
    for (let i = 0; i < withScores.length; i++) {
      sorted.push(withScores[i].delivery);
      if (i > 0) {
        const prev = sorted[i-1];
        const prevDest: [number, number] | null = prev.destination_lat != null && prev.destination_lng != null 
          ? [prev.destination_lat, prev.destination_lng] as [number, number]
          : (prev.pickup_lat != null && prev.pickup_lng != null ? [prev.pickup_lat, prev.pickup_lng] as [number, number] : null);
        const nextPick: [number, number] | null = withScores[i].delivery.pickup_lat != null && withScores[i].delivery.pickup_lng != null 
          ? [withScores[i].delivery.pickup_lat, withScores[i].delivery.pickup_lng] as [number, number]
          : null;
        if (prevDest && nextPick) total += haversineDist(prevDest, nextPick);
      }
      total += withScores[i].score;
    }

    return { deliveries: sorted, totalDistance: Math.round(total * 10) / 10, stops: sorted.length };
  }, [deliveries]);

  const statItems = useMemo(
    () => [
      { id: "id", label: "Fleet Identity", value: `#L${profile?.id || '—'}`, icon: <Truck size={18} />, note: profile?.account_type || "Agent" },
      { id: "status", label: "Protocol State", value: profile?.status || "Offline", icon: <Activity size={18} />, note: profile?.availability || "Status" },
      { id: "assigned", label: "Active Jobs", value: deliverySummary.assigned, icon: <Package size={18} /> },
      { id: "failed", label: "Delivery Failed", value: deliverySummary.failed, icon: <X size={18} />, note: "Needs reattempt or review" },
      { id: "rating", label: "Trust Rating", value: Number(metrics.rating || 0).toFixed(1), icon: <Star size={18} /> },
    ],
    [profile, deliverySummary.assigned, deliverySummary.failed, metrics.rating]
  );

  useEffect(() => {
    if (user?.role === "logistics") void load();
  }, [user?.role]);

  async function load() {
    setLoading(true);
    try {
      const [profileData, deliveriesData] = await Promise.all([
        apiRequest<LogisticsProfile>("/logistics/me"),
        apiRequest<{ deliveries: LogisticsDelivery[] }>("/logistics/deliveries"),
      ]);
      setProfile(profileData);
      setDeliveries(deliveriesData.deliveries || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "System sync failed");
    } finally {
      setLoading(false);
    }
  }

  async function updateAvailability(type: "status" | "availability", value: string) {
    try {
      await apiRequest(`/logistics/${type}`, { method: "PUT", body: { [type]: value } });
      setFlash(`${type} successfully synchronized.`);
      await load();
    } catch (err) {
      setError("Protocol update failed.");
    }
  }

  async function updateDelivery(id: number, status: string) {
    const verification = status === "delivered" ? window.prompt("Enter verification code (Check with Buyer)") || "" : "";
    try {
      await apiRequest(`/logistics/deliveries/${id}/status`, {
        method: "PUT",
        body: { status, verification_code: verification || undefined },
      });
      setFlash(`Job updated to ${status}.`);
      await load();
    } catch (err) {
      setError("Fulfillment update failed.");
    }
  }

  if (loading) return (
    <div className="h-96 flex flex-col items-center justify-center gap-6">
      <div className="w-16 h-16 border-4 border-brand/10 border-t-brand rounded-full animate-spin" />
      <p className="font-black text-[10px] uppercase tracking-[0.3em] text-text-muted animate-pulse">Syncing Fulfillment Node...</p>
    </div>
  );

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      <PageIntro 
        eyebrow="Logistics Mesh"
        title="Agent Command Center"
        description="Monitor assignments, coordinate real-time delivery routes, and manage system availability across the network."
        actions={
          <button 
            onClick={() => updateAvailability("status", profile?.status === "online" ? "offline" : "online")}
            className={`h-12 px-8 rounded-xl font-black text-[10px] uppercase tracking-[0.2em] transition-all shadow-xl
              ${profile?.status === 'online' ? 'bg-emerald-500 text-white shadow-emerald-500/20' : 'bg-surface-strong text-text-muted hover:text-text'}
            `}
          >
            {profile?.status === 'online' ? '● Node Online' : '○ Go Online'}
          </button>
        }
      />

      <StatCards items={statItems} />

      {error && <div className="p-4 bg-danger/10 text-danger rounded-2xl font-bold border border-danger/20 text-xs animate-soft-enter">{error}</div>}
      {flash && <div className="p-4 bg-accent/10 text-accent rounded-2xl font-bold border border-accent/20 text-xs animate-soft-enter">{flash}</div>}

      {activeDelivery && (
        <section className="space-y-6">
          <div className="flex items-center gap-2 px-1">
            <div className="w-2 h-2 rounded-full bg-brand animate-ping" />
            <h2 className="text-[10px] font-black uppercase tracking-[0.3em] text-text">Critical Mission Active</h2>
          </div>
          <ActiveDeliveryManager 
            delivery={activeDelivery} 
            currentUserId={user?.id}
            onStatusUpdate={() => {
               const next = activeDelivery.status === "assigned" ? "picked_up" : 
                            activeDelivery.status === "picked_up" ? "in_transit" : "delivered";
               updateDelivery(activeDelivery.id, next);
            }}
          />
        </section>
      )}

      {/* Route optimization for multiple assigned deliveries */}
      {routeOptimization && (
        <section className="rounded-[2rem] border border-brand/20 bg-gradient-to-br from-brand/5 to-accent/5 p-5 shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="flex items-center gap-2 text-sm font-black uppercase tracking-[0.18em] text-slate-900">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-brand" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M12.395 2.553a1 1 0 00-1.45-.385c-.345.23-.614.558-.822.88-.214.33-.403.713-.57 1.116-.334.804-.614 1.768-.84 2.734a31.365 31.365 0 00-.613 3.58 2.64 2.64 0 01-.945-1.067c-.328-.68-.398-1.534-.398-2.654A1 1 0 005.05 6.05 6.981 6.981 0 003 11a7 7 0 1012.95-4.95c-.592-.591-.98-.985-1.348-1.467-.366-.485-.503-1.554-.503-2.549 0-1.014.393-1.871.943-2.626.095-.197.387-.396.79-.484l.003-.004c.196.094.396.199.603.317.206.118.427.238.662.358.237.12.488.238.753.357z" clipRule="evenodd" />
                </svg>
                Optimized delivery sequence
              </h3>
              <p className="mt-1 text-xs text-slate-600">
                Smart routing suggests visiting stops in this order to minimize distance
              </p>
            </div>
            <div className="text-right">
              <p className="text-2xl font-black text-brand">{routeOptimization.totalDistance} km</p>
              <p className="text-[10px] uppercase tracking-widest text-slate-500">total route distance</p>
            </div>
          </div>

          <div className="mt-4 space-y-2">
            {routeOptimization.deliveries.slice(0, -1).map((delivery, idx) => (
              <div key={delivery.id} className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white/70 px-4 py-3">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand text-xs font-bold text-white">
                  {idx + 1}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-slate-900">Order #{delivery.order_id || delivery.id}</p>
                  <p className="truncate text-xs text-slate-500">{delivery.delivery_location}</p>
                </div>
                <div className="flex items-center gap-1 text-slate-400">
                  <Navigation size={14} />
                  <span className="text-[10px] font-medium">{delivery.estimated_distance_km || '?'} km</span>
                </div>
              </div>
            ))}
            <div className="flex items-center gap-3 rounded-xl border-2 border-brand/30 bg-brand/10 px-4 py-3">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-bold text-white">
                {routeOptimization.stops}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-slate-900">Final stop — all delivered</p>
                <p className="truncate text-xs text-slate-500">Complete all above for full payment</p>
              </div>
            </div>
          </div>
        </section>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2">
          <SectionCard 
            title="Operational Ledger" 
            description="Historical log of fulfillment protocols."
            action={
              <select 
                value={statusFilter} 
                onChange={(e) => setStatusFilter(e.target.value)}
                className="px-4 py-2 bg-surface-soft border border-border rounded-xl outline-none font-bold text-[10px] uppercase tracking-widest cursor-pointer"
              >
                <option value="all">Full Ledger</option>
                <option value="delivered">Completed</option>
                <option value="failed">Delivery failed</option>
                <option value="assigned">Pending</option>
              </select>
            }
          >
            <div className="divide-y divide-border -mx-8 -mb-8">
              {!visibleDeliveries.length ? (
                <div className="p-12 text-center text-text-muted text-[10px] font-black uppercase tracking-[0.2em] opacity-40">No records synchronized.</div>
              ) : (
                visibleDeliveries.map((delivery) => (
                  <div key={delivery.id} className="p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-6 hover:bg-surface-soft/40 transition-colors group">
                    <div className="flex gap-5">
                      <div className="w-12 h-12 rounded-xl bg-brand/5 border border-brand/20 flex items-center justify-center text-brand font-black text-xs">
                        #{delivery.order_id}
                      </div>
                      <div className="space-y-1">
                        <h4 className="text-sm font-black text-text leading-none group-hover:text-brand transition-colors">Target: {delivery.delivery_location}</h4>
                        <p className="text-[10px] font-bold text-text-muted uppercase tracking-wider">From: {delivery.pickup_location}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className={`inline-block px-2 py-0.5 rounded-lg text-[9px] font-black uppercase tracking-tighter
                            ${delivery.status === 'delivered'
                              ? 'bg-emerald-500/10 text-emerald-500'
                              : delivery.status === 'failed'
                                ? 'bg-danger/10 text-danger'
                                : 'bg-brand/10 text-brand'}
                          `}>{delivery.status}</span>
                          {delivery.status === "assigned" && isStaleAssignment(delivery.created_at) && (
                            <span className="flex items-center gap-1 rounded-full bg-rose-100 px-2 py-1 text-[10px] font-bold text-rose-700 border border-rose-200">
                              <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
                                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                              </svg>
                              Reassignment likely
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex flex-col items-end">
                      <span className="text-[9px] font-black uppercase tracking-widest text-text-muted">Settlement</span>
                      <strong className="text-lg font-display font-black text-text">{formatMoney(delivery.price)}</strong>
                      {(delivery.status === "delivered" || delivery.status === "failed") && (delivery.proof_type || delivery.proof_note) && (
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedProofDelivery(delivery);
                            setShowProofModal(true);
                          }}
                          className="mt-2 rounded-full bg-brand/10 text-brand px-3 py-1 text-[10px] font-black uppercase tracking-wider border border-brand/20 hover:bg-brand/20 transition-colors"
                        >
                          View proof
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </SectionCard>
        </div>

        <aside className="space-y-8">
           <article className="glass-card p-8 flex flex-col items-center text-center space-y-6">
              <div className="w-24 h-24 rounded-[2.5rem] overflow-hidden border-4 border-surface shadow-2xl relative group bg-surface-soft">
                 {profile?.profile_photo ? (
                   <img src={resolveImageUrl(profile.profile_photo)} alt={profile.name} className="w-full h-full object-cover" />
                 ) : (
                   <div className="w-full h-full flex items-center justify-center text-brand font-black text-3xl">
                     {(profile?.name || "R")[0].toUpperCase()}
                   </div>
                 )}
              </div>
              <div>
                 <h3 className="text-xl font-display font-black text-text tracking-tight">{profile?.name}</h3>
                 <span className="inline-flex items-center gap-2 mt-2 px-3 py-1 bg-brand/10 text-brand rounded-lg text-[10px] font-black uppercase tracking-widest border border-brand/20">
                    <ShieldCheck size={12} />
                    Verified Node
                 </span>
              </div>

              <div className="w-full space-y-4 pt-6 border-t border-border">
                 {[
                   { label: 'Vehicle', val: profile?.vehicle_type || 'Fleet Default' },
                   { label: 'Asset ID', val: profile?.plate_number || 'Fleet-X' },
                   { label: 'Base Area', val: profile?.base_area || 'Central' }
                 ].map(item => (
                   <div key={item.label} className="flex justify-between items-center">
                      <span className="text-[9px] font-black uppercase tracking-widest text-text-muted">{item.label}</span>
                      <span className="text-xs font-black text-text">{item.val}</span>
                   </div>
                 ))}
              </div>

              <button className="w-full h-12 bg-dark-bg text-white text-[10px] font-black uppercase tracking-[0.2em] rounded-xl hover:bg-brand transition-all shadow-xl active:scale-95">
                Manage Profile
              </button>
           </article>

           <article className="glass-card p-8 bg-dark-bg text-white border-none relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-6 opacity-10 group-hover:scale-110 transition-transform duration-500">
                <Navigation size={60} />
              </div>
              <div className="relative space-y-6">
                 <div className="space-y-1">
                    <span className="text-[10px] font-black uppercase tracking-widest text-white/40">Telemetry Sync</span>
                    <h3 className="text-xl font-display font-black tracking-tight">System Integrity</h3>
                 </div>
                 <div className="p-4 bg-white/5 rounded-2xl border border-white/10 backdrop-blur-md space-y-4">
                    <div className="flex justify-between items-center">
                       <span className="text-[10px] font-bold text-white/50 uppercase tracking-widest">GPS Payload</span>
                       <span className="text-[10px] font-black text-emerald-400">NOMINAL</span>
                    </div>
                    <div className="flex justify-between items-center">
                       <span className="text-[10px] font-bold text-white/50 uppercase tracking-widest">Data Stream</span>
                       <span className="text-[10px] font-black text-emerald-400">ACTIVE</span>
                    </div>
                 </div>
              </div>
           </article>
        </aside>
      </div>

      {/* Proof of Delivery Modal */}
      {showProofModal && selectedProofDelivery && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm" onClick={() => setShowProofModal(false)}>
          <div className="w-full max-w-2xl rounded-[2rem] border border-slate-200 bg-white p-6 shadow-2xl dark:bg-slate-800" onClick={e => e.stopPropagation()}>
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-xl font-black tracking-tight text-slate-950 dark:text-white">
                  Proof of Delivery
                </h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  Order #{selectedProofDelivery.order_id || selectedProofDelivery.id}
                </p>
              </div>
              <button
                onClick={() => setShowProofModal(false)}
                className="rounded-full p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="mt-6 space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:bg-slate-900">
                  <p className="text-[11px] font-black uppercase tracking-[0.15em] text-slate-500">Proof type</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-white capitalize">
                    {selectedProofDelivery.proof_type || "Not recorded"}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:bg-slate-900">
                  <p className="text-[11px] font-black uppercase tracking-[0.15em] text-slate-500">Delivered at</p>
                  <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">
                    {selectedProofDelivery.delivered_at ? new Date(selectedProofDelivery.delivered_at).toLocaleString() : "N/A"}
                  </p>
                </div>
              </div>

              {(selectedProofDelivery.proof_note || selectedProofDelivery.delivery_notes || selectedProofDelivery.special_instructions) && (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:bg-slate-900">
                  <p className="text-[11px] font-black uppercase tracking-[0.15em] text-slate-500 mb-2">Notes</p>
                  <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-300">
                    {selectedProofDelivery.proof_note || selectedProofDelivery.delivery_notes || selectedProofDelivery.special_instructions}
                  </p>
                </div>
              )}

              {selectedProofDelivery.failure_reason && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 dark:bg-rose-900/20">
                  <p className="text-[11px] font-black uppercase tracking-[0.15em] text-rose-600 mb-2">Issue reported</p>
                  <p className="text-sm font-semibold text-rose-700 dark:text-rose-400">
                    {selectedProofDelivery.failure_reason}
                  </p>
                </div>
              )}

              {selectedProofDelivery.cod_amount_received != null && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 dark:bg-emerald-900/20">
                  <p className="text-[11px] font-black uppercase tracking-[0.15em] text-emerald-600 mb-2">Cash collected</p>
                  <p className="text-lg font-black text-emerald-700 dark:text-emerald-400">
                    TZS {Number(selectedProofDelivery.cod_amount_received).toLocaleString()}
                  </p>
                </div>
              )}
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setShowProofModal(false)}
                className="rounded-xl bg-slate-950 px-6 py-2.5 text-sm font-bold text-white shadow-md transition hover:bg-slate-800"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
