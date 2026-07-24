import { useEffect, useState, MouseEvent } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { 
  ShoppingBag, 
  Zap, 
  ShieldCheck, 
  Truck, 
  Plus, 
  Minus, 
  CheckCircle2, 
  Maximize2, 
  X,
  Store,
  Star,
  ArrowLeft,
  Share2,
  Heart
} from "lucide-react";
import { apiRequest } from "../lib/http";
import { useAuth } from "../features/auth/AuthContext";
import { useCart } from "../features/auth/CartContext";
import { Modal } from "../components/Modal";
import type { Product } from "../types/domain";
import { env } from "../config/env";

const FALLBACK_IMAGE = "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=80";

function formatMoney(value?: number) {
  return `TZS ${Number(value || 0).toLocaleString()}`;
}

function resolveImageUrl(url?: string | null) {
  const raw = String(url || "").trim();
  if (!raw) return FALLBACK_IMAGE;
  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith("/")) return `${env.apiBase}${raw}`;
  return `${env.apiBase}/${raw.replace(/^\/+/, "")}`;
}

export function ProductDetailPage() {
  const { productId } = useParams<{ productId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { addToCart, setIsOpen } = useCart();
  const [product, setProduct] = useState<Product | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showLightbox, setShowLightbox] = useState(false);
  const [zoom, setZoom] = useState(false);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });

  const [similarProducts, setSimilarProducts] = useState<Product[]>([]);

  useEffect(() => {
    void load();
  }, [productId]);

  async function load() {
    if (!productId) return;
    setLoading(true);
    try {
      const data = await apiRequest<Product>(`/products/${productId}`);
      setProduct(data);
      
      // Load similar products
      if (data.category) {
        const similar = await apiRequest<{ items: Product[] }>(`/products/public/search?category=${encodeURIComponent(data.category)}&limit=5`);
        setSimilarProducts((similar.items || []).filter(p => p.id !== data.id));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Product not found");
    } finally {
      setLoading(false);
    }
  }

  async function handleOrder() {
    if (!user) {
      navigate("/login", { state: { from: `/app/checkout?product=${product?.id || productId}&quantity=${quantity}` } });
      return;
    }

    if (user.role !== "user") {
      alert("Only customers can place orders.");
      return;
    }

    setSubmitting(true);
    navigate(`/app/checkout?product=${product?.id || productId}&quantity=${quantity}`);
  }

  function handleImageMouseMove(e: MouseEvent<HTMLImageElement>) {
    if (!zoom) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    setMousePosition({ x, y });
  }

  if (loading) return (
    <div className="min-h-[80vh] flex flex-col items-center justify-center gap-6">
      <div className="w-16 h-16 border-4 border-brand/20 border-t-brand rounded-full animate-spin" />
      <p className="font-display font-black text-text-muted uppercase tracking-widest animate-pulse">Loading Product Asset...</p>
    </div>
  );

  if (error || !product) return (
    <div className="min-h-[60vh] flex items-center justify-center p-8">
      <motion.div 
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-md w-full glass-card p-12 text-center space-y-6"
      >
        <div className="w-24 h-24 bg-danger/10 text-danger rounded-[2rem] flex items-center justify-center mx-auto">
          <X size={48} />
        </div>
        <div className="space-y-2">
          <h2 className="text-3xl font-display font-black text-text tracking-tight uppercase">Unavailable</h2>
          <p className="text-text-muted font-medium">This product asset could not be synchronized.</p>
        </div>
        <button onClick={() => navigate('/app/products')} className="btn-primary w-full h-14">Back to Marketplace</button>
      </motion.div>
    </div>
  );

  const imageUrl = resolveImageUrl(product.image_url);

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="max-w-7xl mx-auto py-8 lg:py-12 space-y-12"
    >
      {/* Navigation & Breadcrumb */}
      <div className="flex items-center justify-between">
        <button 
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-sm font-bold text-text-muted hover:text-brand transition-colors group"
        >
          <ArrowLeft size={18} className="group-hover:-translate-x-1 transition-transform" />
          Back to Listings
        </button>
        <div className="flex items-center gap-4">
          <button className="h-10 w-10 flex items-center justify-center rounded-xl bg-surface border border-border text-text-muted hover:text-danger hover:border-danger/30 transition-all">
            <Heart size={18} />
          </button>
          <button className="h-10 w-10 flex items-center justify-center rounded-xl bg-surface border border-border text-text-muted hover:text-brand hover:border-brand/30 transition-all">
            <Share2 size={18} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-20 items-start">
        {/* Left: Premium Image Gallery */}
        <div className="space-y-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="relative aspect-square md:aspect-[4/5] rounded-[3rem] overflow-hidden bg-white shadow-2xl border border-border group cursor-zoom-in"
            onClick={() => setShowLightbox(true)}
          >
            <img
              src={imageUrl}
              alt={product.name}
              className="w-full h-full object-cover transition-transform duration-1000 group-hover:scale-105"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-dark-bg/40 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

            <div className="absolute bottom-10 left-1/2 -translate-x-1/2 flex items-center gap-3 px-6 py-3 bg-white/10 backdrop-blur-xl border border-white/20 rounded-2xl opacity-0 group-hover:opacity-100 transition-all duration-500 translate-y-4 group-hover:translate-y-0">
              <Maximize2 size={18} className="text-white" />
              <span className="text-[10px] font-black text-white uppercase tracking-widest">Enhanced View</span>
            </div>

            <div className="absolute top-8 left-8">
              <span className="px-4 py-2 bg-brand text-white rounded-2xl text-[10px] font-black uppercase tracking-widest shadow-xl">
                {product.category || "Premium Listing"}
              </span>
            </div>
          </motion.div>
        </div>

        {/* Right: Immersive Product Info */}
        <div className="space-y-12">
          <div className="space-y-6">
            <motion.div 
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              className="space-y-4"
            >
              <div className="flex items-center gap-2">
                <ShieldCheck size={16} className="text-brand" />
                <span className="text-[10px] font-black uppercase tracking-widest text-brand">Verified SokoLnk Smart Listing</span>
              </div>
              <h1 className="text-4xl md:text-6xl font-display font-black text-text leading-[1.1] tracking-tight">
                {product.name}
              </h1>
              <div className="flex items-center gap-4 text-amber-500">
                <div className="flex items-center gap-1">
                  {[1, 2, 3, 4, 5].map(i => <Star key={i} size={14} className="fill-current" />)}
                </div>
                <span className="text-sm font-black text-text">4.9 (120+ Verified Reviews)</span>
              </div>
            </motion.div>

            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 }}
              className="flex flex-wrap items-center gap-8"
            >
              <span className="text-4xl md:text-5xl font-display font-black text-text tracking-tight">
                {formatMoney(product.price)}
              </span>
              <div className="h-10 w-px bg-border hidden sm:block" />
              <div className="flex flex-col">
                <span className={`text-[10px] font-black uppercase tracking-widest mb-1 ${product.stock && product.stock > 0 ? 'text-emerald-500' : 'text-danger'}`}>
                  {product.stock && product.stock > 0 ? 'Immediate Availability' : 'Temporarily Unavailable'}
                </span>
                <span className="text-sm font-bold text-text-muted">{product.stock || 0} Professional Units in Stock</span>
              </div>
            </motion.div>
          </div>

          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="space-y-4"
          >
            <h3 className="text-xs font-black uppercase tracking-widest text-text-muted">Technical Overview</h3>
            <p className="text-xl text-text-muted font-medium leading-relaxed max-w-2xl">
              {product.description || "Designed for mission-critical operations, this premium listing features systematic quality control and optimized fulfillment compatibility."}
            </p>
            <div className="pt-2">
              <button 
                onClick={() => {
                  const el = document.getElementById('similar-products');
                  el?.scrollIntoView({ behavior: 'smooth' });
                }}
                className="text-[10px] font-black uppercase tracking-[0.2em] text-brand hover:underline"
              >
                View Like Products
              </button>
            </div>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-10 py-10 border-y border-border">
            <div className="space-y-6">
              <h4 className="text-[10px] font-black uppercase tracking-widest text-text-muted">Verified Merchant</h4>
              <div className="flex items-center gap-4 group cursor-pointer">
                <div className="w-16 h-16 rounded-[1.5rem] bg-surface-soft flex items-center justify-center text-brand font-black text-2xl border border-border transition-all group-hover:bg-brand group-hover:text-white group-hover:border-brand shadow-sm">
                  {(product.seller_name || "S")[0].toUpperCase()}
                </div>
                <div className="min-w-0">
                  <p className="font-display font-black text-text truncate text-lg leading-none">{product.seller_name || "Independent Seller"}</p>
                  <div className="flex items-center gap-1.5 mt-2">
                    <CheckCircle2 size={12} className="text-emerald-500" />
                    <span className="text-[10px] font-black text-text-muted uppercase tracking-widest">Premium Sourcing Partner</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-6">
              <h4 className="text-[10px] font-black uppercase tracking-widest text-text-muted">Fulfillment Edge</h4>
              <div className="space-y-4">
                {[
                  { label: "Secure Smart Payments", icon: Zap },
                  { label: "Optimized Route Fulfillment", icon: Truck },
                  { label: "Escrow Protected Sourcing", icon: ShieldCheck }
                ].map((item, idx) => (
                  <div key={idx} className="flex items-center gap-3 text-sm font-bold text-text">
                    <div className="w-8 h-8 rounded-xl bg-surface-soft flex items-center justify-center shrink-0 text-brand">
                      <item.icon size={14} />
                    </div>
                    {item.label}
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-8">
            <div className="flex flex-col sm:flex-row items-center gap-6">
              <div className="flex items-center bg-surface-soft rounded-2xl p-1 border-2 border-transparent focus-within:border-brand/30 transition-all h-16">
                <button
                  onClick={() => setQuantity(q => Math.max(1, q - 1))}
                  className="w-14 h-full flex items-center justify-center text-text-muted hover:text-brand transition-all active:scale-90"
                >
                  <Minus size={20} />
                </button>
                <div className="w-14 text-center font-display font-black text-2xl text-text">{quantity}</div>
                <button
                  onClick={() => setQuantity(q => Math.min(product.stock || 100, q + 1))}
                  className="w-14 h-full flex items-center justify-center text-text-muted hover:text-brand transition-all active:scale-90"
                >
                  <Plus size={20} />
                </button>
              </div>

              <div className="flex-1 w-full grid grid-cols-1 sm:grid-cols-2 gap-4">
                <button
                  className="btn-primary !h-16 shadow-brand/40 text-sm active:scale-95"
                  disabled={submitting || !product.stock || product.stock <= 0}
                  onClick={handleOrder}
                >
                  {submitting ? "Syncing..." : "Checkout Order"}
                </button>
                <button
                  className="h-16 bg-dark-bg text-white font-black text-xs uppercase tracking-widest rounded-2xl hover:bg-brand transition-all active:scale-95 shadow-xl disabled:opacity-50 inline-flex items-center justify-center gap-2"
                  disabled={!product.stock || product.stock <= 0}
                  onClick={() => {
                    addToCart({
                      id: product.id,
                      name: product.name || "Product",
                      price: product.price || 0,
                      image_url: product.image_url,
                      seller_id: product.seller_id,
                      seller_name: product.seller_name || null,
                    });
                    setIsOpen(true);
                  }}
                >
                  <ShoppingBag size={18} />
                  Add to Cart
                </button>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-8 py-4 opacity-40">
              <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.2em]">
                <ShieldCheck size={14} /> Global Escrow
              </div>
              <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.2em]">
                <Truck size={14} /> Smart Routing
              </div>
              <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.2em]">
                <Zap size={14} /> Instant Settlement
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Similar Products Section */}
      <section id="similar-products" className="pt-20 space-y-12 border-t border-border">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 border-b border-border pb-8">
          <div className="space-y-2">
            <span className="text-[9px] font-black uppercase tracking-[0.2em] text-brand">Recommendations</span>
            <h2 className="text-3xl font-display font-black text-text tracking-tight">Similar Product Assets</h2>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
          {similarProducts.map((p) => (
            <motion.article
              key={p.id}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="group glass-card overflow-hidden hover:-translate-y-2 flex flex-col h-full cursor-pointer"
              onClick={() => {
                navigate(`/product/${p.id}`);
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
            >
              <div className="relative aspect-[4/5] overflow-hidden bg-surface-soft">
                <img
                  src={resolveImageUrl(p.image_url)}
                  alt={p.name}
                  className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                  loading="lazy"
                />
              </div>

              <div className="p-6 flex flex-col flex-1 space-y-4">
                <div className="space-y-1">
                  <h3 className="font-display font-black text-base text-text leading-tight group-hover:text-brand transition-colors line-clamp-2">
                    {p.name}
                  </h3>
                  <p className="text-[10px] font-black uppercase tracking-widest text-text-muted">{p.category}</p>
                </div>

                <div className="mt-auto pt-4 border-t border-border">
                  <span className="text-lg font-display font-black text-text tracking-tight">{formatMoney(p.price)}</span>
                </div>
              </div>
            </motion.article>
          ))}
          {similarProducts.length === 0 && (
            <p className="text-sm font-medium text-text-muted col-span-full py-12 text-center">No similar products found at this time.</p>
          )}
        </div>
      </section>

      {/* Enhanced Lightbox Overlay */}
      <Modal isOpen={showLightbox} onClose={() => setShowLightbox(false)} title={product.name}>
        <div className="space-y-8 p-4">
          <div
            className={`relative overflow-hidden rounded-[2.5rem] bg-surface-soft cursor-crosshair group ${zoom ? 'h-[75vh]' : 'h-auto'}`}
            onMouseEnter={() => setZoom(true)}
            onMouseLeave={() => setZoom(false)}
            onMouseMove={handleImageMouseMove}
          >
            <img
              src={imageUrl}
              alt={product.name}
              className={`w-full h-full object-contain transition-transform duration-200 ${zoom ? 'scale-[2.5]' : 'scale-100'}`}
              style={zoom ? { transformOrigin: `${mousePosition.x}% ${mousePosition.y}%` } : undefined}
            />
            {!zoom && (
              <div className="absolute inset-0 flex items-center justify-center bg-dark-bg/5 opacity-0 group-hover:opacity-100 transition-opacity">
                <span className="px-6 py-3 bg-white text-dark-bg rounded-2xl font-black text-xs uppercase tracking-widest shadow-2xl">Precision Zoom Enabled</span>
              </div>
            )}
          </div>
          <div className="flex justify-between items-center px-6">
            <div className="space-y-1">
              <h4 className="font-display font-black text-text uppercase tracking-tight">{product.name}</h4>
              <p className="text-[10px] font-black text-text-muted uppercase tracking-widest">High-Definition Asset Preview</p>
            </div>
            <button onClick={() => setShowLightbox(false)} className="btn-secondary !h-12 !px-8">Close View</button>
          </div>
        </div>
      </Modal>
    </motion.div>
  );
}
