import { FormEvent, useState } from "react";
import { AuthScene } from "../components/AuthScene";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../lib/http";

export function CustomerRegisterPage() {
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    const form = new FormData(event.currentTarget);
    const payload = {
      name: String(form.get("name") || "").trim(),
      email: String(form.get("email") || "").trim().toLowerCase(),
      phone: String(form.get("phone") || "").trim(),
      password: String(form.get("password") || ""),
    };

    try {
      // Called directly rather than through AuthContext's register(), which
      // auto-persists a session on success -- registration and signing in
      // are kept as two separate steps here, consistent with the seller
      // and logistics registration flows.
      await apiRequest("/auth/register", {
        method: "POST",
        body: payload,
        auth: false,
      });
      navigate("/login?registered=customer", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
      setIsSubmitting(false);
    }
  }

  return (
    <AuthScene
      eyebrow="Customer onboarding"
      title="Create your buyer account and start sourcing."
      description="Join the marketplace, compare suppliers, and track orders inside the customer dashboard."
      bullets={[
        "Browse verified products and suppliers",
        "Submit RFQs and place orders faster",
        "Track payments and delivery progress",
      ]}
      links={[
        { to: "/login", label: "Back to sign in" },
        { to: "/register/business", label: "Need a seller account?" },
      ]}
    >
      <div className="space-y-8">
        <div className="space-y-1">
          <h2 className="text-2xl font-display font-extrabold text-slate-900 tracking-tight">Customer Registration</h2>
          <p className="text-slate-500 font-medium">Enter your details to create your account.</p>
        </div>

        {error ? (
          <div className="p-4 bg-red-50 text-red-700 rounded-2xl font-bold flex items-center gap-3 border border-red-100 animate-in fade-in slide-in-from-top-2">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            {error}
          </div>
        ) : null}

        <form className="space-y-5" onSubmit={handleSubmit}>
          <div className="space-y-2">
            <label className="text-[11px] font-black uppercase tracking-widest text-slate-400 ml-1">Full Name</label>
            <input 
              name="name" 
              className="w-full px-5 py-3.5 bg-slate-50 border-2 border-transparent focus:border-brand/20 focus:bg-white rounded-2xl outline-none transition-all font-semibold"
              placeholder="John Doe"
              required 
            />
          </div>
          <div className="space-y-2">
            <label className="text-[11px] font-black uppercase tracking-widest text-slate-400 ml-1">Email Address</label>
            <input 
              name="email" 
              type="email" 
              className="w-full px-5 py-3.5 bg-slate-50 border-2 border-transparent focus:border-brand/20 focus:bg-white rounded-2xl outline-none transition-all font-semibold"
              placeholder="john@example.com"
              required 
            />
          </div>
          <div className="space-y-2">
            <label className="text-[11px] font-black uppercase tracking-widest text-slate-400 ml-1">Phone Number</label>
            <input 
              name="phone" 
              className="w-full px-5 py-3.5 bg-slate-50 border-2 border-transparent focus:border-brand/20 focus:bg-white rounded-2xl outline-none transition-all font-semibold"
              placeholder="07..."
              required 
            />
          </div>
          <div className="space-y-2">
            <label className="text-[11px] font-black uppercase tracking-widest text-slate-400 ml-1">Password</label>
            <input 
              name="password" 
              type="password" 
              className="w-full px-5 py-3.5 bg-slate-50 border-2 border-transparent focus:border-brand/20 focus:bg-white rounded-2xl outline-none transition-all font-semibold"
              placeholder="••••••••"
              required 
            />
          </div>
          <button 
            className="w-full btn-primary !py-4 shadow-brand/30 mt-4" 
            disabled={isSubmitting} 
            type="submit"
          >
            {isSubmitting ? "Processing..." : "Register Account"}
          </button>
        </form>
      </div>
    </AuthScene>
  );
}
