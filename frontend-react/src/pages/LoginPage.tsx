import { FormEvent, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { 
  User, 
  Lock, 
  Eye, 
  EyeOff, 
  ArrowRight, 
  AlertCircle,
  CheckCircle2,
  Loader2
} from "lucide-react";
import { AuthScene } from "../components/AuthScene";
import { useAuth } from "../features/auth/AuthContext";
import { getPostLoginPath } from "../features/auth/authStorage";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const registeredAs = searchParams.get("registered");
  const welcomeMessages: Record<string, string> = {
    seller: "Your business account was created. Sign in to set up your storefront.",
    customer: "Your account was created. Sign in to start shopping.",
    logistics: "Your logistics account was created. Sign in to go online and start accepting deliveries.",
  };
  const { login } = useAuth();
  const { sendSmsOtp, verifySmsOtp } = useAuth() as any;
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [smsMode, setSmsMode] = useState(false);
  const [otpSent, setOtpSent] = useState(false);
  const [phoneValue, setPhoneValue] = useState("");
  const [otpValue, setOtpValue] = useState("");

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    const form = new FormData(event.currentTarget);
    const identifier = String(form.get("identifier") || "").trim();
    const password = String(form.get("password") || "");

    try {
      if (smsMode) {
        // In SMS mode, identifier contains phone and password field is OTP
        const phone = identifier;
        const token = password;
        await verifySmsOtp(phone, token);
        // successful; navigate to home
        const from = (location.state as { from?: string } | null)?.from;
        navigate(from || getPostLoginPath(null as any));
        return;
      }

      const user = await login(identifier, password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from || getPostLoginPath(user));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthScene
      eyebrow="Identity Secured"
      title="Access your workspace"
      description="Enter your credentials to manage your marketplace activity and track your performance."
      bullets={[
        "Biometric-ready security layers",
        "Unified session management",
        "Instant performance sync"
      ]}
      links={[
        { to: "/register/customer", label: "Create account" },
        { to: "/forgot-password", label: "Recover access" },
        { to: "/superadmin", label: "Admin portal" }
      ]}
    >
      <div className="space-y-10">
        <div className="space-y-2">
          <h2 className="text-3xl font-display font-black text-text tracking-tight">Sign In</h2>
          <p className="text-text-muted font-medium">Welcome back to the smart marketplace.</p>
        </div>

        {registeredAs && welcomeMessages[registeredAs] && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="p-4 bg-emerald-500/10 text-emerald-600 rounded-2xl font-bold flex items-center gap-3 border border-emerald-500/20 text-sm"
          >
            <CheckCircle2 size={18} />
            Welcome to SokoLnk! {welcomeMessages[registeredAs]}
          </motion.div>
        )}

        {error && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="p-4 bg-danger/10 text-danger rounded-2xl font-bold flex items-center gap-3 border border-danger/20 text-sm"
          >
            <AlertCircle size={18} />
            {error}
          </motion.div>
        )}

        <form className="space-y-6" onSubmit={handleLogin}>
          <div className="space-y-2">
            <label className="text-[11px] font-black uppercase tracking-widest text-text-muted ml-1">Identity</label>
            <div className="relative group">
              <div className="absolute left-5 top-1/2 -translate-y-1/2 text-text-muted group-focus-within:text-brand transition-colors">
                <User size={18} />
              </div>
              <input 
                name="identifier" 
                value={smsMode ? phoneValue : undefined}
                onChange={smsMode ? (e) => setPhoneValue(e.target.value) : undefined}
                className="w-full h-14 pl-12 pr-5 bg-surface-soft border border-transparent focus:border-brand/30 focus:bg-surface rounded-2xl outline-none transition-all font-semibold text-text placeholder:text-text-muted"
                placeholder={smsMode ? "Phone (e.g. +255700...)" : "Email or Phone"} 
                required 
              />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between px-1">
              <label className="text-[11px] font-black uppercase tracking-widest text-text-muted">Passphrase</label>
            </div>
            <div className="relative group">
              <div className="absolute left-5 top-1/2 -translate-y-1/2 text-text-muted group-focus-within:text-brand transition-colors">
                <Lock size={18} />
              </div>
              <input
                name="password"
                value={smsMode ? otpValue : undefined}
                onChange={smsMode ? (e) => setOtpValue(e.target.value) : undefined}
                type={smsMode ? "text" : (showPassword ? "text" : "password")}
                className="w-full h-14 pl-12 pr-14 bg-surface-soft border border-transparent focus:border-brand/30 focus:bg-surface rounded-2xl outline-none transition-all font-semibold text-text placeholder:text-text-muted"
                placeholder={smsMode ? "One-time code" : "Secure Key"}
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
                Validating...
              </div>
            ) : (
              <div className="flex items-center justify-center gap-2 font-black text-sm uppercase tracking-widest">
                Sign In to Platform
                <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
              </div>
            )}
          </button>
        </form>

        <div className="mt-4 flex items-center justify-between">
          <label className="inline-flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={smsMode} onChange={(e) => setSmsMode(e.target.checked)} />
            <span className="font-medium">Sign in with SMS OTP</span>
          </label>
          <button
            className="text-sm text-brand underline"
            onClick={async () => {
              if (!smsMode) return setSmsMode(true);
              // send OTP
              try {
                setError("");
                const phone = phoneValue.trim();
                if (!phone) throw new Error("Enter phone number first");
                await sendSmsOtp(phone);
                setOtpSent(true);
              } catch (err) {
                setError(err instanceof Error ? err.message : String(err));
              }
            }}
          >
            {otpSent ? "Resend OTP" : "Send OTP"}
          </button>
        </div>

        <div className="pt-8 border-t border-border flex flex-col items-center gap-6">
          <p className="text-sm font-bold text-text-muted">
            New to the network? <Link to="/register/customer" className="text-brand hover:underline">Join now</Link>
          </p>
          <div className="flex flex-wrap justify-center gap-8">
            <Link to="/register/business" className="text-[10px] font-black uppercase tracking-widest text-text-muted hover:text-brand transition-colors">Merchant</Link>
            <Link to="/register/logistics" className="text-[10px] font-black uppercase tracking-widest text-text-muted hover:text-brand transition-colors">Logistics</Link>
            <Link to="/" className="text-[10px] font-black uppercase tracking-widest text-text-muted hover:text-brand transition-colors">Home</Link>
          </div>
        </div>
      </div>
    </AuthScene>
  );
}
