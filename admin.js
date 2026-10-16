// Quản trị chỉ thao tác thông qua API có kiểm tra quyền ở server.
const $ = id => document.getElementById(id);
const esc = value => String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const money = n=>Number(n).toLocaleString("vi-VN")+"đ";
const transitions={pending:["confirmed","cancelled"],confirmed:["preparing","cancelled"],preparing:["delivering"],delivering:["delivered"],delivered:[],cancelled:[]};
const labels={confirmed:"Xác nhận đơn",preparing:"Bắt đầu chuẩn bị",delivering:"Bắt đầu giao",delivered:"Đã giao / Thu COD",cancelled:"Hủy đơn"};
let csrf="", currentUser=null, orders=[], products=[], refreshing=false, actionBusy=false;
let currentTab="orders";
let previewCategory="Tất cả";
let previewSearch="";
let formDirty=false;
let activeModalProduct=null;
let settingsData=null, zonesData=[], settingsDirty=false;

function notify(message,error=false){$("notice").textContent=message;$("notice").hidden=false;$("notice").classList.toggle("error",error);}
async function api(path,options={}){
    const controller=new AbortController(); const timeout=setTimeout(()=>controller.abort(),20000);
    try {
        const r=await fetch(path,{credentials:"same-origin",...options,signal:controller.signal,headers:{"Content-Type":"application/json","X-CSRF-Token":csrf}});
        const d=await r.json();
        if(!r.ok){if(r.status===401 && path!=="/api/admin/login"){currentUser=null;showSession();}throw Error(d.error||"Không xử lý được yêu cầu.");}
        if(d.csrfToken)csrf=d.csrfToken;return d;
    } catch(e){if(e.name==="AbortError"||e instanceof TypeError)throw Error("Không kết nối được server.");throw e;}
    finally{clearTimeout(timeout);}
}
function showSession(){
    const isAdmin=currentUser?.role==="admin";
    $("login-panel").hidden=isAdmin;$("dashboard").hidden=!isAdmin;$("logout").hidden=!currentUser;
    $("admin-name").textContent=currentUser?.fullName||"";
    if(currentUser&&!isAdmin)notify("Tài khoản này không có quyền quản trị. Hãy đăng xuất và dùng tài khoản quản trị.",true);
}
$("admin-login").addEventListener("submit",async e=>{
    e.preventDefault();if(actionBusy)return;actionBusy=true;const button=e.submitter;button.disabled=true;
    try{const data=await api("/api/admin/login",{method:"POST",body:JSON.stringify({identifier:$("identifier").value,password:$("password").value})});currentUser=data.user;$("password").value="";$("notice").hidden=true;showSession();if(currentUser.role==="admin")await refresh();}
    catch(e){notify(e.message,true);}finally{actionBusy=false;button.disabled=false;}
});
$("logout").addEventListener("click",async()=>{
    if(!confirmDiscardChanges())return;
    try{await api("/api/admin/logout",{method:"POST",body:"{}"});currentUser=null;orders=[];products=[];settingsData=null;zonesData=[];$("order-list").replaceChildren();$("product-grid").replaceChildren();$("preview-grid").replaceChildren();$("notice").hidden=true;showSession();}catch(e){notify(e.message,true);}
});

async function refresh(){
    if(refreshing||currentUser?.role!=="admin")return;
    if((formDirty&&$("product-dialog")?.open)||settingsDirty)return;
    refreshing=true;$("refresh").disabled=true;
    try{
        const [o,p,s]=await Promise.all([api("/api/admin/orders"),api("/api/products"),api("/api/admin/store/settings")]);
        orders=o.orders;products=p.products;
        settingsData=s.settings;zonesData=s.zones;
        renderOrders();renderProducts();renderPreview();renderStoreSettings();
    }
    catch(e){notify(e.message,true);}finally{refreshing=false;$("refresh").disabled=false;}
}

function renderOrders(){
    $("pending-count").textContent=orders.filter(o=>o.orderStatus==="pending").length;
    $("active-count").textContent=orders.filter(o=>["confirmed","preparing","delivering"].includes(o.orderStatus)).length;
    $("delivered-count").textContent=orders.filter(o=>o.orderStatus==="delivered").length;
    $("revenue").textContent=money(orders.filter(o=>o.orderStatus==="delivered"&&o.paymentMethod==="cod"&&o.paymentStatus==="paid").reduce((sum,o)=>sum+o.totalPrice,0));
    const visible=orders.filter(o=>$("status-filter").value==="all"||o.orderStatus===$("status-filter").value);
    $("order-list").innerHTML=visible.length?visible.map(o=>`<article class="order"><div class="order-header"><strong>${esc(o.id)}</strong><span class="badge ${esc(o.orderStatus)}">${esc(o.status)}</span></div><div class="order-info"><div><p class="hint">${esc(o.orderTime)}</p><p><strong>${esc(o.customerName)}</strong> · ${esc(o.customerPhone)}</p><p>${esc(o.customerAddress)}</p>${o.deliveryZoneName?`<p>Khu vực giao: <strong>${esc(o.deliveryZoneName)}</strong></p>`:""}${o.estimatedDeliveryTime?`<p class="hint">⏱ Dự kiến giao: ${esc(o.estimatedDeliveryTime)}</p>`:""}${o.customerNote?`<p>Ghi chú: ${esc(o.customerNote)}</p>`:""}<ul>${o.items.map(i=>`<li>${esc(i.name)} × ${i.quantity} — ${money(i.subtotal)}</li>`).join("")}</ul></div><div><p>Tạm tính: ${money(o.subtotalPrice)}</p><p>Giao hàng: ${money(o.shippingFee)}</p><p>Giảm: ${money(o.discountAmount)} ${o.voucherCode?"("+esc(o.voucherCode)+")":""}</p><strong class="order-total">${money(o.totalPrice)}</strong><p>${o.paymentMethod==="cod"?"Tiền mặt khi nhận hàng":"Thanh toán DEMO — không có giao dịch thật"}</p><p class="hint">${o.paymentStatus==="paid"?"Đã thu tiền COD":o.paymentStatus==="pending"?"Chờ thu tiền":"Đã xác nhận mô phỏng"}</p></div></div><div class="order-actions">${transitions[o.orderStatus].map(state=>`<button data-order="${esc(o.id)}" data-state="${state}" class="${state==="cancelled"?"danger":"primary"}">${state==="delivered"&&o.paymentMethod!=="cod"?"Đã giao (DEMO)":labels[state]}</button>`).join("")}</div></article>`).join(""):'<p>Không có đơn hàng trong trạng thái này.</p>';
    $("order-list").querySelectorAll("[data-state]").forEach(button=>button.addEventListener("click",async()=>{
        if(actionBusy)return;
        if(button.dataset.state==="cancelled"&&!confirm("Hủy đơn "+button.dataset.order+"?"))return;
        if(button.dataset.state==="delivered"&&!confirm("Xác nhận đã giao món và đã thu tiền COD nếu đơn trả tiền mặt?"))return;
        actionBusy=true;button.disabled=true;
        try{await api("/api/admin/orders/"+encodeURIComponent(button.dataset.order),{method:"PATCH",body:JSON.stringify({state:button.dataset.state})});notify("Đã cập nhật đơn.");await refresh();}
        catch(e){notify(e.message,true);button.disabled=false;}finally{actionBusy=false;}
    }));
}

function renderProducts(){
    $("product-grid").innerHTML=products.map(p=>{
        const stockText=p.stock_quantity!==null&&p.stock_quantity!==undefined?`Còn <strong>${p.stock_quantity}</strong> phần`:`<span style="color:#e53e3e">Chưa nhập tồn kho</span>`;
        return `<article class="product">
            <img src="/${esc(p.image)}" alt="${esc(p.name)}" loading="lazy">
            <div class="product-body">
                <h3>${esc(p.name)}</h3>
                <p>${money(p.price)} · ${esc(p.category)}</p>
                <p class="hint">${stockText}</p>
                <div style="display:flex;align-items:center;gap:0.5rem;margin:0.5rem 0;">
                    <span class="badge ${p.available?"":"cancelled"}">${p.available?"Đang mở bán":"Tạm ngừng bán"}</span>
                    <button data-toggle="${p.id}" class="outline" style="padding:0.25rem 0.6rem;font-size:0.85rem;">${p.available?"Tắt bán":"Bật bán"}</button>
                </div>
                <button data-edit="${p.id}" class="primary" style="margin-top:auto;">Chỉnh sửa</button>
            </div>
        </article>`;
    }).join("");
    $("product-grid").querySelectorAll("[data-edit]").forEach(b=>b.addEventListener("click",()=>openProduct(products.find(p=>p.id===Number(b.dataset.edit)))));
    $("product-grid").querySelectorAll("[data-toggle]").forEach(b=>b.addEventListener("click",async()=>{
        if(actionBusy)return;
        const p=products.find(item=>item.id===Number(b.dataset.toggle));
        if(!p)return;
        actionBusy=true;b.disabled=true;
        try{
            await api("/api/admin/products/"+p.id,{method:"PATCH",body:JSON.stringify({available:!p.available})});
            notify(`Đã chuyển trạng thái món "${p.name}" sang ${!p.available?"Đang mở bán":"Tạm ngừng bán"}.`);
            await refresh();
        }catch(e){notify(e.message,true);b.disabled=false;}
        finally{actionBusy=false;}
    }));
}

/* ========================================================
   XEM CỬA HÀNG DÀNH CHO ADMIN (STORE PREVIEW)
   ======================================================== */
function getProductStockInfo(p){
    const isAvail=Boolean(p.available);
    const s=p.stock_quantity;
    if(!isAvail) return {text:"Tạm ngừng bán", tagBg:"#ef4444", canOrder:false};
    if(s===null||s===undefined) return {text:"Chưa mở bán", tagBg:"#f59e0b", canOrder:false};
    if(s<=0) return {text:"Hết hàng", tagBg:"#ef4444", canOrder:false};
    return {text:`Còn ${s} phần`, tagBg:"#10b981", canOrder:true};
}

function renderPreview(){
    const storeInfoBox = $("preview-store-info");
    if (storeInfoBox && settingsData) {
        let statusBadge = "";
        if (settingsData.is_paused) {
            statusBadge = `<span class="status-badge paused">🔴 Tạm ngừng nhận đơn${settingsData.pause_reason ? ': ' + esc(settingsData.pause_reason) : ''}</span>`;
        } else {
            statusBadge = `<span class="status-badge open">🟢 Đang hoạt động theo cấu hình</span>`;
        }
        let estTimeStr = (settingsData.delivery_time_min && settingsData.delivery_time_max)
            ? `${settingsData.delivery_time_min} - ${settingsData.delivery_time_max} phút (ước tính)`
            : (settingsData.delivery_time_min ? `Khoảng ${settingsData.delivery_time_min} phút` : "Chưa cài đặt");
        let activeZones = (zonesData || []).filter(z => z.isActive);
        let zoneStr = (zonesData && zonesData.length > 0)
            ? (activeZones.length > 0 ? `${activeZones.length} khu vực nhận giao` : "Tất cả khu vực tạm ngừng")
            : "Chưa tạo khu vực (Phí mặc định 15.000đ)";
        storeInfoBox.innerHTML = `
            <div class="preview-store-banner">
                <div>
                    <h3 style="margin:0 0 4px;font-size:16px;">🏪 ${esc(settingsData.store_name || "PHUC-FOODIE")}</h3>
                    <p style="margin:0 0 4px;font-size:13px;color:#475569;">📍 ${esc(settingsData.address || "Chưa thiết lập địa chỉ")} · 📞 ${esc(settingsData.phone || "Chưa có hotline")}</p>
                    <p style="margin:0;font-size:13px;color:#2563eb;font-weight:600;">⏱ Giao hàng: ${esc(estTimeStr)} · 🛵 ${esc(zoneStr)} · 🚚 Miễn phí từ: ${money(settingsData.free_shipping_threshold)}</p>
                </div>
                <div>${statusBadge}</div>
            </div>
        `;
    }
    const grid=$("preview-grid");
    if(!grid)return;
    const kw=previewSearch.trim().toLowerCase();
    const filtered=products.filter(p=>{
        const matchCat=(previewCategory==="Tất cả")||(p.category===previewCategory);
        const matchKw=p.name.toLowerCase().includes(kw);
        return matchCat && matchKw;
    });

    if(filtered.length===0){
        grid.innerHTML='<div style="grid-column:1/-1;text-align:center;padding:40px;background:#fff;border-radius:12px;border:1px dashed #cbd5e1;"><p style="color:#64748b;font-size:16px;">Không tìm thấy món ăn nào phù hợp với bộ lọc hiện tại.</p></div>';
        return;
    }

    grid.innerHTML=filtered.map(p=>{
        const info=getProductStockInfo(p);
        return `<article class="preview-card" data-preview-id="${p.id}">
            <div class="preview-img-wrap">
                <img src="/${esc(p.image)}" alt="${esc(p.name)}" loading="lazy">
                <span class="product-badge">${esc(p.category)}</span>
                <span class="preview-stock-tag" style="background:${info.tagBg}">${esc(info.text)}</span>
            </div>
            <div class="preview-card-body">
                <h3 class="preview-card-title">${esc(p.name)}</h3>
                <p class="preview-card-price">${money(p.price)}</p>
                <p class="preview-card-desc">${esc(p.description||"Chưa có mô tả chi tiết.")}</p>
                <div class="preview-card-status">
                    <span class="badge ${p.available?"":"cancelled"}">${p.available?"Đang mở bán":"Tạm ngừng bán"}</span>
                </div>
                <div class="preview-card-actions">
                    <button type="button" class="btn-preview-view" data-view="${p.id}">👁 Xem chi tiết</button>
                    <button type="button" class="btn-preview-edit" data-edit="${p.id}">✏️ Chỉnh sửa món</button>
                </div>
            </div>
        </article>`;
    }).join("");

    // Sự kiện mở chi tiết món trong preview
    grid.querySelectorAll(".preview-card").forEach(card=>{
        card.addEventListener("click",e=>{
            if(e.target.closest("button"))return;
            const pid=Number(card.dataset.previewId);
            openPreviewDetail(products.find(p=>p.id===pid));
        });
    });
    grid.querySelectorAll("[data-view]").forEach(btn=>{
        btn.addEventListener("click",e=>{
            e.stopPropagation();
            const pid=Number(btn.dataset.view);
            openPreviewDetail(products.find(p=>p.id===pid));
        });
    });
    // Nút chỉnh sửa món trực tiếp từ xem cửa hàng
    grid.querySelectorAll("[data-edit]").forEach(btn=>{
        btn.addEventListener("click",e=>{
            e.stopPropagation();
            const pid=Number(btn.dataset.edit);
            openProduct(products.find(p=>p.id===pid));
        });
    });
}

function openPreviewDetail(p){
    if(!p)return;
    activeModalProduct=p;
    const info=getProductStockInfo(p);
    $("preview-detail-img").src="/"+p.image;
    $("preview-detail-badge").textContent=p.category;
    $("preview-detail-name").textContent=p.name;
    $("preview-detail-price").textContent=money(p.price);
    $("preview-detail-stock").innerHTML=`Trạng thái kho: <span style="color:${info.tagBg}">${esc(info.text)}</span> · ${p.available?"Đang mở bán":"Tạm ngừng bán"}`;
    $("preview-detail-desc").textContent=p.description||"Chưa có mô tả chi tiết cho món này.";
    $("preview-detail-dialog").showModal();
}

function closePreviewDetail(){
    if($("preview-detail-dialog")?.open){
        $("preview-detail-dialog").close();
    }
}
$("close-preview-detail").addEventListener("click",closePreviewDetail);
$("preview-detail-back-btn").addEventListener("click",closePreviewDetail);
$("preview-detail-edit-btn").addEventListener("click",()=>{
    if(activeModalProduct){
        const prod=activeModalProduct;
        closePreviewDetail();
        openProduct(prod);
    }
});

// Tìm kiếm & lọc danh mục trong xem cửa hàng
$("preview-search").addEventListener("input",e=>{
    previewSearch=e.target.value;
    renderPreview();
});
$("preview-search").addEventListener("keydown",e=>{
    if(e.key==="Escape"&&e.target.value){
        e.target.value="";
        previewSearch="";
        renderPreview();
    }
});

$("preview-categories").querySelectorAll(".btn-preview-cat").forEach(btn=>{
    btn.addEventListener("click",()=>{
        $("preview-categories").querySelectorAll(".btn-preview-cat").forEach(b=>b.classList.remove("active"));
        btn.classList.add("active");
        previewCategory=btn.dataset.category;
        renderPreview();
    });
});
$("preview-add-product").addEventListener("click",()=>openProduct());

/* ========================================================
   QUẢN LÝ FORM MÓN & DIRTY CHECK (CẢNH BÁO KHI CÓ THAY ĐỔI DỞ DANG)
   ======================================================== */
let currentPreviewBlobUrl = null;

function revokePreviewBlobUrl(){
    if(currentPreviewBlobUrl){
        try{ URL.revokeObjectURL(currentPreviewBlobUrl); }catch(_){}
        currentPreviewBlobUrl = null;
    }
}

function setupProductImagePreview(){
    const fileInput=$("product-file");
    const selectImg=$("product-image");
    const previewImg=$("product-preview");
    const currentName=$("product-current-img-name");

    fileInput.addEventListener("change",()=>{
        formDirty=true;
        const file=fileInput.files[0];
        if(!file)return;
        if(file.size>5*1024*1024){$("product-error").textContent="Tệp vượt quá 5 MB.";fileInput.value="";return;}
        const validTypes=["image/jpeg","image/png","image/webp"];
        if(!validTypes.includes(file.type)){$("product-error").textContent="Chỉ chấp nhận JPEG, PNG hoặc WebP.";fileInput.value="";return;}
        $("product-error").textContent="";
        revokePreviewBlobUrl();
        currentPreviewBlobUrl=URL.createObjectURL(file);
        previewImg.src=currentPreviewBlobUrl;
        previewImg.style.display="block";
        currentName.textContent=`Đã chọn: ${file.name} (${Math.round(file.size/1024)} KB)`;
        selectImg.value="";
    });

    selectImg.addEventListener("change",()=>{
        formDirty=true;
        if(!selectImg.value)return;
        revokePreviewBlobUrl();
        fileInput.value="";
        previewImg.src="/"+selectImg.value;
        previewImg.style.display="block";
        currentName.textContent=`Ảnh mẫu: ${selectImg.options[selectImg.selectedIndex].text}`;
    });
}

// Đánh dấu form dirty khi người dùng gõ
["product-name","product-price","product-category","product-stock","product-available","product-description"].forEach(id=>{
    $(id).addEventListener("input",()=>{formDirty=true;});
    $(id).addEventListener("change",()=>{formDirty=true;});
});

function confirmDiscardChanges(){
    if(formDirty&&$("product-dialog")?.open){
        return confirm("Bạn có thay đổi chưa lưu trên biểu mẫu món ăn. Bạn có chắc muốn rời đi mà không lưu không?");
    }
    if(settingsDirty){
        return confirm("Bạn có thay đổi chưa lưu trong Cấu hình cửa hàng. Bạn có chắc muốn rời đi mà không lưu không?");
    }
    return true;
}

function openProduct(p){
    if(!confirmDiscardChanges())return;
    revokePreviewBlobUrl();
    formDirty=false;
    $("product-id").value=p?.id||"";
    $("product-current-image").value=p?.image||"";
    $("product-name").value=p?.name||"";
    $("product-price").value=p?.price||"";
    $("product-category").value=p?.category||"Đồ ăn";
    $("product-stock").value=p?.stock_quantity!==null&&p?.stock_quantity!==undefined?p.stock_quantity:"";
    $("product-available").checked=p?Boolean(p.available):true;
    $("product-description").value=p?.description||"";
    $("product-file").value="";
    $("product-error").textContent="";
    $("product-status").textContent="";
    $("product-title").textContent=p?"Chỉnh sửa món":"Thêm món mới";
    $("btn-save-product").textContent="Lưu món";
    $("btn-save-product").disabled=false;

    const preview=$("product-preview");
    const currentName=$("product-current-img-name");
    if(p?.image){
        preview.src="/"+p.image;
        preview.style.display="block";
        currentName.textContent=`Ảnh hiện tại: ${p.image}`;
        $("product-image").value=p.image.startsWith("images/")?p.image:"";
    }else{
        $("product-image").value="images/burger.jpg";
        preview.src="/images/burger.jpg";
        preview.style.display="block";
        currentName.textContent="Ảnh mẫu: Burger";
    }
    $("product-dialog").showModal();
}
$("add-product").addEventListener("click",()=>openProduct());
$("close-product").addEventListener("click",()=>{
    if(confirmDiscardChanges()){
        revokePreviewBlobUrl();
        formDirty=false;
        $("product-dialog").close();
    }
});
$("product-dialog").addEventListener("cancel",e=>{
    if(!confirmDiscardChanges()){
        e.preventDefault();
    }else{
        revokePreviewBlobUrl();
        formDirty=false;
    }
});
window.addEventListener("beforeunload",e=>{
    if((formDirty&&$("product-dialog")?.open)||settingsDirty){
        e.preventDefault();
        e.returnValue="";
    }
});

$("product-form").addEventListener("submit",async e=>{
    e.preventDefault();
    if(actionBusy)return;
    const saveBtn=$("btn-save-product");
    const id=$("product-id").value;
    const fileInput=$("product-file");
    const selectImg=$("product-image");
    const currentImg=$("product-current-image").value;
    const stockValInput=$("product-stock").value.trim();

    let stockVal=null;
    if(stockValInput!==""){
        const n=Number(stockValInput);
        if(!Number.isInteger(n)||n<0){$("product-error").textContent="Số lượng tồn kho phải là số nguyên không âm (>= 0).";return;}
        stockVal=n;
    }

    actionBusy=true;saveBtn.disabled=true;saveBtn.textContent="Đang lưu...";
    $("product-error").textContent="";
    $("product-status").textContent="Đang chuẩn bị dữ liệu...";

    let finalImagePath=currentImg||selectImg.value||"images/burger.jpg";

    try{
        if(fileInput.files.length>0){
            $("product-status").textContent="Đang tải ảnh lên server...";
            const fd=new FormData();
            fd.append("file",fileInput.files[0]);
            const uploadRes=await fetch("/api/admin/upload",{
                method:"POST",
                credentials:"same-origin",
                headers:{"X-CSRF-Token":csrf},
                body:fd
            });
            const uploadData=await uploadRes.json();
            if(!uploadRes.ok)throw Error(uploadData.error||"Tải ảnh thất bại.");
            finalImagePath=uploadData.image;
        }else if(selectImg.value){
            finalImagePath=selectImg.value;
        }

        $("product-status").textContent="Đang cập nhật món...";
        const payloadData={
            name:$("product-name").value.trim(),
            price:Number($("product-price").value),
            category:$("product-category").value,
            image:finalImagePath,
            description:$("product-description").value.trim(),
            available:$("product-available").checked,
            stock_quantity:stockVal
        };

        await api("/api/admin/products"+(id?"/"+id:""),{
            method:id?"PATCH":"POST",
            body:JSON.stringify(payloadData)
        });

        formDirty=false;
        revokePreviewBlobUrl();
        $("product-dialog").close();
        notify(`Đã lưu món "${payloadData.name}" thành công.`);
        await refresh();
    }catch(err){
        $("product-error").textContent=err.message;
        $("product-status").textContent="";
    }finally{
        actionBusy=false;
        saveBtn.disabled=false;
        saveBtn.textContent="Lưu món";
    }
});
setupProductImagePreview();
$("refresh").addEventListener("click",refresh);
$("status-filter").addEventListener("change",renderOrders);

/* ========================================================
   CẤU HÌNH CỬA HÀNG & KHU VỰC GIAO HÀNG
   ======================================================== */
const DAYS = [
    { key: "mon", num: "0", label: "Thứ Hai" },
    { key: "tue", num: "1", label: "Thứ Ba" },
    { key: "wed", num: "2", label: "Thứ Tư" },
    { key: "thu", num: "3", label: "Thứ Năm" },
    { key: "fri", num: "4", label: "Thứ Sáu" },
    { key: "sat", num: "5", label: "Thứ Bảy" },
    { key: "sun", num: "6", label: "Chủ Nhật" }
];
let workingSchedule = null;

function renderStoreSettings(){
    if(!settingsData) return;
    $("settings-store-name").value = settingsData.store_name || "";
    $("settings-store-phone").value = settingsData.phone || "";
    $("settings-store-address").value = settingsData.address || "";
    $("settings-is-paused").checked = Boolean(settingsData.is_paused);
    $("settings-pause-reason").value = settingsData.pause_reason || "";
    $("settings-delivery-min").value = settingsData.delivery_time_min ?? "";
    $("settings-delivery-max").value = settingsData.delivery_time_max ?? "";
    $("settings-free-ship-enabled").checked = Boolean(settingsData.free_shipping_enabled);
    $("settings-free-ship-threshold").value = settingsData.free_shipping_threshold ?? 100000;

    if(!workingSchedule || !settingsDirty){
        const rawSched = settingsData.schedule || {};
        workingSchedule = {};
        DAYS.forEach(d => {
            const dayObj = rawSched[d.key] || rawSched[d.num] || { isOpen: true, ranges: [{ open: "08:00", close: "22:00" }] };
            const isOpen = dayObj.isOpen !== undefined ? Boolean(dayObj.isOpen) : !dayObj.is_closed;
            const ranges = Array.isArray(dayObj.ranges) ? JSON.parse(JSON.stringify(dayObj.ranges)) : [{ open: "08:00", close: "22:00" }];
            const normalized = { isOpen, is_closed: !isOpen, ranges };
            workingSchedule[d.key] = normalized;
            workingSchedule[d.num] = normalized;
        });
    }
    renderScheduleEditor();
    renderZonesList();
}

function renderScheduleEditor(){
    const container = $("settings-schedule-container");
    if(!container || !workingSchedule) return;

    container.innerHTML = DAYS.map(d => {
        const daySched = workingSchedule[d.key] || workingSchedule[d.num] || { isOpen: true, ranges: [{ open: "08:00", close: "22:00" }] };
        const isOpen = daySched.isOpen !== undefined ? Boolean(daySched.isOpen) : !daySched.is_closed;
        const ranges = Array.isArray(daySched.ranges) ? daySched.ranges : [];

        let rangesHtml = "";
        if(isOpen){
            if(ranges.length === 0){
                rangesHtml = `<span class="hint" style="color:#b45309;">Chưa có khoảng giờ mở cửa. Bấm "+ Thêm khung giờ" để cài đặt.</span>`;
            } else {
                rangesHtml = ranges.map((r, idx) => {
                    const isOvernight = r.open && r.close && r.open > r.close;
                    return `
                        <div class="schedule-range-row" data-day="${d.key}" data-idx="${idx}">
                            <input type="time" class="sched-time-input sched-open" data-day="${d.key}" data-idx="${idx}" value="${esc(r.open || '08:00')}" required>
                            <span class="sched-sep">đến</span>
                            <input type="time" class="sched-time-input sched-close" data-day="${d.key}" data-idx="${idx}" value="${esc(r.close || '22:00')}" required>
                            ${isOvernight ? '<span class="overnight-badge" title="Khoảng giờ mở qua nửa đêm sang rạng sáng ngày tiếp theo">🌙 Qua nửa đêm</span>' : ''}
                            <button type="button" class="btn-remove-range outline danger" data-day="${d.key}" data-idx="${idx}" title="Xóa khung giờ này" aria-label="Xóa">×</button>
                        </div>
                    `;
                }).join("");
            }
        } else {
            rangesHtml = `<span class="day-off-tag">💤 Nghỉ bán cả ngày</span>`;
        }

        return `
            <div class="schedule-day-card ${isOpen ? '' : 'is-day-off'}" id="sched-card-${d.key}">
                <div class="schedule-day-header">
                    <label class="schedule-day-label">
                        <input type="checkbox" class="sched-day-toggle" data-day="${d.key}" ${isOpen ? 'checked' : ''}>
                        <strong>${esc(d.label)}</strong>
                    </label>
                    ${isOpen ? `<button type="button" class="btn-add-range outline" data-day="${d.key}">+ Thêm khung giờ</button>` : ''}
                </div>
                <div class="schedule-ranges-list" id="sched-ranges-${d.key}">
                    ${rangesHtml}
                </div>
            </div>
        `;
    }).join("");

    // Gắn sự kiện cho các nút trong bảng lịch
    container.querySelectorAll(".sched-day-toggle").forEach(cb => {
        cb.addEventListener("change", e => {
            const dayKey = cb.dataset.day;
            settingsDirty = true;
            if(!workingSchedule[dayKey]) workingSchedule[dayKey] = { isOpen: false, ranges: [] };
            workingSchedule[dayKey].isOpen = cb.checked;
            if(cb.checked && (!workingSchedule[dayKey].ranges || workingSchedule[dayKey].ranges.length === 0)){
                workingSchedule[dayKey].ranges = [{ open: "08:00", close: "22:00" }];
            }
            renderScheduleEditor();
        });
    });

    container.querySelectorAll(".sched-time-input").forEach(inp => {
        inp.addEventListener("change", e => {
            const dayKey = inp.dataset.day;
            const idx = Number(inp.dataset.idx);
            settingsDirty = true;
            if(workingSchedule[dayKey]?.ranges?.[idx]){
                if(inp.classList.contains("sched-open")){
                    workingSchedule[dayKey].ranges[idx].open = inp.value;
                } else if(inp.classList.contains("sched-close")){
                    workingSchedule[dayKey].ranges[idx].close = inp.value;
                }
                renderScheduleEditor();
            }
        });
    });

    container.querySelectorAll(".btn-add-range").forEach(btn => {
        btn.addEventListener("click", () => {
            const dayKey = btn.dataset.day;
            settingsDirty = true;
            if(!workingSchedule[dayKey]) workingSchedule[dayKey] = { isOpen: true, ranges: [] };
            workingSchedule[dayKey].isOpen = true;
            if(!Array.isArray(workingSchedule[dayKey].ranges)) workingSchedule[dayKey].ranges = [];
            workingSchedule[dayKey].ranges.push({ open: "17:00", close: "22:00" });
            renderScheduleEditor();
        });
    });

    container.querySelectorAll(".btn-remove-range").forEach(btn => {
        btn.addEventListener("click", () => {
            const dayKey = btn.dataset.day;
            const idx = Number(btn.dataset.idx);
            settingsDirty = true;
            if(workingSchedule[dayKey]?.ranges){
                workingSchedule[dayKey].ranges.splice(idx, 1);
                if(workingSchedule[dayKey].ranges.length === 0){
                    workingSchedule[dayKey].isOpen = false;
                }
                renderScheduleEditor();
            }
        });
    });
}

// Lắng nghe thay đổi form cấu hình
["settings-store-name", "settings-store-phone", "settings-store-address", "settings-is-paused", "settings-pause-reason", "settings-delivery-min", "settings-delivery-max", "settings-free-ship-enabled", "settings-free-ship-threshold"].forEach(id => {
    $(id)?.addEventListener("input", () => { settingsDirty = true; });
    $(id)?.addEventListener("change", () => { settingsDirty = true; });
});

// Lưu cấu hình cửa hàng
$("settings-form")?.addEventListener("submit", async e => {
    e.preventDefault();
    if(actionBusy) return;
    const saveBtn = $("btn-save-settings");

    // Kiểm tra thời gian giao hàng
    const minValStr = $("settings-delivery-min").value.trim();
    const maxValStr = $("settings-delivery-max").value.trim();
    let minVal = null, maxVal = null;
    if(minValStr !== ""){
        minVal = Number(minValStr);
        if(!Number.isInteger(minVal) || minVal < 0){
            notify("Thời gian giao hàng tối thiểu phải là số nguyên không âm.", true);
            return;
        }
    }
    if(maxValStr !== ""){
        maxVal = Number(maxValStr);
        if(!Number.isInteger(maxVal) || maxVal < 0){
            notify("Thời gian giao hàng tối đa phải là số nguyên không âm.", true);
            return;
        }
    }
    if(minVal !== null && maxVal !== null && minVal > maxVal){
        notify("Thời gian giao hàng tối thiểu không được lớn hơn thời gian tối đa.", true);
        return;
    }

    // Kiểm tra ngưỡng miễn phí giao hàng
    const thresholdStr = $("settings-free-ship-threshold").value.trim();
    const threshold = Number(thresholdStr);
    if(!Number.isInteger(threshold) || threshold <= 0){
        notify("Ngưỡng miễn phí giao hàng phải là số nguyên lớn hơn 0.", true);
        return;
    }

    // Kiểm tra lịch
    for(const d of DAYS){
        const sched = workingSchedule?.[d.key];
        if(sched?.isOpen){
            if(!sched.ranges || sched.ranges.length === 0){
                notify(`Ngày ${d.label} đang bật mở cửa nhưng chưa có khoảng giờ nào.`, true);
                return;
            }
            for(const r of sched.ranges){
                if(!r.open || !r.close){
                    notify(`Ngày ${d.label} có khung giờ chưa chọn đầy đủ giờ mở và đóng.`, true);
                    return;
                }
                if(r.open === r.close){
                    notify(`Ngày ${d.label} có khung giờ mở và đóng trùng nhau (${r.open}).`, true);
                    return;
                }
            }
        }
    }

    actionBusy = true;
    saveBtn.disabled = true;
    saveBtn.textContent = "⏳ Đang lưu cấu hình...";

    try {
        const payload = {
            store_name: $("settings-store-name").value.trim(),
            phone: $("settings-store-phone").value.trim(),
            address: $("settings-store-address").value.trim(),
            is_paused: $("settings-is-paused").checked,
            pause_reason: $("settings-pause-reason").value.trim(),
            schedule: workingSchedule || settingsData.schedule,
            delivery_time_min: minVal,
            delivery_time_max: maxVal,
            free_shipping_enabled: $("settings-free-ship-enabled").checked,
            free_shipping_threshold: threshold
        };

        const res = await api("/api/admin/store/settings", {
            method: "PATCH",
            body: JSON.stringify(payload)
        });

        settingsDirty = false;
        settingsData = res.settings;
        workingSchedule = JSON.parse(JSON.stringify(settingsData.schedule));
        notify("Đã lưu cấu hình cửa hàng thành công.");
        renderStoreSettings();
        renderPreview();
    } catch(err) {
        notify(err.message, true);
    } finally {
        actionBusy = false;
        saveBtn.disabled = false;
        saveBtn.textContent = "💾 Lưu cấu hình cửa hàng";
    }
});

/* ========================================================
   QUẢN LÝ KHU VỰC GIAO HÀNG (DELIVERY ZONES)
   ======================================================== */
function renderZonesList(){
    const container = $("zone-list-container");
    const reminder = $("zone-empty-reminder");
    if(!container) return;

    if(!zonesData || zonesData.length === 0){
        if(reminder) reminder.style.display = "block";
        container.innerHTML = "";
        return;
    }
    if(reminder) reminder.style.display = "none";

    container.innerHTML = `
        <table class="zone-table">
            <thead>
                <tr>
                    <th>Tên khu vực</th>
                    <th>Phí giao hàng</th>
                    <th>Trạng thái</th>
                    <th>Đơn hàng</th>
                    <th style="text-align:right;">Thao tác</th>
                </tr>
            </thead>
            <tbody>
                ${zonesData.map(z => `
                    <tr class="${z.isActive ? '' : 'zone-inactive-row'}">
                        <td><strong>${esc(z.name)}</strong></td>
                        <td>${z.fee === 0 ? '<span style="color:#16a34a;font-weight:700;">Miễn phí (0đ)</span>' : money(z.fee)}</td>
                        <td>
                            <span class="badge ${z.isActive ? 'active-zone' : 'cancelled'}">
                                ${z.isActive ? 'Đang nhận giao' : 'Tạm tắt giao'}
                            </span>
                        </td>
                        <td class="hint">${z.usedInOrders ? `${z.usedInOrders} đơn` : 'Chưa có đơn'}</td>
                        <td style="text-align:right;white-space:nowrap;">
                            <button type="button" class="outline btn-edit-zone" data-zone-id="${z.id}" style="padding:4px 8px;font-size:13px;">Sửa</button>
                            <button type="button" class="outline btn-toggle-zone" data-zone-id="${z.id}" style="padding:4px 8px;font-size:13px;">
                                ${z.isActive ? 'Tắt giao' : 'Bật giao'}
                            </button>
                            <button type="button" class="outline danger btn-delete-zone" data-zone-id="${z.id}" 
                                ${z.usedInOrders > 0 ? 'disabled title="Khu vực này đã có đơn hàng trong lịch sử, hãy tắt nhận giao thay vì xóa."' : ''} 
                                style="padding:4px 8px;font-size:13px;">
                                Xóa
                            </button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    container.querySelectorAll(".btn-edit-zone").forEach(b => {
        b.addEventListener("click", () => {
            const zid = Number(b.dataset.zoneId);
            const z = zonesData.find(item => item.id === zid);
            if(z) openZoneDialog(z);
        });
    });

    container.querySelectorAll(".btn-toggle-zone").forEach(b => {
        b.addEventListener("click", async () => {
            if(actionBusy) return;
            const zid = Number(b.dataset.zoneId);
            const z = zonesData.find(item => item.id === zid);
            if(!z) return;
            actionBusy = true; b.disabled = true;
            try {
                await api("/api/admin/delivery-zones/" + zid, {
                    method: "PATCH",
                    body: JSON.stringify({ isActive: !z.isActive })
                });
                notify(`Đã chuyển khu vực "${z.name}" sang ${!z.isActive ? 'Đang nhận giao' : 'Tạm tắt giao'}.`);
                await refresh();
            } catch(e) {
                notify(e.message, true);
                b.disabled = false;
            } finally {
                actionBusy = false;
            }
        });
    });

    container.querySelectorAll(".btn-delete-zone").forEach(b => {
        b.addEventListener("click", async () => {
            if(actionBusy || b.disabled) return;
            const zid = Number(b.dataset.zoneId);
            const z = zonesData.find(item => item.id === zid);
            if(!z) return;
            if(!confirm(`Xác nhận xóa khu vực "${z.name}"? Thao tác này không thể hoàn tác.`)) return;
            actionBusy = true; b.disabled = true;
            try {
                await api("/api/admin/delivery-zones/" + zid, { method: "DELETE", body: "{}" });
                notify(`Đã xóa khu vực "${z.name}".`);
                await refresh();
            } catch(e) {
                notify(e.message, true);
                b.disabled = false;
            } finally {
                actionBusy = false;
            }
        });
    });
}

function openZoneDialog(z = null) {
    $("zone-id").value = z?.id || "";
    $("zone-name").value = z?.name || "";
    $("zone-fee").value = z !== null && z !== undefined ? z.fee : "";
    $("zone-active").checked = z ? Boolean(z.isActive) : true;
    $("zone-title").textContent = z ? "Chỉnh sửa khu vực giao hàng" : "Thêm khu vực giao hàng";
    $("zone-error").style.display = "none";
    $("zone-error").textContent = "";
    $("btn-save-zone").disabled = false;
    $("btn-save-zone").textContent = "Lưu khu vực";
    $("zone-dialog").showModal();
}

function closeZoneDialog() {
    if($("zone-dialog")?.open) $("zone-dialog").close();
}

$("btn-add-zone")?.addEventListener("click", () => openZoneDialog());
$("close-zone")?.addEventListener("click", closeZoneDialog);
$("btn-cancel-zone")?.addEventListener("click", closeZoneDialog);

$("zone-form")?.addEventListener("submit", async e => {
    e.preventDefault();
    if(actionBusy) return;
    const zid = $("zone-id").value;
    const name = $("zone-name").value.trim();
    const feeStr = $("zone-fee").value.trim();
    const fee = Number(feeStr);
    const isActive = $("zone-active").checked;

    if(!name) {
        $("zone-error").textContent = "Vui lòng nhập tên khu vực.";
        $("zone-error").style.display = "block";
        return;
    }
    if(!Number.isInteger(fee) || fee < 0) {
        $("zone-error").textContent = "Phí giao hàng phải là số nguyên không âm (>= 0).";
        $("zone-error").style.display = "block";
        return;
    }

    actionBusy = true;
    $("btn-save-zone").disabled = true;
    $("btn-save-zone").textContent = "Đang lưu...";
    $("zone-error").style.display = "none";

    try {
        if(zid) {
            await api("/api/admin/delivery-zones/" + zid, {
                method: "PATCH",
                body: JSON.stringify({ name, fee, isActive })
            });
            notify(`Đã cập nhật khu vực "${name}".`);
        } else {
            await api("/api/admin/delivery-zones", {
                method: "POST",
                body: JSON.stringify({ name, fee, isActive })
            });
            notify(`Đã thêm khu vực "${name}".`);
        }
        closeZoneDialog();
        await refresh();
    } catch(err) {
        $("zone-error").textContent = err.message;
        $("zone-error").style.display = "block";
    } finally {
        actionBusy = false;
        $("btn-save-zone").disabled = false;
        $("btn-save-zone").textContent = "Lưu khu vực";
    }
});

/* ========================================================
   CHUYỂN TAB VÀ KHỞI TẠO
   ======================================================== */
function switchTab(tab){
    if((formDirty || settingsDirty) && !confirmDiscardChanges()) return;
    currentTab = tab;
    const tabNames = ["orders", "products", "preview", "settings"];
    tabNames.forEach(name => {
        const isTarget = name === tab;
        $(`${name}-panel`).hidden = !isTarget;
        $(`${name}-tab`).classList.toggle("active", isTarget);
        $(`${name}-tab`).setAttribute("aria-selected", String(isTarget));
    });
    if(tab === "preview"){
        renderPreview();
    }
    if(tab === "settings"){
        renderStoreSettings();
    }
}

$("orders-tab").addEventListener("click", () => switchTab("orders"));
$("products-tab").addEventListener("click", () => switchTab("products"));
$("preview-tab").addEventListener("click", () => switchTab("preview"));
$("settings-tab")?.addEventListener("click", () => switchTab("settings"));
$("header-preview-btn").addEventListener("click", () => switchTab("preview"));

(async()=>{
    try{
        const data=await api("/api/admin/session");
        currentUser=data.user;
        showSession();
        await refresh();
    }catch(e){
        notify(e.message,true);
    }
})();

setInterval(()=>{if(!document.hidden&&!$("product-dialog").open&&!actionBusy)refresh();},20000);

