"""Tính toán phí và voucher đơn hàng."""
from phuc_foodie.common.errors import ApiError

VOUCHERS = {
    "PHUC10": (10, 50000),
    "FOOD20": (20, 100000),
    "WELCOME15": (15, 50000),
}


def calculate_discount(voucher: str, subtotal: int) -> int:
    """Tính tiền giảm theo voucher (tỷ lệ phần trăm và ngưỡng tối thiểu)."""
    if not voucher:
        return 0
    voucher_key = voucher.upper().strip()
    if voucher_key not in VOUCHERS or subtotal < VOUCHERS[voucher_key][1]:
        raise ApiError("Mã giảm giá không hợp lệ hoặc đơn chưa đủ điều kiện.")
    return (subtotal * VOUCHERS[voucher_key][0] + 50) // 100


def calculate_shipping(subtotal: int, base_shipping: int, free_shipping_enabled: bool, free_shipping_threshold: int) -> int:
    """Tính phí giao hàng với ngưỡng miễn phí dựa trên subtotal trước voucher."""
    if free_shipping_enabled and subtotal >= free_shipping_threshold:
        return 0
    return base_shipping
