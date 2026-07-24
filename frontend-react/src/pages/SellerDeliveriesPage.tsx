import { useEffect, useMemo, useState } from "react";
import { apiRequest } from "../lib/http";
import type { LogisticsDelivery } from "../types/domain";

interface LogisticsOption {
  id: number;
  name: string;
  vehicle_type?: string | null;
  base_area?: string | null;
}

interface CommunicationItem {
  thread_id: string;
  order_id?: number | null;
  customer_id?: number | null;
  subject?: string | null;
  latest_message?: string | null;
  delivery_address?: string | null;
}

interface NotificationItem {
  type: string;
  title: string;
  message: string;
  created_at?: string | null;
}

function money(value?: number | null) {
  return `TZS ${Number(value || 0).toLocaleString()}`;
}

function deliveryStatusLabel(value?: string | null) {
  if (!value) return "Pending";
  return String(value).replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function deliveryStatusClass(status?: string | null) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "delivered") return "ok";
  if (normalized === "failed") return "danger";
  if (["assigned", "picked_up", "in_transit"].includes(normalized)) return "warn";
  if (normalized === "cancelled") return "danger";
  return "warn";
}

export function SellerDeliveriesPage() {
  const [deliveries, setDeliveries] = useState<LogisticsDelivery[]>([]);
  const [communication, setCommunication] = useState<CommunicationItem[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [logistics, setLogistics] = useState<LogisticsOption[]>([]);
  const [instructions, setInstructions] = useState<Record<number, string>>({});
  const [destinations, setDestinations] = useState<Record<number, string>>({});
  const [selectedLogistics, setSelectedLogistics] = useState<Record<number, string>>({});
  const [statusFilter, setStatusFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setLoading(true);
    setError("");
    setFlash("");
    try {
      const [deliveryData, communicationData, notificationData] = await Promise.all([
        apiRequest<{ items: LogisticsDelivery[] }>("/business/deliveries"),
        apiRequest<{ items: CommunicationItem[] }>("/business/communication/feed"),
        apiRequest<{ items: NotificationItem[] }>("/business/notifications"),
      ]);
      setDeliveries(deliveryData.items || []);
      setCommunication(communicationData.items || []);
      setNotifications(notificationData.items || []);

      const nextInstructions: Record<number, string> = {};
      const nextDestinations: Record<number, string> = {};
      for (const item of deliveryData.items || []) {
        nextInstructions[item.id] = String(item.special_instructions || "");
        nextDestinations[item.id] = String(item.delivery_location || "");
      }
      setInstructions(nextInstructions);
      setDestinations(nextDestinations);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load seller deliveries");
    } finally {
      setLoading(false);
    }

    try {
      const logisticsData = await apiRequest<{ items: LogisticsOption[] }>("/logistics/available", { auth: false });
      setLogistics(logisticsData.items || []);
    } catch {
      setLogistics([]);
    }
  }

  const visibleDeliveries = useMemo(() => {
    if (statusFilter === "all") return deliveries;
    return deliveries.filter((item) => item.status === statusFilter);
  }, [deliveries, statusFilter]);

  const summary = useMemo(() => {
    const ongoing = deliveries.filter((item) => ["assigned", "picked_up", "in_transit"].includes(String(item.status || ""))).length;
    const completed = deliveries.filter((item) => item.status === "delivered").length;
    const failed = deliveries.filter((item) => item.status === "failed").length;
    const cancelled = deliveries.filter((item) => item.status === "cancelled").length;
    return {
      total: deliveries.length,
      ongoing,
      completed,
      failed,
      cancelled,
    };
  }, [deliveries]);

  async function saveInstructions(deliveryId: number) {
    setError("");
    setFlash("");
    try {
      await apiRequest(`/business/deliveries/${deliveryId}/instructions`, {
        method: "PATCH",
        body: {
          special_instructions: instructions[deliveryId] || null,
          delivery_location: destinations[deliveryId] || null,
        },
      });
      setFlash(`Delivery #${deliveryId} instructions updated.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update delivery instructions");
    }
  }

  async function reassignDelivery(delivery: LogisticsDelivery) {
    const logisticsId = Number(selectedLogistics[delivery.id] || 0);
    if (!delivery.order_id || !logisticsId) {
      setError("Select a logistics partner before reassigning.");
      return;
    }
    setError("");
    setFlash("");
    try {
      await apiRequest(`/business/orders/${delivery.order_id}/assign-delivery`, {
        method: "POST",
        body: {
          logistics_id: logisticsId,
          delivery_location: destinations[delivery.id] || delivery.delivery_location,
          special_instructions: instructions[delivery.id] || delivery.special_instructions || null,
        },
      });
      setFlash(`Delivery for order #${delivery.order_id} reassigned successfully.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reassign delivery");
    }
  }

  return (
    <div className="space-y-6 animate-soft-enter">
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-brand mb-2">Seller deliveries</p>
        <h1 className="text-2xl font-display font-bold text-slate-900 dark:text-white">Delivery coordination and customer communication</h1>
        <p className="text-slate-500 dark:text-slate-400 mt-2">
          Track assigned deliveries, update destination instructions, and keep customer order conversations visible from one page.
        </p>
      </div>

      {error ? <div className="p-4 bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded-xl font-bold flex items-center gap-3 border border-red-100 dark:border-red-800">{error}</div> : null}
      {flash ? <div className="p-4 bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 rounded-xl font-bold flex items-center gap-3 border border-emerald-100 dark:border-emerald-800">{flash}</div> : null}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <article className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 p-6 space-y-1">
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Total deliveries</span>
          <strong className="text-2xl font-display font-black text-slate-900 dark:text-white">{summary.total}</strong>
          <p className="text-sm text-slate-500 dark:text-slate-400">All time</p>
        </article>
        <article className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 p-6 space-y-1">
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Ongoing</span>
          <strong className="text-2xl font-display font-black text-brand">{summary.ongoing}</strong>
          <p className="text-sm text-slate-500 dark:text-slate-400">In progress</p>
        </article>
        <article className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 p-6 space-y-1">
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Delivered</span>
          <strong className="text-2xl font-display font-black text-slate-900 dark:text-white">{summary.completed}</strong>
          <p className="text-sm text-slate-500 dark:text-slate-400">Successful</p>
        </article>
        <article className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 p-6 space-y-1">
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Delivery failed</span>
          <strong className="text-2xl font-display font-black text-red-600">{summary.failed}</strong>
          <p className="text-sm text-slate-500 dark:text-slate-400">Needs reattempt or review</p>
        </article>
        <article className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 p-6 space-y-1">
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Cancelled</span>
          <strong className="text-2xl font-display font-black text-red-600">{summary.cancelled}</strong>
          <p className="text-sm text-slate-500 dark:text-slate-400">Closed without fulfillment</p>
        </article>
      </div>

      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
        <label className="block space-y-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Delivery status</span>
          <select
            className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="all">All statuses</option>
            <option value="assigned">Assigned</option>
            <option value="picked_up">Picked up</option>
            <option value="in_transit">In transit</option>
            <option value="delivered">Delivered</option>
            <option value="failed">Delivery failed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </label>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {loading ? (
          <article className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
            <p className="text-slate-500 dark:text-slate-400">Loading deliveries...</p>
          </article>
        ) : null}
        {!loading && !visibleDeliveries.length ? (
          <article className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
            <p className="text-slate-500 dark:text-slate-400">No deliveries found.</p>
          </article>
        ) : null}
        {visibleDeliveries.map((delivery) => (
          <article key={delivery.id} className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
            <div className="p-6 flex justify-between items-start border-b border-slate-100 dark:border-slate-700">
              <div>
                <strong className="text-slate-900 dark:text-white">Order #{delivery.order_id || "-"}</strong>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{delivery.delivery_address || delivery.pickup_location || "Delivery route"}</p>
              </div>
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                deliveryStatusClass(delivery.status) === "ok" ? "bg-green-100 text-green-800" :
                deliveryStatusClass(delivery.status) === "warn" ? "bg-yellow-100 text-yellow-800" :
                "bg-red-100 text-red-800"
              }`}>
                {deliveryStatusLabel(delivery.status)}
              </span>
            </div>

            <div className="p-6 grid grid-cols-3 gap-4 border-b border-slate-100 dark:border-slate-700">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Pickup</p>
                <strong className="text-sm text-slate-900 dark:text-white">{delivery.pickup_location || "Not specified"}</strong>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Destination</p>
                <strong className="text-sm text-slate-900 dark:text-white">{destinations[delivery.id] || delivery.delivery_location || "Not specified"}</strong>
              </div>
              <div>
                <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Price</p>
                <strong className="text-sm text-slate-900 dark:text-white">{money(delivery.price)}</strong>
              </div>
            </div>

            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Logistics partner</span>
                <select
                  className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand"
                  value={selectedLogistics[delivery.id] || ""}
                  onChange={(event) =>
                    setSelectedLogistics((prev) => ({ ...prev, [delivery.id]: event.target.value }))
                  }
                >
                  <option value="">Choose logistics</option>
                  {logistics.map((agent) => (
                    <option key={agent.id} value={agent.id}>
                      {agent.name} {agent.vehicle_type ? `(${agent.vehicle_type})` : ""}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Delivery destination</span>
                <input
                  className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand"
                  value={destinations[delivery.id] || ""}
                  onChange={(event) =>
                    setDestinations((prev) => ({ ...prev, [delivery.id]: event.target.value }))
                  }
                  placeholder="Delivery destination"
                />
              </label>

              <label className="block md:col-span-2 space-y-2">
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Special instructions</span>
                <textarea
                  rows={3}
                  className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand"
                  value={instructions[delivery.id] || ""}
                  onChange={(event) =>
                    setInstructions((prev) => ({ ...prev, [delivery.id]: event.target.value }))
                  }
                  placeholder="Special handling notes"
                />
              </label>
            </div>

            <div className="p-6 flex gap-3 border-t border-slate-100 dark:border-slate-700">
              <button className="px-4 py-2 bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-300 dark:hover:bg-slate-600 transition-colors text-sm font-medium" type="button" onClick={() => saveInstructions(delivery.id)}>
                Save updates
              </button>
              <button className="px-4 py-2 bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-300 dark:hover:bg-slate-600 transition-colors text-sm font-medium" type="button" onClick={() => reassignDelivery(delivery)}>
                Reassign delivery
              </button>
            </div>
          </article>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <article className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
          <div className="p-6 border-b border-slate-100 dark:border-slate-700 flex justify-between items-center">
            <h2 className="text-xl font-display font-bold text-slate-900 dark:text-white">Communication feed</h2>
            <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">{communication.length}</span>
          </div>
          <div className="divide-y divide-slate-100 dark:divide-slate-700">
            {!communication.length ? <p className="p-6 text-slate-500 dark:text-slate-400">No order conversations yet.</p> : null}
            {communication.map((thread) => (
              <div key={thread.thread_id} className="p-6 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
                <div>
                  <strong className="text-sm font-medium text-slate-900 dark:text-white">{thread.subject || `Order #${thread.order_id || "-"}`}</strong>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{thread.latest_message || "No message yet."}</p>
                </div>
                <span className="text-sm text-slate-500 dark:text-slate-400">{thread.delivery_address || "-"}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
          <div className="p-6 border-b border-slate-100 dark:border-slate-700 flex justify-between items-center">
            <h2 className="text-xl font-display font-bold text-slate-900 dark:text-white">Business notifications</h2>
            <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">{notifications.length}</span>
          </div>
          <div className="divide-y divide-slate-100 dark:divide-slate-700">
            {!notifications.length ? <p className="p-6 text-slate-500 dark:text-slate-400">No notifications yet.</p> : null}
            {notifications.map((item, index) => (
              <div key={`${item.type}-${index}`} className="p-6 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
                <div>
                  <strong className="text-sm font-medium text-slate-900 dark:text-white">{item.title}</strong>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{item.message}</p>
                </div>
                <span className="text-sm text-slate-500 dark:text-slate-400">{item.type}</span>
              </div>
            ))}
          </div>
        </article>
      </div>
    </div>
  );
}
