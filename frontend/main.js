// frontend/main.js
// Usa el mismo origen donde se sirve la pagina para evitar problemas de CORS (127.0.0.1 vs localhost)
const API_BASE = window.location.origin;
window.API_BASE = API_BASE;

window.appState = {
  products: [],
  files: [],
  events: [],
};

async function fetchJson(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    console.error("Error fetch", path, res.status);
    return [];
  }
  return await res.json();
}

async function loadAllData() {
  try {
    const [products, files, events] = await Promise.all([
      fetchJson("/api/products"),
      fetchJson("/api/files"),
      fetchJson("/api/events"),
    ]);

    window.appState.products = products;
    window.appState.files = files;
    window.appState.events = events;

    updateSummary();
    renderProductsTable(products);
    renderFilesTable(files);
    initCalendar(events);
  } catch (err) {
    console.error("Error cargando datos:", err);
  }
}

function updateSummary() {
  const products = window.appState.products;
  const events = window.appState.events;

  const total = products.length;
  const active = products.filter((p) => p.is_active).length;

  document.getElementById("total-products").textContent = total;
  document.getElementById("active-products").textContent = active;
  document.getElementById("recent-events-count").textContent = events.length;
}

document.addEventListener("DOMContentLoaded", () => {
  loadAllData();
  const downloadButton = document.getElementById("download-pdf-btn");
  if (downloadButton) {
    // Descarga el PDF generado por el backend sin redirigir la página
    downloadButton.addEventListener("click", downloadPdfReport);
  }
});


async function downloadPdfReport(productId) {
  try {
    const endpoint = productId
      ? `${API_BASE}/api/export/products/${productId}/pdf`
      : `${API_BASE}/api/export/pdf`;
    const response = await fetch(endpoint);
    if (!response.ok) {
      throw new Error("No se pudo generar el PDF");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const tempLink = document.createElement("a");
    tempLink.style.display = "none";
    tempLink.href = url;
    tempLink.download = "reporte_scraper.pdf";
    document.body.appendChild(tempLink);
    tempLink.click();
    document.body.removeChild(tempLink);
    URL.revokeObjectURL(url);
  } catch (err) {
    console.error("Error descargando PDF:", err);
    alert("No se pudo descargar el reporte PDF en este momento; intentaremos abrirlo en otra pestaña.");
    const fallbackLink = document.createElement("a");
    fallbackLink.href = `${API_BASE}/api/export/pdf`;
    fallbackLink.target = "_blank";
    fallbackLink.rel = "noreferrer";
    fallbackLink.download = "reporte_scraper.pdf";
    document.body.appendChild(fallbackLink);
    fallbackLink.click();
    document.body.removeChild(fallbackLink);
  }
}

// Hacemos la función accesible globalmente para los botones de fila
window.downloadPdfReport = downloadPdfReport;
