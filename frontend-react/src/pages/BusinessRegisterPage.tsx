import { FormEvent, useState } from "react";
import { AuthScene } from "../components/AuthScene";
import { persistSession } from "../features/auth/authStorage";
import type { SessionUser } from "../types/auth";
import { apiRequest } from "../lib/http";
import { useAuth } from "../features/auth/AuthContext";

export function BusinessRegisterPage() {
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { register: supabaseRegister } = useAuth();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSuccess("");
    setIsSubmitting(true);

    const form = new FormData(event.currentTarget);
    const payload = {
      business_name: String(form.get("business_name") || "").trim(),
      owner_name: String(form.get("owner_name") || "").trim(),
      email: String(form.get("email") || "").trim().toLowerCase(),
      phone: String(form.get("phone") || "").trim(),
      password: String(form.get("password") || ""),
      business_type: String(form.get("business_type") || "individual"),
      category: String(form.get("category") || "").trim() || null,
      description: String(form.get("description") || "").trim() || null,
      region: String(form.get("region") || "Dar es Salaam"),
      area: String(form.get("area") || "").trim() || null,
      street: String(form.get("street") || "").trim() || null,
      shop_number: String(form.get("shop_number") || "").trim() || null,
      operating_hours: String(form.get("operating_hours") || "").trim() || null,
      shop_logo_url: String(form.get("shop_logo_url") || "").trim() || null,
      shop_images: String(form.get("shop_images") || "").trim() || null,
      role: "seller",
    };

    try {
      // Step 1: Create a Supabase Auth account (handles email verification, password reset)
      await supabaseRegister({
        name: payload.business_name,
        email: payload.email,
        password: payload.password,
        phone: payload.phone,
        userType: "business",
      });

      // Step 2: Create the detailed BusinessUser record in the app DB
      const data = await apiRequest<{ user?: SessionUser }>("/business/register", {
        method: "POST",
        body: payload,
      });

      if (data.user) {
        persistSession(localStorage.getItem("access_token") || "", { ...data.user, role: "seller" }, "business");
      }
      setSuccess("Business registered successfully.");
      setTimeout(() => {
        window.location.href = "/app/seller";
      }, 900);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  const InputField = ({ name, label, type = "text", required = false, placeholder = "", defaultValue = "" }: any) => (
    <div className="space-y-1.5">
      <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 ml-1">{label}</label>
      <input 
        name={name}
        type={type}
        required={required}
        placeholder={placeholder}
        defaultValue={defaultValue}
        className="w-full px-4 py-3 bg-slate-50 border-2 border-transparent focus:border-brand/20 focus:bg-white rounded-xl outline-none transition-all font-semibold text-sm"
      />
    </div>
  );

  return (
    <AuthScene
      eyebrow="Business onboarding"
      title="Open your business storefront on SokoLnk."
      description="Set up your seller profile and organize your product catalog instantly."
      bullets={[
        "Create a seller-ready account in one step",
        "Build trust with verified badges",
        "Access advanced marketplace analytics",
      ]}
      links={[
        { to: "/login", label: "Back to sign in" },
        { to: "/register/customer", label: "Join as customer" },
      ]}
    >
      <div className="space-y-8 max-w-2xl mx-auto lg:max-w-none">
        <div className="space-y-1">
          <h2 className="text-2xl font-display font-extrabold text-slate-900 tracking-tight">Business Registration</h2>
          <p className="text-slate-500 font-medium">Launch your digital storefront today.</p>
        </div>

        {error ? (
          <div className="p-4 bg-red-50 text-red-700 rounded-2xl font-bold flex items-center gap-3 border border-red-100">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            {error}
          </div>
        ) : null}

        {success ? (
          <div className="p-4 bg-emerald-50 text-emerald-700 rounded-2xl font-bold flex items-center gap-3 border border-emerald-100">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            {success}
          </div>
        ) : null}

        <form className="grid grid-cols-1 md:grid-cols-2 gap-4" onSubmit={handleSubmit}>
          <InputField name="business_name" label="Business Name" required placeholder="E.g. Soko Retailers" />
          <InputField name="owner_name" label="Owner Name" required placeholder="Full Name" />
          <InputField name="email" label="Email Address" type="email" required placeholder="business@example.com" />
          <InputField name="phone" label="Phone Number" required placeholder="07..." />
          
          <div className="space-y-1.5">
            <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 ml-1">Business Type</label>
            <select name="business_type" defaultValue="individual" className="w-full px-4 py-3 bg-slate-50 border-2 border-transparent focus:border-brand/20 focus:bg-white rounded-xl outline-none transition-all font-semibold text-sm appearance-none cursor-pointer">
              <option value="individual">Individual trader</option>
              <option value="company">Registered company</option>
            </select>
          </div>

          <InputField name="category" label="Category" placeholder="E.g. Electronics" />
          <InputField name="region" label="Region" defaultValue="Dar es Salaam" />
          <InputField name="area" label="Area" placeholder="E.g. Kariakoo" />
          <InputField name="street" label="Street Address" />
          <InputField name="shop_number" label="Shop Number" />
          <InputField name="operating_hours" label="Operating Hours" placeholder="Mon-Sat 08:00-18:00" />
          <InputField name="shop_logo_url" label="Shop Logo URL" />
          
          <div className="md:col-span-2">
            <InputField name="description" label="Business Description" placeholder="Describe your business and what you sell..." />
          </div>
          
          <div className="md:col-span-2">
            <InputField name="password" label="Password" type="password" required placeholder="••••••••" />
          </div>

          <div className="md:col-span-2 pt-4">
            <button 
              className="w-full btn-primary !py-4 shadow-brand/30" 
              disabled={isSubmitting} 
              type="submit"
            >
              {isSubmitting ? "Onboarding..." : "Register Business"}
            </button>
          </div>
        </form>
      </div>
    </AuthScene>
  );
}
