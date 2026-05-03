import { useState } from 'react'
import { useStore } from '@/store'

const SUBSCRIPTION_PRICES = {
  UA: {
    psplus: {
      1: { essential: 40, extra: 50, deluxe: 60 },
      3: { essential: 80, extra: 120, deluxe: 130 },
      12: { essential: 225, extra: 260, deluxe: 280 },
    },
    eaplay: {
      1: 40,
      12: 120,
    },
  },

  TR: {
    psplus: {
      1: { essential: 55, extra: 55, deluxe: 55 },
      3: { essential: 80, extra: 140, deluxe: 150 },
      12: { essential: 225, extra: 370, deluxe: 435 },
    },
    eaplay: {
      1: 35,
      12: 150,
    },
  },
} as const

const PS_PERIODS = [1, 3, 12] as const
const EA_PERIODS = [1, 12] as const

function tabStyle(active: boolean): React.CSSProperties {
  return {
    flex: 1,
    padding: '10px 0',
    borderRadius: 10,
    border: 'none',
    fontWeight: 700,
    fontSize: 13,
    cursor: 'pointer',
    background: active
      ? 'linear-gradient(135deg,#00d4aa,#00a8ff)'
      : 'transparent',
    color: active ? '#fff' : 'var(--text-secondary)',
    transition: 'all .2s',
  }
}

function Card({
  title,
  price,
  image,
}: {
  title: string
  price: number
  image: string
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        background: 'var(--bg-card)',
        borderRadius: 16,
        padding: 14,
        marginBottom: 12,
      }}
    >
      <img
        src={image}
        alt={title}
        style={{
          width: 90,
          height: 90,
          borderRadius: 12,
          objectFit: 'cover',
        }}
      />

      <div style={{ flex: 1, textAlign: 'right' }}>
        <div style={{ fontSize: 24, fontWeight: 900 }}>
          {price} BYN
        </div>

        <div
          style={{
            fontSize: 15,
            color: 'var(--text-secondary)',
            marginTop: 4,
          }}
        >
          {title}
        </div>

        <div
          style={{
            height: 4,
            width: 120,
            marginLeft: 'auto',
            marginTop: 8,
            borderRadius: 999,
            background: 'linear-gradient(135deg,#00d4aa,#00a8ff)',
          }}
        />
      </div>
    </div>
  )
}

export default function SubscriptionsSection() {
  const region = useStore((s) => s.region)

  const [psPeriod, setPsPeriod] = useState<1 | 3 | 12>(12)
  const [eaPeriod, setEaPeriod] = useState<1 | 12>(1)

  const prices = SUBSCRIPTION_PRICES[region]

  return (
    <div style={{ marginBottom: 24 }}>
      <section style={{ marginBottom: 32 }}>
        <h2 style={{ fontSize: 24, fontWeight: 900, marginBottom: 16 }}>
          Подписки PS Plus
        </h2>

        <div
          style={{
            display: 'flex',
            gap: 6,
            padding: 4,
            background: 'var(--bg-card)',
            borderRadius: 12,
            marginBottom: 16,
          }}
        >
          {PS_PERIODS.map((p) => (
            <button
              key={p}
              style={tabStyle(psPeriod === p)}
              onClick={() => setPsPeriod(p)}
            >
              {p} {p === 1 ? 'месяц' : p < 5 ? 'месяца' : 'месяцев'}
            </button>
          ))}
        </div>

        <Card
          title="PS Plus Essential"
          price={prices.psplus[psPeriod].essential}
          image="/images/ps-essential.jpg"
        />

        <Card
          title="PS Plus Extra"
          price={prices.psplus[psPeriod].extra}
          image="/images/ps-extra.jpg"
        />

        <Card
          title="PS Plus Deluxe"
          price={prices.psplus[psPeriod].deluxe}
          image="/images/ps-deluxe.jpg"
        />
      </section>

      <section>
        <h2 style={{ fontSize: 24, fontWeight: 900, marginBottom: 16 }}>
          Подписки EA Play
        </h2>

        <div
          style={{
            display: 'flex',
            gap: 6,
            padding: 4,
            background: 'var(--bg-card)',
            borderRadius: 12,
            marginBottom: 16,
          }}
        >
          {EA_PERIODS.map((p) => (
            <button
              key={p}
              style={tabStyle(eaPeriod === p)}
              onClick={() => setEaPeriod(p)}
            >
              {p} {p === 1 ? 'месяц' : 'месяцев'}
            </button>
          ))}
        </div>

        <Card
          title="EA Play"
          price={prices.eaplay[eaPeriod]}
          image="/images/ea-play.jpg"
        />
      </section>
    </div>
  )
}


