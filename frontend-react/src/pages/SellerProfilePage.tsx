import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { env } from "../config/env";
import { apiRequest } from "../lib/http";
import type { BusinessProfile } from "../types/domain";

const initialProfile: BusinessProfile = {
  id: 0,
  business_name: "",
  owner_name: "",
  phone: "",
  email: "",
  business_type: "individual",
  category: "",
  description: "",
  region: "Dar es Salaam",
  area: "",
  street: "",
  shop_number: "",
  operating_hours: "",
  shop_logo_url: "",
  shop_images: "",
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

export function SellerProfilePage() {
  const [profile, setProfile] = useState<BusinessProfile>(initialProfile);
  const [passwordDraft, setPasswordDraft] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [error, setError] = useState("");
  const [flash, setFlash] = useState("");
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [passwordUpdating, setPasswordUpdating] = useState(false);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [showPassword, setShowPassword] = useState({ current: false, new: false, confirm: false }); // <-- added for eye toggle

  useEffect(() => {
    void load();
  }, []);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await apiRequest<BusinessProfile>("/business/me");
      setProfile({ ...initialProfile, ...data });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load business profile");
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
      const response = await apiRequest<{ image_url: string }>("/business/upload-profile-photo", {
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
        business_name: profile.business_name,
        owner_name: profile.owner_name,
        business_type: profile.business_type,
        email: profile.email || null,
        phone: profile.phone,
        category: profile.category || null,
        description: profile.description || null,
        region: profile.region || null,
        area: profile.area || null,
        street: profile.street || null,
        shop_number: profile.shop_number || null,
        operating_hours: profile.operating_hours || null,
        shop_logo_url: profile.shop_logo_url || null,
        shop_images: profile.shop_images || null,
        profile_photo: profile.profile_photo || null,
      };
      const response = await apiRequest<{ user?: BusinessProfile; message?: string }>("/business/me", {
        method: "PUT",
        body: payload,
      });
      if (response.user) setProfile((prev) => ({ ...prev, ...response.user }));
      if (wantsPasswordChange) {
        setPasswordUpdating(true);
        await apiRequest("/business/change-password", {
          method: "POST",
          body: {
            current_password: passwordDraft.current_password,
            new_password: passwordDraft.new_password,
          },
        });
      }
      setPasswordDraft({ current_password: "", new_password: "", confirm_password: "" });
      setEditing(false);
      setFlash(wantsPasswordChange ? "Business profile and password updated." : response.message || "Business profile updated.");
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
      await apiRequest("/business/verify", {
        method: "POST",
        body: {
          document_type: "business_profile",
          document_url: profile.shop_logo_url || profile.profile_photo || null,
        },
      });
      setFlash("Verification request submitted.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit verification");
    }
  }

  return (
    <section className="panel-stack">
      <div className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Seller profile</p>
            <h1>Business account and storefront identity</h1>
            <p className="muted">View your business information and edit only when needed.</p>
          </div>
          {!editing ? (
            <button className="secondary-button" type="button" onClick={() => setEditing(true)}>
              Edit profile
            </button>
          ) : null}
        </div>
      </div>

      {error ? <p className="alert error">{error}</p> : null}
      {flash ? <p className="alert success">{flash}</p> : null}
      {loading ? <p className="panel">Loading profile...</p> : null}

      {!loading && !editing ? (
        <article className="panel stack-list">
          <div className="panel-header">
            <h2>Business information</h2>
            <span className="role-chip">{profile.verification_status || "unverified"}</span>
          </div>
          {profile.profile_photo ? (
            <img
              src={resolveImageUrl(profile.profile_photo)}
              alt={profile.business_name || "Business profile"}
              style={{ width: "120px", height: "120px", borderRadius: "50%", objectFit: "cover" }}
            />
          ) : (
            <div className="muted">No profile photo</div>
          )}
          <div className="list-card"><strong>Business name</strong><span>{profile.business_name || "-"}</span></div>
          <div className="list-card"><strong>Owner</strong><span>{profile.owner_name || "-"}</span></div>
          <div className="list-card"><strong>Phone</strong><span>{profile.phone || "-"}</span></div>
          <div className="list-card"><strong>Email</strong><span>{profile.email || "-"}</span></div>
          <div className="list-card"><strong>Type</strong><span>{profile.business_type || "-"}</span></div>
          <div className="list-card"><strong>Category</strong><span>{profile.category || "-"}</span></div>
          <div className="list-card"><strong>Location</strong><span>{[profile.area, profile.region].filter(Boolean).join(", ") || "-"}</span></div>
          <div className="list-card"><strong>Address</strong><span>{[profile.street, profile.shop_number].filter(Boolean).join(", ") || "-"}</span></div>
          <div className="list-card"><strong>Operating hours</strong><span>{profile.operating_hours || "-"}</span></div>
          <div className="list-card"><strong>Description</strong><span>{profile.description || "-"}</span></div>
          <div className="hero-actions">
            <button className="secondary-button" type="button" onClick={requestVerification}>
              Request verification ({profile.verification_status || "unverified"})
            </button>
          </div>
        </article>
      ) : null}

      {!loading && editing ? (
        <form className="panel form-grid auth-form-two-col" onSubmit={handleSubmit}>
          <label>Business name<input value={profile.business_name || ""} onChange={(event) => setProfile((prev) => ({ ...prev, business_name: event.target.value }))} required /></label>
          <label>Owner name<input value={profile.owner_name || ""} onChange={(event) => setProfile((prev) => ({ ...prev, owner_name: event.target.value }))} required /></label>
          <label>Phone<input value={profile.phone || ""} onChange={(event) => setProfile((prev) => ({ ...prev, phone: event.target.value }))} required /></label>
          <label>Email<input type="email" value={profile.email || ""} onChange={(event) => setProfile((prev) => ({ ...prev, email: event.target.value }))} /></label>
          <label>Business type<input value={profile.business_type || ""} onChange={(event) => setProfile((prev) => ({ ...prev, business_type: event.target.value }))} /></label>
          <label>Category<input value={profile.category || ""} onChange={(event) => setProfile((prev) => ({ ...prev, category: event.target.value }))} /></label>
          <label>Region<input value={profile.region || ""} onChange={(event) => setProfile((prev) => ({ ...prev, region: event.target.value }))} /></label>
          <label>Area<input value={profile.area || ""} onChange={(event) => setProfile((prev) => ({ ...prev, area: event.target.value }))} /></label>
          <label>Street<input value={profile.street || ""} onChange={(event) => setProfile((prev) => ({ ...prev, street: event.target.value }))} /></label>
          <label>Shop number<input value={profile.shop_number || ""} onChange={(event) => setProfile((prev) => ({ ...prev, shop_number: event.target.value }))} /></label>
          <label>Operating hours<input value={profile.operating_hours || ""} onChange={(event) => setProfile((prev) => ({ ...prev, operating_hours: event.target.value }))} placeholder="Mon-Sat 08:00-18:00" /></label>
          <label>Shop logo URL<input value={profile.shop_logo_url || ""} onChange={(event) => setProfile((prev) => ({ ...prev, shop_logo_url: event.target.value }))} /></label>
          <label>Shop images (comma separated URLs)<input value={profile.shop_images || ""} onChange={(event) => setProfile((prev) => ({ ...prev, shop_images: event.target.value }))} /></label>
          <label>
            Upload profile photo (optional)
            <input type="file" accept="image/*" onChange={handlePhotoUpload} disabled={uploadingPhoto} />
          </label>
          <label>
            Profile photo URL (optional)
            <input value={profile.profile_photo || ""} onChange={(event) => setProfile((prev) => ({ ...prev, profile_photo: event.target.value }))} />
          </label>
          {profile.profile_photo ? (
            <img
              src={resolveImageUrl(profile.profile_photo)}
              alt={profile.business_name || "Profile preview"}
              style={{ width: "120px", height: "120px", borderRadius: "50%", objectFit: "cover" }}
            />
          ) : null}
          <div className="full-width">
            <p className="eyebrow">Security (optional)</p>
          </div>
          <label>
            Current password
            <div className="password-input-wrapper">
              <input
                type={showPassword.current ? "text" : "password"}
                value={passwordDraft.current_password}
                onChange={(event) => setPasswordDraft((prev) => ({ ...prev, current_password: event.target.value }))}
              />
              <button
                type="button"
                className="password-toggle-button"
                onClick={() => setShowPassword((prev) => ({ ...prev, current: !prev.current }))}
                aria-label={showPassword.current ? "Hide password" : "Show password"}
              >
                {showPassword.current ? "👁️" : "👁️‍🗨️"}
              </button>
            </div>
          </label>
          <label>
            New password
            <div className="password-input-wrapper">
              <input
                type={showPassword.new ? "text" : "password"}
                minLength={8}
                value={passwordDraft.new_password}
                onChange={(event) => setPasswordDraft((prev) => ({ ...prev, new_password: event.target.value }))}
              />
              <button
                type="button"
                className="password-toggle-button"
                onClick={() => setShowPassword((prev) => ({ ...prev, new: !prev.new }))}
                aria-label={showPassword.new ? "Hide password" : "Show password"}
              >
                {showPassword.new ? "👁️" : "👁️‍🗨️"}
              </button>
            </div>
          </label>
          <label>
            Confirm new password
            <div className="password-input-wrapper">
              <input
                type={showPassword.confirm ? "text" : "password"}
                minLength={8}
                value={passwordDraft.confirm_password}
                onChange={(event) => setPasswordDraft((prev) => ({ ...prev, confirm_password: event.target.value }))}
              />
              <button
                type="button"
                className="password-toggle-button"
                onClick={() => setShowPassword((prev) => ({ ...prev, confirm: !prev.confirm }))}
                aria-label={showPassword.confirm ? "Hide password" : "Show password"}
              >
                {showPassword.confirm ? "👁️" : "👁️‍🗨️"}
              </button>
            </div>
          </label>
          <label className="full-width">Business description<textarea value={profile.description || ""} onChange={(event) => setProfile((prev) => ({ ...prev, description: event.target.value }))} /></label>
          <div className="hero-actions">
            <button className="primary-button" type="submit">
              {uploadingPhoto || passwordUpdating ? "Saving..." : "Save profile"}
            </button>
            <button
              className="secondary-button"
              type="button"
              onClick={() => {
                setEditing(false);
                setPasswordDraft({ current_password: "", new_password: "", confirm_password: "" });
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      ) : null}
    </section>
  );
}
