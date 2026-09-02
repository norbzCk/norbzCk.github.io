import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { env } from "../config/env";
import { apiRequest } from "../lib/http";
import type { LogisticsUser } from "../types/domain";

const initialProfile: LogisticsUser = {
  id: 0,
  name: "",
  phone: "",
  email: "",
  account_type: "individual",
  vehicle_type: "",
  plate_number: "",
  license_number: "",
  base_area: "",
  coverage_areas: "",
  profile_photo: "",
  verification_status: "unverified",
};

function resolveImageUrl(url?: string | null) {
  const raw = String(url || "").trim();
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith("data:")) return raw;
  if (raw.startsWith("/")) return `${env.apiBase}${raw}`;
  return `${env.apiBase}/${raw.replace(/^\/+/, "")}`;
}

export function LogisticsProfilePage() {
  const [profile, setProfile] = useState<LogisticsUser>(initialProfile);
  const [passwordDraft, setPasswordDraft] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [passwordUpdating, setPasswordUpdating] = useState(false);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [showPassword, setShowPassword] = useState({ current: false, new: false, confirm: false });

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest<LogisticsUser>("/logistics/me");
      setProfile({ ...initialProfile, ...data });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load logistics profile");
    } finally {
      setLoading(false);
    }
  }

  async function handlePhotoUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError("");
    setFlash("");
    setUploadingPhoto(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await apiRequest<{ image_url: string }>("/logistics/upload-profile-photo", {
        method: "POST",
        body: form,
      });
      setProfile((prev) => ({ ...prev, profile_photo: response.image_url }));
      setFlash("Profile photo uploaded. Save profile to apply.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload profile photo");
    } finally {
      setUploadingPhoto(false);
      event.target.value = "";
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setFlash("");

    try {
      const wantsPasswordChange =
        Boolean(passwordDraft.current_password) ||
        Boolean(passwordDraft.new_password) ||
        Boolean(passwordDraft.confirm_password);
      if (wantsPasswordChange) {
        if (!passwordDraft.current_password || !passwordDraft.new_password || !passwordDraft.confirm_password) {
          setError("Fill all password fields to change password.");
          return;
        }
        if (passwordDraft.new_password !== passwordDraft.confirm_password) {
          setError("New passwords do not match.");
          return;
        }
      }

      const payload = {
        name: profile.name,
        phone: profile.phone,
        email: profile.email || null,
        account_type: profile.account_type,
        vehicle_type: profile.vehicle_type || null,
        plate_number: profile.plate_number || null,
        license_number: profile.license_number || null,
        base_area: profile.base_area || null,
        coverage_areas: profile.coverage_areas || null,
        profile_photo: profile.profile_photo || null,
      };

      const response = await apiRequest<{ user?: LogisticsUser; message?: string }>("/logistics/me", {
        method: "PUT",
        body: payload,
      });

      if (response.user) setProfile((prev) => ({ ...prev, ...response.user }));

      if (wantsPasswordChange) {
        setPasswordUpdating(true);
        await apiRequest("/logistics/change-password", {
          method: "POST",
          body: {
            current_password: passwordDraft.current_password,
            new_password: passwordDraft.new_password,
          },
        });
      }

      setPasswordDraft({ current_password: "", new_password: "", confirm_password: "" });
      setEditing(false);
      setFlash(wantsPasswordChange ? "Profile and password updated." : response.message || "Profile updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update profile");
    } finally {
      setPasswordUpdating(false);
    }
  }

  async function requestVerification() {
    setError("");
    setFlash("");
    try {
      await apiRequest("/logistics/verify", {
        method: "POST",
        body: {
          document_type: "logistics_profile",
          document_url: profile.profile_photo || null,
        },
      });
      setFlash("Verification request submitted.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit verification");
    }
  }

  if (loading) {
    return <section className="panel"><p>Loading logistics profile...</p></section>;
  }

  return (
    <div className="space-y-6 animate-soft-enter">
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-brand mb-2">Logistics profile</p>
            <h1 className="text-2xl font-display font-bold text-slate-900 dark:text-white">Delivery account information</h1>
            <p className="text-slate-500 dark:text-slate-400 mt-2">View and edit your logistics details.</p>
          </div>
          {!editing ? (
            <button className="px-4 py-2 bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-300 dark:hover:bg-slate-600 transition-colors text-sm font-medium" type="button" onClick={() => setEditing(true)}>
              Edit profile
            </button>
          ) : null}
        </div>
      </div>

      {error ? <div className="p-4 bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded-xl font-bold flex items-center gap-3 border border-red-100 dark:border-red-800">{error}</div> : null}
      {flash ? <div className="p-4 bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 rounded-xl font-bold flex items-center gap-3 border border-emerald-100 dark:border-emerald-800">{flash}</div> : null}

      {!editing ? (
        <article className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
          <div className="p-6 border-b border-slate-200 dark:border-slate-700 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <h2 className="text-xl font-display font-bold text-slate-900 dark:text-white">Account details</h2>
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
              profile.verification_status === "verified" ? "bg-green-100 text-green-800" : "bg-yellow-100 text-yellow-800"
            }`}>
              {profile.verification_status || "unverified"}
            </span>
          </div>
          <div className="divide-y divide-slate-100 dark:divide-slate-700">
            {profile.profile_photo ? (
              <div className="p-6">
                <img
                  src={resolveImageUrl(profile.profile_photo)}
                  alt={profile.name || "Logistics profile"}
                  className="w-32 h-32 rounded-full object-cover"
                />
              </div>
            ) : null}
            <div className="p-6 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors flex justify-between">
              <strong className="text-sm font-medium text-slate-700 dark:text-slate-300">Name</strong>
              <span className="text-sm text-slate-900 dark:text-white">{profile.name || "-"}</span>
            </div>
            <div className="p-6 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors flex justify-between">
              <strong className="text-sm font-medium text-slate-700 dark:text-slate-300">Email</strong>
              <span className="text-sm text-slate-900 dark:text-white">{profile.email || "-"}</span>
            </div>
            <div className="p-6 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors flex justify-between">
              <strong className="text-sm font-medium text-slate-700 dark:text-slate-300">Phone</strong>
              <span className="text-sm text-slate-900 dark:text-white">{profile.phone || "-"}</span>
            </div>
            <div className="p-6 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors flex justify-between">
              <strong className="text-sm font-medium text-slate-700 dark:text-slate-300">Account type</strong>
              <span className="text-sm text-slate-900 dark:text-white">{profile.account_type || "-"}</span>
            </div>
            <div className="p-6 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors flex justify-between">
              <strong className="text-sm font-medium text-slate-700 dark:text-slate-300">Vehicle type</strong>
              <span className="text-sm text-slate-900 dark:text-white">{profile.vehicle_type || "-"}</span>
            </div>
            <div className="p-6 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors flex justify-between">
              <strong className="text-sm font-medium text-slate-700 dark:text-slate-300">Plate number</strong>
              <span className="text-sm text-slate-900 dark:text-white">{profile.plate_number || "-"}</span>
            </div>
            <div className="p-6 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors flex justify-between">
              <strong className="text-sm font-medium text-slate-700 dark:text-slate-300">License number</strong>
              <span className="text-sm text-slate-900 dark:text-white">{profile.license_number || "-"}</span>
            </div>
            <div className="p-6 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors flex justify-between">
              <strong className="text-sm font-medium text-slate-700 dark:text-slate-300">Base area</strong>
              <span className="text-sm text-slate-900 dark:text-white">{profile.base_area || "-"}</span>
            </div>
            <div className="p-6 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors flex justify-between">
              <strong className="text-sm font-medium text-slate-700 dark:text-slate-300">Coverage areas</strong>
              <span className="text-sm text-slate-900 dark:text-white">{profile.coverage_areas || "-"}</span>
            </div>
            <div className="p-6 flex gap-3">
              <button className="px-4 py-2 bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-300 dark:hover:bg-slate-600 transition-colors text-sm font-medium" type="button" onClick={requestVerification}>
                Request verification ({profile.verification_status || "unverified"})
              </button>
            </div>
          </div>
        </article>
      ) : (
        <form className="bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700 p-6 space-y-4" onSubmit={handleSubmit}>
          <h2 className="text-xl font-display font-bold text-slate-900 dark:text-white">Edit profile</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="block space-y-2">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Name</span>
              <input className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" value={profile.name} onChange={(e) => setProfile((prev) => ({ ...prev, name: e.target.value }))} required />
            </label>
            <label className="block space-y-2">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Email</span>
              <input type="email" className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" value={profile.email || ""} onChange={(e) => setProfile((prev) => ({ ...prev, email: e.target.value }))} />
            </label>
            <label className="block space-y-2">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Phone</span>
              <input className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" value={profile.phone} onChange={(e) => setProfile((prev) => ({ ...prev, phone: e.target.value }))} />
            </label>
            <label className="block space-y-2">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Account type</span>
              <select className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" value={profile.account_type} onChange={(e) => setProfile((prev) => ({ ...prev, account_type: e.target.value }))}>
                <option value="individual">Individual trader</option>
                <option value="company">Registered company</option>
              </select>
            </label>
            <label className="block space-y-2">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Vehicle type</span>
              <input className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" value={profile.vehicle_type || ""} onChange={(e) => setProfile((prev) => ({ ...prev, vehicle_type: e.target.value }))} />
            </label>
            <label className="block space-y-2">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Plate number</span>
              <input className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" value={profile.plate_number || ""} onChange={(e) => setProfile((prev) => ({ ...prev, plate_number: e.target.value }))} />
            </label>
            <label className="block space-y-2">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">License number</span>
              <input className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" value={profile.license_number || ""} onChange={(e) => setProfile((prev) => ({ ...prev, license_number: e.target.value }))} />
            </label>
            <label className="block space-y-2">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Base area</span>
              <input className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" value={profile.base_area || ""} onChange={(e) => setProfile((prev) => ({ ...prev, base_area: e.target.value }))} />
            </label>
            <label className="block md:col-span-2 space-y-2">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Coverage areas (comma separated)</span>
              <input className="mt-1 block w-full rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-brand focus:ring-1 focus:ring-brand" value={profile.coverage_areas || ""} onChange={(e) => setProfile((prev) => ({ ...prev, coverage_areas: e.target.value }))} />
            </label>
            <label className="block md:col-span-2 space-y-2">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Upload profile photo (optional)</span>
              <input type="file" accept="image/*" className="mt-1 block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-brand file:text-white hover:file:bg-brand/90" onChange={handlePhotoUpload} disabled={uploadingPhoto} />
            </label>
            {profile.profile_photo ? (
              <div className="md:col-span-2">
                <img
                  src={resolveImageUrl(profile.profile_photo)}
                  alt="Profile preview"
                  className="w-32 h-32 rounded-full object-cover"
                />
              </div>
            ) : null}
          </div>
          <div className="flex gap-3 pt-4 border-t border-slate-200 dark:border-slate-700">
            <button className="px-6 py-3 bg-brand text-white rounded-xl hover:bg-brand/90 transition-all font-medium text-sm shadow-lg" type="submit" disabled={uploadingPhoto || passwordUpdating}>
              {uploadingPhoto || passwordUpdating ? "Saving..." : "Save profile"}
            </button>
            <button className="px-4 py-2 bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg hover:bg-slate-300 dark:hover:bg-slate-600 transition-colors text-sm font-medium" type="button" onClick={() => {
              setEditing(false);
              setPasswordDraft({ current_password: "", new_password: "", confirm_password: "" });
              void load(); // reload original data
            }}>
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
