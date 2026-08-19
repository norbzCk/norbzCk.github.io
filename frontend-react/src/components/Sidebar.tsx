import { NavLink, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useAuth } from "../features/auth/AuthContext";
import { BrandMark } from "./BrandMark";
import { useEffect } from "react";
import { 
  LayoutDashboard, 
  Package, 
  ShoppingCart, 
  Users, 
  Settings, 
  LogOut, 
  Truck, 
  Store,
  CreditCard,
  X,
  ChevronRight
} from "lucide-react";

interface SidebarProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
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

export function Sidebar({ isOpen, setIsOpen }: SidebarProps) {
  const { user, logout } = useAuth();
  const location = useLocation();

  useEffect(() => {
    setIsOpen(false);
  }, [location.pathname, setIsOpen]);

  const role = String(user?.role || "");
  const isSeller = role === "seller";
  const isCustomer = role === "user";
  const isLogistics = role === "logistics";
  const isSuperadmin = role === "super_admin" || role === "owner";
  const isAdmin = role === "admin";
  
  const displayName = user?.name || user?.business_name || user?.owner_name || user?.email || "User";
  const roleLabel = isSeller ? "Business Hub" : isCustomer ? "Customer Hub" : isLogistics ? "Delivery Workspace" : "Admin Panel";

  const navItems = [
    { to: "/app/superadmin", label: "Dashboard", icon: LayoutDashboard, show: isSuperadmin, end: true },
    { to: "/app/dashboard", label: "Dashboard", icon: LayoutDashboard, show: isAdmin, end: true },
    { to: "/app/seller", label: "Dashboard", icon: LayoutDashboard, show: isSeller, end: true },
    { to: "/app/customer", label: "Dashboard", icon: LayoutDashboard, show: isCustomer, end: true },
    { to: "/app/logistics", label: "Deliveries", icon: LayoutDashboard, show: isLogistics, end: true },
    
    { to: "/app/products", label: "Marketplace", icon: Store, show: isSeller || isCustomer || isAdmin || isSuperadmin },
    { to: "/app/orders", label: "Orders", icon: ShoppingCart, show: isSeller || isCustomer || isAdmin || isSuperadmin },
    { to: "/app/payments", label: "Payments", icon: CreditCard, show: isCustomer || isSuperadmin },
    { to: "/app/providers", label: "Suppliers", icon: Truck, show: isSeller || isAdmin || isSuperadmin },
    { to: "/app/seller/deliveries", label: "Shipments", icon: Truck, show: isSeller || isSuperadmin },
    
    { to: "/app/customers", label: "Customers", icon: Users, show: isSuperadmin },
    { to: "/app/users", label: "Directory", icon: Users, show: isSuperadmin || isAdmin },
  ];

  const sidebarContent = (
    <div className="flex h-full flex-col bg-[var(--sidebar-bg)] text-[var(--sidebar-text)] relative overflow-hidden border-r border-[var(--sidebar-border)]">
      {/* Subtle Dynamic Background */}
      <div className="absolute inset-0 z-0 pointer-events-none opacity-10">
        <div className="absolute -left-20 -top-20 h-64 w-64 rounded-full bg-brand blur-[100px]" />
        <div className="absolute -bottom-20 -right-20 h-64 w-64 rounded-full bg-accent blur-[100px]" />
      </div>

      <div className="relative z-10 flex h-full flex-col px-5 py-8">
        <header className="mb-10 flex items-center justify-between">
          <BrandMark subtitle={roleLabel} />
          <button 
            onClick={() => setIsOpen(false)}
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-surface-soft hover:bg-surface-strong md:hidden"
          >
            <X size={18} />
          </button>
        </header>

        <div className="mb-8 rounded-2xl bg-surface border border-[var(--sidebar-border)] p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 flex items-center justify-center rounded-xl bg-brand font-black text-white shadow-lg shrink-0">
              {getInitials(displayName)}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-bold text-[var(--sidebar-text)]">{displayName}</p>
              <p className="text-[10px] font-black uppercase tracking-widest text-[var(--sidebar-text-muted)]">{role} Node</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto no-scrollbar pr-1">
          {navItems.filter(item => item.show).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `group relative flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-bold transition-all ${
                  isActive ? "text-[var(--sidebar-active-text)]" : "text-[var(--sidebar-text-muted)] hover:text-[var(--sidebar-text)] hover:bg-surface-soft"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <item.icon size={18} className={isActive ? "text-brand" : "text-[var(--sidebar-text-muted)] group-hover:text-[var(--sidebar-text)]"} />
                  <span className="flex-1 truncate">{item.label}</span>
                  {isActive && (
                    <motion.div
                      layoutId="sidebar-active"
                      className="absolute inset-0 z-[-1] rounded-xl bg-[var(--sidebar-active-bg)] border border-brand/10"
                      transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                    />
                  )}
                  <ChevronRight size={14} className={`opacity-0 transition-opacity group-hover:opacity-40 ${isActive ? "opacity-20" : ""}`} />
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <footer className="mt-auto space-y-2 border-t border-[var(--sidebar-border)] pt-6">
          <NavLink
            to={isSuperadmin ? "/app/superadmin/settings" : "/app/settings"}
            className="flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-bold text-[var(--sidebar-text-muted)] hover:text-[var(--sidebar-text)] hover:bg-surface-soft transition-all"
          >
            <Settings size={18} />
            <span>Settings</span>
          </NavLink>
          <button
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-sm font-bold text-danger/70 hover:bg-danger/5 hover:text-danger transition-all"
          >
            <LogOut size={18} />
            <span>Sign Out</span>
          </button>
        </footer>
      </div>
    </div>
  );

  return (
    <>
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setIsOpen(false)}
            className="fixed inset-0 z-40 bg-slate-950/40 backdrop-blur-sm md:hidden"
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {isOpen && (
          <motion.aside
            initial={{ x: "-100%" }}
            animate={{ x: 0 }}
            exit={{ x: "-100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="fixed bottom-0 left-0 top-0 z-50 w-72 md:hidden"
          >
            {sidebarContent}
          </motion.aside>
        )}
      </AnimatePresence>

      <aside className="hidden w-64 shrink-0 md:block">
        <div className="sticky top-0 h-screen w-full">
          {sidebarContent}
        </div>
      </aside>
    </>
  );
}
