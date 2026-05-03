import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import api from "@/api"
import type { Product } from "@/types"
import { useStore } from "@/store"

import HeroBanner from "@/components/HeroBanner"
import ProductCard from "@/components/ProductCard"
import SubscriptionsSection from "@/components/SubscriptionsSection"
import TopUpSection from "@/components/TopUpSection"

type Tab = "all" | "new" | "preorder" | "subs" | "wallet"

export default function Home() {
  const nav    = useNavigate()
  const region = useStore(s => s.region)
  const [tab,       setTab]       = useState<Tab>("all")
  const [newGames,  setNewGames]  = useState<Product[]>([])
  const [preorders, setPreorders] = useState<Product[]>([])
  const [top10,     setTop10]     = useState<Product[]>([])

  useEffect(() => {
    const safe = (d: unknown): Product[] => Array.isArray(d) ? d : []

    api.get<Product[]>("/products", {
      params: { task_type: "new_games", region, limit: 40 },
    })
      .then(r => setNewGames(safe(r.data)))
      .catch(() => setNewGames([]))

    api.get<Product[]>("/products", {
      params: { task_type: "preorders", region, limit: 40 },
    })
      .then(r => setPreorders(safe(r.data)))
      .catch(() => setPreorders([]))

    api.get<Product[]>("/products", { params: { section: "top15", limit: 10 } })
      .then(r => setTop10(safe(r.data)))
      .catch(() => setTop10([]))
  }, [region])

  return (
    <main className="page">
      <div style={{ display: "flex", gap: 8, overflowX: "auto", marginBottom: 16 }}>
        {([ ["all","Все"], ["new","Новинки"], ["preorder","Предзаказы"],
            ["subs","Подписки"], ["wallet","Кошелёк"],
        ] as [Tab, string][]).map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id as Tab)}
            style={{
              padding: "8px 14px", borderRadius: 20, border: "none",
              cursor: "pointer", whiteSpace: "nowrap", fontWeight: 700,
              background: tab === id ? "var(--gradient)" : "var(--bg-card)",
              color:      tab === id ? "#fff" : "var(--text-secondary)",
            }}
          >{label}</button>
        ))}
        <button
          onClick={() => nav('/all-games')}
          style={{
            padding: "8px 14px", borderRadius: 20, border: "none",
            cursor: "pointer", whiteSpace: "nowrap", fontWeight: 700,
            background: "var(--gradient)",
            color: "#fff",
          }}
        >🎮 Все игры</button>
        <button
          onClick={() => nav('/sale')}
          style={{
            padding: "8px 14px", borderRadius: 20, border: "none",
            cursor: "pointer", whiteSpace: "nowrap", fontWeight: 700,
            background: "linear-gradient(135deg, #c0001a, #ff6b00)",
            color: "#fff",
          }}
        >🔥 Распродажа</button>
      </div>

      {tab === "all" && <HeroBanner />}

      {(tab === "all" || tab === "new") && newGames.length > 0 && (
        <section className="section">
          <h2 className="section__title">🆕 Новинки</h2>
          {tab === "all" ? (
            <div className="h-scroll">
              {newGames.slice(0, 10).map(p => <ProductCard key={p.id} product={p} />)}
            </div>
          ) : (
            <div className="game-grid-2">
              {newGames.map(p => <ProductCard key={p.id} product={p} />)}
            </div>
          )}
        </section>
      )}

      {(tab === "all" || tab === "preorder") && preorders.length > 0 && (
        <section className="section">
          <h2 className="section__title">⏳ Предзаказы</h2>
          {tab === "all" ? (
            <div className="h-scroll">
              {preorders.slice(0, 10).map(p => <ProductCard key={p.id} product={p} />)}
            </div>
          ) : (
            <div className="game-grid-2">
              {preorders.map(p => <ProductCard key={p.id} product={p} />)}
            </div>
          )}
        </section>
      )}

      {tab === "all" && top10.length > 0 && (
        <section className="section">
          <h2 className="section__title">🏆 Топ 10 продаж</h2>
          <div className="h-scroll">
            {top10.map(p => <ProductCard key={p.id} product={p} />)}
          </div>
        </section>
      )}

      {(tab === "all" || tab === "subs") && <SubscriptionsSection />}

      {(tab === "all" || tab === "wallet") && <TopUpSection />}
    </main>
  )
}
