// Kết nối giao diện hiện có với server. Không lưu mật khẩu/token trong LocalStorage.
let serverUser = null;
let csrfToken = "";
let selectedPaymentMethod = null;
let orderRequestKey = null;
let orderRequestFingerprint = null;
let orderSubmitting = false;
let authBusy = false;
let ordersBusy = false;
let apiReady = false;
let lastModalFocus = null;

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function money(value) { return Number(value).toLocaleString("vi-VN") + "đ"; }
function getCurrentUser() { return serverUser; }
async function api(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    try {
        const response = await fetch(path, {credentials:"same-origin", ...options, signal:controller.signal,
            headers:{"Content-Type":"application/json", "X-CSRF-Token":csrfToken, ...(options.headers || {})}});
        const data = await response.json();
        if (!response.ok) {
            if (response.status === 401 && path !== "/api/login") {
                serverUser = null; updateAuthUI();
            }
            throw new Error(data.error || "Không thể xử lý yêu cầu.");
        }
        if (data.csrfToken) csrfToken = data.csrfToken;
        return data;
    } catch (e) {
        if (e.name === "AbortError" || e instanceof TypeError) throw new Error("Không kết nối được server. Kiểm tra mạng rồi thử lại.");
        throw e;
    } finally { clearTimeout(timeout); }
}
async function authAction(buttonId, errorId, operation) {
    if (authBusy) return;
    authBusy = true;
    const button = document.getElementById(buttonId);
    if (button) button.disabled = true;
    hideAuthError(errorId);
    try { await operation(); }
    catch (e) { showAuthError(errorId, e.message); }
    finally { authBusy = false; if (button) button.disabled = false; }
}
async function handleLogin() {
    await authAction("btn-login-submit", "login-error-msg", async () => {
        const data = await api("/api/login", {method:"POST", body:JSON.stringify({identifier:document.getElementById("login-identifier").value.trim(), password:document.getElementById("login-password").value})});
        serverUser = data.user;
        document.getElementById("login-password").value = "";
        updateAuthUI(); document.getElementById("order-history-list").textContent = "Đang tải đơn hàng…"; await refreshOrders();
        showToast("Đăng nhập thành công", "Bạn có thể đặt món và theo dõi đơn hàng.");
    });
}
async function handleRegister() {
    await authAction("btn-reg-submit", "reg-error-msg", async () => {
        if (document.getElementById("reg-password").value !== document.getElementById("reg-confirm-password").value) throw new Error("Xác nhận mật khẩu không khớp.");
        const email = document.getElementById("reg-email").value.trim();
        const data = await api("/api/register", {method:"POST", body:JSON.stringify({fullName:document.getElementById("reg-name").value.trim(), email, phone:document.getElementById("reg-phone").value.trim(), password:document.getElementById("reg-password").value, terms:document.getElementById("reg-terms").checked})});
        document.getElementById("register-form").reset(); showLoginForm();
        document.getElementById("login-identifier").value = email;
        showToast("Đăng ký thành công", data.message);
    });
}
async function logoutUser(event) {
    if (event) event.stopPropagation();
    if (orderSubmitting) return;
    stopCustomerOrdersPolling();
    try {
        await api("/api/logout", {method:"POST",body:"{}"});
        serverUser = null; updateAuthUI(); showLoginForm(); await refreshOrders();
        document.getElementById("checkout-form").reset();
        document.getElementById("checkout-section").style.display = "none";
        selectPaymentMethod(null);
        showToast("Đã đăng xuất", "Giỏ hàng của bạn được giữ lại trên thiết bị này.");
    } catch(e) { showToast("Lỗi", e.message, "warning"); }
}
async function handleForgotPassword() {
    await authAction("btn-forgot-submit", "forgot-error-msg", async () => {
        const email = document.getElementById("forgot-email").value.trim();
        const data = await api("/api/password/forgot", {method:"POST",body:JSON.stringify({email})});
        forgotPasswordState = {email};
        document.getElementById("forgot-step-1").style.display = "none";
        document.getElementById("forgot-step-2").style.display = "block";
        document.getElementById("forgot-demo-code-text").textContent = data.message;
        showToast("Kiểm tra email", data.message);
    });
}
async function handleResetPassword() {
    await authAction("btn-reset-submit", "reset-error-msg", async () => {
        if (!forgotPasswordState) throw new Error("Hãy gửi yêu cầu đặt lại mật khẩu trước.");
        const password = document.getElementById("reset-new-password").value;
        if (password !== document.getElementById("reset-confirm-password").value) throw new Error("Xác nhận mật khẩu không khớp.");
        const data = await api("/api/password/reset", {method:"POST",body:JSON.stringify({email:forgotPasswordState.email,code:document.getElementById("reset-code").value.trim(),password})});
        serverUser = null; forgotPasswordState = null;
        document.getElementById("reset-new-password").value = "";
        document.getElementById("reset-confirm-password").value = "";
        updateAuthUI(); showLoginForm(); await refreshOrders();
        showToast("Thành công", data.message);
    });
}
function selectPaymentMethod(method) {
    selectedPaymentMethod = method;
    document.querySelectorAll(".payment-card").forEach(card => card.classList.toggle("selected",card.id === "payment-card-" + method));
    document.getElementById("payment-error-msg").style.display = "none";
    document.getElementById("demo-payment-confirm-wrap").hidden = !method || method === "cod";
    document.getElementById("demo-payment-confirm").checked = false;
    document.getElementById("payment-details").textContent = method === "cod" ? "Bạn thanh toán tiền mặt khi nhận món." : method ? "Thanh toán DEMO — không chuyển tiền thật. Đơn được lưu để cửa hàng kiểm tra, trạng thái này không xác nhận đã nhận tiền." : "";
}
function paymentName(method) { return ({cod:"Tiền mặt khi nhận hàng",bank_transfer:"Chuyển khoản (DEMO)",qr_demo:"QR (DEMO)"})[method] || "Chưa có thông tin"; }
function paymentStatus(status) { return ({pending:"Chờ thanh toán",paid:"Đã thu tiền COD",demo_confirmed:"Đã xác nhận mô phỏng — không có giao dịch tiền thật"})[status] || "Chưa có thông tin"; }
async function confirmOrder() {
    if (orderSubmitting) return;
    if (!apiReady) { showToast("Chưa kết nối", "Hãy chạy server và tải lại trang.", "warning"); return; }
    if (!serverUser) { showToast("Đăng nhập", "Vui lòng đăng nhập trước khi đặt hàng.", "warning"); showLoginForm(); scrollToSection("auth-section"); return; }
    if (!cart.length || !validateCheckoutForm()) return;
    if (!selectedPaymentMethod) {
        const errorEl = document.getElementById("payment-error-msg");
        if (errorEl) {
            errorEl.style.display = "block";
            errorEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
        return;
    }
    if (selectedPaymentMethod !== "cod" && !document.getElementById("demo-payment-confirm").checked) { showToast("Xác nhận", "Vui lòng xác nhận thanh toán mô phỏng.", "warning"); return; }

    // Kiểm tra tính hợp lệ của tồn kho và trạng thái bán trước khi gửi đơn
    for (const item of cart) {
        const p = products.find(prod => prod.id === item.id);
        if (!p || !p.available) {
            showToast("Tạm ngừng bán", `Món "${item.name}" đang tạm ngừng bán. Vui lòng xóa khỏi giỏ.`, "warning");
            return;
        }
        if (p.stock_quantity === null || p.stock_quantity === undefined) {
            showToast("Chưa sẵn sàng", `Món "${item.name}" chưa sẵn sàng phục vụ. Vui lòng xóa khỏi giỏ.`, "warning");
            return;
        }
        if (p.stock_quantity === 0) {
            showToast("Hết hàng", `Món "${item.name}" đã hết hàng. Vui lòng xóa khỏi giỏ.`, "warning");
            return;
        }
        if (item.quantity > p.stock_quantity) {
            showToast("Thiếu hàng", `Món "${item.name}" chỉ còn ${p.stock_quantity} phần (bạn yêu cầu ${item.quantity}). Vui lòng điều chỉnh số lượng.`, "warning");
            return;
        }
    }

    const payload = {
        customer: {
            name: document.getElementById("customer-name").value.trim(),
            phone: document.getElementById("customer-phone").value.trim(),
            address: document.getElementById("customer-address").value.trim(),
            note: document.getElementById("customer-note").value.trim()
        },
        deliveryZoneId: (typeof selectedDeliveryZoneId !== "undefined" && selectedDeliveryZoneId) ? Number(selectedDeliveryZoneId) : null,
        items: cart.map(i => ({id: i.id, quantity: i.quantity})),
        voucherCode: appliedVoucher?.code || "",
        paymentMethod: selectedPaymentMethod,
        demoConfirmed: document.getElementById("demo-payment-confirm").checked,
        expectedTotal: calculateGrandTotal()
    };
    const fingerprint = JSON.stringify(payload);
    // Dùng lại khóa khi retry cùng yêu cầu, tránh tạo hai đơn khi mạng bị ngắt.
    if (fingerprint !== orderRequestFingerprint) {
        orderRequestFingerprint = fingerprint; orderRequestKey = crypto.randomUUID();
    }
    orderSubmitting = true;
    const button = document.getElementById("btn-confirm-order"); button.disabled = true; button.textContent = "Đang gửi đơn…";
    try {
        const {order} = await api("/api/orders",{method:"POST",body:JSON.stringify({...payload,requestKey:orderRequestKey})});
        cart = []; appliedVoucher = null;
        orderRequestKey = null; orderRequestFingerprint = null;
        document.getElementById("checkout-form").reset();
        document.getElementById("checkout-section").style.display = "none";
        selectPaymentMethod(null); renderCart(); updateCartCount();
        showOrderSuccess(order);
        try {
            const prodData = await api("/api/products");
            products.length = 0; products.push(...prodData.products);
            filterProducts();
        } catch {}
        await refreshOrders();
    } catch (e) {
        showToast("Chưa gửi được đơn", e.message, "warning");
        // Giữ nguyên giỏ hàng và dữ liệu form khi thất bại; làm mới thông tin cửa hàng để cập nhật trạng thái/phí mới
        try { await fetchStoreInfo(); } catch {}
    }
    finally { orderSubmitting = false; button.disabled = false; button.textContent = "Xác nhận đặt hàng"; }
}
function showOrderSuccess(order) {
    lastModalFocus = document.activeElement;
    document.getElementById("success-order-id").textContent = order.id;
    document.getElementById("success-order-total").textContent = money(order.totalPrice);
    document.getElementById("success-payment-method").textContent = paymentName(order.paymentMethod);
    document.getElementById("success-payment-status").textContent = paymentStatus(order.paymentStatus);

    const zoneRow = document.getElementById("row-success-zone");
    const zoneEl = document.getElementById("success-order-zone");
    if (zoneRow && zoneEl) {
        if (order.deliveryZoneName) {
            zoneEl.textContent = order.deliveryZoneName;
            zoneRow.style.display = "flex";
        } else {
            zoneRow.style.display = "none";
        }
    }

    const timeRow = document.getElementById("row-success-est-time");
    const timeEl = document.getElementById("success-order-est-time");
    if (timeRow && timeEl) {
        if (order.estimatedDeliveryTime) {
            const timeVal = String(order.estimatedDeliveryTime);
            timeEl.textContent = timeVal.includes("ước tính") ? timeVal : `${timeVal} (ước tính)`;
            timeRow.style.display = "flex";
        } else {
            timeRow.style.display = "none";
        }
    }

    const modal = document.getElementById("order-success-modal");
    modal.style.display = "flex"; modal.setAttribute("role","dialog"); modal.setAttribute("aria-modal","true");
    modal.querySelector("button").focus();
}
function closeOrderSuccessModal() { document.getElementById("order-success-modal").style.display="none"; lastModalFocus?.focus(); }
function handleOrderSuccessOverlayClick(event) { if(event.target.id === "order-success-modal") closeOrderSuccessModal(); }

// ========================================================
// QUẢN LÝ TỰ ĐỘNG CẬP NHẬT ĐƠN HÀNG KHÁCH (8S RECURSIVE POLLING)
// ========================================================
let customerPollTimer = null;
let customerPollSeq = 0;
let customerPollBackoff = 8000;
let isFirstCustomerLoad = true;
let previousCustomerOrdersMap = new Map(); // orderId -> status string
let lastRenderedCustomerSig = "";

function stopCustomerOrdersPolling() {
    if (customerPollTimer) {
        clearTimeout(customerPollTimer);
        customerPollTimer = null;
    }
    customerPollSeq++;
}

function scheduleNextCustomerOrdersPoll() {
    if (customerPollTimer) {
        clearTimeout(customerPollTimer);
        customerPollTimer = null;
    }
    if (!serverUser || document.hidden) return;
    customerPollTimer = setTimeout(() => {
        refreshOrders({ isAuto: true });
    }, customerPollBackoff);
}

function updateCustomerConnStatus(message) {
    const el = document.getElementById("customer-order-conn-status");
    if (!el) return;
    if (message) {
        el.textContent = `⚠️ ${message}`;
        el.hidden = false;
    } else {
        el.hidden = true;
    }
}

async function refreshOrders(options = {}) {
    const isAuto = Boolean(options.isAuto);
    const container = document.getElementById("order-history-list");
    const refreshBtn = document.getElementById("btn-clear-history");
    if (refreshBtn) refreshBtn.style.display = serverUser ? "inline-flex" : "none";
    if (!serverUser) {
        stopCustomerOrdersPolling();
        isFirstCustomerLoad = true;
        previousCustomerOrdersMap.clear();
        lastRenderedCustomerSig = "";
        updateCustomerConnStatus(null);
        if (container) container.innerHTML = '<div class="order-empty-msg"><p>Đăng nhập để xem đơn hàng của bạn.</p></div>';
        return;
    }
    if (ordersBusy && isAuto) return;
    const requestedUserId = serverUser.id;
    const seq = ++customerPollSeq;
    if (!isAuto) {
        ordersBusy = true;
        if (refreshBtn) { refreshBtn.disabled = true; refreshBtn.textContent = "↻ Đang tải…"; }
    }
    try {
        const {orders} = await api("/api/orders");
        if (serverUser?.id !== requestedUserId || seq !== customerPollSeq) return;
        updateCustomerConnStatus(null);
        customerPollBackoff = 8000;

        // Thông báo nhẹ khi trạng thái đơn thay đổi (không thông báo cho toàn bộ đơn ở lần tải đầu)
        if (!isFirstCustomerLoad) {
            for (const order of orders) {
                const prev = previousCustomerOrdersMap.get(order.id);
                if (prev && prev !== order.orderStatus) {
                    showToast(`Đơn hàng #${order.id}`, `Trạng thái mới: ${order.status}`, "info");
                }
            }
        }
        previousCustomerOrdersMap.clear();
        for (const order of orders) {
            previousCustomerOrdersMap.set(order.id, order.orderStatus);
        }
        isFirstCustomerLoad = false;

        // Chỉ cập nhật DOM khi danh sách đơn hoặc trạng thái thực sự thay đổi
        const currentSig = orders.map(o => `${o.id}:${o.orderStatus}:${o.paymentStatus}:${o.status}`).join("|");
        if (currentSig !== lastRenderedCustomerSig || !container.children.length) {
            lastRenderedCustomerSig = currentSig;
            container.innerHTML = orders.length ? orders.map(order => {
                const estTimeFormatted = order.estimatedDeliveryTime ? (String(order.estimatedDeliveryTime).includes("ước tính") ? String(order.estimatedDeliveryTime) : `${order.estimatedDeliveryTime} (ước tính)`) : "";
                return `<article class="order-card"><div class="order-card-header"><strong>${escapeHtml(order.id)}</strong><span class="order-status-badge ${escapeHtml(order.orderStatus)}">${escapeHtml(order.status)}</span></div><div class="order-card-meta"><p>${escapeHtml(order.orderTime)}</p><p>${escapeHtml(order.customerName)} · ${escapeHtml(order.customerPhone)}</p><p>${escapeHtml(order.customerAddress)}</p>${order.deliveryZoneName ? `<p>Khu vực giao: <strong>${escapeHtml(order.deliveryZoneName)}</strong></p>` : ""}${estTimeFormatted ? `<p class="hint">⏱ Dự kiến giao: ${escapeHtml(estTimeFormatted)}</p>` : ""}${order.customerNote ? `<p>Ghi chú: ${escapeHtml(order.customerNote)}</p>` : ""}</div><ul class="order-items-list">${order.items.map(i=>`<li class="order-item-row"><span>${escapeHtml(i.name)} × ${i.quantity}</span><span>${money(i.subtotal)}</span></li>`).join("")}</ul><div class="order-pricing-breakdown"><p>Tạm tính: ${money(order.subtotalPrice)} · Giao hàng: ${money(order.shippingFee)}</p><p>Giảm giá${order.voucherCode ? " ("+escapeHtml(order.voucherCode)+")" : ""}: ${money(order.discountAmount)}</p><div class="order-card-footer"><span>Tổng thanh toán</span><strong class="order-total-price">${money(order.totalPrice)}</strong></div><p>${paymentName(order.paymentMethod)} · ${paymentStatus(order.paymentStatus)}</p></div>${order.orderStatus === "pending" ? `<button type="button" class="order-cancel-btn" data-cancel="${escapeHtml(order.id)}">Hủy đơn</button>` : ""}</article>`;
            }).join("") : '<div class="order-empty-msg"><p>Bạn chưa có đơn hàng nào.</p></div>';
            container.querySelectorAll("[data-cancel]").forEach(button=>button.addEventListener("click", async()=>{
                if (!confirm("Hủy đơn " + button.dataset.cancel + "?")) return;
                button.disabled = true;
                try {
                    await api(`/api/orders/${encodeURIComponent(button.dataset.cancel)}/cancel`,{method:"POST",body:"{}"});
                    try {
                        const prodData = await api("/api/products");
                        products.length = 0; products.push(...prodData.products);
                        filterProducts();
                    } catch {}
                    await refreshOrders();
                }
                catch(e) { showToast("Lỗi",e.message,"warning"); button.disabled=false; }
            }));
        }
    } catch(e) {
        if (serverUser?.id !== requestedUserId || seq !== customerPollSeq) return;
        if (isAuto) {
            updateCustomerConnStatus("Mất kết nối server, đang thử lại...");
            customerPollBackoff = Math.min(customerPollBackoff * 2, 60000);
        } else {
            container.textContent = e.message;
        }
    }
    finally {
        if (!isAuto) {
            ordersBusy = false;
            if (refreshBtn) { refreshBtn.disabled = false; refreshBtn.textContent = "↻ Cập nhật đơn hàng"; }
        }
        scheduleNextCustomerOrdersPoll();
    }
}

async function fetchStoreInfo() {
    try {
        const data = await api("/api/store-info");
        storeInfo = data;
        window.storeInfo = data;
        if (typeof renderStoreStatusBanner === "function") renderStoreStatusBanner();
        if (typeof renderCheckoutZones === "function") renderCheckoutZones();
        if (typeof renderCart === "function") renderCart();
        if (typeof renderCheckoutSummary === "function") renderCheckoutSummary();
    } catch (e) {
        console.warn("Chưa tải được cấu hình cửa hàng:", e.message);
    }
}

document.addEventListener("DOMContentLoaded", async()=>{
    setupEventListeners(); renderCart(); updateCartCount(); updateAuthUI(); refreshOrders();
    document.addEventListener("keydown",event=>{
        const modal=document.getElementById("order-success-modal");
        if (event.key === "Escape") closeOrderSuccessModal();
        if (event.key === "Tab" && modal.style.display !== "none") {
            const buttons=[...modal.querySelectorAll("button")];
            if(event.shiftKey && document.activeElement===buttons[0]) {event.preventDefault(); buttons.at(-1).focus();}
            else if(!event.shiftKey && document.activeElement===buttons.at(-1)) {event.preventDefault(); buttons[0].focus();}
        }
    });
    try {
        if(location.protocol === "file:") throw new Error("Hãy chạy python server.py rồi mở http://127.0.0.1:5000. Không mở trực tiếp index.html.");
        const sessionData = await api("/api/session"); serverUser = sessionData.user;
        const [prodData] = await Promise.all([
            api("/api/products"),
            fetchStoreInfo()
        ]);
        products.push(...prodData.products);
        try {
            const saved = JSON.parse(localStorage.getItem("phuc_foodie_cart_v2") || "[]");
            if(Array.isArray(saved)) cart=saved.filter(i=>Number.isInteger(i.id)&&Number.isInteger(i.quantity)&&i.quantity>0&&i.quantity<=99).map(i=>{const p=products.find(p=>p.id===i.id&&p.available);return p?{...p,quantity:i.quantity}:null;}).filter(Boolean);
        } catch {}
        cartHydrated = true; apiReady = true; filterProducts(); renderCart(); updateCartCount(); updateAuthUI(); await refreshOrders();

        if(typeof window !== "undefined" && window.location && window.location.search) {
            try {
                const urlParams = new URLSearchParams(window.location.search);
                const authErr = urlParams.get("auth_error");
                if(authErr) {
                    if(typeof showToast === "function") {
                        showToast("Đăng nhập Google", authErr, "warning");
                    }
                    const cleanUrl = window.location.pathname + (window.location.hash || "");
                    window.history.replaceState({}, document.title, cleanUrl);
                }
            } catch {}
        }

        const googleBtn = document.getElementById("btn-google-login");
        if(googleBtn && sessionData && sessionData.googleAuthEnabled === false) {
            googleBtn.addEventListener("click", (ev) => {
                ev.preventDefault();
                if(typeof showToast === "function") {
                    showToast("Đăng nhập Google", "Đăng nhập Google hiện chưa được kích hoạt trên hệ thống.", "warning");
                }
            });
        }
    } catch(e) {
        const banner=document.getElementById("connection-error"); banner.hidden=false; banner.textContent=e.message;
        document.getElementById("product-list").textContent="Chưa tải được danh sách món.";
    }
    setInterval(()=>{ 
        if(!document.hidden) {
            fetchStoreInfo();
        }
    }, 30000);
});

document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
        stopCustomerOrdersPolling();
    } else {
        if (serverUser) {
            customerPollBackoff = 8000;
            refreshOrders({ isAuto: true });
        }
    }
});

if (typeof window !== "undefined") {
    window.refreshOrders = refreshOrders;
    window.stopCustomerOrdersPolling = stopCustomerOrdersPolling;
    window.getCustomerPollTimer = () => customerPollTimer;
}

