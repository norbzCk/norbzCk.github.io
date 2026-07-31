import { FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { 
  User, 
  Lock, 
  Eye, 
  EyeOff, 
  ArrowRight, 
  AlertCircle,
  Loader2,
  Shield
} from "lucide-react";
import { AuthScene } from "../components/AuthScene";
import { useAuth } from "../features/auth/AuthContext";

export function SuperadminLoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") || "").trim().toLowerCase();
    const password = String(form.get("password") || "");

    try {
      await login(email, password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from || "/app/superadmin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthScene
      eyebrow="System Administration"
      title="Superadmin Access"
      description="Secure access for system administrators with full platform control."
      bullets={[
        "Manage all users and businesses",
        "View platform analytics and reports",
        "Full system configuration access",
      ]}
      links={[
        { to: "/login", label: "Regular login" },
      ]}
    >
      <div className="space-y-10">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <Shield size={28} className="text-brand" />
            <h2 className="text-3xl font-display font-black text-text tracking-tight">Superadmin Login</h2>
          </div>
          <p className="text-text-muted font-medium">Enterprise-grade administrative control panel.</p>
        </div>

        {error ? (
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="p-4 bg-danger/10 text-danger rounded-2xl font-bold flex items-center gap-3 border border-danger/20 text-sm"
          >
            <AlertCircle size={18} />
            {error}
          </motion.div>
        ) : null}

        <form className="space-y-6" onSubmit={handleLogin}>
          <div className="space-y-2">
            <label className="text-[11px] font-black uppercase tracking-widest text-text-muted ml-1">Administrator Email</label>
            <div className="relative group">
              <div className="absolute left-5 top-1/2 -translate-y-1/2 text-text-muted group-focus-within:text-brand transition-colors">
                <User size={18} />
              </div>
              <input 
                name="email" 
                type="email"
                className="w-full h-14 pl-12 pr-5 bg-surface-soft border border-transparent focus:border-brand/30 focus:bg-surface rounded-2xl outline-none transition-all font-semibold text-text placeholder:text-text-muted"
                placeholder="admin@sokolink.com"
                required 
              />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between px-1">
              <label className="text-[11px] font-black uppercase tracking-widest text-text-muted">Admin Key</label>
            </div>
            <div className="relative group">
              <div className="absolute left-5 top-1/2 -translate-y-1/2 text-text-muted group-focus-within:text-brand transition-colors">
                <Lock size={18} />
              </div>
              <input
                name="password"
                type={showPassword ? "text" : "password"}
                className="w-full h-14 pl-12 pr-14 bg-surface-soft border border-transparent focus:border-brand/30 focus:bg-surface rounded-2xl outline-none transition-all font-semibold text-text placeholder:text-text-muted"
                placeholder="Enter admin passphrase"
                required
              />
              <button
                type="button"
                className="absolute right-4 top-1/2 -translate-y-1/2 p-2 text-text-muted hover:text-brand transition-colors"
                onClick={() => setShowPassword((prev) => !prev)}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          <button 
            className="w-full h-16 btn-primary shadow-brand/40 group active:scale-[0.98]" 
            disabled={isSubmitting} 
            type="submit"
          >
            {isSubmitting ? (
              <div className="flex items-center justify-center gap-2 font-black text-sm uppercase tracking-widest">
                <Loader2 size={20} className="animate-spin" />
                Authenticating...
              </div>
            ) : (
              <div className="flex items-center justify-center gap-2 font-black text-sm uppercase tracking-widest">
                Sign In as Superadmin
                <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
              </div>
            )}
          </button>
        </form>

        <div className="pt-8 border-t border-border flex flex-col items-center gap-6">
          <p className="text-sm font-bold text-text-muted">
            Not an admin? <Link to="/login" className="text-brand hover:underline">Regular login</Link>
          </p>
          <div className="flex flex-wrap justify-center gap-8">
            <Link to="/" className="text-[10px] font-black uppercase tracking-widest text-text-muted hover:text-brand transition-colors">Home</Link>
            <Link to="/register/business" className="text-[10px] font-black uppercase tracking-widest text-text-muted hover:text-brand transition-colors">Merchant</Link>
            <Link to="/register/logistics" className="text-[10px] font-black uppercase tracking-widest text-text-muted hover:text-brand transition-colors">Logistics</Link>
          </div>
        </div>
      </div>
    </AuthScene>
  );
}
