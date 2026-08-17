import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Package, 
  AlertTriangle, 
  TrendingDown, 
  DollarSign, 
  Sparkles, 
  Upload, 
  Search, 
  Filter, 
  ArrowUpDown,
  Trash2,
  Edit2,
  Plus,
  ChevronRight,
  TrendingUp,
  Box,
  Store,
  X
} from "lucide-react";
import { useAuth } from "../features/auth/AuthContext";
import { useCart } from "../features/auth/CartContext";
import { env } from "../config/env";
import { apiRequest } from "../lib/http";
import type { InventoryStats, Product, Provider } from "../types/domain";

const FALLBACK_IMAGE = "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=80";

interface ProductDraft {
  name: string;
  category: string;
  price: string;
  stock: string;
  description: string;
  image_url: string;
  provider_id: string;
  seller_id: string;
}

interface BusinessmanOption {
  id: number;
  business_name: string;
}

interface ProductInsight {
  description: string;
  suggested_price: number;
  seo_keywords: string[];
  confidence: number;
  trend_summary?: string | null;
  demand_level?: string | null;
  price_range?: {
    low?: number;
    high?: number;
    benchmark_average?: number;
  } | null;
}

interface InventoryForecastItem {
  product_id: number;
  product_name: string;
  current_stock: number;
  daily_burn_rate: number;
  days_left: number | string;
  weekly_demand?: number;
  recommended_restock?: number;
  risk_level?: string;
}

const emptyDraft: ProductDraft = {
  name: "",
  category: "",
  price: "",
  stock: "",
  description: "",
  image_url: "",
  provider_id: "",
  seller_id: "",
};

function formatMoney(value?: number) {
  return `TZS ${Number(value || 0).toLocaleString()}`;
}

function canManage(role?: string) {
  return ["admin", "super_admin", "owner", "seller"].includes(String(role || ""));
}

function canEditProduct(product: Product, userRole?: string, userId?: number | null) {
  const role = String(userRole || "");
  if (["admin", "super_admin", "owner"].includes(role)) return true;
  if (role === "seller") {
    return Number(product.seller_id || 0) === Number(userId || 0);
  }
  return false;
}

export function ProductsPage() {
  const { user } = useAuth();
  const { addToCart, setIsOpen } = useCart();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [products, setProducts] = useState<Product[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [businessmen, setBusinessmen] = useState<BusinessmanOption[]>([]);
  const [inventory, setInventory] = useState<InventoryStats | null>(null);
  const [flash, setFlash] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(searchParams.get("q") || "");
  const [category, setCategory] = useState(searchParams.get("category") || "all");
  const [sort, setSort] = useState("featured");
  const [draft, setDraft] = useState<ProductDraft>(emptyDraft);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [insight, setInsight] = useState<ProductInsight | null>(null);
  const [forecast, setForecast] = useState<InventoryForecastItem[]>([]);
  const [generatingInsight, setGeneratingInsight] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const sellerMode = String(user?.role || "") === "seller";
  const adminMode = ["admin", "super_admin", "owner"].includes(String(user?.role || ""));

  useEffect(() => {
    void load();
  }, [sellerMode, adminMode, user?.role, user?.id]);

  useEffect(() => {
    setSearch(searchParams.get("q") || searchParams.get("seller") || "");
    setCategory(searchParams.get("category") || "all");
  }, [searchParams]);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const productPromise = apiRequest<{ items: Product[] } | Product[]>("/products/marketplace")
        .then((data) => (Array.isArray(data) ? { items: data as Product[] } : (data as { items?: Product[] })))
        .catch(() =>
          apiRequest<Product[] | { items: Product[] }>("/products/public")
            .then((data) => (Array.isArray(data) ? { items: data as Product[] } : (data as { items?: Product[] })))
            .catch(() => ({ items: [] as Product[] })),
        );

      const providerPromise = canManage(user?.role)
        ? apiRequest<Provider[]>("/providers/").catch(() => [])
        : Promise.resolve<Provider[]>([]);

      const inventoryPromise = !adminMode && !sellerMode
        ? Promise.resolve<InventoryStats | null>(null)
        : apiRequest<InventoryStats>("/products/inventory/stats").catch(() => null);

      const forecastPromise = sellerMode
        ? apiRequest<{ items: InventoryForecastItem[] }>("/business/inventory/forecast").catch(() => ({ items: [] as InventoryForecastItem[] }))
        : Promise.resolve<{ items: InventoryForecastItem[] }>({ items: [] });

      const [productData, providerData, inventoryData, forecastData] = await Promise.all([
        productPromise,
        providerPromise,
        inventoryPromise,
        forecastPromise,
      ]);
      setProducts(productData?.items || []);
      setProviders(Array.isArray(providerData) ? providerData : []);
      setInventory(inventoryData);
      setForecast(forecastData?.items || []);

      if (adminMode) {
        try {
          const sellers = await apiRequest<{ items: BusinessmanOption[] }>("/business/");
          setBusinessmen(sellers.items || []);
        } catch {
          setBusinessmen([]);
        }
      }
    } catch (err) {
      setProducts([]);
      setError(err instanceof Error ? err.message : "Failed to load products");
    } finally {
      setLoading(false);
    }
  }

  function resolveImageUrl(url?: string | null) {
    const raw = String(url || "").trim();
    if (!raw) return FALLBACK_IMAGE;
    if (/^https?:\/\//i.test(raw)) return raw;
    if (raw.startsWith("/")) return `${env.apiBase}${raw}`;
    return `${env.apiBase}/${raw.replace(/^\/+/, "")}`;
  }

  const categories = useMemo(
    () => ["all", ...Array.from(new Set(products.map((item) => item.category).filter(Boolean) as string[])).sort()],
    [products],
  );

  const visibleProducts = useMemo(() => {
    let data = [...products];
    if (category !== "all") {
      data = data.filter((item) => item.category === category);
    }
    if (search.trim()) {
      const keyword = search.toLowerCase();
      data = data.filter((item) =>
        `${item.name || ""} ${item.category || ""} ${item.seller_name || ""} ${item.seller?.business_name || ""}`
          .toLowerCase()
          .includes(keyword),
      );
    }
    if (sort === "price_low") data.sort((a, b) => (a.price || 0) - (b.price || 0));
    if (sort === "price_high") data.sort((a, b) => (b.price || 0) - (a.price || 0));
    return data;
  }, [products, category, search, sort]);

  function beginEdit(product: Product) {
    setEditingId(product.id);
    setDraft({
      name: String(product.name || ""),
      category: String(product.category || ""),
      price: String(product.price ?? ""),
      stock: String(product.stock ?? ""),
      description: String(product.description || ""),
      image_url: String(product.image_url || ""),
      provider_id: product.provider_id ? String(product.provider_id) : "",
      seller_id: product.seller_id ? String(product.seller_id) : "",
    });
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function resetForm() {
    setEditingId(null);
    setDraft(emptyDraft);
    setInsight(null);
    setFlash("");
    setError("");
    setShowForm(false);
  }

  async function generateInsight() {
    if (!draft.name.trim() || !draft.category.trim()) {
      setError("Enter a product name and category before generating AI insights.");
      return;
    }
    setGeneratingInsight(true);
    setError("");
    try {
      const data = await apiRequest<ProductInsight>("/products/ai-suggest", {
        method: "POST",
        body: {
          name: draft.name,
          category: draft.category,
          current_price: draft.price ? Number(draft.price) : null,
          stock: draft.stock ? Number(draft.stock) : null,
          description: draft.description || null,
          seller_area: user && "area" in user ? (user as never as { area?: string | null }).area : null,
        },
      });
      setInsight(data);
      setDraft((prev) => ({
        ...prev,
        description: data.description || prev.description,
        price: data.suggested_price ? String(Math.round(data.suggested_price)) : prev.price,
      }));
      setFlash("AI listing insight generated. Review and adjust before saving.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate AI product insight");
    } finally {
      setGeneratingInsight(false);
    }
  }

  async function handleCreateOrUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setFlash("");

    const payload = {
      name: draft.name.trim(),
      category: draft.category.trim(),
      price: Number(draft.price || 0),
      stock: Number(draft.stock || 0),
      description: draft.description.trim(),
      image_url: draft.image_url.trim() || null,
      provider_id: draft.provider_id ? Number(draft.provider_id) : null,
      seller_id: draft.seller_id ? Number(draft.seller_id) : null,
    };

    if (!payload.name || !payload.category || payload.price <= 0 || !payload.description) {
      setError("Please provide a valid product name, category, price, and description.");
      return;
    }

    try {
      if (editingId) {
        await apiRequest(`/products/${editingId}`, { method: "PUT", body: payload });
        setFlash("Product updated successfully.");
      } else {
        await apiRequest("/products/", { method: "POST", body: payload });
        setFlash("Product created successfully.");
      }
      resetForm();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save product");
    }
  }

  async function handleImageUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploadingImage(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const data = await apiRequest<{ image_url: string }>("/products/upload-image", {
        method: "POST",
        body: formData,
      });
      setDraft((prev) => ({ ...prev, image_url: data.image_url }));
      setFlash("Image uploaded successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Image upload failed. Please try again.");
    } finally {
      setUploadingImage(false);
      event.target.value = "";
    }
  }

  async function handleDelete(id: number) {
    if (!window.confirm("Are you sure you want to delete this product?")) return;
    try {
      await apiRequest(`/products/${id}`, { method: "DELETE" });
      await load();
      setFlash("Product deleted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete product");
    }
  }

  return (
    <div className="space-y-10 max-w-7xl mx-auto">
      <div className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-gradient-to-br from-slate-950 via-slate-900 to-brand/80 p-8 text-white shadow-[0_30px_80px_-20px_rgba(15,23,42,0.55)]">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,_rgba(255,255,255,0.18),_transparent_42%)]" />
        <div className="relative z-10 flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-[10px] font-black uppercase tracking-[0.3em] text-white/80 backdrop-blur">
              <Sparkles size={12} /> Curated marketplace
            </div>
            <div className="space-y-3">
              <h1 className="text-3xl font-display font-black tracking-tight sm:text-4xl">
                Discover premium listings with a calmer, more elegant buying experience.
              </h1>
              <p className="max-w-xl text-sm leading-7 text-slate-200 sm:text-base">
                Browse trusted products, compare standout offers, and move from discovery to checkout with confidence.
              </p>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              { label: "Live listings", value: products.length },
              { label: "Visible now", value: visibleProducts.length },
            ].map((item) => (
              <div key={item.label} className="rounded-2xl border border-white/15 bg-white/10 px-4 py-3 backdrop-blur">
                <p className="text-[10px] font-black uppercase tracking-[0.3em] text-white/60">{item.label}</p>
                <p className="mt-1 text-2xl font-display font-black">{item.value}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Inventory Stats Grid */}
      {inventory ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {[
            { label: "Total Inventory", value: inventory.total_products, icon: Box, color: "text-brand" },
            { label: "Low Stock", value: inventory.low_stock_count, icon: AlertTriangle, color: "text-amber-500" },
            { label: "Out of Stock", value: inventory.out_of_stock_count, icon: Package, color: "text-danger" },
            { label: "Total Value", value: formatMoney(inventory.total_value), icon: DollarSign, color: "text-emerald-500" }
          ].map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className="glass-card p-6 flex flex-col gap-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-black uppercase tracking-widest text-text-muted">{stat.label}</span>
                <div className={`w-8 h-8 rounded-lg bg-surface-soft flex items-center justify-center ${stat.color}`}>
                  <stat.icon size={16} />
                </div>
              </div>
              <strong className="text-3xl font-display font-black text-text">{stat.value}</strong>
            </motion.div>
          ))}
        </div>
      ) : null}

      {/* Forecasting Section */}
      {sellerMode && forecast.length ? (
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card overflow-hidden"
        >
          <div className="p-6 border-b border-border bg-surface-soft/30 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-display font-black text-text tracking-tight flex items-center gap-2">
                <Sparkles size={18} className="text-brand" />
                Smart Inventory Forecasting
              </h2>
              <p className="text-sm text-text-muted mt-1">AI-powered risk analysis based on your recent performance.</p>
            </div>
          </div>
          <div className="divide-y divide-border">
            {forecast.slice(0, 4).map((item) => (
              <div key={item.product_id} className="p-6 flex flex-wrap items-center justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <strong className="text-text font-bold block truncate">{item.product_name}</strong>
                  <div className="flex items-center gap-3 mt-1 text-sm text-text-muted">
                    <span className="flex items-center gap-1"><Box size={14} /> {item.current_stock} in stock</span>
                    <span className="flex items-center gap-1 text-emerald-500 font-semibold"><TrendingUp size={14} /> {item.daily_burn_rate.toFixed(1)}/day</span>
                  </div>
                </div>
                <div className="flex items-center gap-6">
                  <div className="text-right">
                    <span className="text-[10px] font-black uppercase tracking-widest text-text-muted block">Status</span>
                    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-black uppercase tracking-widest mt-1 ${
                      item.risk_level === "critical" ? "bg-danger/10 text-danger" :
                      item.risk_level === "watch" ? "bg-amber-500/10 text-amber-500" :
                      "bg-emerald-500/10 text-emerald-500"
                    }`}>
                      {item.risk_level || "healthy"}
                    </span>
                  </div>
                  <div className="text-right min-w-[100px]">
                    <span className="text-[10px] font-black uppercase tracking-widest text-text-muted block">Next Restock</span>
                    <span className="text-lg font-display font-black text-text">+{item.recommended_restock || 0}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      ) : null}

      {/* Management & Form Section */}
      {canManage(user?.role) && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-display font-black text-text tracking-tight">Product Management</h2>
            <button 
              onClick={() => setShowForm(!showForm)}
              className="btn-primary !py-2.5 flex items-center gap-2"
            >
              {showForm ? <X size={18} /> : <Plus size={18} />}
              {showForm ? "Cancel" : "List New Product"}
            </button>
          </div>

          <AnimatePresence>
            {showForm && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="glass-card p-8 space-y-8 bg-surface/50 border-brand/20">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-border">
                    <div>
                      <h3 className="text-xl font-display font-black text-text">{editingId ? `Edit Listing #${editingId}` : "Create New Marketplace Listing"}</h3>
                      <p className="text-sm text-text-muted mt-1">Optimization tips: Use high-res images and SEO tags.</p>
                    </div>
                    <button 
                      onClick={() => void generateInsight()} 
                      disabled={generatingInsight} 
                      className="inline-flex items-center gap-2 px-6 py-3 rounded-2xl bg-brand/10 text-brand font-black text-xs uppercase tracking-widest hover:bg-brand hover:text-white transition-all disabled:opacity-50"
                    >
                      <Sparkles size={16} className={generatingInsight ? "animate-spin" : ""} />
                      {generatingInsight ? "Analyzing Market..." : "Generate AI Insights"}
                    </button>
                  </div>

                  {error && <div className="p-4 bg-danger/10 text-danger rounded-2xl font-bold flex items-center gap-3 border border-danger/20">{error}</div>}
                  {flash && <div className="p-4 bg-accent/10 text-accent rounded-2xl font-bold flex items-center gap-3 border border-accent/20">{flash}</div>}

                  <form className="grid gap-8 md:grid-cols-2" onSubmit={handleCreateOrUpdate}>
                    <div className="space-y-2">
                      <label className="text-[11px] font-black uppercase tracking-widest text-text-muted ml-1">Product Name</label>
                      <input
                        className="w-full px-5 py-4 rounded-2xl border-2 border-transparent focus:border-brand/20 bg-surface outline-none transition-all font-semibold text-text placeholder:text-text-muted"
                        value={draft.name}
                        onChange={(e) => setDraft(prev => ({ ...prev, name: e.target.value }))}
                        placeholder="E.g. High-performance Solar Panel"
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-[11px] font-black uppercase tracking-widest text-text-muted ml-1">Category</label>
                      <input
                        className="w-full px-5 py-4 rounded-2xl border-2 border-transparent focus:border-brand/20 bg-surface outline-none transition-all font-semibold text-text"
                        value={draft.category}
                        onChange={(e) => setDraft(prev => ({ ...prev, category: e.target.value }))}
                        placeholder="Electronics, Energy, etc."
                        required
                      />
                    </div>

                    <div className="space-y-2">
                      <label className="text-[11px] font-black uppercase tracking-widest text-text-muted ml-1">Price (TZS)</label>
                      <input
                        type="number"
                        className="w-full px-5 py-4 rounded-2xl border-2 border-transparent focus:border-brand/20 bg-surface outline-none transition-all font-semibold text-text"
                        value={draft.price}
                        onChange={(e) => setDraft(prev => ({ ...prev, price: e.target.value }))}
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-[11px] font-black uppercase tracking-widest text-text-muted ml-1">Inventory Level</label>
                      <input
                        type="number"
                        className="w-full px-5 py-4 rounded-2xl border-2 border-transparent focus:border-brand/20 bg-surface outline-none transition-all font-semibold text-text"
                        value={draft.stock}
                        onChange={(e) => setDraft(prev => ({ ...prev, stock: e.target.value }))}
                        required
                      />
                    </div>

                    <div className="md:col-span-2 space-y-2">
                      <label className="text-[11px] font-black uppercase tracking-widest text-text-muted ml-1">Listing Description</label>
                      <textarea
                        rows={5}
                        className="w-full px-5 py-4 rounded-2xl border-2 border-transparent focus:border-brand/20 bg-surface outline-none transition-all font-semibold text-text resize-none"
                        value={draft.description}
                        onChange={(e) => setDraft(prev => ({ ...prev, description: e.target.value }))}
                        placeholder="Describe technical specs, warranty, and features..."
                        required
                      />
                    </div>

                    <div className="md:col-span-2 space-y-4">
                      <label className="text-[11px] font-black uppercase tracking-widest text-text-muted ml-1">Product Assets</label>
                      <div className="grid gap-4 md:grid-cols-2">
                        <div className="relative group/upload">
                          <input
                            type="file"
                            accept="image/*"
                            className="hidden"
                            id="image-upload"
                            onChange={handleImageUpload}
                            disabled={uploadingImage}
                          />
                          <label 
                            htmlFor="image-upload"
                            className="flex flex-col items-center justify-center gap-3 w-full h-32 rounded-2xl border-2 border-dashed border-border bg-surface-soft/50 hover:bg-surface-soft hover:border-brand transition-all cursor-pointer"
                          >
                            <Upload size={24} className={uploadingImage ? "animate-bounce text-brand" : "text-text-muted"} />
                            <span className="text-xs font-bold text-text-muted">{uploadingImage ? "Uploading..." : "Click to Upload Photo"}</span>
                          </label>
                        </div>
                        <div className="space-y-2">
                          <input
                            type="text"
                            placeholder="Or paste high-res image URL"
                            className="w-full px-5 py-4 h-32 rounded-2xl border-2 border-transparent focus:border-brand/20 bg-surface outline-none transition-all font-semibold text-text"
                            value={draft.image_url}
                            onChange={(e) => setDraft(prev => ({ ...prev, image_url: e.target.value }))}
                          />
                        </div>
                      </div>
                    </div>

                    {draft.image_url && (
                      <div className="md:col-span-2 flex justify-center p-6 bg-surface-soft rounded-[2rem] border border-border">
                        <img src={resolveImageUrl(draft.image_url)} alt="Preview" className="h-64 rounded-2xl object-cover shadow-2xl border-4 border-surface" />
                      </div>
                    )}

                    {insight && (
                      <motion.div 
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="md:col-span-2 rounded-[2rem] bg-brand text-white p-8 relative overflow-hidden"
                      >
                        <div className="absolute top-0 right-0 p-8 opacity-10"><Sparkles size={120} /></div>
                        <div className="relative z-10 space-y-6">
                          <div className="flex items-start justify-between">
                            <div>
                              <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/20 text-[10px] font-black uppercase tracking-widest border border-white/20">
                                <Sparkles size={12} /> AI Strategy Insight
                              </span>
                              <h4 className="text-2xl font-display font-black mt-3">Smart Pricing Analysis</h4>
                              <p className="text-white/70 font-medium mt-1">{insight.trend_summary}</p>
                            </div>
                            <div className="h-16 w-16 rounded-2xl bg-white/10 flex flex-col items-center justify-center border border-white/10 backdrop-blur-md">
                              <span className="text-xs font-bold opacity-60">Conf.</span>
                              <span className="text-xl font-black">{Math.round((insight.confidence || 0) * 100)}%</span>
                            </div>
                          </div>
                          
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                            <div className="p-4 rounded-2xl bg-white/10 border border-white/10 backdrop-blur-md">
                              <span className="text-[10px] font-black uppercase tracking-widest opacity-60">Suggested Price</span>
                              <p className="text-lg font-black mt-1">{formatMoney(insight.suggested_price)}</p>
                            </div>
                            <div className="p-4 rounded-2xl bg-white/10 border border-white/10 backdrop-blur-md">
                              <span className="text-[10px] font-black uppercase tracking-widest opacity-60">Market Range</span>
                              <p className="text-sm font-black mt-1">{formatMoney(insight.price_range?.low)} - {formatMoney(insight.price_range?.high)}</p>
                            </div>
                            <div className="p-4 rounded-2xl bg-white/10 border border-white/10 backdrop-blur-md">
                              <span className="text-[10px] font-black uppercase tracking-widest opacity-60">Demand Level</span>
                              <p className="text-sm font-black mt-1 uppercase tracking-widest">{insight.demand_level}</p>
                            </div>
                            <div className="p-4 rounded-2xl bg-white/10 border border-white/10 backdrop-blur-md">
                              <span className="text-[10px] font-black uppercase tracking-widest opacity-60">Benchmark Avg</span>
                              <p className="text-sm font-black mt-1">{formatMoney(insight.price_range?.benchmark_average)}</p>
                            </div>
                          </div>
                        </div>
                      </motion.div>
                    )}

                    <div className="flex flex-wrap gap-4 md:col-span-2 pt-4 border-t border-border">
                      <button className="btn-primary !px-10 h-14" type="submit">{editingId ? "Update Listing" : "Launch Listing"}</button>
                      <button className="btn-secondary !px-10 h-14" type="button" onClick={resetForm}>Discard Changes</button>
                    </div>
                  </form>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* Main Filter & Grid Section */}
      <div className="space-y-8">
        <div className="flex flex-col lg:flex-row lg:items-center gap-6 justify-between bg-surface border border-border p-6 rounded-[2rem]">
          <div className="flex-1 relative group">
            <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-text-muted group-focus-within:text-brand transition-colors" />
            <input
              className="w-full pl-12 pr-4 py-3 rounded-2xl bg-surface-soft border border-transparent focus:border-brand/20 outline-none font-bold text-text transition-all"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search inventory, sellers, categories..."
            />
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-3 px-4 py-3 bg-surface-soft rounded-2xl border border-transparent">
              <Filter size={16} className="text-text-muted" />
              <select
                className="bg-transparent outline-none font-bold text-sm text-text pr-2"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                {categories.map(c => <option key={c} value={c}>{c === 'all' ? 'All Categories' : c.charAt(0).toUpperCase() + c.slice(1)}</option>)}
              </select>
            </div>
            <div className="flex items-center gap-3 px-4 py-3 bg-surface-soft rounded-2xl border border-transparent">
              <ArrowUpDown size={16} className="text-text-muted" />
              <select
                className="bg-transparent outline-none font-bold text-sm text-text pr-2"
                value={sort}
                onChange={(e) => setSort(e.target.value)}
              >
                <option value="featured">Best Matches</option>
                <option value="price_low">Price: Low to High</option>
                <option value="price_high">Price: High to Low</option>
              </select>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-8">
          <AnimatePresence>
            {loading ? (
              <div className="col-span-full py-20 flex flex-col items-center justify-center gap-4">
                <div className="w-12 h-12 border-4 border-brand/20 border-t-brand rounded-full animate-spin" />
                <p className="font-bold text-text-muted">Synchronizing marketplace data...</p>
              </div>
            ) : visibleProducts.length === 0 ? (
              <div className="col-span-full glass-card p-20 text-center space-y-4">
                <div className="w-20 h-20 bg-surface-soft rounded-3xl flex items-center justify-center mx-auto text-text-muted"><Search size={40} /></div>
                <h3 className="text-2xl font-black text-text">Inventory is empty</h3>
                <p className="text-text-muted max-w-sm mx-auto">Try adjusting your filters or search keywords to find what you're looking for.</p>
              </div>
            ) : (
              visibleProducts.map((product) => (
                <motion.article
                  key={product.id}
                  layout
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  className="group flex h-full flex-col overflow-hidden rounded-[1.75rem] border border-slate-200/70 bg-white/90 shadow-[0_20px_60px_-20px_rgba(15,23,42,0.25)] backdrop-blur transition-all duration-300 hover:-translate-y-1 hover:border-brand/30 hover:shadow-[0_28px_70px_-20px_rgba(59,130,246,0.35)]"
                >
                  <div 
                    className="relative aspect-[4/5] cursor-pointer overflow-hidden bg-surface-soft" 
                    onClick={() => navigate(`/product/${product.id}`)}
                  >
                    <img
                      src={resolveImageUrl(product.image_url)}
                      alt={product.name}
                      className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-110"
                      loading="lazy"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-950/70 via-slate-950/10 to-transparent" />
                    <div className="absolute top-4 left-4 flex flex-col gap-2">
                      <span className="rounded-full border border-white/50 bg-white/90 px-3 py-1 text-[10px] font-black uppercase tracking-widest text-text shadow-sm backdrop-blur-md">
                        {product.category || "General"}
                      </span>
                      {product.stock && product.stock <= 5 && (
                        <span className="flex items-center gap-1.5 rounded-full bg-danger/90 px-3 py-1 text-[10px] font-black uppercase tracking-widest text-white shadow-sm backdrop-blur-md">
                          <AlertTriangle size={12} /> Low Stock
                        </span>
                      )}
                    </div>
                    {canEditProduct(product, user?.role, user?.id) && (
                      <div className="absolute top-4 right-4 flex gap-2 translate-x-12 group-hover:translate-x-0 transition-transform duration-300">
                        <button 
                          onClick={(e) => { e.stopPropagation(); beginEdit(product); }}
                          className="h-10 w-10 rounded-xl bg-white/90 backdrop-blur-md text-text hover:bg-brand hover:text-white transition-all shadow-lg flex items-center justify-center border border-white/50"
                        >
                          <Edit2 size={16} />
                        </button>
                        <button 
                          onClick={(e) => { e.stopPropagation(); handleDelete(product.id); }}
                          className="h-10 w-10 rounded-xl bg-white/90 backdrop-blur-md text-danger hover:bg-danger hover:text-white transition-all shadow-lg flex items-center justify-center border border-white/50"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-1 flex-col gap-6 p-6">
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <Store size={14} className="text-text-muted" />
                        <span className="truncate text-[10px] font-bold uppercase tracking-widest text-text-muted">{product.seller_name || "Independent Seller"}</span>
                      </div>
                      <h3 className="cursor-pointer font-display text-lg font-bold leading-tight text-text transition-colors line-clamp-2 group-hover:text-brand" onClick={() => navigate(`/product/${product.id}`)}>
                        {product.name}
                      </h3>
                    </div>

                    <div className="mt-auto flex items-end justify-between border-t border-border pt-4">
                      <div>
                        <span className="text-[10px] font-black uppercase tracking-widest text-text-muted block leading-none mb-1">Price</span>
                        <span className="text-2xl font-display font-black text-text tracking-tight">{formatMoney(product.price)}</span>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
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
                        disabled={!(product.stock && product.stock > 0)}
                        className="h-12 px-5 rounded-xl bg-gradient-to-r from-slate-900 to-brand text-white flex items-center gap-2 font-black text-xs uppercase tracking-widest shadow-lg shadow-brand/20 hover:shadow-brand/30 active:scale-95 transition-all disabled:cursor-not-allowed disabled:opacity-35"
                      >
                        <Plus size={18} />
                        {product.stock && product.stock > 0 ? "Add to Cart" : "Out of Stock"}
                      </button>
                    </div>
                  </div>
                </motion.article>
              ))
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
