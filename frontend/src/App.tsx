import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useStore } from '@/store'
import api from '@/api'
import type { PriceSettings } from '@/utils/price'
import Header     from '@/components/Header'
import Navigation from '@/components/Navigation'
import Home         from '@/pages/Home'
import ProductPage  from '@/pages/Product'
import Cart         from '@/pages/Cart'
import OrderSuccess from '@/pages/OrderSuccess'
import Profile      from '@/pages/Profile'
import Favourites   from '@/pages/Favourites'
import SalesHub      from '@/pages/SalesHub'
import Sale          from '@/pages/Sale'
import BigGamesSale  from '@/pages/BigGamesSale'
import HotDealsSale  from '@/pages/HotDealsSale'
import AllGames     from '@/pages/AllGames'
import NewGames     from '@/pages/NewGames'
import Preorders    from '@/pages/Preorders'
import Orders       from '@/pages/Orders'
import Keys         from '@/pages/Keys'
import AdminApp     from '@/pages/Admin'
import Collection   from '@/pages/Collection'

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        ready(): void
        expand(): void
        disableVerticalSwipes?(): void
        initDataUnsafe?: { user?: { id: number; username?: string; first_name?: string; last_name?: string } }
      }
    }
  }
}

function Layout() {
  const { pathname } = useLocation()
  const isProductPage  = pathname.startsWith('/product/')
  const isSuccessPage  = pathname === '/order-success'
  const isFullPage     = pathname.startsWith('/sale') || pathname.startsWith('/collection/') || ['/all-games', '/new-games', '/preorders', '/orders', '/keys'].includes(pathname)

  return (
    <>
      {!isProductPage && !isSuccessPage && !isFullPage && <Header />}
      <Routes>
        <Route path="/"              element={<Home />} />
        <Route path="/product/:id"   element={<ProductPage />} />
        <Route path="/cart"          element={<Cart />} />
        <Route path="/order-success" element={<OrderSuccess />} />
        <Route path="/profile"       element={<Profile />} />
        <Route path="/favourites"    element={<Favourites />} />
        <Route path="/sale"              element={<SalesHub />} />
        <Route path="/sale/all"          element={<Sale />} />
        <Route path="/sale/big-games"    element={<BigGamesSale />} />
        <Route path="/sale/hot-deals"    element={<HotDealsSale />} />
        <Route path="/all-games"     element={<AllGames />} />
        <Route path="/new-games"     element={<NewGames />} />
        <Route path="/preorders"     element={<Preorders />} />
        <Route path="/orders"        element={<Orders />} />
        <Route path="/keys"          element={<Keys />} />
        <Route path="/collection/:slug" element={<Collection />} />
        <Route path="*"              element={<Navigate to="/" replace />} />
      </Routes>
      {!isSuccessPage && <Navigation />}
    </>
  )
}

export default function App() {
  const setUserId = useStore(s => s.setUserId)
  const setPriceSettings = useStore(s => s.setPriceSettings)

  useEffect(() => {
    // Load price settings from backend once on startup
    api.get<PriceSettings>('/settings').then(r => {
      if (r.data && typeof r.data === 'object') setPriceSettings(r.data)
    }).catch(() => {})
  }, []) // eslint-disable-line

  useEffect(() => {
    // Lock viewport height to prevent collapse on scroll
    const lockHeight = () =>
      document.documentElement.style.setProperty('--app-h', `${window.innerHeight}px`)
    lockHeight()
    window.addEventListener('resize', lockHeight)

    // Skip all Telegram init on admin routes (opened in browser, not Telegram)
    if (window.location.pathname.startsWith('/admin')) {
      setUserId(123456789)
      return () => window.removeEventListener('resize', lockHeight)
    }

    // Compute Telegram safe area (device notch + Telegram UI buttons in fullscreen)
    const updateSafeArea = () => {
      const tgWA = window.Telegram?.WebApp as any
      const safeTop = (tgWA?.safeAreaInset?.top ?? 0) + (tgWA?.contentSafeAreaInset?.top ?? 0)
      document.documentElement.style.setProperty('--tg-top', `${safeTop}px`)
    }
    updateSafeArea()

    const tg = window.Telegram?.WebApp
    if (tg) {
      tg.ready()
      tg.expand()
      tg.disableVerticalSwipes?.()
      try {
        if ((tg as any).requestFullscreen) {
          (tg as any).requestFullscreen()
        }
      } catch (e) {
        console.log('requestFullscreen not supported:', e)
      }
      ;(tg as any).onEvent?.('safeAreaChanged', updateSafeArea);
      (tg as any).onEvent?.('contentSafeAreaChanged', updateSafeArea)
      const uid = tg.initDataUnsafe?.user?.id
      setUserId(uid ?? 123456789)
    } else {
      setUserId(123456789)
    }

    return () => window.removeEventListener('resize', lockHeight)
  }, [setUserId])

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/admin/*" element={<AdminApp />} />
        <Route path="/*" element={<Layout />} />
      </Routes>
    </BrowserRouter>
  )
}

