// ========================================================
// PHUC-FOODIE - script.js
// Nhiệm vụ: Xử lý toàn bộ logic và tương tác người dùng
// ========================================================

// 1. KHỞI TẠO DỮ LIỆU SẢN PHẨM KÈM MÔ TẢ (Array of Objects)
const products = []; // Danh sách lấy từ server trong api.js.

// 2. MẢNG QUẢN LÝ GIỎ HÀNG VÀ TRẠNG THÁI
let cart = [];
let cartHydrated = false;
let currentCategory = "Tất cả";
let searchKeyword = "";

// Biến lưu thông tin cấu hình cửa hàng và khu vực giao hàng (STEP STORE SETTINGS)
let storeInfo = null;
let selectedDeliveryZoneId = null;

// Biến trạng thái modal chi tiết sản phẩm
let currentModalProductId = null;
let selectedQuantity = 1;

// ========================================================
// HỆ THỐNG VOUCHER / MÃ GIẢM GIÁ (BƯỚC 9)
// ========================================================

// Danh sách mã giảm giá hợp lệ
const vouchers = [
    {
        code: "PHUC10",
        discount: 10,        // Giảm 10%
        minOrder: 50000      // Đơn tối thiểu 50.000đ
    },
    {
        code: "FOOD20",
        discount: 20,        // Giảm 20%
        minOrder: 100000     // Đơn tối thiểu 100.000đ
    },
    {
        code: "WELCOME15",
        discount: 15,        // Giảm 15%
        minOrder: 50000      // Đơn tối thiểu 50.000đ
    }
];

// Biến lưu voucher đang được áp dụng (null = chưa áp dụng)
let appliedVoucher = null;

// 3. HÀM HIỂN THỊ THÔNG BÁO DẠNG TOAST
function showToast(title, message, type = "success") {
    const container = document.getElementById("toast-container");
    if (!container) {
        alert(message ? `${escapeHtml(title)}\n${escapeHtml(message)}` : title);
        return;
    }

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <div class="toast-icon">${type === "success" ? "✓" : "!"}</div>
        <div class="toast-body">
            <strong class="toast-title">${escapeHtml(title)}</strong>
            <p class="toast-message">${escapeHtml(message)}</p>
        </div>
    `;

    container.appendChild(toast);

    setTimeout(function () {
        toast.classList.add("fade-out");
        setTimeout(function () {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 3500);
}

// 4. HÀM ĐIỀU HƯỚNG CUỘN MƯỢT TRANG (Smooth Scroll)
function scrollToSection(sectionId) {
    if (sectionId === "home") {
        window.scrollTo({ top: 0, behavior: "smooth" });
        return;
    }
    const section = document.getElementById(sectionId);
    if (section) {
        section.scrollIntoView({ behavior: "smooth" });
    }
}

function filterAndScrollCategory(categoryName) {
    const categoryButtons = document.querySelectorAll(".btn-category");
    categoryButtons.forEach(function (button) {
        if (button.getAttribute("data-category") === categoryName) {
            button.click();
        }
    });

    scrollToSection("menu-section");
}

// 5. HIỂN THỊ DANH SÁCH MENU SẢN PHẨM (renderProducts)
function renderProducts(itemsToRender) {
    const productContainer = document.getElementById("product-list");
    if (!productContainer) return;

    if (itemsToRender.length === 0) {
        productContainer.innerHTML = `
            <div class="no-results">
                <p>Không tìm thấy món ăn phù hợp.</p>
            </div>
        `;
        return;
    }

    let htmlContent = "";

    itemsToRender.forEach(function (product) {
        const formattedPrice = product.price.toLocaleString("vi-VN") + "đ";
        const isAvailable = Boolean(product.available);
        const stock = product.stock_quantity;

        let statusText = "";
        let canOrder = false;
        let btnText = "Thêm vào giỏ";

        if (!isAvailable) {
            statusText = "Tạm ngừng bán";
            canOrder = false;
            btnText = "Tạm ngừng bán";
        } else if (stock === null || stock === undefined) {
            statusText = "Chưa mở bán";
            canOrder = false;
            btnText = "Chưa mở bán";
        } else if (stock === 0) {
            statusText = "Hết hàng";
            canOrder = false;
            btnText = "Hết hàng";
        } else {
            statusText = `Còn ${stock} phần`;
            canOrder = true;
            btnText = "Thêm vào giỏ";
        }

        // Click vào card mở modal chi tiết sản phẩm; click nút Thêm vào giỏ có stopPropagation
        htmlContent += `
            <div class="product-card" onclick="openProductModal(${product.id})">
                <div class="product-image-wrap">
                    <img src="${escapeHtml(product.image)}" alt="${escapeHtml(product.name)}" class="product-image" loading="lazy">
                    <span class="product-badge">${escapeHtml(product.category)}</span>
                    <span class="product-stock-tag ${canOrder ? "in-stock" : "out-stock"}" style="position:absolute;bottom:8px;left:8px;background:${canOrder ? "rgba(16,185,129,0.9)" : "rgba(239,68,68,0.9)"};color:#fff;padding:2px 8px;border-radius:12px;font-size:0.75rem;font-weight:600;">${escapeHtml(statusText)}</span>
                </div>
                <div class="product-info">
                    <h3 class="product-name">${escapeHtml(product.name)}</h3>
                    <p class="product-price">${formattedPrice}</p>
                    <button class="btn-add-cart" type="button" onclick="event.stopPropagation(); addToCart(${product.id})"${canOrder ? "" : "disabled"}>${escapeHtml(btnText)}</button>
                </div>
            </div>
        `;
    });

    productContainer.innerHTML = htmlContent;
}

// 6. BỘ LỌC KẾT HỢP TÌM KIẾM VÀ DANH MỤC (filterProducts)
function filterProducts() {
    const filtered = products.filter(function (product) {
        const matchCategory = (currentCategory === "Tất cả") || (product.category === currentCategory);
        const productNameLower = product.name.toLowerCase();
        const keywordLower = searchKeyword.toLowerCase().trim();
        const matchSearch = productNameLower.includes(keywordLower);

        return matchCategory && matchSearch;
    });

    renderProducts(filtered);
}

// 7. THÊM SẢN PHẨM VÀO GIỎ HÀNG (addToCart có hỗ trợ số lượng và kiểm tra tồn kho)
function addToCart(productId, quantity = 1) {
    const product = products.find(function (item) {
        return item.id === productId;
    });

    if (!product) return;
    if (!product.available) {
        showToast("Tạm ngừng bán", "Món này hiện đang tạm ngừng bán.", "warning");
        return;
    }
    if (product.stock_quantity === null || product.stock_quantity === undefined) {
        showToast("Chưa sẵn sàng", "Món này chưa thiết lập tồn kho để bán.", "warning");
        return;
    }
    if (product.stock_quantity <= 0) {
        showToast("Hết hàng", "Món này hiện đã hết hàng.", "warning");
        return;
    }

    const maxStock = Math.min(product.stock_quantity, 99);
    const qtyToAdd = Number.isInteger(quantity) && quantity > 0 ? quantity : 1;
    const oldQty = cart.find(i => i.id === productId)?.quantity || 0;

    if (oldQty + qtyToAdd > maxStock) {
        showToast("Giới hạn tồn kho", `Món này chỉ còn ${product.stock_quantity} phần (bạn đã có ${oldQty} phần trong giỏ).`, "warning");
        return;
    }

    const existingItem = cart.find(function (item) {
        return item.id === productId;
    });

    if (existingItem) {
        existingItem.quantity += qtyToAdd;
    } else {
        cart.push({
            id: product.id,
            name: product.name,
            price: product.price,
            image: product.image,
            quantity: qtyToAdd
        });
    }

    renderCart();
    updateCartCount();

    const qtyText = qtyToAdd > 1 ? ` x${qtyToAdd}` : "";
    showToast("✓ Đã thêm vào giỏ", `${escapeHtml(product.name)}${qtyText} đã được thêm vào giỏ hàng.`, "success");
}

// 8. TĂNG SỐ LƯỢNG MÓN TRONG GIỎ (increaseQuantity)
function increaseQuantity(productId) {
    const item = cart.find(function (cartItem) {
        return cartItem.id === productId;
    });
    const product = products.find(p => p.id === productId);

    if (item) {
        const maxStock = product && product.stock_quantity !== null && product.stock_quantity !== undefined
            ? Math.min(product.stock_quantity, 99)
            : 99;

        if (item.quantity >= maxStock) {
            showToast("Giới hạn tồn kho", `Món này chỉ còn ${maxStock} phần trong kho.`, "warning");
            return;
        }
        item.quantity += 1;
        checkVoucherValidity(); // Kiểm tra lại voucher sau khi thay đổi giỏ
        renderCart();
        updateCartCount();
    }
}

// 9. GIẢM SỐ LƯỢNG MÓN TRONG GIỎ (decreaseQuantity)
function decreaseQuantity(productId) {
    const itemIndex = cart.findIndex(function (cartItem) {
        return cartItem.id === productId;
    });

    if (itemIndex !== -1) {
        if (cart[itemIndex].quantity > 1) {
            cart[itemIndex].quantity -= 1;
        } else {
            cart.splice(itemIndex, 1);
        }
        checkVoucherValidity(); // Kiểm tra lại voucher sau khi thay đổi giỏ
        renderCart();
        updateCartCount();
    }
}

// 10. XÓA MÓN KHỎI GIỎ HÀNG (removeFromCart)
function removeFromCart(productId) {
    cart = cart.filter(function (cartItem) {
        return cartItem.id !== productId;
    });

    checkVoucherValidity(); // Kiểm tra lại voucher sau khi xóa món
    renderCart();
    updateCartCount();
}

// 11. TÍNH TỔNG TIỀN GIỎ HÀNG (calculateTotal)
function calculateTotal() {
    let total = 0;
    cart.forEach(function (item) {
        total += item.price * item.quantity;
    });
    return total;
}

// 11b. TÍNH TIỀN GIẢM TỪ VOUCHER (calculateDiscount)
function calculateDiscount() {
    if (!appliedVoucher) return 0;
    const discount = calculateTotal() * appliedVoucher.discount / 100;
    return Math.round(discount); // Làm tròn đến đơn vị đồng
}

// 11c. TÍNH PHÍ GIAO HÀNG (calculateShippingFee - STEP STORE SETTINGS)
// Quy tắc:
// - Phí cơ sở: Nếu đã có khu vực, lấy phí theo khu vực khách chọn; nếu chưa có khu vực, lấy phí mặc định 15.000đ.
// - Ngưỡng miễn phí: Nếu bật miễn phí giao hàng theo giá trị đơn và subtotal >= ngưỡng (mặc định 100.000đ) thì phí = 0đ.
// - Ngưỡng được tính trên tiền món (subtotal) trước khi trừ voucher.
// - Nếu giỏ hàng rỗng (subtotal <= 0), phí giao hàng = 0đ.
function getActiveZoneFee() {
    if (!storeInfo) return 15000;
    if (storeInfo.hasDeliveryZones) {
        if (!selectedDeliveryZoneId) {
            return storeInfo.defaultShippingFee || 15000;
        }
        const zone = (storeInfo.deliveryZones || []).find(z => z.id === Number(selectedDeliveryZoneId));
        return zone ? zone.fee : (storeInfo.defaultShippingFee || 15000);
    }
    return storeInfo.defaultShippingFee || 15000;
}

function calculateShippingFee(customSubtotal) {
    const subtotal = typeof customSubtotal === "number" ? customSubtotal : calculateTotal();
    if (subtotal <= 0) {
        return 0;
    }
    const baseFee = getActiveZoneFee();
    if (storeInfo) {
        if (storeInfo.freeShippingEnabled && subtotal >= storeInfo.freeShippingThreshold) {
            return 0;
        }
        return baseFee;
    }
    // Fallback mặc định khi chưa tải được storeInfo
    if (subtotal >= 100000) {
        return 0;
    }
    return baseFee;
}

// 11d. TÍNH TỔNG THANH TOÁN (calculateGrandTotal - STEP 10)
// Công thức: grandTotal = calculateTotal() + calculateShippingFee() - calculateDiscount()
// Đảm bảo grandTotal không bao giờ nhỏ hơn 0
function calculateGrandTotal() {
    const subtotal = calculateTotal();
    if (subtotal <= 0) {
        return 0;
    }
    const shippingFee = calculateShippingFee(subtotal);
    const discount = calculateDiscount();
    const grandTotal = subtotal + shippingFee - discount;
    return Math.max(0, grandTotal);
}

// 11e. TÍNH TỔNG SAU GIẢM GIÁ (calculateFinalTotal - giữ lại để tương thích)
function calculateFinalTotal() {
    return calculateGrandTotal();
}

// 11d. KIỂM TRA TÍNH HỢP LỆ CỦA VOUCHER ĐANG ÁP DỤNG
// Dùng khi giỏ hàng thay đổi (xóa/giảm số lượng)
function checkVoucherValidity() {
    if (!appliedVoucher) return; // Chưa có voucher, bỏ qua

    const total = calculateTotal();
    if (total < appliedVoucher.minOrder) {
        // Đơn hàng xuống dưới minOrder → tự động bỏ voucher
        const removedCode = appliedVoucher.code;
        appliedVoucher = null;
        showToast(
            "⚠ Đã bỏ mã giảm giá",
            `Mã ${removedCode} đã bị bỏ vì đơn hàng không còn đủ điều kiện.`,
            "warning"
        );
    }
}

// 11e. ÁP DỤNG MÃ GIẢM GIÁ (applyVoucher)
function applyVoucher() {
    const input = document.getElementById("voucher-input");
    if (!input) return;

    const rawCode = input.value.trim().toUpperCase(); // Chuyển hoa và xóa khoảng trắng

    // Kiểm tra giỏ hàng trống
    if (cart.length === 0) {
        showToast("⚠ Giỏ hàng trống", "Vui lòng thêm sản phẩm vào giỏ trước.", "warning");
        return;
    }

    // Kiểm tra mã rỗng
    if (rawCode === "") {
        showToast("⚠ Thiếu mã", "Vui lòng nhập mã giảm giá.", "warning");
        return;
    }

    // Tìm mã trong danh sách vouchers
    const found = vouchers.find(function (v) {
        return v.code === rawCode;
    });

    if (!found) {
        showToast("⚠ Mã không hợp lệ", `Mã "${rawCode}" không tồn tại.`, "warning");
        return;
    }

    // Kiểm tra điều kiện đơn hàng tối thiểu
    const total = calculateTotal();
    if (total < found.minOrder) {
        const minFormatted = found.minOrder.toLocaleString("vi-VN") + "đ";
        showToast(
            "⚠ Chưa đủ điều kiện",
            `Đơn hàng cần tối thiểu ${minFormatted} để dùng mã ${found.code}.`,
            "warning"
        );
        return;
    }

    // Áp dụng voucher thành công
    appliedVoucher = found;
    showToast(
        "✓ Áp dụng voucher thành công!",
        `Mã ${found.code} giảm ${found.discount}%.`,
        "success"
    );
    renderCart(); // Cập nhật giỏ hàng
}

// 11f. XÓA MÃ GIẢM GIÁ (removeVoucher)
function removeVoucher() {
    if (!appliedVoucher) return;
    appliedVoucher = null;

    const input = document.getElementById("voucher-input");
    if (input) input.value = "";

    showToast("Đã bỏ mã giảm giá", "Mã giảm giá đã được gỡ bỏ.", "success");
    renderCart();
}

// 12. CẬP NHẬT SỐ LƯỢNG GIỎ HÀNG TRÊN HEADER (updateCartCount)
function updateCartCount() {
    let totalCount = 0;
    cart.forEach(function (item) {
        totalCount += item.quantity;
    });

    const cartCountElement = document.getElementById("cart-count");
    if (cartCountElement) {
        cartCountElement.textContent = totalCount;
    }
}

// 13. HIỂN THỊ GIỎ HÀNG (renderCart)
function renderCart() {
    if (cartHydrated) try { localStorage.setItem("phuc_foodie_cart_v2", JSON.stringify(cart.map(i => ({id:i.id, quantity:i.quantity})))); } catch {}
    const cartItemsContainer = document.getElementById("cart-items");
    const cartTotalPrice = document.getElementById("cart-total-price");
    const checkoutSection = document.getElementById("checkout-section");

    if (!cartItemsContainer || !cartTotalPrice) return;

    if (cart.length === 0) {
        cartItemsContainer.innerHTML = `
            <div class="cart-empty-msg">
                <p>Giỏ hàng đang trống.</p>
            </div>
        `;
        cartTotalPrice.textContent = "0đ";

        // Reset voucher khi giỏ trống
        appliedVoucher = null;
        renderVoucherSection(); // Cập nhật khu vực voucher

        if (checkoutSection) {
            checkoutSection.style.display = "none";
        }
        return;
    }

    let htmlContent = "";

    cart.forEach(function (item) {
        const itemUnitPrice = item.price.toLocaleString("vi-VN") + "đ";
        const itemSubtotal = (item.price * item.quantity).toLocaleString("vi-VN") + "đ";

        htmlContent += `
            <div class="cart-item">
                <img src="${escapeHtml(item.image)}" alt="${escapeHtml(item.name)}" class="cart-item-img">
                <div class="cart-item-info">
                    <h4 class="cart-item-name">${escapeHtml(item.name)}</h4>
                    <p class="cart-item-price">${itemUnitPrice}</p>
                </div>
                <div class="cart-quantity-controls">
                    <button class="btn-qty" type="button" onclick="decreaseQuantity(${item.id})">-</button>
                    <span class="cart-qty-value">${item.quantity}</span>
                    <button class="btn-qty" type="button" onclick="increaseQuantity(${item.id})">+</button>
                </div>
                <div class="cart-item-subtotal">
                    ${itemSubtotal}
                </div>
                <button class="btn-remove-item" type="button" onclick="removeFromCart(${item.id})" title="Xóa món">
                    🗑 Xóa
                </button>
            </div>
        `;
    });

    cartItemsContainer.innerHTML = htmlContent;

    // Cập nhật khu vực voucher và bảng tổng tiền chi tiết
    renderVoucherSection();

    // Cập nhật hiển thị tổng tiền (dùng calculateGrandTotal cho tổng thanh toán cuối cùng)
    const grandTotal = calculateGrandTotal();
    cartTotalPrice.textContent = grandTotal.toLocaleString("vi-VN") + "đ";

    // Cập nhật tóm tắt checkout nếu đang mở
    renderCheckoutSummary();
}

// 13b. HIỂN THỊ KHU VỰC VOUCHER VÀ BẢNG TỔNG CHI TIẾT (STEP 10)
function renderVoucherSection() {
    const voucherSection = document.getElementById("voucher-section");
    const cartPriceDetails = document.getElementById("cart-price-details");
    if (!voucherSection) return;

    // ---- PHẦN NHẬP VOUCHER ----
    const currentInputVal = appliedVoucher ? appliedVoucher.code : (document.getElementById("voucher-input") ? document.getElementById("voucher-input").value : "");

    if (cart.length === 0) {
        // Giỏ trống: ẩn khu vực voucher và bảng chi tiết
        voucherSection.style.display = "none";
        if (cartPriceDetails) cartPriceDetails.style.display = "none";
        return;
    }

    voucherSection.style.display = "block";

    if (appliedVoucher) {
        // Đã áp dụng voucher → hiển thị trạng thái đã áp dụng
        voucherSection.innerHTML = `
            <div class="voucher-wrap">
                <span class="voucher-label">🎟️ Mã giảm giá</span>
                <div class="voucher-applied">
                    <span class="voucher-applied-badge">
                        <span class="voucher-applied-code">${appliedVoucher.code}</span>
                        <span class="voucher-applied-pct">Giảm ${appliedVoucher.discount}%</span>
                    </span>
                    <button type="button" class="btn-remove-voucher" onclick="removeVoucher()">Xóa</button>
                </div>
            </div>
        `;
    } else {
        // Chưa áp dụng → hiển thị ô nhập
        voucherSection.innerHTML = `
            <div class="voucher-wrap">
                <span class="voucher-label">🎟️ Mã giảm giá</span>
                <div class="voucher-input-row">
                    <input type="text" id="voucher-input" class="voucher-input"
                        placeholder="Nhập mã giảm giá..." autocomplete="off"
                        value="${currentInputVal}"
                        onkeydown="if(event.key==='Enter'){event.preventDefault();applyVoucher();}">
                    <button type="button" class="btn-apply-voucher" onclick="applyVoucher()">Áp dụng</button>
                </div>
                <p class="voucher-hint">Thử: PHUC10 · FOOD20 · WELCOME15</p>
            </div>
        `;
    }

    // ---- PHẦN BẢNG TỔNG TIỀN CHI TIẾT (STEP 10) ----
    if (!cartPriceDetails) return;

    if (cart.length === 0) {
        cartPriceDetails.style.display = "none";
        return;
    }

    cartPriceDetails.style.display = "block";

    const subtotal = calculateTotal();
    const shippingFee = calculateShippingFee(subtotal);
    const discount = calculateDiscount();
    const grandTotal = calculateGrandTotal();

    const subtotalFmt = subtotal.toLocaleString("vi-VN") + "đ";
    const shippingFmt = shippingFee === 0 ? "Miễn phí" : shippingFee.toLocaleString("vi-VN") + "đ";
    const discountFmt = discount > 0 ? "-" + discount.toLocaleString("vi-VN") + "đ" : "0đ";
    const grandTotalFmt = grandTotal.toLocaleString("vi-VN") + "đ";

    // Thông báo gợi ý mua thêm để được miễn phí giao hàng theo ngưỡng cấu hình
    let shippingNoticeHtml = "";
    const freeShipEnabled = storeInfo ? storeInfo.freeShippingEnabled : true;
    const threshold = storeInfo ? storeInfo.freeShippingThreshold : 100000;
    if (freeShipEnabled && threshold && subtotal > 0 && subtotal < threshold) {
        const remaining = threshold - subtotal;
        const remainingFmt = remaining.toLocaleString("vi-VN") + "đ";
        shippingNoticeHtml = `
            <div class="shipping-notice" id="shipping-notice">
                <span class="shipping-notice-icon">🚚</span> Mua thêm <strong>${remainingFmt}</strong> để được miễn phí giao hàng
            </div>
        `;
    }

    const discountRow = discount > 0 ? `
        <div class="price-detail-row price-detail-discount">
            <span>Giảm giá (${appliedVoucher ? appliedVoucher.code : ""}):</span>
            <span class="price-discount-val">${discountFmt}</span>
        </div>
    ` : `
        <div class="price-detail-row price-detail-discount">
            <span>Giảm giá:</span>
            <span>0đ</span>
        </div>
    `;

    cartPriceDetails.innerHTML = `
        ${shippingNoticeHtml}
        <div class="price-detail-row">
            <span>Tạm tính:</span>
            <span id="cart-subtotal-val">${subtotalFmt}</span>
        </div>
        <div class="price-detail-row price-detail-shipping">
            <span>Phí giao hàng:</span>
            <span id="cart-shipping-val" class="${shippingFee === 0 ? 'price-shipping-free' : ''}">${shippingFmt}</span>
        </div>
        ${discountRow}
        <div class="price-detail-row price-detail-final">
            <span>Tổng thanh toán:</span>
            <strong id="cart-grand-total-val">${grandTotalFmt}</strong>
        </div>
    `;
}

// ========================================================
// HIỂN THỊ THÔNG TIN CỬA HÀNG & KHU VỰC GIAO HÀNG (STEP STORE SETTINGS)
// ========================================================
function renderStoreStatusBanner() {
    const banner = document.getElementById("store-status-banner");
    if (!banner || !storeInfo) return;

    let badgeClass = "open";
    let badgeText = "🟢 Đang nhận đơn";
    let statusExtra = "";

    if (storeInfo.isPaused) {
        badgeClass = "paused";
        badgeText = "🔴 Tạm ngừng nhận đơn";
        statusExtra = storeInfo.pauseReason ? `<div class="store-closed-banner-hint"><strong>Thông báo từ quán:</strong> ${escapeHtml(storeInfo.pauseReason)}</div>` : "";
    } else if (!storeInfo.isOpen) {
        badgeClass = "closed";
        badgeText = "🕒 Ngoài giờ hoạt động";
        statusExtra = `<div class="store-closed-banner-hint">Cửa hàng hiện đang ngoài giờ nhận đơn. Quý khách vẫn có thể xem menu và chọn món vào giỏ hàng.</div>`;
    }

    const phoneHtml = storeInfo.phone ? ` · 📞 Hotline: <a href="tel:${escapeHtml(storeInfo.phone)}" style="color:inherit;text-decoration:underline;">${escapeHtml(storeInfo.phone)}</a>` : "";
    const addrHtml = storeInfo.address ? `📍 ${escapeHtml(storeInfo.address)}` : "";

    const tags = [];
    if (storeInfo.todaySchedule) tags.push(`🕒 Hôm nay: ${escapeHtml(storeInfo.todaySchedule)}`);
    if (storeInfo.deliveryTimeText) tags.push(`⏱ Dự kiến giao: ${escapeHtml(storeInfo.deliveryTimeText)}`);
    if (storeInfo.freeShippingEnabled && storeInfo.freeShippingThreshold) {
        tags.push(`🚚 Miễn phí giao từ ${money(storeInfo.freeShippingThreshold)}`);
    }

    banner.innerHTML = `
        <div class="store-banner-main">
            <h1 class="store-banner-title">
                ${escapeHtml(storeInfo.storeName || "PHUC-FOODIE")}
            </h1>
            ${(addrHtml || phoneHtml) ? `<div class="store-banner-meta">${addrHtml}${phoneHtml}</div>` : ""}
            <div class="store-banner-tags">
                ${tags.map(t => `<span class="store-tag">${t}</span>`).join("")}
            </div>
        </div>
        <div>
            <span class="store-badge ${badgeClass}">${badgeText}</span>
        </div>
        ${statusExtra}
    `;
    banner.style.display = "flex";
}

function renderCheckoutZones() {
    const zoneSelect = document.getElementById("customer-zone");
    const zoneHint = document.getElementById("zone-hint");
    if (!zoneSelect) return;

    if (!storeInfo) {
        zoneSelect.innerHTML = `<option value="">-- Đang tải khu vực phục vụ... --</option>`;
        return;
    }

    if (storeInfo.hasDeliveryZones) {
        let optionsHtml = `<option value="">-- Chọn khu vực giao hàng --</option>`;
        const zones = storeInfo.deliveryZones || [];
        zones.forEach(z => {
            const feeText = z.fee === 0 ? "Miễn phí (0đ)" : money(z.fee);
            const isSel = selectedDeliveryZoneId !== null && Number(selectedDeliveryZoneId) === z.id ? "selected" : "";
            optionsHtml += `<option value="${z.id}" ${isSel}>${escapeHtml(z.name)} (${feeText})</option>`;
        });
        zoneSelect.innerHTML = optionsHtml;
        if (storeInfo.allZonesInactive) {
            if (zoneHint) {
                zoneHint.innerHTML = `<span style="color:#dc2626;font-weight:600;">⚠️ Tất cả khu vực giao hàng đều đang tạm tắt phục vụ. Quán tạm thời không nhận đơn giao.</span>`;
            }
        } else {
            if (zoneHint) {
                zoneHint.textContent = "Chọn khu vực nhận hàng để áp dụng đúng mức phí giao.";
            }
        }
    } else {
        const feeText = storeInfo.defaultShippingFee === 0 ? "Miễn phí" : money(storeInfo.defaultShippingFee || 15000);
        zoneSelect.innerHTML = `<option value="default" selected>Khu vực giao mặc định (${feeText})</option>`;
        if (zoneHint) {
            zoneHint.textContent = `Chưa cấu hình phân vùng riêng, áp dụng mức phí mặc định ${feeText}.`;
        }
    }
}

function handleZoneChange() {
    const zoneSelect = document.getElementById("customer-zone");
    if (!zoneSelect) return;
    const val = zoneSelect.value;
    if (val === "" || val === "default") {
        selectedDeliveryZoneId = null;
    } else {
        selectedDeliveryZoneId = Number(val);
    }
    renderCart();
    renderCheckoutSummary();
    updateCheckoutStoreStatusUI();
}

function updateCheckoutStoreStatusUI() {
    const alertBox = document.getElementById("checkout-store-closed-msg");
    const confirmBtn = document.getElementById("btn-confirm-order");
    if (!alertBox) return;

    if (storeInfo?.isPaused) {
        alertBox.innerHTML = `<strong>🔴 Cửa hàng tạm ngừng nhận đơn:</strong> ${escapeHtml(storeInfo.pauseReason || "Quán đang tạm ngưng phục vụ, xin quý khách quay lại sau ít phút.")}`;
        alertBox.style.display = "block";
        if (confirmBtn) confirmBtn.disabled = true;
    } else if (storeInfo && !storeInfo.isOpen) {
        alertBox.innerHTML = `<strong>🕒 Cửa hàng ngoài giờ hoạt động:</strong> Lịch hôm nay: ${escapeHtml(storeInfo.todaySchedule || "Nghỉ bán")}. Quý khách vẫn xem được menu nhưng tạm thời chưa thể tạo đơn mới.`;
        alertBox.style.display = "block";
        if (confirmBtn) confirmBtn.disabled = true;
    } else if (storeInfo?.hasDeliveryZones && storeInfo?.allZonesInactive) {
        alertBox.innerHTML = `<strong>⚠️ Tạm ngừng giao hàng:</strong> Hiện tại tất cả khu vực giao hàng đều đang tạm ngừng phục vụ. Quán chưa thể nhận đơn giao.`;
        alertBox.style.display = "block";
        if (confirmBtn) confirmBtn.disabled = true;
    } else {
        alertBox.style.display = "none";
        alertBox.innerHTML = "";
        if (confirmBtn && typeof orderSubmitting !== "undefined" && !orderSubmitting) {
            confirmBtn.disabled = false;
        }
    }
}

// 13c. HIỂN THỊ TÓM TẮT ĐƠN HÀNG TRONG FORM CHECKOUT (STEP STORE SETTINGS)
function renderCheckoutSummary() {
    const checkoutPriceDetails = document.getElementById("checkout-price-details");
    if (!checkoutPriceDetails) return;

    if (cart.length === 0) {
        checkoutPriceDetails.innerHTML = "";
        return;
    }

    const subtotal = calculateTotal();
    const shippingFee = calculateShippingFee(subtotal);
    const discount = calculateDiscount();
    const grandTotal = calculateGrandTotal();

    const subtotalFmt = subtotal.toLocaleString("vi-VN") + "đ";
    const shippingFmt = shippingFee === 0 ? "Miễn phí" : shippingFee.toLocaleString("vi-VN") + "đ";
    const discountFmt = discount > 0 ? "-" + discount.toLocaleString("vi-VN") + "đ" : "0đ";
    const grandTotalFmt = grandTotal.toLocaleString("vi-VN") + "đ";

    let zoneNameText = "Khu vực mặc định";
    if (storeInfo?.hasDeliveryZones) {
        if (selectedDeliveryZoneId) {
            const z = (storeInfo.deliveryZones || []).find(item => item.id === Number(selectedDeliveryZoneId));
            zoneNameText = z ? z.name : "Chưa chọn khu vực";
        } else {
            zoneNameText = "Chưa chọn khu vực";
        }
    }

    const estTimeRow = storeInfo?.deliveryTimeText ? `
        <div class="price-detail-row" style="color:#2563eb;font-weight:600;">
            <span>⏱ Dự kiến giao (ước tính):</span>
            <span>${escapeHtml(storeInfo.deliveryTimeText)}</span>
        </div>
    ` : "";

    const freeShipThresholdNotice = (storeInfo?.freeShippingEnabled && subtotal >= storeInfo.freeShippingThreshold) ? `
        <p class="hint" style="color:#16a34a;margin:4px 0 0;font-size:13px;">✓ Đơn đạt từ ${money(storeInfo.freeShippingThreshold)} được miễn phí giao hàng</p>
    ` : "";

    checkoutPriceDetails.innerHTML = `
        <div class="checkout-summary-box">
            <h4 class="checkout-summary-title">Tóm tắt thanh toán & giao hàng</h4>
            <div class="price-detail-row">
                <span>Khu vực giao:</span>
                <strong>${escapeHtml(zoneNameText)}</strong>
            </div>
            ${estTimeRow}
            <div class="price-detail-row">
                <span>Tiền món (Tạm tính):</span>
                <span>${subtotalFmt}</span>
            </div>
            <div class="price-detail-row price-detail-shipping">
                <span>Phí giao hàng:</span>
                <span class="${shippingFee === 0 ? 'price-shipping-free' : ''}">${shippingFmt}</span>
            </div>
            ${freeShipThresholdNotice}
            <div class="price-detail-row price-detail-discount">
                <span>Giảm giá${appliedVoucher ? ` (${appliedVoucher.code})` : ""}:</span>
                <span class="${discount > 0 ? 'price-discount-val' : ''}">${discountFmt}</span>
            </div>
            <div class="price-detail-row price-detail-final">
                <span>Tổng thanh toán:</span>
                <strong>${grandTotalFmt}</strong>
            </div>
        </div>
    `;
    updateCheckoutStoreStatusUI();
}

// 14. HIỂN THỊ FORM ĐẶT HÀNG (showCheckoutForm)
function showCheckoutForm() {
    if (cart.length === 0) {
        showToast("Giỏ hàng trống", "Vui lòng thêm sản phẩm vào giỏ hàng.", "warning");
        return;
    }

    // Tự động điền thông tin nếu user đã đăng nhập, hoặc nhắc đăng nhập
    if (typeof getCurrentUser === "function") {
        const currentUser = getCurrentUser();
        if (currentUser) {
            const nameInput = document.getElementById("customer-name");
            const phoneInput = document.getElementById("customer-phone");
            if (nameInput && !nameInput.value) nameInput.value = currentUser.fullName;
            if (phoneInput && !phoneInput.value) phoneInput.value = currentUser.phone;
        } else {
            showToast("Đăng nhập", "Vui lòng đăng nhập để tiếp tục đặt hàng.", "warning");
            if (typeof showLoginForm === "function") showLoginForm();
            if (typeof scrollToSection === "function") scrollToSection("auth-section");
            return;
        }
    }

    renderCheckoutZones();
    renderCheckoutSummary();
    updateCheckoutStoreStatusUI();

    const checkoutSection = document.getElementById("checkout-section");
    if (checkoutSection) {
        checkoutSection.style.display = "block";
        checkoutSection.scrollIntoView({ behavior: "smooth" });
    }
}

function checkout() {
    showCheckoutForm();
}

// 15. KIỂM TRA DỮ LIỆU FORM GIAO HÀNG (validateCheckoutForm)
function validateCheckoutForm() {
    // 1. Kiểm tra trạng thái đóng cửa / tạm ngừng
    if (storeInfo?.isPaused) {
        showToast("Tạm ngừng nhận đơn", storeInfo.pauseReason || "Cửa hàng hiện đang tạm ngừng nhận đơn.", "warning");
        updateCheckoutStoreStatusUI();
        return false;
    }
    if (storeInfo && !storeInfo.isOpen) {
        showToast("Ngoài giờ hoạt động", `Cửa hàng đang đóng cửa (${storeInfo.todaySchedule || "Ngoài giờ"}). Quý khách vui lòng đặt món trong giờ hoạt động.`, "warning");
        updateCheckoutStoreStatusUI();
        return false;
    }
    if (storeInfo?.hasDeliveryZones) {
        if (storeInfo.allZonesInactive) {
            showToast("Tạm ngừng giao", "Tất cả khu vực giao hàng đều đang tạm ngừng phục vụ.", "warning");
            updateCheckoutStoreStatusUI();
            return false;
        }
        const zoneSelect = document.getElementById("customer-zone");
        if (!zoneSelect || !zoneSelect.value || zoneSelect.value === "") {
            showToast("Thiếu thông tin", "Vui lòng chọn khu vực giao hàng.", "warning");
            if (zoneSelect) zoneSelect.focus();
            return false;
        }
    }

    const nameInput = document.getElementById("customer-name");
    const phoneInput = document.getElementById("customer-phone");
    const addressInput = document.getElementById("customer-address");

    const name = nameInput ? nameInput.value.trim() : "";
    const phone = phoneInput ? phoneInput.value.trim() : "";
    const address = addressInput ? addressInput.value.trim() : "";

    if (name === "") {
        showToast("Thiếu thông tin", "Vui lòng nhập họ và tên.", "warning");
        if (nameInput) nameInput.focus();
        return false;
    }

    if (phone === "") {
        showToast("Thiếu thông tin", "Vui lòng nhập số điện thoại.", "warning");
        if (phoneInput) phoneInput.focus();
        return false;
    }

    const phoneRegex = /^0\d{9}$/;
    if (!phoneRegex.test(phone)) {
        showToast("Không hợp lệ", "Số điện thoại phải gồm 10 chữ số và bắt đầu bằng 0.", "warning");
        if (phoneInput) phoneInput.focus();
        return false;
    }

    if (address === "") {
        showToast("Thiếu thông tin", "Vui lòng nhập địa chỉ giao hàng.", "warning");
        if (addressInput) addressInput.focus();
        return false;
    }

    return true;
}

// ========================================================
// HỆ THỐNG MODAL CHI TIẾT SẢN PHẨM (BƯỚC 8)
// ========================================================

// 16. MỞ MODAL CHI TIẾT SẢN PHẨM (openProductModal)
function openProductModal(productId) {
    const product = products.find(item => item.id === productId);
    if (!product) return;

    currentModalProductId = productId;
    selectedQuantity = 1; // Đặt lại số lượng ban đầu là 1

    const isAvailable = Boolean(product.available);
    const stock = product.stock_quantity;
    const canOrder = isAvailable && stock !== null && stock !== undefined && stock > 0;

    const modal = document.getElementById("product-modal");
    const modalImg = document.getElementById("modal-product-img");
    const modalBadge = document.getElementById("modal-product-badge");
    const modalName = document.getElementById("modal-product-name");
    const modalDesc = document.getElementById("modal-product-desc");
    const modalPrice = document.getElementById("modal-product-price");
    const modalQty = document.getElementById("modal-qty-value");
    const modalAddBtn = document.getElementById("btn-modal-add-cart");

    if (modalImg) {
        modalImg.src = product.image;
        modalImg.alt = product.name;
    }
    if (modalBadge) modalBadge.textContent = product.category;
    if (modalName) modalName.textContent = product.name;

    let stockInfoText = "";
    if (!isAvailable) {
        stockInfoText = " [Tạm ngừng bán]";
    } else if (stock === null || stock === undefined) {
        stockInfoText = " [Chưa mở bán]";
    } else if (stock === 0) {
        stockInfoText = " [Hết hàng]";
    } else {
        stockInfoText = ` [Còn ${stock} phần]`;
    }

    if (modalDesc) modalDesc.textContent = (product.description || "") + stockInfoText;
    if (modalPrice) modalPrice.textContent = product.price.toLocaleString("vi-VN") + "đ";
    if (modalQty) modalQty.textContent = selectedQuantity;
    if (modalAddBtn) {
        modalAddBtn.disabled = !canOrder;
        modalAddBtn.textContent = canOrder ? "Thêm vào giỏ" : (!isAvailable ? "Tạm ngừng bán" : (stock === 0 ? "Hết hàng" : "Chưa mở bán"));
    }

    if (modal) {
        modal.style.display = "flex";
        if (document.body) document.body.style.overflow = "hidden";
    }
}

// 17. ĐÓNG MODAL CHI TIẾT SẢN PHẨM (closeProductModal)
function closeProductModal() {
    const modal = document.getElementById("product-modal");
    if (modal) {
        modal.style.display = "none";
        if (document.body) document.body.style.overflow = "";
    }
    currentModalProductId = null;
    selectedQuantity = 1;
}

// 18. ĐÓNG MODAL KHI CLICK VÙNG NỀN BÊN NGOÀI
function handleModalOverlayClick(event) {
    if (event.target.id === "product-modal") {
        closeProductModal();
    }
}

// 19. TĂNG SỐ LƯỢNG TRONG MODAL
function increaseModalQuantity() {
    const product = products.find(p => p.id === currentModalProductId);
    const maxStock = product && product.stock_quantity !== null && product.stock_quantity !== undefined
        ? Math.min(product.stock_quantity, 99)
        : 99;

    if (selectedQuantity >= maxStock) {
        showToast("Giới hạn tồn kho", `Chỉ có thể chọn tối đa ${maxStock} phần.`, "warning");
        return;
    }
    selectedQuantity += 1;
    const modalQty = document.getElementById("modal-qty-value");
    if (modalQty) {
        modalQty.textContent = selectedQuantity;
    }
}

// 20. GIẢM SỐ LƯỢNG TRONG MODAL (Không giảm dưới 1)
function decreaseModalQuantity() {
    if (selectedQuantity > 1) {
        selectedQuantity -= 1;
        const modalQty = document.getElementById("modal-qty-value");
        if (modalQty) {
            modalQty.textContent = selectedQuantity;
        }
    }
}

// 21. THÊM VÀO GIỎ TỪ MODAL
function addModalProductToCart() {
    if (!currentModalProductId) return;
    addToCart(currentModalProductId, selectedQuantity);
    closeProductModal();
}

// ========================================================
// HỆ THỐNG QUẢN LÝ ĐƠN HÀNG VỚI LOCALSTORAGE (BƯỚC 7)
// ========================================================

const ORDERS_STORAGE_KEY = "phuc_foodie_orders";

// 22. HÀM TẠO MÃ ĐƠN HÀNG: PF-YYYYMMDD-XXXX
function generateOrderId() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    const randomNum = Math.floor(1000 + Math.random() * 9000);
    return `PF-${year}${month}${day}-${randomNum}`;
}

// 23. HÀM ĐỊNH DẠNG NGÀY GIỜ ĐẶT HÀNG: DD/MM/YYYY HH:mm
function formatOrderTime(date) {
    const d = date || new Date();
    const day = String(d.getDate()).padStart(2, "0");
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const year = d.getFullYear();
    const hours = String(d.getHours()).padStart(2, "0");
    const minutes = String(d.getMinutes()).padStart(2, "0");
    return `${day}/${month}/${year} ${hours}:${minutes}`;
}

// 24. LẤY DANH SÁCH ĐƠN HÀNG TỪ LOCALSTORAGE

// 25. LƯU ĐƠN HÀNG VÀO LOCALSTORAGE

// 26. HIỂN THỊ DANH SÁCH LỊCH SỬ ĐƠN HÀNG

// 27. XÓA TOÀN BỘ LỊCH SỬ ĐƠN HÀNG

// 28. XÁC NHẬN ĐẶT HÀNG (đã tích hợp voucher và phí giao hàng - STEP 10)

// 29. GẮN SỰ KIỆN TÌM KIẾM VÀ LỌC
function setupEventListeners() {
    const searchInput = document.getElementById("search-input");
    if (searchInput) {
        searchInput.addEventListener("input", function (event) {
            searchKeyword = event.target.value;
            filterProducts();
        });
    }

    const categoryButtons = document.querySelectorAll(".btn-category");
    categoryButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            categoryButtons.forEach(function (btn) {
                btn.classList.remove("active");
            });

            this.classList.add("active");
            currentCategory = this.getAttribute("data-category");
            filterProducts();
        });
    });

    // Hỗ trợ phím Escape để đóng modal chi tiết
    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closeProductModal();
        }
    });
}

// Đưa các hàm ra window để gọi từ inline HTML
window.addToCart = addToCart;
window.increaseQuantity = increaseQuantity;
window.decreaseQuantity = decreaseQuantity;
window.removeFromCart = removeFromCart;
window.checkout = checkout;
window.showCheckoutForm = showCheckoutForm;
window.validateCheckoutForm = validateCheckoutForm;
window.showToast = showToast;
window.scrollToSection = scrollToSection;
window.filterAndScrollCategory = filterAndScrollCategory;
window.generateOrderId = generateOrderId;
window.openProductModal = openProductModal;
window.closeProductModal = closeProductModal;
window.handleModalOverlayClick = handleModalOverlayClick;
window.increaseModalQuantity = increaseModalQuantity;
window.decreaseModalQuantity = decreaseModalQuantity;
window.addModalProductToCart = addModalProductToCart;
// Voucher functions (BƯỚC 9)
window.applyVoucher = applyVoucher;
window.removeVoucher = removeVoucher;
window.renderVoucherSection = renderVoucherSection;
// Shipping fee & Grand Total functions (BƯỚC 10)
window.calculateShippingFee = calculateShippingFee;
window.calculateGrandTotal = calculateGrandTotal;
window.calculateFinalTotal = calculateFinalTotal;
window.renderCheckoutSummary = renderCheckoutSummary;
// Store settings & zones exports
window.handleZoneChange = handleZoneChange;
window.renderStoreStatusBanner = renderStoreStatusBanner;
window.renderCheckoutZones = renderCheckoutZones;
window.updateCheckoutStoreStatusUI = updateCheckoutStoreStatusUI;

// ========================================================
// HỆ THỐNG TÀI KHOẢN NGƯỜI DÙNG - AUTHENTICATION (STEP 11)
// Thông tin phiên lấy từ server trong api.js; không lưu mật khẩu tại trình duyệt.
// ========================================================

const USERS_STORAGE_KEY = "phuc_foodie_users";
const CURRENT_USER_STORAGE_KEY = "phuc_foodie_current_user";

// Biến lưu trạng thái quên mật khẩu tạm thời
let forgotPasswordState = null;

// 31. ĐỌC DANH SÁCH USERS TỪ LOCALSTORAGE

// 32. LƯU DANH SÁCH USERS VÀO LOCALSTORAGE

// 33. LẤY USER ĐANG ĐĂNG NHẬP (getCurrentUser)

// 34. LƯU USER ĐANG ĐĂNG NHẬP

// 35. XÓA USER ĐANG ĐĂNG NHẬP

// 36. CẬP NHẬT GIAO DIỆN AUTH VÀ HEADER (updateAuthUI)
function updateAuthUI() {
    const currentUser = getCurrentUser();
    const userDisplayText = document.getElementById("user-display-text");
    const userProfileCard = document.getElementById("user-profile-card");
    const authFormsCard = document.getElementById("auth-forms-card");

    // Cập nhật Header
    if (userDisplayText) {
        if (currentUser) {
            userDisplayText.textContent = `👤 Xin chào, ${currentUser.fullName}`;
        } else {
            userDisplayText.textContent = "👤 Đăng nhập";
        }
    }

    // Cập nhật Thẻ hiển thị trong auth-section
    if (userProfileCard && authFormsCard) {
        if (currentUser) {
            userProfileCard.style.display = "block";
            authFormsCard.style.display = "none";

            const profileGreeting = document.getElementById("profile-greeting");
            const profileEmail = document.getElementById("profile-email");
            const profilePhone = document.getElementById("profile-phone");

            if (profileGreeting) profileGreeting.textContent = `Xin chào, ${currentUser.fullName}!`;
            if (profileEmail) profileEmail.textContent = currentUser.email;
            if (profilePhone) profilePhone.textContent = currentUser.phone;
        } else {
            userProfileCard.style.display = "none";
            authFormsCard.style.display = "block";
        }
    }
}

// 37. XỬ LÝ CLICK NÚT TÀI KHOẢN TRÊN HEADER
function handleHeaderUserClick() {
    const currentUser = getCurrentUser();
    if (!currentUser) {
        showLoginForm();
    }
    scrollToSection("auth-section");
}

// 38. CHUYỂN SANG FORM ĐĂNG NHẬP
function showLoginForm() {
    const tabLogin = document.getElementById("tab-login");
    const tabRegister = document.getElementById("tab-register");
    const loginForm = document.getElementById("login-form");
    const registerForm = document.getElementById("register-form");
    const forgotForm = document.getElementById("forgot-password-form");

    if (tabLogin) tabLogin.classList.add("active");
    if (tabRegister) tabRegister.classList.remove("active");
    if (loginForm) loginForm.style.display = "block";
    if (registerForm) registerForm.style.display = "none";
    if (forgotForm) forgotForm.style.display = "none";

    hideAuthError("login-error-msg");
}

// 39. CHUYỂN SANG FORM ĐĂNG KÝ
function showRegisterForm() {
    const tabLogin = document.getElementById("tab-login");
    const tabRegister = document.getElementById("tab-register");
    const loginForm = document.getElementById("login-form");
    const registerForm = document.getElementById("register-form");
    const forgotForm = document.getElementById("forgot-password-form");

    if (tabLogin) tabLogin.classList.remove("active");
    if (tabRegister) tabRegister.classList.add("active");
    if (loginForm) loginForm.style.display = "none";
    if (registerForm) registerForm.style.display = "block";
    if (forgotForm) forgotForm.style.display = "none";

    hideAuthError("reg-error-msg");
}

// 40. CHUYỂN SANG FORM QUÊN MẬT KHẨU
function showForgotPasswordForm() {
    const tabLogin = document.getElementById("tab-login");
    const tabRegister = document.getElementById("tab-register");
    const loginForm = document.getElementById("login-form");
    const registerForm = document.getElementById("register-form");
    const forgotForm = document.getElementById("forgot-password-form");
    const forgotStep1 = document.getElementById("forgot-step-1");
    const forgotStep2 = document.getElementById("forgot-step-2");

    if (tabLogin) tabLogin.classList.remove("active");
    if (tabRegister) tabRegister.classList.remove("active");
    if (loginForm) loginForm.style.display = "none";
    if (registerForm) registerForm.style.display = "none";
    if (forgotForm) forgotForm.style.display = "block";

    if (forgotStep1) forgotStep1.style.display = "block";
    if (forgotStep2) forgotStep2.style.display = "none";

    hideAuthError("forgot-error-msg");
    hideAuthError("reset-error-msg");
}

// Hàm trợ giúp hiển thị và ẩn thông báo lỗi
function showAuthError(elementId, message) {
    const el = document.getElementById(elementId);
    if (el) {
        el.textContent = message;
        el.style.display = "block";
    }
}

function hideAuthError(elementId) {
    const el = document.getElementById(elementId);
    if (el) {
        el.textContent = "";
        el.style.display = "none";
    }
}

// 41. HIỆN / ẨN MẬT KHẨU (togglePasswordVisibility)
function togglePasswordVisibility(inputId, btnElement) {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === "password") {
        input.type = "text";
        if (btnElement) btnElement.textContent = "🙈";
    } else {
        input.type = "password";
        if (btnElement) btnElement.textContent = "👁";
    }
}

// 42. XỬ LÝ ĐĂNG NHẬP (handleLogin)

// 43. XỬ LÝ ĐĂNG KÝ TÀI KHOẢN (handleRegister)

// 44. XỬ LÝ ĐĂNG XUẤT (logoutUser)

// 45. XỬ LÝ QUÊN MẬT KHẨU - BƯỚC 1 (handleForgotPassword)

// 46. XỬ LÝ ĐẶT LẠI MẬT KHẨU - BƯỚC 2 (handleResetPassword)

// Đưa các hàm auth ra window
window.updateAuthUI = updateAuthUI;
window.showLoginForm = showLoginForm;
window.showRegisterForm = showRegisterForm;
window.showForgotPasswordForm = showForgotPasswordForm;
window.togglePasswordVisibility = togglePasswordVisibility;
window.handleHeaderUserClick = handleHeaderUserClick;
window.handleZoneChange = handleZoneChange;
window.renderStoreStatusBanner = renderStoreStatusBanner;
window.renderCheckoutZones = renderCheckoutZones;
window.updateCheckoutStoreStatusUI = updateCheckoutStoreStatusUI;
window.renderCheckoutSummary = renderCheckoutSummary;

// 30. KHỞI ĐỘNG KHI TẢI TRANG
// Khởi động và phiên đăng nhập được quản lý trong api.js.
