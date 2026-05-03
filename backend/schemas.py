"""Pydantic request / response schemas."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional


class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str
    icon: Optional[str] = None
    sort_order: int


class EditionOut(BaseModel):
    id: int
    name: str
    price_uah: Optional[float] = None
    price_try: Optional[float] = None
    price_inr: Optional[float] = None
    price_pln: Optional[float] = None
    is_default: bool = False
    sort_order: int = 0


class GameEditionOut(BaseModel):
    id: int
    edition_name: str
    price_uah: Optional[float] = None
    price_try: Optional[float] = None
    price_byn: Optional[int] = None
    price_byn_tr: Optional[int] = None
    old_price_uah: Optional[float] = None
    old_price_try: Optional[float] = None
    discount_pct: int = 0
    platform: Optional[str] = None
    ps_store_url: Optional[str] = None
    region: str = "UA"
    is_free: bool = False
    linked_product_id: Optional[int] = None


class ProductOut(BaseModel):
    id: int
    category_id: int
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    price_uah: Optional[float] = None
    price_try: Optional[float] = None
    price_inr: Optional[float] = None
    price_pln: Optional[float] = None
    price_byn: Optional[int] = None
    price_byn_tr: Optional[int] = None
    platform: Optional[str] = None
    rating: float = 0
    is_featured: bool = False
    discount_pct: float = 0
    discount_until: Optional[str] = None
    release_date: Optional[str] = None
    product_type: str = "game"
    is_preorder: bool = False
    task_type: Optional[str] = ""
    region: Optional[str] = "UA"
    genre: Optional[str] = None
    requires_ps_plus: bool = False
    editions: list[EditionOut] = []


class ProductIn(BaseModel):
    category_id: int
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    price_uah: Optional[float] = None
    price_try: Optional[float] = None
    price_inr: Optional[float] = None
    price_pln: Optional[float] = None
    price_byn: Optional[int] = None
    price_byn_tr: Optional[int] = None
    platform: Optional[str] = "PS"
    rating: float = 0
    is_featured: bool = False
    is_active: bool = True
    discount_pct: float = 0
    discount_until: Optional[str] = None
    release_date: Optional[str] = None
    product_type: str = "game"
    is_preorder: bool = False


class CartItemIn(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1)
    region: str = Field(default="UA", pattern="^(UA|TR|IN|PL)$")


class CartItemOut(BaseModel):
    id: int
    product_id: int
    quantity: int
    region: str
    title: str
    image_url: Optional[str] = None
    price: Optional[float] = None


class OrderIn(BaseModel):
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    region: str = Field(default="UA", pattern="^(UA|TR|IN|PL)$")
    items: list[CartItemIn]
    account_type: Optional[str] = "no_account"
    ps_email: Optional[str] = None
    ps_password: Optional[str] = None


class OrderItemOut(BaseModel):
    product_id: int
    title: str
    quantity: int
    price_paid: float
    region: str


class OrderOut(BaseModel):
    id: int
    user_id: int
    status: str
    total_byn: float = 0
    items: list[OrderItemOut]
    created_at: str
    account_type: Optional[str] = "no_account"
    ps_email: Optional[str] = None
    ps_password: Optional[str] = None


class AdminLoginIn(BaseModel):
    password: str


class AdminStatusIn(BaseModel):
    status: str


class MessageOut(BaseModel):
    message: str
