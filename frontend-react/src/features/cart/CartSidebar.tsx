import { useEffect, useState } from "react";
import { useLocation, useNavigate, Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { 
  ShoppingBag, 
  X, 
  Plus, 
  Minus, 
  Trash2, 
  Zap, 
  ArrowRight, 
  CreditCard,
  Package,
  ShieldCheck,
  TrendingUp,
  Sparkles
} from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { useCart } from "../auth/CartContext";
import { apiRequest } from "../../lib/http";
import type { CartOptimization } from "../../types/domain";

function formatMoney(value?: number) {
  return `TZS ${Number(value || 0).toLocaleString()}`;
}

const sidebarVariants = {
  hidden: { x: "100%", opacity: 0.5 },
  visible: { 
    x: 0, 
    opacity: 1,
    transition: { type: "spring" as const, damping: 25, stiffness: 200 }
  },
  exit: { 
    x: "100%", 
    opacity: 0.5,
    transition: { duration: 0.3 }
  }
};

export function CartSidebar() {
  const { cart, isOpen, removeFromCart, updateQuantity, clearCart, cartCount, cartTotal, setIsOpen } = useCart();
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [optimization, setOptimization] = useState<CartOptimization | null>(null);

  const canShowCartUi =
    location.pathname === "/" ||
    location.pathname.startsWith("/product/") ||
    location.pathname.startsWith("/app/products") ||
    location.pathname.startsWith("/app/orders") ||
    location.pathname.startsWith("/app/customer");

  useEffect(() => {
    let cancelled = false;
    async function loadOptimization() {
      if (!cart.length) {
        setOptimization(null);
        return;
      }
      try {
        const data = await apiRequest<CartOptimization>("/products/cart-optimization", {
          method: "POST",
          auth: false,
          body: {
            items: cart.map((item) => ({
              product_id: item.id,
              quantity: item.qty,
            })),
          },
        });
        if (!cancelled) setOptimization(data);
      } catch {
        if (!cancelled) setOptimization(null);
      }
    }

    void loadOptimization();
    return () => {
      cancelled = true;
    };
  }, [cart]);

  const handleCheckout = () => {
    if (!token || !user) {
      navigate("/login", { state: { from: "/app/orders" } });
      return;
    }
    navigate("/app/checkout");
    setIsOpen(false);
  };

  if (!canShowCartUi) return null;

  return (
    <>
      {/* Floating Launcher */}
      <AnimatePresence>
        {cartCount > 0 && !isOpen && (
          <motion.button
            initial={{ scale: 0, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0, opacity: 0, y: 20 }}
            onClick={() => setIsOpen(true)}
            className="fixed bottom-8 right-8 z-40 flex items-center gap-4 bg-dark-bg text-white p-2 pl-6 rounded-3xl shadow-2xl border border-white/10 group active:scale-95 transition-transform"
          >
            <div className="flex flex-col items-start">
              <span className="text-[10px] font-black uppercase tracking-widest text-white/40">Draft Cart</span>
              <span className="text-sm font-bold">{formatMoney(cartTotal)}</span>
            </div>
            <div className="relative w-12 h-12 rounded-2xl bg-brand flex items-center justify-center shadow-lg group-hover:bg-brand-strong transition-colors">
              <ShoppingBag size={20} />
              <span className="absolute -top-1.5 -right-1.5 w-6 h-6 rounded-full bg-danger border-2 border-dark-bg text-[10px] font-black flex items-center justify-center">
                {cartCount}
              </span>
            </div>
          </motion.button>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {isOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsOpen(false)}
              className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-sm"
            />

            {/* Sidebar */}
            <motion.aside
              variants={sidebarVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="fixed right-0 top-0 bottom-0 z-50 w-full max-w-md bg-surface shadow-2xl border-l border-border flex flex-col"
            >
              {/* Header */}
              <div className="p-8 border-b border-border flex items-center justify-between">
                <div>
                  <h3 className="text-2xl font-display font-black text-text tracking-tight flex items-center gap-3">
                    <ShoppingBag className="text-brand" size={24} />
                    Draft Cart
                  </h3>
                  <p className="text-xs font-medium text-text-muted mt-1">{cartCount} items ready for fulfillment</p>
                </div>
                <button 
                  onClick={() => setIsOpen(false)}
                  className="w-10 h-10 rounded-xl bg-surface-soft flex items-center justify-center text-text-muted hover:bg-surface-strong hover:text-text transition-all"
                >
                  <X size={20} />
                </button>
              </div>

              {/* Items List */}
              <div className="flex-1 overflow-y-auto no-scrollbar p-6 space-y-6">
                {cart.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center space-y-4 opacity-60">
                    <div className="w-20 h-20 rounded-3xl bg-surface-soft flex items-center justify-center text-text-muted">
                      <Package size={40} />
                    </div>
                    <div>
                      <h4 className="font-bold text-text">Your cart is empty</h4>
                      <p className="text-sm text-text-muted max-w-[200px] mx-auto">Add marketplace items to begin drafting your order.</p>
                    </div>
                    <button onClick={() => { setIsOpen(false); navigate("/app/products"); }} className="btn-secondary !h-12">Browse Products</button>
                  </div>
                ) : (
                  cart.map((item) => (
                    <motion.div 
                      key={item.id}
                      layout
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="group relative flex gap-5 p-4 rounded-[2rem] bg-surface border border-border hover:border-brand/30 transition-all"
                    >
                      <div className="relative w-24 h-24 rounded-2xl overflow-hidden shrink-0 bg-surface-soft">
                        <img src={item.image_url || "/placeholder-product.png"} alt={item.name} className="w-full h-full object-cover transition-transform group-hover:scale-110" />
                      </div>
                      <div className="flex-1 min-w-0 flex flex-col justify-between py-1">
                        <div>
                          <h4 className="font-bold text-text truncate pr-6 leading-tight">{item.name}</h4>
                          <p className="text-[10px] font-black uppercase tracking-widest text-text-muted mt-1">{item.seller_name || "Verified Seller"}</p>
                        </div>
                        <div className="flex items-center justify-between">
                          <strong className="text-brand font-display font-black">{formatMoney(item.price)}</strong>
                          <div className="flex items-center bg-surface-soft rounded-xl p-1 border border-border">
                            <button onClick={() => updateQuantity(item.id, item.qty - 1)} className="w-7 h-7 flex items-center justify-center text-text-muted hover:text-brand transition-colors"><Minus size={14} /></button>
                            <span className="w-8 text-center text-xs font-black">{item.qty}</span>
                            <button onClick={() => updateQuantity(item.id, item.qty + 1)} className="w-7 h-7 flex items-center justify-center text-text-muted hover:text-brand transition-colors"><Plus size={14} /></button>
                          </div>
                        </div>
                      </div>
                      <button 
                        onClick={() => removeFromCart(item.id)}
                        className="absolute top-4 right-4 text-text-muted hover:text-danger opacity-0 group-hover:opacity-100 transition-all"
                      >
                        <Trash2 size={16} />
                      </button>
                    </motion.div>
                  ))
                )}
              </div>

              {/* Optimization & Footer */}
              <div className="p-8 space-y-6 bg-surface-soft/50 border-t border-border">
                {optimization && cart.length > 0 && (
                  <motion.div 
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="p-5 rounded-[1.75rem] bg-brand text-white shadow-xl shadow-brand/20 relative overflow-hidden group"
                  >
                    <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:rotate-12 transition-transform duration-500">
                      <Sparkles size={60} />
                    </div>
                    <div className="relative z-10 flex flex-col gap-4">
                      <div className="flex items-center justify-between">
                        <span className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-white/20 text-[9px] font-black uppercase tracking-widest border border-white/20">
                          <Zap size={10} className="fill-current" /> Smart Sourcing
                        </span>
                        <strong className="text-sm font-black">Save {formatMoney(optimization.summary.estimated_savings)}</strong>
                      </div>
                      <p className="text-xs font-medium text-white/80 leading-relaxed">
                        Nearby sellers detected. Optimization can reduce delivery fees by grouping your shipments.
                      </p>
                    </div>
                  </motion.div>
                )}

                <div className="space-y-4">
                  <div className="flex items-center justify-between px-2">
                    <span className="text-xs font-black uppercase tracking-widest text-text-muted">Total Draft Amount</span>
                    <strong className="text-2xl font-display font-black text-text">{formatMoney(cartTotal)}</strong>
                  </div>
                  <div className="grid grid-cols-1 gap-3">
                    <button 
                      onClick={handleCheckout}
                      disabled={cart.length === 0}
                      className="w-full h-16 btn-primary flex items-center justify-center gap-3 active:scale-95"
                    >
                      <CreditCard size={20} />
                      <span className="font-black text-sm uppercase tracking-widest">Process Order</span>
                      <ArrowRight size={18} className="opacity-50" />
                    </button>
                    <button 
                      onClick={clearCart}
                      disabled={cart.length === 0}
                      className="w-full h-14 btn-secondary text-danger hover:bg-danger/5 hover:border-danger/20 active:scale-95"
                    >
                      Clear Draft List
                    </button>
                  </div>
                  <div className="flex items-center justify-center gap-4 py-2 opacity-40">
                    <div className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-widest"><ShieldCheck size={12} /> Secure Checkout</div>
                    <div className="w-1 h-1 rounded-full bg-border" />
                    <div className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-widest"><TrendingUp size={12} /> Best Routes</div>
                  </div>
                </div>
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
