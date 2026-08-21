import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Filter,
  MessageSquare,
  Navigation,
  Package,
  Search,
  ShieldCheck,
  ShoppingBag,
  Truck,
  XCircle,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "../features/auth/AuthContext";
import { getStoredToken } from "../features/auth/authStorage";
import { useDeliverySocket } from "../features/logistics/useDeliverySocket";
import { DeliveryChat } from "../features/logistics/DeliveryChat";
import { LiveTrackingMap } from "../features/logistics/LiveTrackingMap";
import { apiRequest } from "../lib/http";
import { Modal } from "../components/Modal";
import { EmptyState, InlineNotice, PageIntro, SectionCard, StatCards } from "../components/ui/PageSections";
import type { Order, SellerLogisticsOption } from "../types/domain";

const SELLER_FLOW = [
  "Pending",
  "Confirmed",
  "Packed",
  "Ready For Shipping",
  "Shipped",
  "Delivery Failed",
  "Received",
  "Cancelled",
] as const;

type SellerOrderStage = typeof SELLER_FLOW[number];

function normalizeStatus(value?: string | null): SellerOrderStage {
  const status = String(value || "").trim().toLowerCase();
  if (status === "ready for shipping") return "Ready For Shipping";
  if (status.includes("delivery failed")) return "Delivery Failed";
  if (status.includes("cancel")) return "Cancelled";
  if (status.includes("receive") || status.includes("deliver")) return "Received";
  if (status.includes("ship")) return "Shipped";
  if (status.includes("pack")) return "Packed";
  if (status.includes("confirm")) return "Confirmed";
  return "Pending";
}


function nextStatus(status: SellerOrderStage): SellerOrderStage | null {
  const flow: Record<SellerOrderStage, SellerOrderStage | null> = {
    Pending: "Confirmed",
    Confirmed: "Packed",
    Packed: "Ready For Shipping",
    "Ready For Shipping": "Shipped",
    Shipped: null,
    "Delivery Failed": "Ready For Shipping",
    Received: null,
    Cancelled: null,
  };
  return flow[status];
}

function stageTone(stage: SellerOrderStage) {
  if (stage === "Received") return "bg-emerald-500/10 text-emerald-600 border-emerald-500/20";
  if (stage === "Cancelled") return "bg-danger/10 text-danger border-danger/20";
  if (stage === "Delivery Failed") return "bg-danger/10 text-danger border-danger/20";
  if (stage === "Shipped") return "bg-sky-500/10 text-sky-600 border-sky-500/20";
  if (stage === "Ready For Shipping") return "bg-indigo-500/10 text-indigo-600 border-indigo-500/20";
  if (stage === "Packed") return "bg-amber-500/10 text-amber-600 border-amber-500/20";
  if (stage === "Confirmed") return "bg-brand/10 text-brand border-brand/20";
  return "bg-slate-500/10 text-slate-600 border-slate-500/20";
}

function paymentTone(status?: string | null) {
  const normalized = String(status || "").trim().toLowerCase();
  if (normalized === "completed") return "success";
  if (normalized === "failed") return "error";
  if (normalized === "pending_delivery") return "warning";
  if (normalized === "pending") return "warning";
  return "info";
}

function paymentLabel(status?: string | null) {
  const normalized = String(status || "").trim().toLowerCase();
  if (normalized === "completed") return "Paid";
  if (normalized === "pending_delivery") return "Cash on Delivery";
  if (normalized === "pending") return "Payment Pending";
  if (normalized === "failed") return "Payment Failed";
  return "Not Started";
}

function priorityTone(priority?: string | null) {
  const normalized = String(priority || "").trim().toLowerCase();
  if (normalized === "urgent") return "bg-danger/10 text-danger border-danger/20";
  if (normalized === "delayed") return "bg-amber-500/10 text-amber-600 border-amber-500/20";
  return "bg-slate-500/10 text-slate-600 border-slate-500/20";
}

function formatMoney(value?: number | null) {
  return `TZS ${Number(value || 0).toLocaleString()}`;
}

function formatDate(value?: string | null) {
  if (!value) return "Unknown date";
  return new Date(value).toLocaleDateString();
}

function workflowNote(order: Order, stage: SellerOrderStage) {
  const payment = paymentLabel(order.payment_status);
  if (stage === "Pending") return `Review items, stock, address, and ${payment.toLowerCase()}.`;
  if (stage === "Confirmed") return "Accepted and ready for fulfillment handling.";
  if (stage === "Packed") return "Items are prepared. Next step is shipping readiness.";
  if (stage === "Ready For Shipping") return "Assign logistics and handoff the parcel.";
  if (stage === "Shipped") return order.logistics_name ? `In motion with ${order.logistics_name}.` : "Delivery is underway.";
  if (stage === "Delivery Failed") return order.status_reason || "Delivery hit an exception and needs reattempt or review.";
  if (stage === "Received") return "Customer confirmed the order lifecycle is complete.";
  return order.status_reason || "This order was cancelled and may need review.";
}

function SellerOrdersBoard() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const token = getStoredToken();

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<SellerOrderStage | "All">("All");
  const [priorityFilter, setPriorityFilter] = useState<"All" | "urgent" | "delayed" | "normal">("All");
  const [reason, setReason] = useState("");
  const [selectedLogisticsId, setSelectedLogisticsId] = useState("");
  const [shippingDestination, setShippingDestination] = useState("");
  const [shippingInstructions, setShippingInstructions] = useState("");
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [isMapOpen, setIsMapOpen] = useState(false);

  const { data: orders = [], isLoading, error } = useQuery({
    queryKey: ["seller-orders"],
    queryFn: async () => {
      const response = await apiRequest<{ items: Order[] }>("/business/orders");
      return response.items || [];
    },
    refetchInterval: 10000,
  });

  const { data: logisticsOptions = [] } = useQuery({
    queryKey: ["seller-logistics-options"],
    queryFn: async () => {
      const response = await apiRequest<{ items: SellerLogisticsOption[] }>("/business/logistics-options");
      return response.items || [];
    },
  });

  const filteredOrders = useMemo(() => {
    return orders.filter((order) => {
      const stage = normalizeStatus(order.status);
      const priority = String(order.priority || "normal").toLowerCase();
      const haystack = [
        order.product,
        order.category,
        order.customer_name,
        order.customer_phone,
        order.customer_email,
        order.delivery_address,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      if (statusFilter !== "All" && stage !== statusFilter) return false;
      if (priorityFilter !== "All" && priority !== priorityFilter) return false;
      if (search.trim() && !haystack.includes(search.trim().toLowerCase())) return false;
      return true;
    });
  }, [orders, priorityFilter, search, statusFilter]);

  const groupedOrders = useMemo(() => {
    const initial: Record<SellerOrderStage, Order[]> = {
      Pending: [],
      Confirmed: [],
      Packed: [],
      "Ready For Shipping": [],
      Shipped: [],
      "Delivery Failed": [],
      Received: [],
      Cancelled: [],
    };
    for (const order of filteredOrders) {
      initial[normalizeStatus(order.status)].push(order);
    }
    return initial;
  }, [filteredOrders]);

  useEffect(() => {
    if (!filteredOrders.length) {
      setSelectedId(null);
      return;
    }
    if (!selectedId || !filteredOrders.some((order) => order.id === selectedId)) {
      setSelectedId(filteredOrders[0].id);
    }
  }, [filteredOrders, selectedId]);

  const activeOrder = useMemo(
    () => filteredOrders.find((order) => order.id === selectedId) || filteredOrders[0] || null,
    [filteredOrders, selectedId],
  );

  useEffect(() => {
    if (!activeOrder) return;
    setShippingDestination(activeOrder.delivery_address || "");
    setShippingInstructions(activeOrder.delivery_notes || "");
    setSelectedLogisticsId(activeOrder.logistics_id ? String(activeOrder.logistics_id) : "");
    setReason(activeOrder.status_reason || "");
  }, [activeOrder?.id]);

  const {
    messages,
    sendChat,
    sendTyping,
    location: liveLoc,
    isConnected,
    isOtherPartyTyping,
  } = useDeliverySocket(
    activeOrder?.id,
    token,
    (statusUpdate) => {
      if (statusUpdate.order_id) {
        void queryClient.invalidateQueries({ queryKey: ["seller-orders"] });
        void queryClient.invalidateQueries({ queryKey: ["seller-logistics-options"] });
      }
    },
  );

  const acceptRejectMutation = useMutation({
    mutationFn: async ({
      orderId,
      decision,
      nextReason,
    }: {
      orderId: number;
      decision: "accept" | "reject";
      nextReason?: string;
    }) =>
      apiRequest(`/business/orders/${orderId}/decision`, {
        method: "PATCH",
        body: { decision, reason: nextReason || undefined },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["seller-orders"] });
    },
  });

  const statusMutation = useMutation({
    mutationFn: async ({
      orderId,
      status,
      nextReason,
    }: {
      orderId: number;
      status: SellerOrderStage;
      nextReason?: string;
    }) =>
      apiRequest(`/business/orders/${orderId}/status`, {
        method: "PATCH",
        body: { status, reason: nextReason || undefined },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["seller-orders"] });
    },
  });

  const assignDeliveryMutation = useMutation({
    mutationFn: async (orderId: number) =>
      apiRequest(`/business/orders/${orderId}/assign-delivery`, {
        method: "POST",
        body: {
          logistics_id: selectedLogisticsId ? Number(selectedLogisticsId) : undefined,
          delivery_location: shippingDestination || undefined,
          special_instructions: shippingInstructions || undefined,
        },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["seller-orders"] });
      void queryClient.invalidateQueries({ queryKey: ["seller-logistics-options"] });
    },
  });

  const statItems = useMemo(() => {
    const pending = groupedOrders.Pending.length;
    const active = groupedOrders.Confirmed.length + groupedOrders.Packed.length + groupedOrders["Ready For Shipping"].length;
    const shipped = groupedOrders.Shipped.length;
    const completed = groupedOrders.Received.length;
    return [
      { id: "total", label: "Order Intake", value: orders.length, note: "Visible orders in pipeline", icon: <ShoppingBag size={18} /> },
      { id: "review", label: "Needs Review", value: pending, note: "Pending intake decisions", icon: <Clock size={18} /> },
      { id: "fulfillment", label: "In Fulfillment", value: active, note: "Accepted and being prepared", icon: <Package size={18} /> },
      { id: "shipping", label: "In Transit", value: shipped, note: "Currently with logistics", icon: <Truck size={18} /> },
      { id: "done", label: "Completed", value: completed, note: "Confirmed by customer", icon: <CheckCircle2 size={18} /> },
    ];
  }, [groupedOrders, orders.length]);

  const activeStage = normalizeStatus(activeOrder?.status);
  const primaryNextStatus = activeOrder ? nextStatus(activeStage) : null;
  const availableLogistics = logisticsOptions;

  return (
    <div className="space-y-8">
      <PageIntro
        eyebrow="Seller Order Control"
        title="Order Command Center"
        description="Review, accept, fulfill, ship, and resolve orders from one seller workflow. Each action here follows your real marketplace lifecycle."
        badges={
          <>
            <span className="rounded-full border border-brand/20 bg-brand/10 px-3 py-1 text-[10px] font-black uppercase tracking-widest text-brand">
              Live lifecycle
            </span>
            <span className="rounded-full border border-border bg-surface px-3 py-1 text-[10px] font-black uppercase tracking-widest text-text-muted">
              {user?.business_name || user?.owner_name || "Seller workspace"}
            </span>
          </>
        }
      />

      <StatCards items={statItems} />

      <SectionCard
        title="Order Intake"
        description="Search, filter, and prioritize new and active orders before you move them through fulfillment."
      >
        <div className="grid gap-4 lg:grid-cols-[2fr,1fr,1fr]">
          <label className="space-y-2">
            <span className="text-[11px] font-black uppercase tracking-widest text-text-muted">Search Orders</span>
            <div className="flex items-center gap-3 rounded-2xl border border-border bg-surface-soft px-4 py-3">
              <Search size={16} className="text-text-muted" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                className="w-full bg-transparent text-sm font-semibold text-text outline-none placeholder:text-text-muted"
                placeholder="Product, category, customer, address..."
              />
            </div>
          </label>

          <label className="space-y-2">
            <span className="text-[11px] font-black uppercase tracking-widest text-text-muted">Stage</span>
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as SellerOrderStage | "All")}
              className="h-[50px] w-full rounded-2xl border border-border bg-surface-soft px-4 text-sm font-semibold text-text outline-none"
            >
              <option value="All">All stages</option>
              {SELLER_FLOW.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-2">
            <span className="text-[11px] font-black uppercase tracking-widest text-text-muted">Priority</span>
            <select
              value={priorityFilter}
              onChange={(event) => setPriorityFilter(event.target.value as "All" | "urgent" | "delayed" | "normal")}
              className="h-[50px] w-full rounded-2xl border border-border bg-surface-soft px-4 text-sm font-semibold text-text outline-none"
            >
              <option value="All">All priorities</option>
              <option value="urgent">Urgent</option>
              <option value="delayed">Delayed</option>
              <option value="normal">Normal</option>
            </select>
          </label>
        </div>
      </SectionCard>

      {error ? <InlineNotice tone="error">{error instanceof Error ? error.message : "Failed to load seller orders."}</InlineNotice> : null}

      {isLoading ? (
        <SectionCard title="Loading Orders" description="Syncing your seller workflow and preparing lifecycle actions.">
          <div className="flex min-h-[280px] items-center justify-center">
            <div className="flex flex-col items-center gap-4">
              <div className="h-14 w-14 animate-spin rounded-full border-4 border-brand/10 border-t-brand" />
              <p className="text-[10px] font-black uppercase tracking-[0.3em] text-text-muted">Synchronizing orders</p>
            </div>
          </div>
        </SectionCard>
      ) : filteredOrders.length === 0 ? (
        <EmptyState
          title="No Orders Match These Filters"
          description="Try widening the stage or priority filters, or search by customer name, product, or delivery address."
          icon={<Filter size={32} />}
        />
      ) : (
        <div className="grid gap-8 xl:grid-cols-[1.4fr,0.95fr]">
          <SectionCard
            title="Lifecycle Pipeline"
            description="A kanban-style view helps sellers move orders clearly from review to completion."
          >
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5">
              {SELLER_FLOW.filter((stage) => stage !== "Received" && stage !== "Cancelled").map((stage) => (
                <div key={stage} className="rounded-[1.75rem] border border-border bg-surface-soft/35 p-4">
                  <div className="mb-4 flex items-center justify-between">
                    <span className={`rounded-full border px-3 py-1 text-[10px] font-black uppercase tracking-widest ${stageTone(stage)}`}>
                      {stage}
                    </span>
                    <span className="text-xs font-black text-text-muted">{groupedOrders[stage].length}</span>
                  </div>

                  <div className="space-y-3">
                    {groupedOrders[stage].length ? (
                      groupedOrders[stage].map((order) => (
                        <button
                          key={order.id}
                          onClick={() => setSelectedId(order.id)}
                          className={`w-full rounded-[1.5rem] border p-4 text-left transition-all ${
                            activeOrder?.id === order.id
                              ? "border-brand bg-brand/6 shadow-premium"
                              : "border-border bg-surface hover:border-brand/30 hover:bg-brand/5"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-black text-text">{order.product || "Order item"}</p>
                              <p className="mt-1 text-[10px] font-black uppercase tracking-widest text-text-muted">
                                #{order.id} • {formatDate(order.order_date)}
                              </p>
                            </div>
                            <span className={`rounded-full border px-2 py-1 text-[9px] font-black uppercase tracking-widest ${priorityTone(order.priority)}`}>
                              {order.priority || "normal"}
                            </span>
                          </div>
                          <div className="mt-3 flex items-center justify-between text-xs font-bold text-text-muted">
                            <span>{order.customer_name || "Customer pending"}</span>
                            <span>{formatMoney(order.total)}</span>
                          </div>
                        </button>
                      ))
                    ) : (
                      <div className="rounded-[1.5rem] border border-dashed border-border px-4 py-6 text-center text-xs font-bold uppercase tracking-widest text-text-muted">
                        No orders
                      </div>
                    )}
                  </div>
                </div>
              ))}

              <div className="rounded-[1.75rem] border border-border bg-surface-soft/35 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <span className={`rounded-full border px-3 py-1 text-[10px] font-black uppercase tracking-widest ${stageTone("Received")}`}>
                    Closed
                  </span>
                  <span className="text-xs font-black text-text-muted">
                    {groupedOrders.Received.length + groupedOrders.Cancelled.length}
                  </span>
                </div>
                <div className="space-y-3">
                  {[...groupedOrders.Received, ...groupedOrders.Cancelled].slice(0, 8).map((order) => (
                    <button
                      key={order.id}
                      onClick={() => setSelectedId(order.id)}
                      className={`w-full rounded-[1.5rem] border p-4 text-left transition-all ${
                        activeOrder?.id === order.id
                          ? "border-brand bg-brand/6 shadow-premium"
                          : "border-border bg-surface hover:border-brand/30 hover:bg-brand/5"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="truncate text-sm font-black text-text">{order.product || "Order item"}</p>
                        <span className={`rounded-full border px-2 py-1 text-[9px] font-black uppercase tracking-widest ${stageTone(normalizeStatus(order.status))}`}>
                          {normalizeStatus(order.status)}
                        </span>
                      </div>
                      <p className="mt-2 text-[10px] font-black uppercase tracking-widest text-text-muted">
                        #{order.id} • {order.customer_name || "Customer"}
                      </p>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </SectionCard>

          <AnimatePresence mode="wait">
            {activeOrder ? (
              <motion.div key={activeOrder.id} initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -8 }}>
                <SectionCard
                  title={`Order #${activeOrder.id}`}
                  description={workflowNote(activeOrder, activeStage)}
                  action={
                    <div className="flex flex-wrap gap-2">
                      <span className={`rounded-full border px-3 py-2 text-[10px] font-black uppercase tracking-widest ${stageTone(activeStage)}`}>
                        {activeStage}
                      </span>
                      <span className={`rounded-full border px-3 py-2 text-[10px] font-black uppercase tracking-widest ${priorityTone(activeOrder.priority)}`}>
                        {activeOrder.priority || "normal"}
                      </span>
                    </div>
                  }
                >
                  <div className="space-y-6">
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="rounded-[1.5rem] border border-border bg-surface-soft/35 p-4">
                        <p className="text-[10px] font-black uppercase tracking-widest text-text-muted">Customer</p>
                        <p className="mt-2 text-lg font-black text-text">{activeOrder.customer_name || "Unknown customer"}</p>
                        <p className="mt-1 text-sm font-medium text-text-muted">{activeOrder.customer_phone || activeOrder.delivery_phone || "Phone not available"}</p>
                        <p className="text-sm font-medium text-text-muted">{activeOrder.customer_email || "Email not available"}</p>
                      </div>
                      <div className="rounded-[1.5rem] border border-border bg-surface-soft/35 p-4">
                        <p className="text-[10px] font-black uppercase tracking-widest text-text-muted">Order Value</p>
                        <p className="mt-2 text-lg font-black text-text">{formatMoney(activeOrder.total)}</p>
                        <p className="mt-1 text-sm font-medium text-text-muted">
                          {activeOrder.quantity || 0} units • {activeOrder.category || "Uncategorized"}
                        </p>
                        <p className="text-sm font-medium text-text-muted">{formatDate(activeOrder.order_date)}</p>
                      </div>
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="rounded-[1.5rem] border border-border bg-surface-soft/35 p-4">
                        <p className="text-[10px] font-black uppercase tracking-widest text-text-muted">Payment Check</p>
                        <div className="mt-3">
                          <InlineNotice tone={paymentTone(activeOrder.payment_status) as "info" | "success" | "warning" | "error"}>
                            {paymentLabel(activeOrder.payment_status)}
                          </InlineNotice>
                        </div>
                        <p className="mt-3 text-sm font-medium text-text-muted">
                          Method: {activeOrder.payment_method || "Not chosen yet"}
                        </p>
                        {activeOrder.payment_transaction_id ? (
                          <p className="text-sm font-medium text-text-muted">Txn: {activeOrder.payment_transaction_id}</p>
                        ) : null}
                      </div>
                      <div className="rounded-[1.5rem] border border-border bg-surface-soft/35 p-4">
                        <p className="text-[10px] font-black uppercase tracking-widest text-text-muted">Delivery Feasibility</p>
                        <p className="mt-2 text-sm font-semibold text-text">{activeOrder.delivery_address || "No delivery address on file"}</p>
                        <p className="mt-1 text-sm font-medium text-text-muted">
                          Method: {activeOrder.delivery_method || "Standard"}
                        </p>
                        {activeOrder.estimated_distance_km ? (
                          <p className="text-sm font-medium text-text-muted">Estimated distance: {activeOrder.estimated_distance_km} km</p>
                        ) : null}
                      </div>
                    </div>

                    {activeOrder.status_reason ? (
                      <InlineNotice tone={activeStage === "Cancelled" ? "warning" : "info"}>
                        Reason / note: {activeOrder.status_reason}
                      </InlineNotice>
                    ) : null}

                    <div className="rounded-[1.75rem] border border-border bg-surface-soft/35 p-5">
                      <div className="flex items-center gap-2">
                        <ShieldCheck size={18} className="text-brand" />
                        <h3 className="text-sm font-black uppercase tracking-widest text-text">Lifecycle Actions</h3>
                      </div>

                      <div className="mt-4 space-y-4">
                        <label className="block space-y-2">
                          <span className="text-[11px] font-black uppercase tracking-widest text-text-muted">Decision / Status Note</span>
                          <textarea
                            value={reason}
                            onChange={(event) => setReason(event.target.value)}
                            rows={3}
                            className="w-full rounded-2xl border border-border bg-surface px-4 py-3 text-sm font-medium text-text outline-none"
                            placeholder="Out of stock, address issue, customer clarified request, packaging note..."
                          />
                        </label>

                        <div className="flex flex-wrap gap-3">
                          {activeStage === "Pending" ? (
                            <>
                              <button
                                onClick={() => acceptRejectMutation.mutate({ orderId: activeOrder.id, decision: "accept", nextReason: reason })}
                                disabled={acceptRejectMutation.isPending}
                                className="btn-primary"
                                type="button"
                              >
                                Accept Order
                              </button>
                              <button
                                onClick={() => acceptRejectMutation.mutate({ orderId: activeOrder.id, decision: "reject", nextReason: reason })}
                                disabled={acceptRejectMutation.isPending}
                                className="btn-secondary text-danger hover:border-danger/30 hover:bg-danger/5"
                                type="button"
                              >
                                Reject Order
                              </button>
                            </>
                          ) : null}

                          {primaryNextStatus ? (
                            <button
                              onClick={() => statusMutation.mutate({ orderId: activeOrder.id, status: primaryNextStatus, nextReason: reason })}
                              disabled={statusMutation.isPending}
                              className="btn-primary"
                              type="button"
                            >
                              Move to {primaryNextStatus}
                            </button>
                          ) : null}

                          {activeStage !== "Cancelled" && activeStage !== "Received" ? (
                            <button
                              onClick={() => statusMutation.mutate({ orderId: activeOrder.id, status: "Cancelled", nextReason: reason })}
                              disabled={statusMutation.isPending}
                              className="btn-secondary text-danger hover:border-danger/30 hover:bg-danger/5"
                              type="button"
                            >
                              Cancel Order
                            </button>
                          ) : null}
                        </div>
                      </div>
                    </div>

                    <div className="rounded-[1.75rem] border border-border bg-surface-soft/35 p-5">
                      <div className="flex items-center gap-2">
                        <Truck size={18} className="text-brand" />
                        <h3 className="text-sm font-black uppercase tracking-widest text-text">Shipping & Logistics</h3>
                      </div>

                      <div className="mt-4 grid gap-4 md:grid-cols-2">
                        <label className="space-y-2">
                          <span className="text-[11px] font-black uppercase tracking-widest text-text-muted">Delivery Partner</span>
                          <select
                            value={selectedLogisticsId}
                            onChange={(event) => setSelectedLogisticsId(event.target.value)}
                            className="h-[50px] w-full rounded-2xl border border-border bg-surface px-4 text-sm font-semibold text-text outline-none"
                          >
                            <option value="">Choose logistics partner</option>
                            {availableLogistics.map((item) => (
                              <option key={item.id} value={item.id}>
                                {item.name} {item.vehicle_type ? `(${item.vehicle_type})` : ""}
                              </option>
                            ))}
                          </select>
                        </label>

                        <label className="space-y-2">
                          <span className="text-[11px] font-black uppercase tracking-widest text-text-muted">Destination</span>
                          <input
                            value={shippingDestination}
                            onChange={(event) => setShippingDestination(event.target.value)}
                            className="h-[50px] w-full rounded-2xl border border-border bg-surface px-4 text-sm font-semibold text-text outline-none"
                            placeholder="Delivery destination"
                          />
                        </label>
                      </div>

                      <label className="mt-4 block space-y-2">
                        <span className="text-[11px] font-black uppercase tracking-widest text-text-muted">Shipping Instructions</span>
                        <textarea
                          value={shippingInstructions}
                          onChange={(event) => setShippingInstructions(event.target.value)}
                          rows={3}
                          className="w-full rounded-2xl border border-border bg-surface px-4 py-3 text-sm font-medium text-text outline-none"
                          placeholder="Fragile item, call before arrival, pickup constraints..."
                        />
                      </label>

                      <div className="mt-4 flex flex-wrap items-center gap-3">
                        <button
                          onClick={() => assignDeliveryMutation.mutate(activeOrder.id)}
                          disabled={assignDeliveryMutation.isPending || !["Packed", "Ready For Shipping", "Confirmed"].includes(activeStage)}
                          className="btn-primary"
                          type="button"
                        >
                          Assign Delivery
                        </button>

                        <span className="text-sm font-medium text-text-muted">
                          {activeOrder.logistics_name
                            ? `Current partner: ${activeOrder.logistics_name}${activeOrder.delivery_status ? ` • ${activeOrder.delivery_status}` : ""}`
                            : "No logistics partner assigned yet."}
                        </span>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-3">
                      <button onClick={() => setIsChatOpen(true)} className="btn-secondary flex items-center gap-2" type="button">
                        <MessageSquare size={16} />
                        Customer / Delivery Chat
                      </button>

                      {activeOrder.delivery_status ? (
                        <button onClick={() => setIsMapOpen(true)} className="btn-secondary flex items-center gap-2" type="button">
                          <Navigation size={16} />
                          Track Delivery
                        </button>
                      ) : null}
                    </div>
                  </div>
                </SectionCard>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>
      )}

      <Modal isOpen={isChatOpen} onClose={() => setIsChatOpen(false)} title="Order Communication">
        <div className="p-4">
          <DeliveryChat
            messages={messages}
            onSend={sendChat}
            onTyping={sendTyping}
            currentUserId={user?.id}
            otherPartyName={activeOrder?.customer_name || activeOrder?.logistics_name || "Order Contact"}
            isConnected={isConnected}
            isOtherPartyTyping={isOtherPartyTyping}
          />
        </div>
      </Modal>

      <Modal isOpen={isMapOpen} onClose={() => setIsMapOpen(false)} title="Delivery Tracking">
        <div className="p-4">
          <LiveTrackingMap
            currentLocation={liveLoc ? [liveLoc.lat, liveLoc.lng] : null}
            destination={null}
            pickup={null}
          />
        </div>
      </Modal>
    </div>
  );
}

function CustomerOrdersView() {
  const { user } = useAuth();
  const token = getStoredToken();
  const queryClient = useQueryClient();
  const [activeOrderId, setActiveOrderId] = useState<number | null>(null);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const { data: orders = [], isLoading, error } = useQuery({
    queryKey: ["customer-orders"],
    queryFn: async () => {
      const response = await apiRequest<Order[]>("/orders/");
      return Array.isArray(response) ? response : [];
    },
    refetchInterval: 15000,
  });
  const activeOrder = useMemo(
    () => orders.find((order) => order.id === activeOrderId) || null,
    [activeOrderId, orders],
  );
  const { messages, sendChat, sendTyping, isConnected, isOtherPartyTyping } = useDeliverySocket(
    activeOrder?.id,
    token,
    (statusUpdate) => {
      if (statusUpdate.order_id) {
        void queryClient.invalidateQueries({ queryKey: ["customer-orders"] });
      }
    },
  );

  if (isLoading) {
    return (
      <SectionCard title="Loading Orders" description="Preparing your customer order history.">
        <div className="flex min-h-[240px] items-center justify-center">
          <div className="h-12 w-12 animate-spin rounded-full border-4 border-brand/10 border-t-brand" />
        </div>
      </SectionCard>
    );
  }

  if (error) {
    return <InlineNotice tone="error">{error instanceof Error ? error.message : "Failed to load orders."}</InlineNotice>;
  }

  return (
    <div className="space-y-6">
      <PageIntro
        eyebrow="Customer Orders"
        title="Order History"
        description="Track your order status, delivery details, and purchase history."
      />

      {!orders.length ? (
        <EmptyState
          title="No Orders Yet"
          description="Once you place orders, they will appear here with status updates and delivery progress."
          icon={<ShoppingBag size={32} />}
        />
      ) : (
        <SectionCard title="Orders" description="Your current and completed purchases.">
          <div className="space-y-4">
            {orders.map((order) => {
              const stage = normalizeStatus(order.status);
              return (
                <div key={order.id} className="rounded-[1.75rem] border border-border bg-surface-soft/35 p-5">
                  <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div>
                      <p className="text-lg font-black text-text">{order.product || "Order item"}</p>
                      <p className="text-sm font-medium text-text-muted">
                        {formatDate(order.order_date)} • {order.quantity || 0} units • {formatMoney(order.total)}
                      </p>
                    </div>
                    <span className={`rounded-full border px-3 py-2 text-[10px] font-black uppercase tracking-widest ${stageTone(stage)}`}>
                      {stage}
                    </span>
                  </div>
                  <div className="mt-4 flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      className="btn-secondary flex items-center gap-2"
                      onClick={() => {
                        setActiveOrderId(order.id);
                        setIsChatOpen(true);
                      }}
                    >
                      <MessageSquare size={16} />
                      Order Chat
                    </button>
                    <span className="text-sm font-medium text-text-muted">
                      {order.provider_name || "Seller"} communication thread
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </SectionCard>
      )}

      <Modal isOpen={isChatOpen} onClose={() => setIsChatOpen(false)} title="Order Communication">
        <div className="p-4">
          <DeliveryChat
            messages={messages}
            onSend={sendChat}
            onTyping={sendTyping}
            currentUserId={user?.id}
            otherPartyName={activeOrder?.provider_name || "Seller"}
            isConnected={isConnected}
            isOtherPartyTyping={isOtherPartyTyping}
          />
        </div>
      </Modal>
    </div>
  );
}

export function OrdersPage() {
  const { user } = useAuth();
  return user?.role === "seller" ? <SellerOrdersBoard /> : <CustomerOrdersView />;
}
