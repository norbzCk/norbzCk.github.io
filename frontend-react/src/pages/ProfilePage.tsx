import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { useAuth } from "../features/auth/AuthContext";
import { env } from "../config/env";
import { apiRequest } from "../lib/http";

interface ProfileState {
  name: string;
  email: string;
  phone: string;
  address: string;
  profile_photo: string;
}

interface PasswordState {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

function resolveImageUrl(url?: string | null) {
  const raw = String(url || "").trim();
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw)) return raw;
  if (raw.startsWith("data:")) return raw;
  if (raw.startsWith("/")) return `${env.apiBase}${raw}`;
  return `${env.apiBase}/${raw.replace(/^\/+/, "")}`;
}

function getInitials(name?: string) {
  const text = String(name || "User").trim();
  return text
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("");
}

export function ProfilePage() {
  const { user, refreshUser } = useAuth();
  const [profile, setProfile] = useState<ProfileState>({ name: "", email: "", phone: "", address: "", profile_photo: "" });
  const [passwordDraft, setPasswordDraft] = useState<PasswordState>({ current_password: "", new_password: "", confirm_password: "" });
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [passwordUpdating, setPasswordUpdating] = useState(false);
  const [showPhotoModal, setShowPhotoModal] = useState(false);
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");
  const [showPassword, setShowPassword] = useState({ current: false, new: false, confirm: false });

  useEffect(() => {
    setProfile({
      name: user?.name || "",
      email: user?.email || "",
      phone: user?.phone || "",
      address: user?.address || "",
      profile_photo: user?.profile_photo || "",
    });
  }, [user]);

  async function handleProfileSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setFlash("");
    try {
      const updated = await apiRequest<{
        name: string;
        email: string;
        phone?: string;
        address?: string;
        profile_photo?: string;
      }>("/auth/me", {
        method: "PUT",
        body: {
          name: profile.name,
          phone: profile.phone,
          address: profile.address,
          profile_photo: profile.profile_photo || null,
        },
      });
      setProfile({
        name: updated.name || "",
        email: updated.email || "",
        phone: updated.phone || "",
        address: updated.address || "",
        profile_photo: updated.profile_photo || "",
      });
      await refreshUser();
      setFlash("Profile updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update profile");
    }
  }

  async function handlePasswordSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setFlash("");
    setPasswordUpdating(true);

    if (!passwordDraft.current_password || !passwordDraft.new_password || !passwordDraft.confirm_password) {
      setError("Fill all password fields to change password.");
      setPasswordUpdating(false);
      return;
    }
    if (passwordDraft.new_password !== passwordDraft.confirm_password) {
      setError("New passwords do not match.");
      setPasswordUpdating(false);
      return;
    }

    try {
      await apiRequest("/auth/change-password", {
        method: "POST",
        body: {
          current_password: passwordDraft.current_password,
          new_password: passwordDraft.new_password,
        },
      });
      setPasswordDraft({ current_password: "", new_password: "", confirm_password: "" });
      setFlash("Password updated successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update password");
    } finally {
      setPasswordUpdating(false);
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
      const response = await apiRequest<{ image_url: string }>("/auth/upload-profile-photo", {
        method: "POST",
        body: form,
      });
      setProfile((state) => ({ ...state, profile_photo: response.image_url }));
      setFlash("Profile photo uploaded. Save profile to apply.");
      setShowPhotoModal(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload profile photo");
    } finally {
      setUploadingPhoto(false);
      event.target.value = "";
    }
  }

  if (user?.role !== "user") {
    return (
      <section className="rounded-[2rem] border border-white/60 bg-white/80 p-8 shadow-[0_18px_50px_rgba(15,23,42,0.06)] backdrop-blur dark:border-white/10 dark:bg-slate-900/70">
        <h1 className="font-display text-2xl font-black tracking-tight text-slate-950 dark:text-white">Profile</h1>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">The polished customer profile experience is available for customer accounts.</p>
      </section>
    );
  }

  return (
    <div className="space-y-6 animate-soft-enter">
      <section className="relative overflow-hidden rounded-[2rem] border border-white/60 bg-white/80 p-6 shadow-[0_18px_50px_rgba(15,23,42,0.07)] backdrop-blur md:p-8 dark:border-white/10 dark:bg-slate-900/70">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.12),transparent_34%),radial-gradient(circle_at_bottom_right,rgba(249,115,22,0.12),transparent_28%)]" />
        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-3">
            <p className="text-[11px] font-black uppercase tracking-[0.28em] text-brand">Profile & Settings</p>
            <h1 className="font-display text-3xl font-black tracking-tight text-slate-950 md:text-4xl dark:text-white">Manage your account</h1>
            <p className="max-w-2xl text-sm leading-6 text-slate-600 md:text-base dark:text-slate-300">
              A cleaner account center with stronger visual hierarchy, reliable feedback, and a consistent blue and orange identity across light and dark themes.
            </p>
          </div>
          <div className="flex items-center gap-4 rounded-[1.75rem] border border-white/70 bg-white/70 px-5 py-4 shadow-sm dark:border-white/10 dark:bg-slate-800/60">
            {profile.profile_photo ? (
              <img src={resolveImageUrl(profile.profile_photo)} alt={profile.name || "Profile"} className="h-16 w-16 rounded-2xl object-cover shadow-md" />
            ) : (
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand/10 text-lg font-black text-brand">
                {getInitials(profile.name || "User")}
              </div>
            )}
            <div>
              <p className="font-display text-xl font-black text-slate-950 dark:text-white">{profile.name || "User"}</p>
              <p className="text-sm text-slate-500 dark:text-slate-400">{user?.email}</p>
            </div>
          </div>
        </div>
      </section>

      {error ? <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-300">{error}</div> : null}
      {flash ? <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300">{flash}</div> : null}

      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        <div className="space-y-6">
          <section className="rounded-[2rem] border border-white/60 bg-white/85 p-6 shadow-[0_16px_40px_rgba(15,23,42,0.06)] backdrop-blur dark:border-white/10 dark:bg-slate-900/75">
            <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
              <div>
                 <p className="text-[11px] font-black uppercase tracking-[0.24em] text-slate-500 dark:text-slate-300">Identity</p>
                <h2 className="mt-2 font-display text-2xl font-black tracking-tight text-slate-950 dark:text-white">Personal details</h2>
              </div>
              <button className="btn-secondary" onClick={() => setShowPhotoModal(true)} type="button">Change photo</button>
            </div>

            <form className="mt-6 grid gap-4 md:grid-cols-2" onSubmit={handleProfileSubmit}>
              <label className="space-y-2 text-sm font-semibold text-slate-700 dark:text-slate-300">
                Full name
                <input
                  value={profile.name}
                  onChange={(event) => setProfile((state) => ({ ...state, name: event.target.value }))}
                  required
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-brand/30 focus:bg-white dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                />
              </label>
              <label className="space-y-2 text-sm font-semibold text-slate-700 dark:text-slate-300">
                Email
                <input
                  value={profile.email}
                  readOnly
                  disabled
                   className="w-full cursor-not-allowed rounded-2xl border border-slate-200 bg-slate-100 px-4 py-3 text-slate-500 dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-300"
                />
              </label>
              <label className="space-y-2 text-sm font-semibold text-slate-700 dark:text-slate-300">
                Phone
                <input
                  value={profile.phone}
                  onChange={(event) => setProfile((state) => ({ ...state, phone: event.target.value }))}
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-brand/30 focus:bg-white dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                />
              </label>
              <label className="space-y-2 text-sm font-semibold text-slate-700 dark:text-slate-300">
                Address
                <input
                  value={profile.address}
                  onChange={(event) => setProfile((state) => ({ ...state, address: event.target.value }))}
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-brand/30 focus:bg-white dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                />
              </label>
              <div className="md:col-span-2 flex items-center justify-between rounded-[1.5rem] bg-slate-50 px-4 py-4 dark:bg-slate-800/60">
                <div>
                  <p className="text-sm font-semibold text-slate-900 dark:text-white">Account reliability</p>
                  <p className="text-sm text-slate-500 dark:text-slate-400">Keep contact information current so delivery and payment updates reach you immediately.</p>
                </div>
                <button className="btn-primary" type="submit" disabled={uploadingPhoto}>
                  {uploadingPhoto ? "Processing..." : "Save changes"}
                </button>
              </div>
            </form>
          </section>

          <section className="rounded-[2rem] border border-white/60 bg-white/85 p-6 shadow-[0_16px_40px_rgba(15,23,42,0.06)] backdrop-blur dark:border-white/10 dark:bg-slate-900/75">
            <div>
                 <p className="text-[11px] font-black uppercase tracking-[0.24em] text-slate-500 dark:text-slate-300">Security</p>
              <h2 className="mt-2 font-display text-2xl font-black tracking-tight text-slate-950 dark:text-white">Change password</h2>
              <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">Keep your account secure with a strong password and updated credentials.</p>
            </div>
            <form className="mt-6 space-y-4" onSubmit={handlePasswordSubmit}>
              <div>
                <label className="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-300">Current password</label>
                <div className="relative">
                  <input
                    type={showPassword.current ? "text" : "password"}
                    value={passwordDraft.current_password}
                    onChange={(event) => setPasswordDraft((prev) => ({ ...prev, current_password: event.target.value }))}
                    required
                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 pr-14 outline-none transition focus:border-brand/30 focus:bg-white dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                  />
                  <button type="button" className="absolute inset-y-0 right-0 px-4 text-xs font-semibold text-slate-400" onClick={() => setShowPassword((prev) => ({ ...prev, current: !prev.current }))}>
                    {showPassword.current ? "Hide" : "Show"}
                  </button>
                </div>
              </div>
              <div>
                <label className="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-300">New password</label>
                <div className="relative">
                  <input
                    type={showPassword.new ? "text" : "password"}
                    minLength={8}
                    value={passwordDraft.new_password}
                    onChange={(event) => setPasswordDraft((prev) => ({ ...prev, new_password: event.target.value }))}
                    required
                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 pr-14 outline-none transition focus:border-brand/30 focus:bg-white dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                  />
                  <button type="button" className="absolute inset-y-0 right-0 px-4 text-xs font-semibold text-slate-400" onClick={() => setShowPassword((prev) => ({ ...prev, new: !prev.new }))}>
                    {showPassword.new ? "Hide" : "Show"}
                  </button>
                </div>
              </div>
              <div>
                <label className="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-300">Confirm new password</label>
                <div className="relative">
                  <input
                    type={showPassword.confirm ? "text" : "password"}
                    minLength={8}
                    value={passwordDraft.confirm_password}
                    onChange={(event) => setPasswordDraft((prev) => ({ ...prev, confirm_password: event.target.value }))}
                    required
                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 pr-14 outline-none transition focus:border-brand/30 focus:bg-white dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                  />
                  <button type="button" className="absolute inset-y-0 right-0 px-4 text-xs font-semibold text-slate-400" onClick={() => setShowPassword((prev) => ({ ...prev, confirm: !prev.confirm }))}>
                    {showPassword.confirm ? "Hide" : "Show"}
                  </button>
                </div>
              </div>
              <button className="btn-primary w-full" type="submit" disabled={passwordUpdating}>
                {passwordUpdating ? "Updating..." : "Update password"}
              </button>
            </form>
          </section>
        </div>

        <div className="space-y-6">
          <section className="rounded-[2rem] border border-white/60 bg-white/85 p-6 shadow-[0_16px_40px_rgba(15,23,42,0.06)] backdrop-blur dark:border-white/10 dark:bg-slate-900/75">
               <p className="text-[11px] font-black uppercase tracking-[0.24em] text-slate-500 dark:text-slate-300">Overview</p>
            <h2 className="mt-2 font-display text-2xl font-black tracking-tight text-slate-950 dark:text-white">Account snapshot</h2>
            <div className="mt-6 grid gap-4">
              <div className="rounded-[1.5rem] bg-slate-50 px-4 py-4 dark:bg-slate-800/60">
                 <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-500 dark:text-slate-300">Email</p>
                <p className="mt-2 text-sm font-semibold text-slate-900 dark:text-white">{profile.email || "Not available"}</p>
              </div>
              <div className="rounded-[1.5rem] bg-slate-50 px-4 py-4 dark:bg-slate-800/60">
                <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-400">Phone</p>
                <p className="mt-2 text-sm font-semibold text-slate-900 dark:text-white">{profile.phone || "Add your phone number"}</p>
              </div>
              <div className="rounded-[1.5rem] bg-slate-50 px-4 py-4 dark:bg-slate-800/60">
                 <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-500 dark:text-slate-300">Address</p>
                <p className="mt-2 text-sm font-semibold text-slate-900 dark:text-white">{profile.address || "Add your delivery address"}</p>
              </div>
            </div>
          </section>
        </div>
      </div>

      {showPhotoModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 px-4 backdrop-blur-sm">
          <div className="w-full max-w-md overflow-y-auto rounded-[2rem] border border-white/60 bg-white p-6 shadow-2xl dark:border-white/10 dark:bg-slate-900">
            <div className="border-b border-slate-200 pb-4 dark:border-slate-800">
              <h2 className="font-display text-2xl font-black tracking-tight text-slate-950 dark:text-white">Change profile photo</h2>
            </div>
            <div className="space-y-4 pt-6">
              <div>
                <label className="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-300">Upload new photo</label>
                <input
                  type="file"
                  accept="image/*"
                  onChange={handlePhotoUpload}
                  disabled={uploadingPhoto}
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-brand/30 focus:bg-white dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-semibold text-slate-700 dark:text-slate-300">Or enter photo URL</label>
                <input
                  value={profile.profile_photo}
                  onChange={(event) => setProfile((state) => ({ ...state, profile_photo: event.target.value }))}
                  placeholder="/uploads/profile-photo.jpg or https://example.com/avatar.png"
                  className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 outline-none transition focus:border-brand/30 focus:bg-white dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                />
              </div>
              {profile.profile_photo ? (
                <div className="flex justify-center">
                  <img src={resolveImageUrl(profile.profile_photo)} alt="Profile preview" className="h-24 w-24 rounded-3xl object-cover shadow-lg" />
                </div>
              ) : null}
              <div className="flex justify-end border-t border-slate-200 pt-4 dark:border-slate-800">
                <button className="btn-secondary" onClick={() => setShowPhotoModal(false)} disabled={uploadingPhoto} type="button">
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
