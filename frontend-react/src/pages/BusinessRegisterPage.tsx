import { FormEvent, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AuthScene } from "../components/AuthScene";
import { apiRequest } from "../lib/http";

export function BusinessRegisterPage() {
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleLogoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] || null;
    setLogoFile(file);
    if (file) {
      setLogoPreview(URL.createObjectURL(file));
    } else {
      setLogoPreview(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    const form = new FormData(event.currentTarget);
    // FormData already picked up every named <input>/<select> in the form,
    // including the file input (name="logo") if one was chosen -- just
    // trim the text fields in place rather than rebuilding the payload.
    for (const key of ["business_name", "owner_name", "email", "phone", "area", "street", "shop_number", "operating_hours", "description"]) {
      const value = form.get(key);
      if (typeof value === "string") form.set(key, value.trim());
    }
    const emailValue = String(form.get("email") || "").toLowerCase();
    form.set("email", emailValue);

    try {
      // Single call: /business/register creates the account, sets auth
      // cookies, and returns its own access token -- it doesn't need (and
      // previously was broken by) a separate pre-registration step.
      await apiRequest("/business/register", {
        method: "POST",
        body: form,
        auth: false,
      });

      // Redirect to login rather than auto-logging in: keeps registration
      // and authentication as two clearly separate steps, and avoids ever
      // risking a mismatched session (the bug this used to have, where the
      // stored token didn't match the account that was actually created).
      navigate("/login?registered=seller", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
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

        <form className="grid grid-cols-1 md:grid-cols-2 gap-4" onSubmit={handleSubmit}>
          <InputField name="business_name" label="Business Name" required placeholder="E.g. Soko Retailers" />
          <InputField name="owner_name" label="Owner Name" required placeholder="Full Name" />
          <InputField name="email" label="Email Address" type="email" placeholder="business@example.com" />
          <InputField name="phone" label="Phone Number" required placeholder="0712345678" />
          
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

          <div className="space-y-1.5">
            <label className="text-[10px] font-black uppercase tracking-widest text-slate-400 ml-1">Shop Logo</label>
            <div className="flex items-center gap-3">
              {logoPreview ? (
                <img src={logoPreview} alt="Logo preview" className="h-12 w-12 rounded-xl object-cover border-2 border-slate-100" />
              ) : (
                <div className="h-12 w-12 rounded-xl bg-slate-100 flex items-center justify-center text-slate-300 text-lg font-black">?</div>
              )}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="flex-1 px-4 py-3 bg-slate-50 border-2 border-dashed border-slate-200 hover:border-brand/40 rounded-xl outline-none transition-all font-semibold text-sm text-slate-500 text-left truncate"
              >
                {logoFile ? logoFile.name : "Choose an image..."}
              </button>
              <input
                ref={fileInputRef}
                name="logo"
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif"
                onChange={handleLogoChange}
                className="hidden"
              />
            </div>
          </div>
          
          <div className="md:col-span-2">
            <InputField name="description" label="Business Description" placeholder="Describe your business and what you sell..." />
          </div>
          
          <div className="md:col-span-2">
            <InputField name="password" label="Password" type="password" required placeholder="At least 8 characters, with a number and symbol" />
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
