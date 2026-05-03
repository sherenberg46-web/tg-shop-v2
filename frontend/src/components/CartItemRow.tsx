import type { CartItem } from '@/types'
import { formatBYN } from '@/utils/price'

interface Props {
  item: CartItem
  onIncrease: () => void
  onDecrease: () => void
  onRemove: () => void
}

export default function CartItemRow({ item, onIncrease, onDecrease, onRemove }: Props) {
  // price from API is already in BYN (converted server-side)
  const byn = item.price != null ? item.price * item.quantity : null
  return (
    <div className="cart-item">
      <img
        className="cart-item__img"
        src={item.image_url ?? 'https://placehold.co/64x64?text=?'}
        alt={item.title}
      />
      <div className="cart-item__info">
        <p className="cart-item__title">{item.title}</p>
        {byn != null && (
          <p className="cart-item__price">{formatBYN(byn)}</p>
        )}
        <div className="qty-control" style={{ marginTop: 6 }}>
          <button className="qty-btn" onClick={onDecrease}>−</button>
          <span style={{ fontSize: 14, fontWeight: 600 }}>{item.quantity}</span>
          <button className="qty-btn" onClick={onIncrease}>+</button>
        </div>
      </div>
      <button onClick={onRemove} style={{ color: 'red', fontSize: 20, padding: 4 }}>✕</button>
    </div>
  )
}
