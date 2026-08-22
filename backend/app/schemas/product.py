#This defines the schema for creating a new product, you only pass what is needed to be created(product by user)(not the id, it made bugs here)
#pydantic checks for correct data types and required fields
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

class AISuggestRequest(BaseModel):
    name: str
    category: str | None = None
    current_price: float | None = None
    stock: int | None = None
    description: str | None = None
    seller_area: str | None = None

class AISuggestResponse(BaseModel):
    description: str
    suggested_price: float
    seo_keywords: list[str]
    confidence: float
    price_range: dict[str, float] | None = None
    trend_summary: str | None = None
    demand_level: str | None = None

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., min_length=1, max_length=100)
    price: float = Field(..., gt=0, description="Must be a positive price")
    stock: int = Field(..., ge=0, description="Zero is valid (out of stock); negative is not")
    description: str = Field(..., min_length=1, max_length=5000)
    image_url: str | None = None
    provider_id: int | None = None
    seller_id: int | None = None

    @field_validator("name", "category", "description")
    @classmethod
    def _reject_blank_after_strip(cls, value: str) -> str:
        # min_length=1 alone doesn't catch "   " (whitespace-only input),
        # which was previously accepted and produced garbage listings.
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class ProductSearchQuery(BaseModel):
    q: str | None = None
    category: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    in_stock: bool | None = None
    sort: str = "featured"
    limit: int = 50
    offset: int = 0


class ProductSearchResult(BaseModel):
    items: list
    total: int
    categories: list[str]


class CustomerCreate(BaseModel):
    name: str
    phone: str | None = None
    email: str | None = None
    location: str | None = None

class CustomerResponse(CustomerCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class RFQCreate(BaseModel):
    company_name: str
    contact_name: str
    email: str
    phone: str | None = None
    product_interest: str
    quantity: int
    target_budget: str | None = None
    notes: str | None = None


class ProviderCreate(BaseModel):
    name: str
    location: str | None = None
    email: str | None = None
    phone: str | None = None
    verified: bool = False
    response_time: str | None = None
    min_order_qty: str | None = None
    description: str | None = None
    rating_avg: float | None = None
    total_sales: int | None = None


class ProviderProfile(BaseModel):
    id: int
    name: str
    location: str | None = None
    email: str | None = None
    phone: str | None = None
    verified: bool = False
    response_time: str | None = None
    min_order_qty: str | None = None
    description: str | None = None
    rating_avg: float | None = None
    rating_count: int | None = None
    total_sales: int | None = None
    total_products: int | None = None
    created_at: str | None = None


class InventoryAlert(BaseModel):
    product_id: int
    product_name: str
    current_stock: int
    low_stock_threshold: int
    provider_id: int | None = None
    provider_name: str | None = None


class InventoryStats(BaseModel):
    total_products: int
    low_stock_count: int
    out_of_stock_count: int
    total_value: float
    alerts: list[InventoryAlert]


class PaymentMethod(BaseModel):
    id: str
    name: str
    type: str
    enabled: bool = True
    instructions: str | None = None


class MobileMoneyPayment(BaseModel):
    phone_number: str
    provider: str
    amount: float
    reference: str | None = None


class PaymentRequest(BaseModel):
    order_id: int
    amount: float
    payment_method: str
    phone_number: str | None = None
    notes: str | None = None


class PaymentResponse(BaseModel):
    transaction_id: str
    status: str
    amount: float
    message: str
    timestamp: str


class BusinessRegister(BaseModel):
    business_name: str
    owner_name: str
    phone: str
    email: str | None = None
    password: str
    business_type: str = "individual"
    category: str | None = None
    description: str | None = None
    region: str = "Dar es Salaam"
    area: str | None = None
    street: str | None = None
    shop_number: str | None = None
    operating_hours: str | None = None
    shop_logo_url: str | None = None
    shop_images: str | None = None
    profile_photo: str | None = None
    website_url: str | None = None
    social_facebook: str | None = None
    social_instagram: str | None = None
    social_whatsapp: str | None = None
    social_x: str | None = None
    role: str = "seller"


class BusinessLogin(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    password: str


class BusinessProfile(BaseModel):
    id: int
    business_name: str
    owner_name: str
    phone: str
    email: str | None = None
    business_type: str
    category: str | None = None
    description: str | None = None
    region: str | None = None
    area: str | None = None
    street: str | None = None
    shop_number: str | None = None
    operating_hours: str | None = None
    shop_logo_url: str | None = None
    shop_images: str | None = None
    profile_photo: str | None = None
    website_url: str | None = None
    social_facebook: str | None = None
    social_instagram: str | None = None
    social_whatsapp: str | None = None
    social_x: str | None = None
    verification_status: str
    role: str
    created_at: str | None = None


class BusinessUpdate(BaseModel):
    business_name: str | None = None
    owner_name: str | None = None
    business_type: str | None = None
    email: str | None = None
    phone: str | None = None
    category: str | None = None
    description: str | None = None
    region: str | None = None
    area: str | None = None
    street: str | None = None
    shop_number: str | None = None
    operating_hours: str | None = None
    shop_logo_url: str | None = None
    shop_images: str | None = None
    profile_photo: str | None = None
    website_url: str | None = None
    social_facebook: str | None = None
    social_instagram: str | None = None
    social_whatsapp: str | None = None
    social_x: str | None = None
    auto_confirm: bool | None = None


class BusinessVerificationSubmit(BaseModel):
    document_type: str
    document_url: str | None = None


class LogisticsRegister(BaseModel):
    name: str
    phone: str
    email: str | None = None
    password: str
    account_type: str = "individual"
    vehicle_type: str
    plate_number: str | None = None
    license_number: str | None = None
    base_area: str | None = None
    coverage_areas: str | None = None


class LogisticsLogin(BaseModel):
    phone: str | None = None
    email: str | None = None
    password: str


class LogisticsProfile(BaseModel):
    id: int
    name: str
    phone: str
    email: str | None = None
    account_type: str
    vehicle_type: str | None = None
    plate_number: str | None = None
    base_area: str | None = None
    coverage_areas: str | None = None
    status: str
    availability: str
    profile_photo: str | None = None
    verification_status: str
    created_at: str | None = None


class DeliveryOrderCreate(BaseModel):
    order_id: int | None = None
    seller_id: int | None = None
    buyer_id: int | None = None
    pickup_location: str
    delivery_location: str
    pickup_phone: str | None = None
    delivery_phone: str | None = None
    price: float | None = None


class DeliveryOrderResponse(BaseModel):
    id: int
    order_id: int | None = None
    seller_id: int | None = None
    buyer_id: int | None = None
    logistics_id: int | None = None
    pickup_location: str
    delivery_location: str
    status: str
    price: float | None = None
    verification_code: str | None = None
    created_at: str | None = None


class DeliveryStatusUpdate(BaseModel):
    status: str
    verification_code: str | None = None
    current_lat: float | None = None
    current_lng: float | None = None
    current_location: str | None = None
    failure_reason: str | None = None
    proof_type: str | None = None
    proof_note: str | None = None
    cod_amount_received: float | None = None
