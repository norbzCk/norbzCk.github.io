import { FormEvent, useState } from "react";
import { AuthScene } from "../components/AuthScene";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../lib/http";
import { persistSession } from "../features/auth/authStorage";
import type { SessionUser } from "../types/auth";

export function CustomerRegisterPage() {
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSuccess("");
    setIsSubmitting(true);

    const form = new FormData(event.currentTarget);
    const payload = {
      name: String(form.get("name") || "").trim(),
      email: String(form.get("email") || "").trim().toLowerCase(),
      phone: String(form.get("phone") || "").trim(),
      password: String(form.get("password") || ""),
    };

    try {
      const data = await apiRequest<{ access_token?: string; user?: SessionUser; userType?: string }>("/auth/register-customer", {
        method: "POST",
        auth: false,
        body: payload,
      });
      if (data.access_token && data.user) {
        persistSession(data.access_token, data.user, data.userType || "user");
      }
      setSuccess("Customer registered successfully.");
      setTimeout(() => navigate("/app/customer"), 900);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
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

        {success ? (
          <div className="p-4 bg-emerald-50 text-emerald-700 rounded-2xl font-bold flex items-center gap-3 border border-emerald-100 animate-in fade-in slide-in-from-top-2">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            {success}
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
