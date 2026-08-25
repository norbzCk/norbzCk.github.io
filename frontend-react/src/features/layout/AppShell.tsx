import { Link, Outlet, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useAuth } from "../auth/AuthContext";
import { useTheme } from "../../features/auth/ThemeContext";
import { Sidebar } from "../../components/Sidebar";
import { VerifyEmailBanner } from "../../components/VerifyEmailBanner";
import { env } from "../../config/env";
import { 
  Bell, 
  Search, 
  User as UserIcon, 
  Moon, 
  Sun, 
  Menu
} from "lucide-react";
import { useState } from "react";

function resolveImageUrl(url?: string | null) {
  const raw = String(url || "").trim();
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw)) return raw;
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

export function AppShell() {
  const { user } = useAuth();
  const location = useLocation();
  const { effectiveTheme: theme, toggleTheme } = useTheme();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const role = String(user?.role || "");
  const roleLabel =
    role === "seller" ? "Seller" : 
    role === "user" ? "Buyer" : 
    role === "logistics" ? "Delivery Agent" : 
    role === "super_admin" ? "Super Admin" : 
    role === "owner" ? "Owner" : "Admin";

  const currentSection = location.pathname
    .replace(/^\/app\/?/, "")
    .split("/")
    .filter(Boolean)
    .map((segment) => segment.replace(/-/g, " "))
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" / ") || "Dashboard";

  const displayName = user?.name || user?.business_name || user?.owner_name || user?.email || "User";
  const profilePath =
    role === "seller" ? "/app/seller/profile" : 
    role === "logistics" ? "/app/logistics/profile" : 
    role === "user" ? "/app/customer/profile" : 
    role === "super_admin" ? "/app/superadmin/profile" : "/app/profile";

  return (
    <div className="flex min-h-screen bg-bg selection:bg-brand/20">
      <Sidebar isOpen={isSidebarOpen} setIsOpen={setIsSidebarOpen} />
      
      <main className="flex min-w-0 flex-1 flex-col">
        <VerifyEmailBanner />
        <header className="sticky top-0 z-30 w-full px-4 py-4 md:px-8">
          <div className="mx-auto flex h-16 items-center justify-between rounded-2xl border border-border bg-surface/80 px-4 shadow-premium backdrop-blur-xl md:h-20 md:px-6">
            <div className="flex items-center gap-4">
              <button 
                onClick={() => setIsSidebarOpen(true)}
                className="flex h-10 w-10 items-center justify-center rounded-xl hover:bg-surface-soft md:hidden"
              >
                <Menu size={20} className="text-text" />
              </button>
              
              <div className="flex flex-col overflow-hidden">
                <h1 className="truncate font-display text-lg font-bold tracking-tight text-text md:text-xl">
                  {currentSection}
                </h1>
                <p className="text-[10px] font-bold uppercase tracking-widest text-text-muted md:text-xs">
                  <span className="text-brand">{roleLabel}</span> Account
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 md:gap-4">
              <div className="h-8 w-px bg-border mx-1 hidden md:block" />

              <div className="flex items-center gap-1 md:gap-2">
                <button
                  onClick={toggleTheme}
                  className="flex h-10 w-10 items-center justify-center rounded-xl text-text-muted transition-colors hover:bg-surface-soft hover:text-text md:h-12 md:w-12"
                >
                  {theme === "light" ? <Moon size={20} /> : <Sun size={20} />}
                </button>
                
                <Link
                  to="/app/notifications"
                  className="relative flex h-10 w-10 items-center justify-center rounded-xl text-text-muted transition-colors hover:bg-surface-soft hover:text-text md:h-12 md:w-12"
                >
                  <Bell size={20} />
                  <span className="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-danger border-2 border-surface" />
                </Link>
              </div>

              <Link 
                to={profilePath} 
                className="flex items-center gap-3 rounded-xl bg-surface-soft p-1.5 pr-3 transition-all hover:bg-surface-strong"
              >
                <div className="h-8 w-8 overflow-hidden rounded-lg bg-brand shadow-sm md:h-9 md:w-9">
                  {user?.profile_photo ? (
                    <img src={resolveImageUrl(user.profile_photo)} alt={displayName} className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center text-xs font-bold text-white">
                      {getInitials(displayName)}
                    </div>
                  )}
                </div>
                <div className="hidden flex-col items-start md:flex">
                  <span className="text-xs font-bold leading-none text-text">{displayName.split(" ")[0]}</span>
                  <span className="mt-1 text-[9px] font-bold uppercase tracking-widest text-text-muted">Profile</span>
                </div>
              </Link>
            </div>
          </div>
        </header>

        <div className="flex-1 px-4 pb-8 md:px-8">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.25, ease: "easeInOut" }}
              className="page-transition-wrapper"
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}
