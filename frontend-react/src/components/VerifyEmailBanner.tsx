import { useState } from "react";
import { Mail, X } from "lucide-react";
import { useAuth } from "../features/auth/AuthContext";

const DISMISS_KEY = "verify_email_banner_dismissed";

export function VerifyEmailBanner() {
  const { user, resendConfirmationEmail } = useAuth();
  const [dismissed, setDismissed] = useState(() => sessionStorage.getItem(DISMISS_KEY) === "1");
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");

  if (!user || user.is_verified || dismissed) {
    return null;
  }

  async function handleResend() {
    if (!user?.email) return;
    setStatus("sending");
    try {
      await resendConfirmationEmail(user.email);
      setStatus("sent");
    } catch {
      setStatus("error");
    }
  }

  function handleDismiss() {
    sessionStorage.setItem(DISMISS_KEY, "1");
    setDismissed(true);
  }

  return (
    <div className="flex items-center gap-3 bg-amber-50 border-b border-amber-200 px-4 py-2 text-sm text-amber-900 dark:bg-amber-950/40 dark:border-amber-900 dark:text-amber-200">
      <Mail size={16} className="shrink-0" />
      <span className="flex-1">
        Verify your email to unlock selling and delivery features.
        {status === "sent" && <span className="ml-2 font-semibold">Confirmation email sent — check your inbox.</span>}
        {status === "error" && <span className="ml-2 font-semibold">Couldn't send it, please try again shortly.</span>}
      </span>
      <button
        onClick={handleResend}
        disabled={status === "sending" || status === "sent"}
        className="shrink-0 font-bold underline decoration-2 underline-offset-2 hover:no-underline disabled:opacity-60"
      >
        {status === "sending" ? "Sending…" : status === "sent" ? "Sent" : "Resend email"}
      </button>
      <button onClick={handleDismiss} className="shrink-0 opacity-70 hover:opacity-100" aria-label="Dismiss">
        <X size={16} />
      </button>
    </div>
  );
}
