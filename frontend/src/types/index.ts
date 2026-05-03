export type Region = 'UA' | 'TR'

export interface Category {
  id: number
  name: string
  slug: string
  icon: string | null
  sort_order: number
}

export interface Edition {
  id: number
  name: string
  price_uah: number | null
  price_try: number | null
  price_inr: number | null
  price_pln: number | null
  is_default: boolean
  sort_order: number
}

export interface GameEdition {
  id: number
  edition_name: string
  price_uah: number | null
  price_try: number | null
  price_byn: number | null
  price_byn_tr: number | null
  old_price_uah: number | null
  old_price_try: number | null
  discount_pct: number
  platform: string | null
  ps_store_url: string | null
  region: string
  is_free: boolean
  linked_product_id?: number | null
}

export interface Product {
  id: number
  category_id: number
  title: string
  description: string | null
  image_url: string | null
  price_uah: number | null
  price_try: number | null
  price_inr: number | null
  price_pln: number | null
  price_byn: number | null
  price_byn_tr: number | null
  platform: string | null
  rating: number
  is_featured: boolean
  discount_pct: number
  discount_until: string | null
  release_date: string | null
  product_type: string
  is_preorder: boolean
  genre: string | null
  requires_ps_plus: boolean
  editions: Edition[]
}

export interface CartItem {
  id: number
  product_id: number
  quantity: number
  region: Region
  title: string
  image_url: string | null
  price: number | null
}

export interface OrderItem {
  product_id: number
  title: string
  quantity: number
  price_paid: number
  region: Region
}

export interface Order {
  id: number
  user_id: number
  status: string
  total_byn: number
  items: OrderItem[]
  created_at: string
}

