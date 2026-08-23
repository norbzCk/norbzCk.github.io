import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Search, 
  ArrowRight, 
  Zap, 
  ShieldCheck, 
  Truck, 
  Plus, 
  Menu, 
  X,
  Globe,
  Sparkles,
  ChevronRight,
  TrendingUp,
  Star,
  Activity,
  BarChart3,
  Layers,
  CloudLightning,
  Clock,
  Instagram,
  Twitter,
  Linkedin,
  Facebook,
  Github,
  Mail,
  MapPin,
  Phone,
  ArrowUp
} from "lucide-react";
import logoUrl from "../assets/sokolink-logo.png";
import { useAuth } from "../features/auth/AuthContext";
import { useTheme } from "../features/auth/ThemeContext";
import { useCart } from "../features/auth/CartContext";
import { env } from "../config/env";
import { getPostLoginPath } from "../features/auth/authStorage";
import { apiRequest } from "../lib/http";
import type { Product } from "../types/domain";

const FALLBACK_IMAGE = "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=80";

const HERO_TRANSITION = { duration: 0.45, ease: [0.22, 1, 0.36, 1] as const };
const HERO_INTERVAL_MS = 5000;

const SLIDES = [
  {
    image: "/slides/hero-1.jpg",
    title: "Systematic sourcing for modern trade",
    description: "Find reliable products and smarter pricing coordination.",
    accent: "Marketplace"
  },
  {
    image: "/slides/hero-2.jpg",
    title: "Trusted sellers, visible fulfillment",
    description: "Browse top-rated sellers and track last-mile operations.",
    accent: "Trust Built-in"
  },
  {
    image: "/slides/hero-3.jpg",
    title: "AI-assisted discovery for buyers",
    description: "Switch to AI mode to describe what you want instantly.",
    accent: "Smart Search"
  },
  {
    image: "/slides/hero-4.jpg",
    title: "Local inventory, real marketplace motion",
    description: "Showcase your own products with a cleaner, faster hero presentation.",
    accent: "Live Catalog"
  },
];

const CAMPAIGNS = [
  { 
    title: "Fresh Delivery", 
    copy: "Optimized grouped grocery routing.", 
    accent: "Top campaign",
    icon: Truck,
    color: "text-blue-500",
    bg: "bg-blue-500/10"
  },
  { 
    title: "Verified Spotlight", 
    copy: "Trust high-performing verified stores.", 
    accent: "Trust builder",
    icon: ShieldCheck,
    color: "text-emerald-500",
    bg: "bg-emerald-500/10"
  },
  { 
    title: "Bulk Advantage", 
    copy: "Send an RFQ for needed products.", 
    accent: "Buyer tool",
    icon: Zap,
    color: "text-amber-500",
    bg: "bg-amber-500/10"
  },
];

type MarketTickerItem = {
  label: string;
  trend: string;
  status: string;
};

type MarketTickerResponse = {
  items: MarketTickerItem[];
  generated_at?: string;
};

type ProductSearchResponse = {
  items: Product[];
  total: number;
  categories?: string[];
};

function formatMoney(value?: number) {
  return `TZS ${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function resolveImageUrl(url?: string | null) {
  const raw = String(url || "").trim();
  if (!raw) return FALLBACK_IMAGE;
  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith("/")) return `${env.apiBase}${raw}`;
  return `${env.apiBase}/${raw.replace(/^\/+/, "")}`;
}

export function HomePage() {
  const { token, user, loading } = useAuth();
  const { openAssistant } = useAIAssistant();
  const { addToCart, setIsOpen } = useCart();
  const navigate = useNavigate();
  const { toggleTheme, effectiveTheme } = useTheme();
  const [allItems, setAllItems] = useState<Product[]>([]);
  const [categories, setCategories] = useState<string[]>(["all"]);
  const [activeCategory, setActiveCategory] = useState("all");
  const [search, setSearch] = useState("");
  const [currentSlide, setCurrentSlide] = useState(0);
  const [rfqDraft, setRfqDraft] = useState({
    company_name: "",
    contact_name: "",
    email: "",
    phone: "",
    product_interest: "",
    quantity: "1",
    target_budget: "",
    notes: "",
  });
  const [flash, setFlash] = useState("");
  const [error, setError] = useState("");
  const [isLoadingProducts, setIsLoadingProducts] = useState(false);
  const [tickerItems, setTickerItems] = useState<MarketTickerItem[]>([]);
  const [isTickerLoading, setIsTickerLoading] = useState(true);
  const [tickerError, setTickerError] = useState("");

  const [hasScrolledToFeed, setHasScrolledToFeed] = useState(false);

  useEffect(() => {
    if (!loading && token && user) {
      navigate(getPostLoginPath(user), { replace: true });
    }
  }, [loading, navigate, token, user]);

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (!isLoadingProducts && allItems.length > 0 && !hasScrolledToFeed) {
      setHasScrolledToFeed(true);
      document.getElementById("products")?.scrollIntoView({ behavior: "smooth" });
    }
  }, [isLoadingProducts, allItems, hasScrolledToFeed]);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentSlide((prev) => (prev + 1) % SLIDES.length);
    }, HERO_INTERVAL_MS);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    SLIDES.forEach((slide) => {
      const image = new Image();
      image.src = slide.image;
    });
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadMarketTrends() {
      try {
        const response = await apiRequest<MarketTickerResponse>("/marketplace/trends", { auth: false });
        const items = Array.isArray(response?.items)
          ? response.items.filter((item) => item && item.label && item.trend && item.status)
          : [];
        if (!cancelled) {
          setTickerItems(items);
          setTickerError("");
        }
      } catch {
        if (!cancelled) {
          setTickerItems([]);
          setTickerError("Live market trends are unavailable right now.");
        }
      } finally {
        if (!cancelled) {
          setIsTickerLoading(false);
        }
      }
    }

    void loadMarketTrends();
    const timer = setInterval(loadMarketTrends, 120000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  async function fetchProducts(query = "", category = "all") {
    try {
      setIsLoadingProducts(true);
      if (!query.trim() && category === "all") {
        const items = await apiRequest<Product[]>("/products/public", { auth: false });
        setAllItems(Array.isArray(items) ? items : []);
        return;
      }

      const params = new URLSearchParams();
      if (query.trim()) params.set("q", query.trim());
      if (category !== "all") params.set("category", category);
      const response = await apiRequest<ProductSearchResponse>(`/products/public/search?${params.toString()}`, {
        auth: false,
      });
      setAllItems(response.items || []);
      if (Array.isArray(response.categories) && response.categories.length) {
        setCategories(["all", ...response.categories]);
      }
    } catch (err) {
      setError("Unable to load product results. Please try again.");
      setAllItems([]);
    } finally {
      setIsLoadingProducts(false);
    }
  }

  async function load() {
    try {
      const [items, categoryData] = await Promise.all([
        apiRequest<Product[]>("/products/public", { auth: false }),
        apiRequest<{ categories: string[] }>("/products/public/categories", { auth: false }),
      ]);
      setAllItems(Array.isArray(items) ? items : []);
      setCategories(["all", ...(categoryData?.categories || [])]);
    } catch {
      setAllItems([]);
      setCategories(["all"]);
    }
  }

  const categoryValues = useMemo(() => categories, [categories]);

  const [displayCount, setDisplayCount] = useState(12);

  const filteredItems = useMemo(() => {
    if (!search.trim() && activeCategory === "all") {
      return allItems;
    }
    return allItems.filter((item) => {
      const inCategory = activeCategory === "all" || (item.category || "").trim() === activeCategory;
      if (!inCategory) return false;
      if (!search.trim()) return true;
      return `${item.name || ""} ${item.category || ""} ${item.description || ""}`
        .toLowerCase()
        .includes(search.trim().toLowerCase());
    });
  }, [activeCategory, allItems, search]);

  const displayedItems = filteredItems.slice(0, displayCount);

  function activateMode(newMode: "marketplace" | "ai") {
    if (newMode === "ai") {
      openAssistant();
    } else {
      document.getElementById("products")?.scrollIntoView({ behavior: "smooth" });
    }
  }

  async function handleSearch() {
    if (!search.trim()) return;
    setError("");
    await fetchProducts(search, activeCategory);
    setDisplayCount(12);
    document.getElementById("products")?.scrollIntoView({ behavior: "smooth" });
  }

  async function submitRfq(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setFlash("");
    try {
      await apiRequest("/rfq/", {
        method: "POST",
        auth: false,
        body: {
          ...rfqDraft,
          quantity: Number(rfqDraft.quantity || 1),
        },
      });
      setFlash("Your request has been sent. Sellers can now recommend or source what you need.");
      setRfqDraft({
        company_name: "",
        contact_name: "",
        email: "",
        phone: "",
        product_interest: "",
        quantity: "1",
        target_budget: "",
        notes: "",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send product request");
    }
  }

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen bg-bg font-sans text-text selection:bg-brand/20 overflow-x-hidden">
      {/* Market Intelligence Ticker */}
      <div className="w-full bg-dark-bg text-white py-2 border-b border-white/5 relative z-50">
        {isTickerLoading ? (
          <div className="flex whitespace-nowrap">
            <div className="flex items-center gap-6 px-10 border-r border-white/10">
              <span className="text-[9px] font-black uppercase tracking-[0.2em] text-white/40">Market Signals</span>
              <span className="text-xs font-black text-brand">Loading live trends...</span>
            </div>
          </div>
        ) : tickerItems.length ? (
          <div className="flex whitespace-nowrap animate-marquee hover:[animation-play-state:paused]">
            {[...tickerItems, ...tickerItems].map((item, i) => (
              <div key={`${item.label}-${i}`} className="flex items-center gap-6 px-10 border-r border-white/10">
                <span className="text-[9px] font-black uppercase tracking-[0.2em] text-white/40">{item.label}</span>
                <span className="text-xs font-black text-brand">{item.trend}</span>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-white/5 text-[8px] font-bold uppercase text-white/60">
                  <Activity size={10} className="text-emerald-500" />
                  {item.status}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex whitespace-nowrap">
            <div className="flex items-center gap-6 px-10 border-r border-white/10">
              <span className="text-[9px] font-black uppercase tracking-[0.2em] text-white/40">Market Signals</span>
              <span className="text-xs font-black text-brand">{tickerError || "No live market signals yet."}</span>
            </div>
          </div>
        )}
      </div>

      {/* Premium Sticky Navigation */}
      <header className="sticky top-0 z-50 w-full transition-all">
        <nav className="bg-surface/90 backdrop-blur-xl border-b border-border py-4">
          <div className="max-w-6xl mx-auto px-4 md:px-8 flex items-center justify-between gap-8">
            <Link to="/" className="flex items-center gap-3 shrink-0 group">
              <div className="w-10 h-10 rounded-xl bg-brand flex items-center justify-center p-1.5 shadow-lg group-hover:scale-105 transition-transform duration-500">
                <img src={logoUrl} alt="SokoLink" className="w-full h-full object-contain" />
              </div>
              <div className="hidden sm:flex flex-col">
                <span className="font-display font-black text-xl tracking-tight text-text leading-none">SokoLnk</span>
                <span className="text-[8px] uppercase font-black text-brand tracking-[0.2em] mt-1">Smart Network</span>
              </div>
            </Link>

            <div className="flex-1 max-w-xl hidden lg:flex relative group">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-text-muted group-focus-within:text-brand transition-all">
                <Search size={18} />
              </div>
              <input
                type="text"
                className="w-full pl-11 pr-5 py-2.5 bg-surface-soft border border-transparent focus:border-brand/20 focus:bg-surface rounded-2xl transition-all outline-none text-xs font-bold text-text placeholder:text-text-muted shadow-sm group-hover:shadow-md"
                placeholder="Search inventory or verified suppliers..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              />
            </div>

            <div className="flex items-center gap-4">
              <button
                onClick={toggleTheme}
                className="w-10 h-10 rounded-xl bg-surface-soft border border-border hover:border-brand/30 flex items-center justify-center transition-all hover:scale-110 active:scale-95"
                aria-label="Toggle theme"
              >
                {effectiveTheme === 'dark' ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-yellow-400">
                    <circle cx="12" cy="12" r="5"/>
                    <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-slate-400">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                  </svg>
                )}
              </button>
              <Link to="/login" className="px-4 py-2 text-xs font-black uppercase tracking-widest text-text hover:text-brand transition-colors hidden sm:block">Sign In</Link>
              <Link to="/register/customer" className="h-10 px-6 bg-brand text-white font-black text-[10px] uppercase tracking-[0.1em] rounded-xl shadow-lg shadow-brand/20 hover:bg-brand-strong transition-all flex items-center gap-2 group">
                Join Network
                <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" />
              </Link>
            </div>
          </div>
        </nav>

        {/* Categories Bar */}
        <div className="bg-surface/80 backdrop-blur-md border-b border-border overflow-x-auto no-scrollbar">
          <div className="max-w-6xl mx-auto px-4 md:px-8 flex gap-8 whitespace-nowrap py-3">
            {categoryValues.map((cat) => (
              <button
                key={cat}
                onClick={async (e) => {
                  e.preventDefault();
                  setActiveCategory(cat);
                  await fetchProducts(search, cat);
                  setDisplayCount(12);
                  document.getElementById("products")?.scrollIntoView({ behavior: "smooth", block: "start" });
                }}
                className={`text-[10px] font-black uppercase tracking-[0.15em] transition-all relative py-1
                  ${activeCategory === cat ? 'text-brand' : 'text-text-muted hover:text-text'}
                `}
              >
                {cat === "all" ? "Marketplace" : cat}
                {activeCategory === cat && (
                  <motion.span 
                    layoutId="category-active"
                    className="absolute -bottom-1 left-0 w-full h-0.5 bg-brand rounded-full" 
                  />
                )}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 md:px-8 py-12 space-y-24">
        {/* Scaled-down Hero Section */}
        <section className="relative h-[460px] md:h-[560px] rounded-[2.5rem] overflow-hidden shadow-premium-xl bg-dark-bg">
          <AnimatePresence initial={false}>
            <motion.div
              key={currentSlide}
              initial={{ opacity: 0, x: 96, scale: 1.04 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: -96, scale: 0.98 }}
              transition={HERO_TRANSITION}
              className="absolute inset-0"
            >
              <div className="absolute inset-0 bg-dark-bg" />
              <motion.img
                key={`blur-${currentSlide}`}
                initial={{ scale: 1.08, opacity: 0 }}
                animate={{ scale: 1.04, opacity: 0.32 }}
                exit={{ scale: 1.12, opacity: 0 }}
                transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
                src={SLIDES[currentSlide].image}
                alt=""
                aria-hidden="true"
                className="absolute inset-[-12%] w-[124%] h-[124%] object-cover blur-xl"
              />
              <motion.img
                initial={{ scale: 0.985, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 1.015, opacity: 0 }}
                transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
                src={SLIDES[currentSlide].image}
                alt={SLIDES[currentSlide].title}
                className="relative z-10 w-full h-full object-contain object-center opacity-95"
              />
              <div className="absolute inset-0 z-20 bg-gradient-to-t from-dark-bg via-dark-bg/45 to-dark-bg/20" />
              <div className="absolute inset-0 z-20 bg-[radial-gradient(circle_at_70%_35%,rgba(59,130,246,0.28),transparent_34%),radial-gradient(circle_at_20%_80%,rgba(16,185,129,0.18),transparent_28%)]" />

              <div className="absolute inset-0 z-30 flex flex-col justify-end p-8 md:p-16 lg:p-20 space-y-6">
                <motion.div
                  initial={{ y: 34, opacity: 0, filter: "blur(8px)" }}
                  animate={{ y: 0, opacity: 1, filter: "blur(0px)" }}
                  transition={{ delay: 0.16, duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
                  className="max-w-3xl space-y-5"
                >
                  <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/12 text-white text-[9px] font-black uppercase tracking-widest shadow-lg ring-1 ring-white/20 backdrop-blur-md">
                    {SLIDES[currentSlide].accent}
                  </span>
                  <h1 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-display font-black text-white leading-[0.95] tracking-[-0.055em] drop-shadow-2xl">
                    {SLIDES[currentSlide].title}
                  </h1>
                  <p className="text-sm sm:text-base md:text-lg text-white/82 font-medium max-w-2xl leading-relaxed drop-shadow">
                    {SLIDES[currentSlide].description}
                  </p>
                </motion.div>

                <motion.div
                  initial={{ y: 28, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  transition={{ delay: 0.28, duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
                  className="flex flex-wrap gap-4"
                >
                  <button
                    onClick={() => activateMode("marketplace")}
                    className="h-12 px-8 rounded-2xl bg-white text-dark-bg font-black text-xs uppercase tracking-widest hover:bg-surface-soft hover:scale-[1.03] transition-all active:scale-95 shadow-2xl"
                  >
                    Enter Shop
                  </button>
                  <button
                    onClick={() => activateMode("ai")}
                    className="h-12 px-8 rounded-2xl bg-white/10 backdrop-blur-md border border-white/25 text-white font-black text-xs uppercase tracking-widest hover:bg-white/20 hover:scale-[1.03] transition-all active:scale-95 inline-flex items-center gap-2 shadow-xl"
                  >
                    <Zap size={16} className="fill-current text-brand" />
                    AI Help
                  </button>
                </motion.div>
              </div>
            </motion.div>
          </AnimatePresence>

          <div className="absolute bottom-7 right-7 flex gap-2">
            {SLIDES.map((_, idx) => (
              <button
                key={idx}
                onClick={() => setCurrentSlide(idx)}
                aria-label={`Show slide ${idx + 1}`}
                className={`h-1.5 rounded-full transition-all duration-300 ${idx === currentSlide ? 'w-9 bg-white' : 'w-1.5 bg-white/30 hover:bg-white/60'}`}
              />
            ))}
          </div>
        </section>

        {/* Scaled Grid - Campaigns */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {CAMPAIGNS.map((campaign, idx) => (
            <motion.div
              key={campaign.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: idx * 0.1 }}
              className="stat-card p-8 group cursor-default"
            >
              <div className={`w-12 h-12 rounded-2xl bg-surface-soft flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-300 ${campaign.color}`}>
                <campaign.icon size={24} />
              </div>
              <h3 className="text-lg font-display font-black text-text mb-2 tracking-tight">{campaign.title}</h3>
              <p className="text-xs text-text-muted font-medium leading-relaxed">{campaign.copy}</p>
            </motion.div>
          ))}
        </section>

        {/* Product Feed */}
        <section id="products" className="space-y-12">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 border-b border-border pb-8">
            <div className="space-y-2">
              <span className="text-[9px] font-black uppercase tracking-[0.2em] text-brand">Live Feed</span>
              <h2 className="text-3xl font-display font-black text-text tracking-tight">Verified Listings</h2>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 rounded-lg text-emerald-500 border border-emerald-500/20 text-[10px] font-black uppercase tracking-widest">
              <ShieldCheck size={14} />
              Trust Protocol Active
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
            {displayedItems.map((product, idx) => (
              <motion.article
                key={product.id}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                className="group glass-card overflow-hidden hover:-translate-y-2 flex flex-col h-full cursor-pointer"
                onClick={() => navigate(`/product/${product.id}`)}
              >
                <div className="relative aspect-[4/5] overflow-hidden bg-surface-soft">
                  <img
                    src={resolveImageUrl(product.image_url)}
                    alt={product.name}
                    className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                    loading="lazy"
                  />
                  <div className="absolute top-4 left-4">
                    <span className="px-3 py-1 bg-white/90 backdrop-blur-md rounded-xl text-[8px] font-black uppercase tracking-widest text-text shadow-sm">
                      {product.category || "Standard"}
                    </span>
                  </div>
                </div>

                <div className="p-6 flex flex-col flex-1 space-y-4">
                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[9px] font-bold text-text-muted uppercase tracking-widest truncate max-w-[120px]">
                        {product.seller_name || "Merchant"}
                      </span>
                      <div className="flex items-center gap-1 text-amber-500">
                        <Star size={10} className="fill-current" />
                        <span className="text-[9px] font-black text-text">{product.rating_avg || '4.9'}</span>
                      </div>
                    </div>
                    <h3 className="font-display font-black text-base text-text leading-tight group-hover:text-brand transition-colors line-clamp-2">
                      {product.name}
                    </h3>
                  </div>

                  <div className="mt-auto flex items-end justify-between pt-4 border-t border-border">
                    <div className="flex flex-col">
                      <span className="text-xl font-display font-black text-text tracking-tight">{formatMoney(product.price)}</span>
                    </div>
                    <button className="w-8 h-8 rounded-full bg-brand text-white flex items-center justify-center hover:bg-brand-strong transition-all shadow-lg active:scale-90">
                      <Plus size={16} />
                    </button>
                  </div>
                </div>
              </motion.article>
            ))}
          </div>

          {filteredItems.length > displayCount && (
            <div className="flex justify-center pt-8">
              <button 
                onClick={() => setDisplayCount(prev => prev + 12)}
                className="btn-secondary group flex items-center gap-2 !px-12"
              >
                Show More Products
                <ChevronRight size={16} className="group-hover:translate-x-1 transition-transform" />
              </button>
            </div>
          )}
        </section>

        {/* Global Sourcing - Scaled down */}
        <section id="request" className="relative p-1 overflow-hidden rounded-[3rem] bg-dark-bg">
          <div className="relative z-10 p-8 md:p-16 lg:p-20 flex flex-col lg:flex-row gap-12 items-center">
            <div className="lg:w-1/2 space-y-8">
              <div className="space-y-4">
                <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 text-white text-[9px] font-black uppercase tracking-widest border border-white/10">
                  <Globe size={14} className="text-brand" />
                  Sourcing Protocol
                </span>
                <h2 className="text-3xl md:text-5xl font-display font-black text-white tracking-tight leading-tight">
                  Can&apos;t find an asset? <br />
                  <span className="text-brand">We&apos;ll source it.</span>
                </h2>
                <p className="text-white/50 text-base font-medium leading-relaxed max-w-md">
                  Initiate a systematic sourcing request to our global network of verified suppliers.
                </p>
              </div>

              <div className="grid gap-6">
                {[
                  { title: "Smart Match", icon: Sparkles },
                  { title: "Trust Layer", icon: ShieldCheck },
                  { title: "Visibility", icon: Globe }
                ].map((item, idx) => (
                  <div key={idx} className="flex items-center gap-4 text-white/80 group cursor-default">
                    <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center border border-white/10 text-brand group-hover:bg-brand group-hover:text-white transition-all">
                      <item.icon size={18} />
                    </div>
                    <span className="text-sm font-bold">{item.title}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="w-full lg:w-1/2">
              <div className="bg-surface rounded-[2rem] p-8 md:p-12 shadow-2xl border border-white/5">
                <div className="mb-8">
                  <h3 className="text-xl font-display font-black text-text">Launch Request</h3>
                  <p className="text-xs text-text-muted font-medium mt-1">Professional outcomes, zero obligations.</p>
                </div>
                <form onSubmit={submitRfq} className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <input className="modern-input h-12" value={rfqDraft.company_name} onChange={(e) => setRfqDraft(p => ({...p, company_name: e.target.value}))} placeholder="Business Name" required />
                  <input className="modern-input h-12" value={rfqDraft.contact_name} onChange={(e) => setRfqDraft(p => ({...p, contact_name: e.target.value}))} placeholder="Your Name" required />
                  <input className="modern-input h-12" type="email" value={rfqDraft.email} onChange={(e) => setRfqDraft(p => ({...p, email: e.target.value}))} placeholder="Email Protocol" required />
                  <input className="modern-input h-12" value={rfqDraft.product_interest} onChange={(e) => setRfqDraft(p => ({...p, product_interest: e.target.value}))} placeholder="Target Asset" required />
                  <textarea rows={3} className="modern-input md:col-span-2 resize-none" value={rfqDraft.notes} onChange={(e) => setRfqDraft(p => ({...p, notes: e.target.value}))} placeholder="Operational Specs..." />
                  <button type="submit" className="md:col-span-2 btn-primary !h-14 !text-[10px]">Execute Sourcing Protocol</button>
                </form>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="bg-dark-bg pt-24 pb-12 text-white relative overflow-hidden">
        {/* Background Decorative Element */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
        
        <div className="max-w-6xl mx-auto px-4 md:px-8">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-12 lg:gap-8 mb-20">
            {/* Brand Column */}
            <div className="lg:col-span-2 space-y-8">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-brand flex items-center justify-center p-1.5 shadow-lg">
                  <img src={logoUrl} alt="SokoLink" className="w-full h-full object-contain" />
                </div>
                <span className="font-display font-black text-2xl tracking-tight text-white leading-none">SokoLnk</span>
              </div>
              <p className="text-white/50 font-medium text-sm leading-relaxed max-w-sm">
                The platform command for modern commerce. Systematic sourcing, verified trust, and transparent fulfillment protocols for global enterprises.
              </p>
              <div className="flex gap-4">
                {[
                  { icon: Twitter, href: "#", label: "Twitter" },
                  { icon: Linkedin, href: "#", label: "LinkedIn" },
                  { icon: Instagram, href: "#", label: "Instagram" },
                  { icon: Github, href: "#", label: "GitHub" }
                ].map((social) => (
                  <a 
                    key={social.label} 
                    href={social.href}
                    className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-white/40 hover:bg-brand hover:text-white hover:border-brand transition-all duration-300"
                  >
                    <social.icon size={18} />
                  </a>
                ))}
              </div>
            </div>

            {/* Links Columns */}
            <div className="space-y-8">
              <h4 className="text-[10px] font-black uppercase tracking-[0.3em] text-white/30">Marketplace</h4>
              <ul className="space-y-4">
                {["Live Catalog", "Verified Sellers", "Global Sourcing", "AI Assistant", "Flash Deals"].map(link => (
                  <li key={link}><a href="#" className="text-white/50 hover:text-brand transition-colors font-bold text-xs">{link}</a></li>
                ))}
              </ul>
            </div>

            <div className="space-y-8">
              <h4 className="text-[10px] font-black uppercase tracking-[0.3em] text-white/30">Intelligence</h4>
              <ul className="space-y-4">
                {["Market Analysis", "Route Optimization", "Inventory Risk", "Supplier Trust", "Price Index"].map(link => (
                  <li key={link}><a href="#" className="text-white/50 hover:text-brand transition-colors font-bold text-xs">{link}</a></li>
                ))}
              </ul>
            </div>

            <div className="space-y-8">
              <h4 className="text-[10px] font-black uppercase tracking-[0.3em] text-white/30">Platform</h4>
              <ul className="space-y-4">
                {["Merchant Hub", "Logistics Mesh", "Escrow Protocol", "Marketplace API", "Trust Center"].map(link => (
                  <li key={link}><a href="#" className="text-white/50 hover:text-brand transition-colors font-bold text-xs">{link}</a></li>
                ))}
              </ul>
            </div>

            <div className="space-y-8">
              <h4 className="text-[10px] font-black uppercase tracking-[0.3em] text-white/30">Connect</h4>
              <div className="space-y-6">
                <ul className="space-y-4">
                  <li className="flex items-center gap-3 text-white/50 font-bold text-xs">
                    <Mail size={14} className="text-brand" />
                    support@sokolink.net
                  </li>
                  <li className="flex items-center gap-3 text-white/50 font-bold text-xs">
                    <MapPin size={14} className="text-brand" />
                    SokoLnk Hub, DSM
                  </li>
                </ul>
                <div className="pt-4 space-y-4">
                  <p className="text-[9px] font-black uppercase tracking-widest text-white/30">Newsletter</p>
                  <div className="flex gap-2">
                    <input className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-[10px] outline-none focus:border-brand/50 transition-all w-full" placeholder="Enter email..." />
                    <button className="p-2 bg-brand text-white rounded-lg hover:bg-brand-strong transition-all"><ArrowRight size={14} /></button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Bottom Bar */}
          <div className="pt-12 border-t border-white/5 flex flex-col md:flex-row justify-between items-center gap-8">
            <div className="flex flex-col md:flex-row items-center gap-8">
              <p className="text-white/20 text-[9px] font-black uppercase tracking-[0.4em]">© 2026 SOKOLNK SMART MARKETPLACE</p>
              <div className="flex gap-6">
                {["Privacy Protocol", "Terms of Service", "Cookie Policy"].map(legal => (
                  <a key={legal} href="#" className="text-white/20 hover:text-white transition-colors text-[9px] font-black uppercase tracking-widest">{legal}</a>
                ))}
              </div>
            </div>
            <button 
              onClick={scrollToTop}
              className="group flex items-center gap-3 px-5 py-2.5 rounded-xl bg-white/5 border border-white/10 text-[9px] font-black uppercase tracking-widest text-white/40 hover:bg-white/10 hover:text-white transition-all"
            >
              Back to Apex
              <ArrowUp size={14} className="group-hover:-translate-y-1 transition-transform" />
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
}
