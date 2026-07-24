import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";
import { CartProvider } from "../features/auth/CartContext";
import { ProtectedRoute, RoleRoute } from "../features/auth/ProtectedRoute";
import { AppShell } from "../features/layout/AppShell";
import { AdminDashboardPage } from "../pages/AdminDashboardPage";
import { BusinessRegisterPage } from "../pages/BusinessRegisterPage";
import { CustomersPage } from "../pages/CustomersPage";
import { CustomerDashboardPage } from "../pages/CustomerDashboardPage";
import { CustomerRegisterPage } from "../pages/CustomerRegisterPage";
import { ForgotPasswordPage } from "../pages/ForgotPasswordPage";
import { HomePage } from "../pages/HomePage";
import { LogisticsDashboardPage } from "../pages/LogisticsDashboardPage";
import { LogisticsRegisterPage } from "../pages/LogisticsRegisterPage";
import { LoginPage } from "../pages/LoginPage";
import { OrdersPage } from "../pages/OrdersPage";
import { PaymentsPage } from "../pages/PaymentsPage";
import { NotificationsPage } from "../pages/NotificationsPage";
import { ProductsPage } from "../pages/ProductsPage";
import { ProfilePage } from "../pages/ProfilePage";
import { ProvidersPage } from "../pages/ProvidersPage";
import { SellerDashboardPage } from "../pages/SellerDashboardPage";
import { SellerDeliveriesPage } from "../pages/SellerDeliveriesPage";
import { SellerProfilePage } from "../pages/SellerProfilePage";
import { SuperadminDashboardPage } from "../pages/SuperadminDashboardPage";
import { SuperadminLoginPage } from "../pages/SuperadminLoginPage";
import { UsersPage } from "../pages/UsersPage";
import { LogisticsProfilePage } from "../pages/LogisticsProfilePage";
import { SuperadminProfilePage } from "../pages/SuperadminProfilePage";
import { SuperadminSettingsPage } from "../pages/SuperadminSettingsPage";
import { SettingsPage } from "../pages/SettingsPage";
import { VerifyEmailPage } from "../pages/VerifyEmailPage";

import { ProductDetailPage } from "../pages/ProductDetailPage";
import { TrackDeliveryPage } from "../pages/TrackDeliveryPage";
import { CheckoutPage } from "../pages/CheckoutPage";

function AppLanding() {
  const { user } = useAuth();
  const role = String(user?.role || "");
  if (role === "super_admin" || role === "owner") return <Navigate to="/app/superadmin" replace />;
  if (role === "user") return <Navigate to="/app/customer" replace />;
  if (role === "logistics") return <Navigate to="/app/logistics" replace />;
  if (role === "seller") return <Navigate to="/app/seller" replace />;
  return <Navigate to="/app/dashboard" replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/product/:productId" element={<ProductDetailPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route path="/superadmin" element={<SuperadminLoginPage />} />
      <Route path="/register/business" element={<BusinessRegisterPage />} />
      <Route path="/register/customer" element={<CustomerRegisterPage />} />
      <Route path="/register/logistics" element={<LogisticsRegisterPage />} />

      <Route
        path="/app"
        element={
          <ProtectedRoute>
            <CartProvider>
              <AppShell />
            </CartProvider>
          </ProtectedRoute>
        }
      >
        <Route index element={<AppLanding />} />
        <Route path="dashboard" element={<RoleRoute allowedRoles={["admin", "owner"]}><AdminDashboardPage /></RoleRoute>} />
        <Route path="superadmin" element={<RoleRoute allowedRoles={["super_admin", "owner"]}><SuperadminDashboardPage /></RoleRoute>} />
        <Route path="seller" element={<RoleRoute allowedRoles={["seller"]}><SellerDashboardPage /></RoleRoute>} />
        <Route path="seller/profile" element={<RoleRoute allowedRoles={["seller"]}><SellerProfilePage /></RoleRoute>} />
        <Route path="seller/deliveries" element={<RoleRoute allowedRoles={["seller"]}><SellerDeliveriesPage /></RoleRoute>} />
        <Route path="customer" element={<RoleRoute allowedRoles={["user"]}><CustomerDashboardPage /></RoleRoute>} />
        <Route path="customer/profile" element={<RoleRoute allowedRoles={["user"]}><ProfilePage /></RoleRoute>} />
        <Route path="logistics" element={<RoleRoute allowedRoles={["logistics"]}><LogisticsDashboardPage /></RoleRoute>} />
        <Route path="logistics/profile" element={<RoleRoute allowedRoles={["logistics"]}><LogisticsProfilePage /></RoleRoute>} />
        <Route path="products" element={<ProductsPage />} />
        <Route path="orders" element={<OrdersPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="customers" element={<RoleRoute allowedRoles={["super_admin", "owner"]}><CustomersPage /></RoleRoute>} />
        <Route path="product/:productId" element={<ProductDetailPage />} />
        <Route path="checkout" element={<RoleRoute allowedRoles={["user"]}><CheckoutPage /></RoleRoute>} />
        <Route path="track/:trackingCode" element={<TrackDeliveryPage />} />
        <Route path="track" element={<TrackDeliveryPage />} />
        <Route path="providers" element={<RoleRoute allowedRoles={["seller", "admin", "super_admin", "owner"]}><ProvidersPage /></RoleRoute>} />
        <Route path="payments" element={<RoleRoute allowedRoles={["user"]}><PaymentsPage /></RoleRoute>} />
        <Route path="profile" element={<RoleRoute allowedRoles={["admin", "owner"]}><ProfilePage /></RoleRoute>} />
        <Route path="superadmin/profile" element={<RoleRoute allowedRoles={["super_admin", "owner"]}><SuperadminProfilePage /></RoleRoute>} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="superadmin/settings" element={<RoleRoute allowedRoles={["super_admin", "owner"]}><SuperadminSettingsPage /></RoleRoute>} />
        <Route path="users" element={<RoleRoute allowedRoles={["admin", "super_admin", "owner"]}><UsersPage /></RoleRoute>} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
