// frontend/results.js

function formatPrice(price, currency) {
  if (price == null) return "-";
  const val = Number(price);
  if (Number.isNaN(val)) return "-";
  const formatted = val.toLocaleString("es-CR", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
  if (currency === "CRC") return `₡${formatted}`;
  return `${formatted} ${currency || ""}`;
}

function createProductImageCell(product) {
  const td = document.createElement("td");
  td.classList.add("product-image-cell");
  const imageUrl = product.image_url;
  if (imageUrl) {
    const thumb = document.createElement("img");
    thumb.src = imageUrl;
    thumb.alt = product.name || "Imagen del producto";
    thumb.loading = "lazy";
    thumb.className = "product-thumb";
    td.appendChild(thumb);
  } else {
    const placeholder = document.createElement("span");
    placeholder.className = "text-muted small";
    placeholder.textContent = "Sin imagen";
    td.appendChild(placeholder);
  }
  return td;
}

const PRODUCTS_API_BASE = window.API_BASE || window.location.origin;
const productViewModalEl = document.getElementById("productViewModal");
const productViewModal = productViewModalEl ? new bootstrap.Modal(productViewModalEl) : null;
const productViewImageContainerEl = document.getElementById("product-view-image-container");
const productViewImageEl = document.getElementById("product-view-image");
const productEditModalEl = document.getElementById("productEditModal");
const productEditModal = productEditModalEl ? new bootstrap.Modal(productEditModalEl) : null;
const productEditForm = document.getElementById("product-edit-form");

function populateProductView(product) {
  if (!productViewModal) return;
  const imageUrl = product.image_url;
  if (productViewImageEl) {
    if (imageUrl) {
      productViewImageEl.src = imageUrl;
      productViewImageEl.alt = product.name || "Imagen del producto";
      productViewImageContainerEl?.classList.remove("d-none");
    } else {
      productViewImageEl.removeAttribute("src");
      productViewImageEl.alt = "";
      productViewImageContainerEl?.classList.add("d-none");
    }
  }
  // Muestra los datos del producto en el modal de solo lectura
  document.getElementById("product-view-name").textContent = product.name || "-";
  document.getElementById("product-view-brand").textContent = product.brand || "-";
  document.getElementById("product-view-category").textContent = product.category || "-";
  document.getElementById("product-view-price").textContent = formatPrice(product.price, product.currency);
  const urlEl = document.getElementById("product-view-url");
  urlEl.href = product.url || "#";
  urlEl.textContent = product.url || "Sin enlace";
  document.getElementById("product-view-active").textContent = product.is_active ? "Activo" : "Inactivo";
  document.getElementById("product-view-first").textContent = product.first_seen_at || "-";
  document.getElementById("product-view-last").textContent = product.last_seen_at || "-";
  productViewModal.show();
}

function prepareProductEdit(product) {
  if (!productEditModal || !productEditForm) return;
  // Carga la información en el formulario y muestra el modal para editar
  productEditForm.dataset.productId = product.id;
  document.getElementById("product-edit-name").value = product.name || "";
  document.getElementById("product-edit-brand").value = product.brand || "";
  document.getElementById("product-edit-category").value = product.category || "";
  document.getElementById("product-edit-price").value = product.price ?? "";
  document.getElementById("product-edit-currency").value = product.currency || "";
  document.getElementById("product-edit-active").checked = Boolean(product.is_active);
  productEditModal.show();
}

async function submitProductEdit(event) {
  event.preventDefault();
  if (!productEditForm) return;
  const productId = productEditForm.dataset.productId;
  if (!productId) return;

  const payload = {
    name: document.getElementById("product-edit-name").value.trim(),
    brand: document.getElementById("product-edit-brand").value.trim() || null,
    category: document.getElementById("product-edit-category").value.trim() || null,
    price: document.getElementById("product-edit-price").value
      ? Number(document.getElementById("product-edit-price").value)
      : null,
    currency: document.getElementById("product-edit-currency").value.trim() || null,
    is_active: document.getElementById("product-edit-active").checked,
  };

  try {
    // Envía los cambios al backend y actualiza la tabla sin recargar
    const response = await fetch(`${PRODUCTS_API_BASE}/api/products/${productId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error("No se pudo actualizar el producto");
    }

    productEditModal.hide();
    await loadAllData();
  } catch (err) {
    console.error("Error guardando producto:", err);
    alert("No se pudo guardar el producto en este momento.");
  }
}

async function handleProductDelete(productId) {
  if (!confirm("¿Seguro que deseas eliminar este producto?")) {
    return;
  }

  try {
    // Solicita al backend que marque el producto como eliminado para mantener coherencia
    const response = await fetch(`${PRODUCTS_API_BASE}/api/products/${productId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      throw new Error("Falla eliminando el producto");
    }
    await loadAllData();
  } catch (err) {
    console.error("Error eliminando producto:", err);
    alert("No se pudo eliminar el producto.");
  }
}

function createProductActionButtons(product) {
  const actionsTd = document.createElement("td");
  actionsTd.classList.add("text-nowrap");

  // Genera los botones de Ver, Editar y Eliminar para cada fila
  const viewBtn = document.createElement("button");
  viewBtn.type = "button";
  viewBtn.className = "btn btn-sm btn-info me-1";
  viewBtn.textContent = "Ver";
  viewBtn.addEventListener("click", () => populateProductView(product));

  const editBtn = document.createElement("button");
  editBtn.type = "button";
  editBtn.className = "btn btn-sm btn-warning me-1";
  editBtn.textContent = "Editar";
  editBtn.addEventListener("click", () => prepareProductEdit(product));

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "btn btn-sm btn-danger";
  deleteBtn.textContent = "Eliminar";
  deleteBtn.addEventListener("click", () => handleProductDelete(product.id));

  const printBtn = document.createElement("button");
  printBtn.type = "button";
  printBtn.className = "btn btn-sm btn-secondary";
  printBtn.textContent = "Imprimir PDF";
  printBtn.addEventListener("click", () => {
    // Descarga un PDF personalizado solo para este producto
    window.downloadPdfReport(product.id);
  });

  actionsTd.append(viewBtn, editBtn, deleteBtn, printBtn);
  return actionsTd;
}

function renderProductsTable(products) {
  const tbody = document.querySelector("#products-table tbody");
  tbody.innerHTML = "";

  // Solo mostramos productos activos para que el botón eliminar parezca efectivo
  const visibleProducts = products.filter((p) => p.is_active);

  visibleProducts.forEach((p) => {
    const tr = document.createElement("tr");

    const nameTd = document.createElement("td");
    const link = document.createElement("a");
    link.href = p.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = p.name;
    nameTd.appendChild(link);

    const imageTd = createProductImageCell(p);

    const brandTd = document.createElement("td");
    brandTd.textContent = p.brand || "-";

    const catTd = document.createElement("td");
    catTd.textContent = p.category || "-";

    const priceTd = document.createElement("td");
    priceTd.textContent = formatPrice(p.price, p.currency);

    const stateTd = document.createElement("td");
    const badge = document.createElement("span");
    badge.classList.add("badge");
    if (p.is_active) {
      badge.classList.add("badge-active");
      badge.textContent = "Activo";
    } else {
      badge.classList.add("badge-inactive");
      badge.textContent = "Inactivo";
    }
    stateTd.appendChild(badge);

    const lastSeenTd = document.createElement("td");
    lastSeenTd.textContent = p.last_seen_at || "";

    tr.append(nameTd, imageTd, brandTd, catTd, priceTd, stateTd, lastSeenTd);
    tr.appendChild(createProductActionButtons(p));
    tbody.appendChild(tr);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const searchInput = document.getElementById("product-search");
  if (!searchInput) return;

  searchInput.addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    const all = window.appState.products || [];
    const filtered = all.filter((p) => (p.name || "").toLowerCase().includes(q));
    renderProductsTable(filtered);
  });

  if (productEditForm) {
    productEditForm.addEventListener("submit", submitProductEdit);
  }
});
