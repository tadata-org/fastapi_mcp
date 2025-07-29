from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class Item(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    tags: List[str] = []


class OrderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"


class PaymentMethod(str, Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PAYPAL = "paypal"
    BANK_TRANSFER = "bank_transfer"
    CASH_ON_DELIVERY = "cash_on_delivery"


class ProductCategory(str, Enum):
    ELECTRONICS = "electronics"
    CLOTHING = "clothing"
    FOOD = "food"
    BOOKS = "books"
    OTHER = "other"


class ProductVariant(BaseModel):
    sku: str = Field(..., description="Stock keeping unit code")
    color: Optional[str] = Field(None, description="Color variant")
    size: Optional[str] = Field(None, description="Size variant")
    weight: Optional[float] = Field(None, description="Weight in kg", gt=0)
    dimensions: Optional[Dict[str, float]] = Field(None, description="Dimensions in cm (length, width, height)")
    in_stock: bool = Field(True, description="Whether this variant is in stock")
    stock_count: Optional[int] = Field(None, description="Number of items in stock", ge=0)


class Address(BaseModel):
    street: str
    city: str
    state: str
    postal_code: str
    country: str
    is_primary: bool = False


class CustomerTier(str, Enum):
    STANDARD = "standard"
    PREMIUM = "premium"
    VIP = "vip"


class Customer(BaseModel):
    id: UUID
    email: str
    full_name: str
    phone: Optional[str] = Field(None, min_length=10, max_length=15)
    tier: CustomerTier = CustomerTier.STANDARD
    addresses: List[Address] = []
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None
    preferences: Dict[str, Any] = {}
    consent: Dict[str, bool] = {}


class Product(BaseModel):
    id: UUID
    name: str
    description: str
    category: ProductCategory
    price: float = Field(..., gt=0)
    discount_percent: Optional[float] = Field(None, ge=0, le=100)
    tax_rate: Optional[float] = Field(None, ge=0, le=100)
    variants: List[ProductVariant] = []
    tags: List[str] = []
    image_urls: List[str] = []
    rating: Optional[float] = Field(None, ge=0, le=5)
    review_count: int = Field(0, ge=0)
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_available: bool = True
    metadata: Dict[str, Any] = {}
    related_products: Optional[List[Product]] = None


class OrderItem(BaseModel):
    product_id: UUID
    variant_sku: Optional[str] = None
    quantity: int = Field(..., gt=0)
    unit_price: float
    discount_amount: float = 0
    total: float


class PaymentDetails(BaseModel):
    method: PaymentMethod
    transaction_id: Optional[str] = None
    status: str
    amount: float
    currency: str = "USD"
    paid_at: Optional[datetime] = None


class OrderRequest(BaseModel):
    customer_id: UUID
    items: List[OrderItem]
    shipping_address_id: UUID
    billing_address_id: Optional[UUID] = None
    payment_method: PaymentMethod
    notes: Optional[str] = None
    use_loyalty_points: bool = False


class OrderResponse(BaseModel):
    id: UUID
    customer_id: UUID
    status: OrderStatus = OrderStatus.PENDING
    items: List[OrderItem]
    shipping_address: Address
    billing_address: Address
    payment: PaymentDetails
    subtotal: float
    shipping_cost: float
    tax_amount: float
    discount_amount: float
    total_amount: float
    tracking_number: Optional[str] = None
    estimated_delivery: Optional[date] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = {}


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    size: int
    pages: int


class ErrorResponse(BaseModel):
    status_code: int
    message: str
    details: Optional[Dict[str, Any]] = None
