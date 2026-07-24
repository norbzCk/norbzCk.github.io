import { useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { MapPin, Phone, Package, Clock, CheckCircle, XCircle, Navigation, ShieldCheck, Star, MessageSquare } from "lucide-react";
import { useAuth } from "../features/auth/AuthContext";
import { apiRequest } from "../lib/http";
import { LiveTrackingMap } from "../features/logistics/LiveTrackingMap";
import type { OrderTracking } from "../types/domain";

export function TrackDeliveryPage() {
  const { trackingCode } = useParams<{ trackingCode: string }>();
  const [searchParams] = useSearchParams();
  const orderIdFromQuery = searchParams.get("order_id");
  
  const { user } = useAuth();
  
  const [trackingData, setTrackingData] = useState<OrderTracking | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [codeInput, setCodeInput] = useState(trackingCode || orderIdFromQuery || "");
  const [ratingSubmitted, setRatingSubmitted] = useState(false);
  const [submittingRating, setSubmittingRating] = useState(false);
  const [hoveredStar, setHoveredStar] = useState(0);
  const [localComment, setLocalComment] = useState("");

  async function handleTrack(e: React.FormEvent) {
    e.preventDefault();
    if (!codeInput.trim()) return;

    setLoading(true);
    setError("");
    try {
      // Try order_id first, then verification_code
      let data = await apiRequest<OrderTracking>(`/logistics/track?order_id=${encodeURIComponent(codeInput.trim())}`).catch(() => null);
      if (!data) {
        data = await apiRequest<OrderTracking>(`/logistics/track?code=${encodeURIComponent(codeInput.trim())}`);
      }
      setTrackingData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tracking code not found");
    } finally {
      setLoading(false);
    }
  }

  async function submitRating(rating: number) {
    if (!trackingData) return;
    setSubmittingRating(true);
    setError("");
    try {
      await apiRequest(`/logistics/deliveries/${trackingData.delivery_id}/rating`, {
        method: "POST",
        body: { rating, comment: localComment.trim() || undefined },
      });
      setRatingSubmitted(true);
      // Refresh tracking to get updated rating
      const fresh = await apiRequest<OrderTracking>(`/logistics/track?order_id=${trackingData.order_id}`).catch(() => null);
      if (fresh) setTrackingData(fresh);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit rating");
    } finally {
      setSubmittingRating(false);
    }
  }

  function statusIcon(status: string) {
    switch (status?.toLowerCase()) {
      case "delivered":
        return <CheckCircle className="h-6 w-6 text-emerald-500" />;
      case "failed":
      case "delivery_failed":
      case "cancelled":
        return <XCircle className="h-6 w-6 text-rose-500" />;
      default:
        return <Package className="h-6 w-6 text-brand" />;
    }
  }

  function statusColor(status: string) {
    switch (status?.toLowerCase()) {
      case "delivered":
        return "bg-emerald-50 border-emerald-200 text-emerald-800";
      case "failed":
      case "delivery_failed":
      case "cancelled":
        return "bg-rose-50 border-rose-200 text-rose-800";
      case "in_transit":
      case "picked_up":
        return "bg-amber-50 border-amber-200 text-amber-800";
      default:
        return "bg-sky-50 border-sky-200 text-sky-800";
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 py-12 px-4">
      <div className="mx-auto max-w-3xl">
        <header className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-3xl bg-brand shadow-lg">
            <Navigation className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-3xl font-black tracking-tight text-slate-900 dark:text-white">Track Your Delivery</h1>
          <p className="mt-2 text-slate-500 dark:text-slate-400">
            Enter your order number or verification code to see real-time status
          </p>
        </header>

        <form onSubmit={handleTrack} className="mb-8 flex gap-3">
          <input
            type="text"
            value={codeInput}
            onChange={(e) => setCodeInput(e.target.value)}
            placeholder="Order # or verification code"
            className="flex-1 rounded-2xl border border-slate-200 bg-white px-5 py-4 text-lg font-semibold outline-none transition focus:border-brand/40 shadow-sm dark:border-slate-700 dark:bg-slate-800"
          />
          <button
            type="submit"
            disabled={loading || !codeInput.trim()}
            className="rounded-2xl bg-brand px-8 py-4 text-lg font-bold text-white shadow-lg transition hover:bg-brand-strong disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Searching…" : "Track"}
          </button>
        </form>

        {error && (
          <div className="mb-6 rounded-2xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm font-semibold text-rose-700 dark:bg-rose-900/30 dark:text-rose-400">
            {error}
          </div>
        )}

        {trackingData && (
          <div className="space-y-5 animate-in fade-in slide-in-from-bottom-4">
            {/* Header Card */}
            <div className={`rounded-[2rem] border-2 p-6 shadow-lg ${statusColor(trackingData.status)}`}>
              <div className="flex flex-col items-center gap-4 md:flex-row md:justify-between">
                <div className="flex items-center gap-4">
                  {statusIcon(trackingData.status)}
                  <div>
                    <h2 className="text-2xl font-black tracking-tight">
                      Order #{trackingData.order_id || trackingData.delivery_id}
                    </h2>
                    <p className="text-sm font-bold uppercase tracking-wider opacity-80">
                      {trackingData.status?.replace(/_/g, " ")}
                    </p>
                  </div>
                </div>
                <div className="text-center md:text-right">
                  <p className="text-3xl font-black">{trackingData.eta_minutes || 0} min</p>
                  <p className="text-xs font-bold uppercase tracking-widest opacity-70">ETA</p>
                </div>
              </div>
            </div>

            {/* Progress timeline */}
            <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm dark:bg-slate-800 dark:border-slate-700">
              <h3 className="mb-4 flex items-center gap-2 text-sm font-black uppercase tracking-[0.15em] text-slate-900 dark:text-white">
                <Clock size={16} />
                Delivery timeline
              </h3>
              <div className="space-y-4">
                {trackingData.checkpoints?.map((cp, idx) => (
                  <div key={cp.id} className="flex items-start gap-4">
                    <div className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 text-xs font-bold ${
                      cp.done ? "bg-emerald-500 border-emerald-500 text-white" : "border-slate-300 text-slate-400"
                    }`}>
                      {cp.done ? "✓" : idx + 1}
                    </div>
                    <div className="flex-1">
                      <p className={`text-sm font-semibold ${cp.done ? "text-slate-900 dark:text-white" : "text-slate-400"}`}>
                        {cp.label}
                      </p>
                      {cp.timestamp && (
                        <p className="text-xs text-slate-500 dark:text-slate-500">
                          {new Date(cp.timestamp).toLocaleString()}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Live map */}
            {trackingData.status !== "delivered" && trackingData.status !== "failed" && trackingData.status !== "delivery_failed" && trackingData.status !== "cancelled" && (
              <div className="rounded-[2rem] border border-slate-200 bg-white p-4 shadow-sm dark:bg-slate-800 dark:border-slate-700 overflow-hidden">
                <h3 className="mb-3 flex items-center gap-2 text-sm font-black uppercase tracking-[0.15em] text-slate-900 dark:text-white px-2">
                  <MapPin size={16} />
                  Live location
                </h3>
                <div className="h-[320px] md:h-[400px]">
                  <LiveTrackingMap
                    currentLocation={trackingData.map?.current ? [trackingData.map.current.lat, trackingData.map.current.lng] as [number, number] : null}
                    destination={trackingData.map?.destination ? [trackingData.map.destination.lat, trackingData.map.destination.lng] as [number, number] : null}
                    pickup={trackingData.map?.pickup ? [trackingData.map.pickup.lat, trackingData.map.pickup.lng] as [number, number] : null}
                  />
                </div>
              </div>
            )}

            {/* Contact info */}
            {trackingData.logistics_partner && (
              <div className="rounded-[2rem] border border-slate-200 bg-white p-5 shadow-sm dark:bg-slate-800 dark:border-slate-700">
                <h3 className="mb-3 flex items-center gap-2 text-sm font-black uppercase tracking-[0.15em] text-slate-900 dark:text-white">
                  <ShieldCheck size={16} />
                  Your delivery partner
                </h3>
                <div className="flex items-center gap-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand text-xl font-bold text-white">
                    {trackingData.logistics_partner.name?.[0] || "D"}
                  </div>
                  <div className="flex-1">
                    <p className="font-semibold text-slate-900 dark:text-white">
                      {trackingData.logistics_partner.name || "Delivery Partner"}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 capitalize">
                      {trackingData.logistics_partner.vehicle_type?.replace("_", " ") || "Logistics"}
                    </p>
                  </div>
                   {trackingData.logistics_partner.phone && (
                     <a
                       href={`tel:${trackingData.logistics_partner.phone}`}
                       className="flex items-center gap-2 rounded-xl bg-slate-100 px-4 py-2 text-sm font-bold text-slate-700 hover:bg-slate-200 dark:bg-slate-700 dark:text-slate-300"
                     >
                       <Phone size={16} />
                       Call
                     </a>
                   )}
                 </div>
               </div>
             )}

             {/* Rating section - only for delivered orders */}
             {trackingData.status === "delivered" && (
               <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm dark:bg-slate-800 dark:border-slate-700">
                 <h3 className="flex items-center gap-2 text-sm font-black uppercase tracking-[0.15em] text-slate-900 dark:text-white">
                   <Star size={16} className="text-brand fill-brand" />
                   Rate your delivery
                 </h3>
                 
                 {ratingSubmitted ? (
                   <div className="mt-4 flex items-center gap-3 text-emerald-600 dark:text-emerald-400">
                     <CheckCircle size={20} />
                     <p className="text-sm font-semibold">Thank you! Your rating has been submitted.</p>
                   </div>
                 ) : trackingData.rating ? (
                   <div className="mt-4">
                     <div className="flex items-center gap-2">
                       {[1, 2, 3, 4, 5].map((star) => (
                         <Star
                           key={star}
                           size={24}
                           className={`${
                             star <= (trackingData.rating || 0) ? "text-amber-400 fill-amber-400" : "text-slate-300 dark:text-slate-600"
                           }`}
                         />
                       ))}
                       <span className="ml-2 text-sm font-semibold text-slate-700 dark:text-slate-300">
                         {trackingData.rating}/5
                       </span>
                     </div>
                     {trackingData.rating_comment && (
                       <p className="mt-2 text-sm text-slate-500 dark:text-slate-400 italic">
                         "{trackingData.rating_comment}"
                       </p>
                     )}
                     <p className="mt-1 text-xs text-slate-400">
                       Rated on {trackingData.rated_at ? new Date(trackingData.rated_at).toLocaleDateString() : "N/A"}
                     </p>
                   </div>
                 ) : user && user.id === trackingData.buyer_id ? (
                   <div className="mt-4">
                     <p className="text-sm text-slate-600 dark:text-slate-300 mb-3">
                       How was your delivery experience? Rate your delivery partner.
                     </p>
                     <div className="flex items-center gap-2 mb-3">
                       {[1, 2, 3, 4, 5].map((star) => (
                         <button
                           key={star}
                           type="button"
                           onClick={() => submitRating(star)}
                           disabled={submittingRating}
                           className="focus:outline-none disabled:opacity-50"
                         >
                           <Star
                             size={32}
                             className={`cursor-pointer transition-colors ${
                               star <= (hoveredStar || 0)
                                 ? "text-amber-400 fill-amber-400"
                                 : star <= (trackingData.rating || 0)
                                 ? "text-amber-400 fill-amber-400"
                                 : "text-slate-300 dark:text-slate-600 hover:text-amber-300"
                             }`}
                             onMouseEnter={() => setHoveredStar(star)}
                             onMouseLeave={() => setHoveredStar(0)}
                           />
                         </button>
                       ))}
                     </div>
                     <textarea
                       value={localComment}
                       onChange={(e) => setLocalComment(e.target.value)}
                       placeholder="Add a comment (optional)"
                       rows={3}
                       className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 text-sm font-medium outline-none transition focus:border-brand/30"
                     />
                     <button
                       type="button"
                       onClick={() => submitRating(hoveredStar || trackingData.rating || 5)}
                       disabled={submittingRating || (hoveredStar === 0 && !trackingData.rating)}
                       className="mt-3 rounded-xl bg-brand px-6 py-2.5 text-sm font-bold text-white shadow-md transition hover:bg-brand-strong disabled:cursor-not-allowed disabled:opacity-60"
                     >
                       {submittingRating ? "Submitting…" : "Submit rating"}
                     </button>
                     {user.id !== trackingData.buyer_id && (
                       <p className="mt-2 text-xs text-slate-500">
                         Only the buyer can rate this delivery.
                       </p>
                     )}
                   </div>
                 ) : (
                   <div className="mt-4 text-sm text-slate-500 dark:text-slate-400">
                     <p>
                       {user ? (
                         <>
                           You must be the buyer to rate this delivery. If this is your order, ensure you're logged in with the buyer account.
                         </>
                       ) : (
                         <>
                           <Link to="/login" className="text-brand font-semibold hover:underline">Log in</Link> to rate your delivery.
                         </>
                       )}
                     </p>
                   </div>
                 )}
               </div>
             )}
           </div>
         )}

        {/* Empty state - not tracking anything */}
        {!trackingData && !loading && !error && (
          <div className="rounded-[2rem] border border-dashed border-slate-300 bg-slate-50 p-10 text-center dark:bg-slate-800/50">
            <Package className="mx-auto h-12 w-12 text-slate-300 dark:text-slate-600" />
            <h3 className="mt-4 text-lg font-bold text-slate-900 dark:text-white">No delivery selected</h3>
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
              Enter your order ID or verification code above to start tracking.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
