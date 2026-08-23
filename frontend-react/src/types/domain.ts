export interface Product {
  id: number;
  name: string;
  category?: string;
  price?: number;
  stock?: number;
  description?: string;
  in_stock?: boolean;
  image_url?: string;
  seller_id?: number | null;
  is_active?: boolean;
  provider_id?: number | null;
  provider?: Provider | null;
  seller_name?: string | null;
  seller?: {
    id?: number;
    business_name?: string;
    owner_name?: string;
    phone?: string;
    email?: string | null;
    region?: string | null;
    area?: string | null;
    street?: string | null;
    verification_status?: string | null;
    badges?: Array<{
      id: string;
      label: string;
      icon?: string;
    }>;
  } | null;
  rating_avg?: number;
  rating_count?: number;
}

export interface Provider {
  id: number;
  name: string;
  location?: string;
  email?: string | null;
  phone?: string | null;
  verified?: boolean;
  response_time?: string;
  min_order_qty?: string;
  description?: string;
  rating_avg?: number;
  rating_count?: number;
  total_sales?: number;
  total_products?: number;
}

export interface DashboardStats {
  total_revenue: number;
  total_orders: number;
  total_units: number;
  top_product: string;
}

export interface DashboardMetricCard {
  id: string;
  label: string;
  display: string;
  value: number;
  kind: "money" | "count" | "text";
  subtitle?: string;
}

export interface DashboardChartPoint {
  label: string;
  value: number;
}

export interface DashboardRecentSale {
  id?: number;
  date?: string | null;
  product?: string | null;
  category?: string | null;
  quantity?: number;
  revenue?: number;
}

export interface DashboardAnalytics {
  cards: DashboardMetricCard[];
  revenueByProduct: DashboardChartPoint[];
  revenueOverTime: DashboardChartPoint[];
  recentSales: DashboardRecentSale[];
  orderStatusBreakdown?: Record<string, number>;
  graphs?: {
    revenueByProduct?: string;
    revenueOverTime?: string;
  };
  peakPeriods?: {
    day_of_week: Record<string, { orders: number; revenue: number }>;
    hour_of_day: Record<string, { orders: number; revenue: number }>;
  };
  customerPatterns?: {
    top_customers: Array<{ id: number; name: string; orders: number; total_spent: number }>;
    repeat_purchase_rate_percent: number;
  };
}

export interface InventoryStats {
  total_products: number;
  low_stock_count: number;
  out_of_stock_count: number;
  total_value: number;
  alerts: Array<{
    product_id: number;
    product_name: string;
    current_stock: number;
    low_stock_threshold: number;
    provider_id?: number | null;
    provider_name?: string | null;
  }>;
}

export interface Order {
  id: number;
  order_date?: string | null;
  product?: string | null;
  category?: string | null;
  provider_id?: number | null;
  provider_name?: string | null;
  seller_id?: number | null;
  quantity?: number;
  unit_price?: number;
  total?: number;
  status?: string | null;
  status_reason?: string | null;
  rating?: number | null;
  created_by?: number | string | null;
  product_id?: number | null;
  delivery_address?: string | null;
  delivery_phone?: string | null;
  delivery_notes?: string | null;
  delivery_method?: string | null;
  customer_name?: string | null;
  customer_email?: string | null;
  customer_phone?: string | null;
  payment_status?: string | null;
  payment_method?: string | null;
  payment_transaction_id?: string | null;
  delivery_id?: number | null;
  delivery_status?: string | null;
  delivery_price?: number | null;
  logistics_id?: number | null;
  logistics_name?: string | null;
  estimated_distance_km?: number | null;
  priority?: string | null;
}

export interface SellerLogisticsOption {
  id: number;
  name: string;
  vehicle_type?: string | null;
  base_area?: string | null;
  status?: string | null;
  availability?: string | null;
  verification_status?: string | null;
}

export interface PaymentMethod {
  id: string;
  name: string;
  type: string;
  enabled: boolean;
  instructions?: string | null;
}

export interface PaymentHistoryItem {
  transaction_id: string;
  order_id: number;
  product?: string | null;
  amount: number;
  status: string;
  date?: string | null;
  payment_method?: string | null;
}

export interface PaymentResponse {
  transaction_id: string;
  status: string;
  amount: number;
  message: string;
  timestamp?: string;
  instructions?: string | null;
  order_id?: number;
  payment_method?: string | null;
  provider?: string | null;
}

export interface NotificationEntry {
  id: number | string;
  title: string;
  message: string;
  type?: string;
  severity?: string;
  action_href?: string | null;
  is_read?: boolean;
  email_status?: string;
  created_at?: string | null;
  read_at?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface Sale {
  id: number;
  date?: string | null;
  product?: string | null;
  category?: string | null;
  quantity?: number;
  unit_price?: number;
  revenue?: number;
  status?: string | null;
}

export interface Customer {
  id: number;
  name: string;
  email?: string | null;
  phone?: string | null;
  location?: string | null;
  is_verified?: boolean;
  is_active?: boolean;
}

export interface AdminUser {
  id: number;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  is_verified?: boolean;
}

export interface LogisticsDelivery {
  id: number;
  order_id?: number | null;
  pickup_location: string;
  delivery_location: string;
  delivery_address?: string | null;
  customer_name?: string | null;
  customer_phone?: string | null;
  customer_phone_masked?: string | null;
  pickup_phone?: string | null;
  delivery_phone?: string | null;
  status: string;
  price?: number | null;
  payment_method?: string | null;
  payment_status?: string | null;
  cod_amount?: number | null;
  cod_amount_received?: number | null;
  delivery_notes?: string | null;
  special_instructions?: string | null;
  verification_code?: string | null;
  pickup_lat?: number | null;
  pickup_lng?: number | null;
  destination_lat?: number | null;
  destination_lng?: number | null;
  current_lat?: number | null;
  current_lng?: number | null;
  estimated_distance_km?: number | null;
  last_location_name?: string | null;
  tracking_updated_at?: string | null;
  created_at?: string | null;
  accepted_at?: string | null;
  picked_at?: string | null;
  delivered_at?: string | null;
  failed_at?: string | null;
  failure_reason?: string | null;
  proof_type?: string | null;
  proof_note?: string | null;
}

export interface LogisticsUser {
  id: number;
  name: string;
  phone: string;
  email?: string | null;
  account_type: string;
  vehicle_type?: string | null;
  plate_number?: string | null;
  license_number?: string | null;
  base_area?: string | null;
  coverage_areas?: string | null;
  profile_photo?: string | null;
  verification_status?: string | null;
  created_at?: string | null;
}

export interface BusinessProfile {
  id: number;
  business_name: string;
  owner_name: string;
  phone: string;
  email?: string | null;
  business_type?: string | null;
  category?: string | null;
  description?: string | null;
  region?: string | null;
  area?: string | null;
  street?: string | null;
  shop_number?: string | null;
  operating_hours?: string | null;
  shop_logo_url?: string | null;
  shop_images?: string | null;
  profile_photo?: string | null;
  verification_status?: string | null;
}

export interface SellerDashboardOverview {
  business: BusinessProfile;
  performance_badges?: Array<{
    id: string;
    label: string;
    icon?: string;
  }>;
  summary: {
    revenue_today: number;
    revenue_week: number;
    revenue_month: number;
    revenue_total: number;
    orders_total: number;
    orders_pending: number;
    orders_completed: number;
    orders_cancelled: number;
    ongoing_deliveries: number;
    completed_deliveries: number;
    inventory_low_stock: number;
    inventory_out_of_stock: number;
  };
  top_products: Array<{
    product: string;
    units: number;
    revenue: number;
  }>;
  inventory: {
    total_products: number;
    total_value: number;
    out_of_stock: number;
    low_stock: number;
    alerts: Array<{
      product_id: number;
      product_name: string;
      current_stock: number;
      low_stock_threshold: number;
    }>;
  };
  inventory_forecast?: Array<{
    product_id: number;
    product_name: string;
    current_stock: number;
    daily_burn_rate: number;
    days_left: number | string;
    weekly_demand?: number;
    recommended_restock?: number;
    risk_level?: string;
    is_critical?: boolean;
  }>;
}

export interface SuperadminOverview {
  total_businessmen: number;
  active_businessmen: number;
  total_customers: number;
  active_customers: number;
  total_logistics: number;
  active_logistics: number;
  total_products: number;
  active_products: number;
  total_orders: number;
  completed_orders: number;
  pending_orders: number;
  in_transit_orders: number;
  total_revenue: number;
  average_order_value: number;
  low_stock_products: number;
  pending_business_verifications: number;
  pending_logistics_verifications: number;
  pending_user_verifications: number;
  pending_user_verifications: number;
  seller_leaderboard: Array<{
    id: number;
    business_name: string;
    region?: string | null;
    area?: string | null;
    rating: number;
    total_sales: number;
    total_revenue: number;
    badges?: Array<{ id: string; label: string; icon?: string }>;
  }>;
  category_performance: Array<{
    category: string;
    units: number;
    revenue: number;
  }>;
  recent_orders: Array<{
    id: number;
    product?: string | null;
    provider_name?: string | null;
    status?: string | null;
    quantity?: number;
    revenue?: number;
    date?: string | null;
  }>;
  inventory_watch: Array<{
    product_id: number;
    product_name: string;
    stock: number;
    seller_name: string;
    seller_area?: string | null;
  }>;
  status_breakdown: Array<{
    status: string;
    count: number;
  }>;
  revenue_trend: Array<{
    date: string;
    orders: number;
    revenue: number;
  }>;
  insights: Array<{
    id: string;
    title: string;
    message: string;
  }>;
}

export interface VerificationBusinessman {
  id: number;
  business_name: string;
  owner_name: string;
  phone?: string | null;
  email?: string | null;
  category?: string | null;
  region?: string | null;
  area?: string | null;
  verification_status: string;
  created_at?: string | null;
}

export interface VerificationLogistics {
  id: number;
  name: string;
  phone?: string | null;
  email?: string | null;
  vehicle_type?: string | null;
  base_area?: string | null;
  coverage_areas?: string | null;
  verification_status: string;
  created_at?: string | null;
}

export interface VerificationUser {
  id: number;
  name: string;
  email?: string | null;
  phone?: string | null;
  is_verified: boolean;
  created_at?: string | null;
}

export interface OrderTracking {
  order_id?: number | null;
  delivery_id: number;
  status: string;
  progress_percent: number;
  eta_minutes: number;
  distance_km: number;
  last_updated_at?: string | null;
  logistics_partner?: {
    id?: number | null;
    name?: string | null;
    phone?: string | null;
    vehicle_type?: string | null;
  };
  buyer_id?: number | null;
  map: {
    pickup: { label: string; lat: number; lng: number };
    current: { label: string; lat: number; lng: number };
    destination: { label: string; lat: number; lng: number };
  };
  checkpoints: Array<{
    id: string;
    label: string;
    done: boolean;
    location?: string | null;
    timestamp?: string | null;
  }>;
  order: {
    id?: number | null;
    product?: string | null;
    status?: string | null;
  };
  rating?: number | null;
  rated_at?: string | null;
  rating_comment?: string | null;
}

export interface CartOptimization {
  recommendations: Array<{
    id: string;
    title: string;
    seller_area: string;
    seller_region: string;
    item_count: number;
    seller_names: string[];
    estimated_delivery_fee: number;
    separate_delivery_fee: number;
    estimated_savings: number;
    message: string;
    items: Array<{
      product_id: number;
      name: string;
      quantity: number;
      seller_name: string;
    }>;
  }>;
  summary: {
    separate_delivery_fee: number;
    optimized_delivery_fee: number;
    estimated_savings: number;
  };
}

export type BuyerOrderLifecycleStatus =
  | "Pending"
  | "Confirmed"
  | "Processing"
  | "Dispatched"
  | "In Transit"
  | "Delivered"
  | "Cancelled";

export interface BuyerAddress {
  id: string;
  label?: string;
  recipientName?: string;
  phone?: string;
  line1: string;
  line2?: string;
  city?: string;
  state?: string;
  postalCode?: string;
  country?: string;
  deliveryNotes?: string;
  isDefault?: boolean;
  type?: "Home" | "Office" | "Warehouse" | "Other";
}

export interface BuyerPreference {
  id: string;
  key: string;
  label?: string;
  value?: string | number | boolean | string[];
  category?: string;
  updatedAt?: string;
}

export interface BuyerSuggestion {
  id: string;
  title: string;
  description?: string;
  reason?: string;
  category?: string;
  keywords?: string[];
  product?: Product;
  provider?: Provider;
  relevanceScore?: number;
  priceHint?: number;
  availabilityText?: string;
}

export interface BuyerNotification {
  id: string;
  title: string;
  message: string;
  type?: "order" | "delivery" | "promotion" | "system" | "chat";
  createdAt?: string;
  isRead?: boolean;
  actionLabel?: string;
  actionHref?: string;
  orderId?: Order["id"];
  severity?: "info" | "success" | "warning" | "error";
}

export interface BuyerChatMessage {
  id: string;
  senderId?: string;
  senderName?: string;
  senderRole?: "buyer" | "seller" | "agent" | "system";
  message: string;
  sentAt?: string;
  isRead?: boolean;
  orderId?: Order["id"];
}

export interface BuyerChatThread {
  id: string;
  title: string;
  participantName?: string;
  participantRole?: "seller" | "agent" | "system";
  orderId?: Order["id"];
  productId?: Product["id"];
  lastMessageAt?: string;
  unreadCount?: number;
  messages?: BuyerChatMessage[];
}

export interface BuyerDeliveryEvent {
  id: string;
  status: BuyerOrderLifecycleStatus;
  title?: string;
  description?: string;
  location?: string;
  timestamp?: string;
  isCompleted?: boolean;
}

export interface BuyerTrackedOrder {
  id: string;
  order?: Order;
  orderNumber?: string;
  status: BuyerOrderLifecycleStatus;
  placedAt?: string;
  estimatedDeliveryAt?: string;
  deliveredAt?: string;
  provider?: Provider;
  address?: BuyerAddress;
  items?: BuyerCartItem[];
  events?: BuyerDeliveryEvent[];
  progressPercent?: number;
  trackingCode?: string;
  supportThreadId?: BuyerChatThread["id"];
}

export interface BuyerCartItem {
  id: string;
  product?: Product;
  provider?: Provider;
  orderId?: Order["id"];
  quantity: number;
  unitPrice?: number;
  subtotal?: number;
  currency?: string;
  note?: string;
  availabilityStatus?: "in_stock" | "limited" | "preorder" | "out_of_stock";
}

export interface BuyerAccountSnapshot {
  buyerId?: string;
  fullName?: string;
  email?: string;
  phone?: string;
  loyaltyTier?: string;
  addresses?: BuyerAddress[];
  preferences?: BuyerPreference[];
  suggestions?: BuyerSuggestion[];
  notifications?: BuyerNotification[];
  chatThreads?: BuyerChatThread[];
  trackedOrders?: BuyerTrackedOrder[];
  cartItems?: BuyerCartItem[];
  recentOrders?: Order[];
}
