import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import api from "@/api"
import type { Product } from "@/types"

type WalletRegion = "UA" | "TR" | "PL" | "IN"

const TABS: { id: WalletRegion; flag: string; label: string }[] = [
  { id: "UA", flag: "🇺🇦", label: "Украина" },
  { id: "TR", flag: "🇹🇷", label: "Турция" },
  { id: "PL", flag: "🇵🇱", label: "Польша" },
  { id: "IN", flag: "🇮🇳", label: "Индия" },
]

/** Detect wallet region from product title (matched to real DB titles) */
function detectRegion(title: string): WalletRegion | null {
  const t = title.toLowerCase()
  // Ukraine: "store ua" or "гривен" / "грн"
  if (t.includes("store ua") || t.includes("гривен") || t.includes("грн")) return "UA"
  // Turkey: "store tl" or "лир" (Turkish lira)
  if (t.includes("store tl") || t.includes(" лир") || t.includes("лиры") || t.includes("лирах")) return "TR"
  // Poland: "store pl" or "злот" / "pln"
  if (t.includes("store pl") || t.includes("злот") || t.includes("pln")) return "PL"
  // India: "store in" or "рупи" / "inr"
  if (t.includes("store in") || t.includes("рупи") || t.includes("inr")) return "IN"
  return null
}

/** Extract the first standalone number from a product title */
function extractAmount(title: string): number | null {
  const m = title.match(/\b(\d+)\b/)
  return m ? parseInt(m[1], 10) : null
}

/** Map product title to a local image in /images/ */
function localImage(title: string): string | null {
  const t = title.toLowerCase()
  const n = extractAmount(t)
  if (n === null) return null

  const isUA = t.includes("гривен") || t.includes("грн") || t.includes("store ua")
  const isTR = t.includes("store tl") || t.includes("лир")
  const isPL = t.includes("store pl") || t.includes("злот") || t.includes("pln") || t.includes(" zl")
  const isIN = t.includes("store in") || t.includes("рупи") || t.includes("inr")

  if (isUA) {
    const UA: Record<number, string> = {
      400:  "/images/topup-400uah.jpg",
      600:  "/images/topup600-uah.jpg",
      1000: "/images/topup1000-uah.jpg",
      2000: "/images/topup2000-uah.jpg",
      3000: "/images/topup3000-uah.jpg",
      4000: "/images/topup4000-uah.jpg",
    }
    return UA[n] ?? null
  }
  if (isTR) {
    const TR: Record<number, string> = {
      250:  "/images/topup250-tr.jpg",
      500:  "/images/topup500-tr.jpg",
      750:  "/images/topup750-tr.jpg",
      1000: "/images/topup1000-tr.jpg",
      1500: "/images/topup1500-tr.jpg",
      2000: "/images/topup2000-tr.jpg",
      2500: "/images/topup2500-tr.jpg",
      3000: "/images/topup3000-tr.jpg",
      4000: "/images/topup4000-tr.jpg",
      5000: "/images/topup5000-tr.jpg",
    }
    return TR[n] ?? null
  }
  if (isPL) {
    const PL: Record<number, string> = {
      50:   "/images/topup50-zl.jpg",
      100:  "/images/topup100-zl.jpg",
      200:  "/images/topup200-zl.jpg",
      300:  "/images/topup300-zl.jpg",
      350:  "/images/topup350-zl.jpg",
      500:  "/images/topup500-zl.jpg",
      650:  "/images/topup650-zl.jpg",
      900:  "/images/topup900-zl.jpg",
      1100: "/images/topup1100-zl.jpg",
    }
    return PL[n] ?? null
  }
  if (isIN) {
    const IN: Record<number, string> = {
      1000: "/images/topup1000-inr.jpg",
      2000: "/images/topup2000-inr.jpg",
      3000: "/images/topup3000-inr.jpg",
      4000: "/images/topup4000-inr.jpg",
      5000: "/images/topup5000-inr.jpg",
      6000: "/images/topup6000-inr.jpg",
      7000: "/images/topup7000-inr.jpg",
      8000: "/images/topup8000-inr.jpg",
      9000: "/images/topup9000-inr.jpg",
    }
    return IN[n] ?? null
  }
  return null
}

export default function TopUpSection() {
  const nav = useNavigate()
  const [products, setProducts] = useState<Product[]>([])
  const [activeTab, setActiveTab] = useState<WalletRegion>("UA")

  useEffect(() => {
    api
      .get<Product[]>("/products", { params: { product_type: "topup", limit: 100 } })
      .then((res) => setProducts(Array.isArray(res.data) ? res.data : []))
      .catch((err) => console.error(err))
  }, [])

  // Only show products whose region is detected AND matches the active tab
  const visible = products.filter((p) => detectRegion(p.title) === activeTab)

  if (!products.length) return null

  return (
    <section style={{ marginTop: 24 }}>
      <h2 style={{ fontSize: 24, fontWeight: 800, marginBottom: 12 }}>
        Пополнение кошелька
      </h2>

      {/* Region tabs */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, overflowX: "auto", scrollbarWidth: "none" }}>
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              flexShrink: 0,
              padding: "6px 14px",
              borderRadius: 20,
              border: "1.5px solid",
              borderColor: activeTab === tab.id ? "transparent" : "var(--border)",
              background: activeTab === tab.id ? "var(--gradient)" : "var(--bg-card)",
              color: activeTab === tab.id ? "#fff" : "var(--text-secondary)",
              fontWeight: 700,
              fontSize: 13,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 5,
            }}
          >
            {tab.flag} {tab.label}
          </button>
        ))}
      </div>

      {/* Product grid */}
      {visible.length === 0 ? (
        <div style={{
          textAlign: "center",
          padding: "32px 0",
          color: "var(--text-secondary)",
          fontSize: 14,
        }}>
          Нет товаров для этого региона
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 14 }}>
          {visible.map((product) => {
            const img = localImage(product.title) ?? product.image_url ?? undefined
            return (
              <div
                key={product.id}
                onClick={() => nav(`/product/${product.id}`)}
                style={{
                  background: "var(--bg-card)",
                  padding: 14,
                  borderRadius: 16,
                  textAlign: "center",
                  cursor: "pointer",
                  border: "1px solid var(--border)",
                }}
              >
                <img
                  src={img}
                  alt={product.title}
                  style={{
                    width: "100%",
                    height: 130,
                    objectFit: "contain",
                    marginBottom: 10,
                    borderRadius: 10,
                  }}
                  onError={(e) => {
                    (e.currentTarget as HTMLImageElement).style.display = "none"
                  }}
                />
                <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 6, lineHeight: 1.3 }}>
                  {product.title}
                </div>
                <div style={{ color: "#00e0c6", fontWeight: 800, fontSize: 18 }}>
                  {product.price_byn} BYN
                </div>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
