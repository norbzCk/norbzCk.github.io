import { FormEvent, useState } from "react";
import { AuthScene } from "../components/AuthScene";
import { persistSession } from "../features/auth/authStorage";
import type { SessionUser } from "../types/auth";
import { apiRequest } from "../lib/http";

export function LogisticsRegisterPage() {
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
      phone: String(form.get("phone") || "").trim(),
      email: String(form.get("email") || "").trim().toLowerCase(),
      password: String(form.get("password") || ""),
      account_type: String(form.get("account_type") || "individual"),
      vehicle_type: String(form.get("vehicle_type") || "").trim(),
      plate_number: String(form.get("plate_number") || "").trim(),
      license_number: String(form.get("license_number") || "").trim(),
      base_area: String(form.get("base_area") || "").trim(),
      coverage_areas: String(form.get("coverage_areas") || "").trim(),
    };

    try {
      const data = await apiRequest<{ access_token?: string; user?: SessionUser }>("/logistics/register", {
        method: "POST",
        auth: false,
        body: payload,
      });
      if (data.access_token && data.user) {
        persistSession(data.access_token, { ...data.user, role: "logistics" }, "logistics");
      }
      setSuccess("Logistics account registered successfully.");
      setTimeout(() => {
        window.location.href = "/app/logistics";
      }, 900);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
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
      {success ? <div className="p-4 bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 rounded-xl font-bold flex items-center gap-3 border border-emerald-100 dark:border-emerald-800">{success}</div> : null}

      <form className="grid grid-cols-1 md:grid-cols-2 gap-6 p-6" onSubmit={handleSubmit}>
        <label className="block space-y-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Full name</span>
          <input className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" name="name" required />
        </label>
        <label className="block space-y-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Phone</span>
          <input className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" name="phone" required />
        </label>
        <label className="block space-y-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Email</span>
          <input type="email" className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" name="email" required />
        </label>
        <label className="block space-y-2">
          <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Password</span>
          <input type="password" className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" name="password" required minLength={8} />
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
        <button className="md:col-span-2 px-6 py-3 bg-brand text-white rounded-xl hover:bg-brand/90 transition-all font-medium text-sm shadow-lg" disabled={isSubmitting} type="submit">
          {isSubmitting ? "Submitting..." : "Register logistics"}
        </button>
      </form>
    </AuthScene>
  );
}
