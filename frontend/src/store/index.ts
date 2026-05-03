import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { CartItem, Product, Region } from '@/types'
import { type PriceSettings, DEFAULT_PRICE_SETTINGS } from '@/utils/price'

interface AppState {
  region: Region
  setRegion: (r: Region) => void

  // cart (local mirror – source of truth is the server)
  cartItems: CartItem[]
  setCartItems: (items: CartItem[]) => void

  // favourites (local)
  favouriteIds: Set<number>
  toggleFavourite: (id: number) => void

  // telegram user_id (read from initData)
  userId: number | null
  setUserId: (id: number) => void

  // search (not persisted)
  searchQuery: string
  searchResults: Product[] | null   // null = no active search
  searchLoading: boolean
  setSearch: (query: string, results: Product[] | null, loading?: boolean) => void
  clearSearch: () => void

  // price settings (loaded from backend on startup)
  priceSettings: PriceSettings
  setPriceSettings: (s: PriceSettings) => void
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      region: 'UA',
      setRegion: (region) => set({ region }),

      cartItems: [],
      setCartItems: (cartItems) => set({ cartItems }),

      favouriteIds: new Set(),
      toggleFavourite: (id) =>
        set((s) => {
          const next = new Set(s.favouriteIds)
          next.has(id) ? next.delete(id) : next.add(id)
          return { favouriteIds: next }
        }),

      userId: null,
      setUserId: (userId) => set({ userId }),

      searchQuery: '',
      searchResults: null,
      searchLoading: false,
      setSearch: (searchQuery, searchResults, searchLoading = false) =>
        set({ searchQuery, searchResults, searchLoading }),
      clearSearch: () => set({ searchQuery: '', searchResults: null, searchLoading: false }),

      priceSettings: DEFAULT_PRICE_SETTINGS,
      setPriceSettings: (priceSettings) => set({ priceSettings }),
    }),
    {
      name: 'tg-shop',
      // Sets are not JSON-serialisable by default
      partialize: (s) => ({
        region: s.region,
        favouriteIds: [...s.favouriteIds],
      }),
      merge: (persisted: any, current) => ({
        ...current,
        ...(persisted as object),
        favouriteIds: new Set((persisted as any).favouriteIds ?? []),
      }),
    }
  )
)
