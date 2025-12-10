// frontend/files.js

const FILE_API_BASE = window.API_BASE || window.location.origin;
const fileViewModalEl = document.getElementById("fileViewModal");
const fileViewModal = fileViewModalEl ? new bootstrap.Modal(fileViewModalEl) : null;
const fileEditModalEl = document.getElementById("fileEditModal");
const fileEditModal = fileEditModalEl ? new bootstrap.Modal(fileEditModalEl) : null;
const fileEditForm = document.getElementById("file-edit-form");

function populateFileView(file) {
  if (!fileViewModal) return;
  // Muestra la información completa en el modal de solo lectura
  document.getElementById("file-view-name").textContent = file.filename || "-";
  document.getElementById("file-view-mime").textContent = file.mime_type || "-";
  const urlEl = document.getElementById("file-view-url");
  urlEl.href = file.url || file.local_path || "#";
  urlEl.textContent = file.url || file.local_path || "Sin enlace";
  document.getElementById("file-view-local").textContent = file.local_path || "-";
  document.getElementById("file-view-active").textContent = file.is_active ? "Activo" : "Inactivo";
  document.getElementById("file-view-last").textContent = file.last_seen_at || "-";
  fileViewModal.show();
}

function prepareFileEdit(file) {
  if (!fileEditModal || !fileEditForm) return;
  // Rellena el formulario de edición con los datos actuales del archivo
  fileEditForm.dataset.fileId = file.id;
  document.getElementById("file-edit-name").value = file.filename || "";
  document.getElementById("file-edit-local").value = file.local_path || "";
  document.getElementById("file-edit-mime").value = file.mime_type || "";
  document.getElementById("file-edit-active").checked = Boolean(file.is_active);
  fileEditModal.show();
}

async function submitFileEdit(event) {
  event.preventDefault();
  if (!fileEditForm) return;
  const fileId = fileEditForm.dataset.fileId;
  if (!fileId) return;

  const payload = {
    filename: document.getElementById("file-edit-name").value.trim() || null,
    local_path: document.getElementById("file-edit-local").value.trim() || null,
    mime_type: document.getElementById("file-edit-mime").value.trim() || null,
    is_active: document.getElementById("file-edit-active").checked,
  };

  try {
    // Envía los cambios al backend y recarga los datos con loadAllData
    const response = await fetch(`${FILE_API_BASE}/api/files/${fileId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error("No se pudo actualizar el archivo");
    }
    fileEditModal.hide();
    await loadAllData();
  } catch (err) {
    console.error("Error guardando archivo:", err);
    alert("No se pudo guardar el archivo en este momento.");
  }
}

async function handleFileDelete(fileId) {
  if (!confirm("¿Seguro que deseas eliminar este archivo?")) {
    return;
  }

  try {
    const response = await fetch(`${FILE_API_BASE}/api/files/${fileId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      throw new Error("Falla eliminando el archivo");
    }
    await loadAllData();
  } catch (err) {
    console.error("Error eliminando archivo:", err);
    alert("No se pudo eliminar el archivo.");
  }
}

function createFileActionButtons(file) {
  const actionsTd = document.createElement("td");
  actionsTd.classList.add("text-nowrap");

  // Botones de acciones que interactúan con los modales y la API
  const viewBtn = document.createElement("button");
  viewBtn.type = "button";
  viewBtn.className = "btn btn-sm btn-info me-1";
  viewBtn.textContent = "Ver";
  viewBtn.addEventListener("click", () => populateFileView(file));

  const editBtn = document.createElement("button");
  editBtn.type = "button";
  editBtn.className = "btn btn-sm btn-warning me-1";
  editBtn.textContent = "Editar";
  editBtn.addEventListener("click", () => prepareFileEdit(file));

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "btn btn-sm btn-danger";
  deleteBtn.textContent = "Eliminar";
  deleteBtn.addEventListener("click", () => handleFileDelete(file.id));

  const printBtn = document.createElement("button");
  printBtn.type = "button";
  printBtn.className = "btn btn-sm btn-secondary";
  printBtn.textContent = "Imprimir PDF";
  printBtn.addEventListener("click", () => {
    // Utilizamos la misma descarga para imprimir rápidamente desde cada fila
    window.downloadPdfReport();
  });

  actionsTd.append(viewBtn, editBtn, deleteBtn, printBtn);
  return actionsTd;
}

function renderFilesTable(files) {
  const tbody = document.querySelector("#files-table tbody");
  tbody.innerHTML = "";

  const visibleFiles = files.filter((f) => f.is_active);

  visibleFiles.forEach((f) => {
    const tr = document.createElement("tr");

    const nameTd = document.createElement("td");
    nameTd.textContent = f.filename;

    const hashTd = document.createElement("td");
    hashTd.textContent = f.hash?.slice(0, 16) + "...";

    const stateTd = document.createElement("td");
    const badge = document.createElement("span");
    badge.classList.add("badge");
    if (f.is_active) {
      badge.classList.add("badge-active");
      badge.textContent = "Activo";
    } else {
      badge.classList.add("badge-inactive");
      badge.textContent = "Inactivo";
    }
    stateTd.appendChild(badge);

    const lastSeenTd = document.createElement("td");
    lastSeenTd.textContent = f.last_seen_at || "";

    tr.append(nameTd, hashTd, stateTd, lastSeenTd);
    tr.appendChild(createFileActionButtons(f));
    tbody.appendChild(tr);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  if (fileEditForm) {
    fileEditForm.addEventListener("submit", submitFileEdit);
  }
});
