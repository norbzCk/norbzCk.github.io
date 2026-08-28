import { FormEvent, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AuthScene } from "../components/AuthScene";
import { apiRequest } from "../lib/http";

export function LogisticsRegisterPage() {
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handlePhotoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] || null;
    setPhotoFile(file);
    setPhotoPreview(file ? URL.createObjectURL(file) : null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    const form = new FormData(event.currentTarget);
    for (const key of ["name", "phone", "vehicle_type", "plate_number", "license_number", "base_area", "coverage_areas"]) {
      const value = form.get(key);
      if (typeof value === "string") form.set(key, value.trim());
    }
    form.set("email", String(form.get("email") || "").trim().toLowerCase());

    try {
      // Single call: /logistics/register creates the account and sets auth
      // cookies itself -- no separate pre-registration step needed.
      await apiRequest("/logistics/register", {
        method: "POST",
        body: form,
        auth: false,
      });

      navigate("/login?registered=logistics", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
      setIsSubmitting(false);
    }
  }

  return (
    <AuthScene
      eyebrow="Logistics onboarding"
      title="Join the delivery network for SokoLnk orders."
      description="Register a rider or delivery company, manage live availability, and update order statuses seamlessly."
      bullets={[
        "Go online and manage availability in real time",
        "Track assigned deliveries and update statuses",
        "Use the same logistics API contract as the legacy app",
      ]}
      links={[
        { to: "/login", label: "Back to sign in" },
        { to: "/register/customer", label: "Join as customer" },
      ]}
    >
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-brand mb-2">Logistics partner</p>
          <h2 className="text-2xl font-display font-bold text-slate-900 dark:text-white">Logistics registration</h2>
        </div>
      </div>

      {error ? <div className="p-4 bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded-xl font-bold flex items-center gap-3 border border-red-100 dark:border-red-800">{error}</div> : null}

      <form className="grid grid-cols-1 md:grid-cols-2 gap-6 p-6" onSubmit={handleSubmit}>
        <label className="block space-y-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Full name</span>
          <input className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" name="name" required />
        </label>
        <label className="block space-y-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Phone</span>
          <input className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" name="phone" required placeholder="0712345678" />
        </label>
        <label className="block space-y-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Email (optional)</span>
          <input type="email" className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" name="email" />
        </label>
        <label className="block space-y-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Password</span>
          <input type="password" className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" name="password" required minLength={8} placeholder="At least 8 characters, with a number and symbol" />
        </label>
        <label className="block space-y-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Account type</span>
          <select className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" name="account_type" defaultValue="individual">
            <option value="individual">Individual rider</option>
            <option value="company">Registered company</option>
          </select>
        </label>
        <label className="block space-y-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Vehicle type</span>
          <input className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" name="vehicle_type" placeholder="E.g. Motorcycle, Van, Truck" />
        </label>
        <label className="block space-y-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Plate number</span>
          <input className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" name="plate_number" />
        </label>
        <label className="block space-y-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">License number</span>
          <input className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" name="license_number" />
        </label>
        <label className="block space-y-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Base area</span>
          <input className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" name="base_area" placeholder="E.g. Kariakoo, Sinza" />
        </label>
        <label className="block md:col-span-2 space-y-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Coverage areas</span>
          <input className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" name="coverage_areas" placeholder="Comma separated, e.g. Sinza, Magomeni" />
        </label>
        <label className="block md:col-span-2 space-y-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Profile photo (optional)</span>
          <div className="flex items-center gap-3">
            {photoPreview ? (
              <img src={photoPreview} alt="Profile preview" className="h-12 w-12 rounded-full object-cover border-2 border-slate-100 dark:border-slate-600" />
            ) : (
              <div className="h-12 w-12 rounded-full bg-slate-100 dark:bg-slate-700 flex items-center justify-center text-slate-300 text-lg font-black">?</div>
            )}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex-1 rounded-lg border border-dashed border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 px-4 py-3 text-sm font-medium text-slate-500 dark:text-slate-400 text-left truncate hover:border-brand/40"
            >
              {photoFile ? photoFile.name : "Choose an image..."}
            </button>
            <input
              ref={fileInputRef}
              name="profile_photo"
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif"
              onChange={handlePhotoChange}
              className="hidden"
            />
          </div>
        </label>
        <button className="md:col-span-2 px-6 py-3 bg-brand text-white rounded-xl hover:bg-brand/90 transition-all font-medium text-sm shadow-lg" disabled={isSubmitting} type="submit">
          {isSubmitting ? "Submitting..." : "Register logistics"}
        </button>
      </form>
    </AuthScene>
  );
}
