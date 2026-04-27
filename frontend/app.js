const state = {
  classes: [],
  activeMode: "structured",
  entryCount: 0,
};

const elements = {
  form: document.getElementById("playgroundForm"),
  classSelect: document.getElementById("classSelect"),
  modeSelect: document.getElementById("modeSelect"),
  languageInput: document.getElementById("languageInput"),
  healthBadge: document.getElementById("healthBadge"),
  classCount: document.getElementById("classCount"),
  classCatalog: document.getElementById("classCatalog"),
  entriesContainer: document.getElementById("entriesContainer"),
  entryTemplate: document.getElementById("entryTemplate"),
  addEntryButton: document.getElementById("addEntryButton"),
  resetButton: document.getElementById("resetButton"),
  structuredPanel: document.getElementById("structuredPanel"),
  uploadPanel: document.getElementById("uploadPanel"),
  fileInput: document.getElementById("fileInput"),
  fileList: document.getElementById("fileList"),
  responseState: document.getElementById("responseState"),
  responsePanel: document.getElementById("responsePanel"),
  scoreValue: document.getElementById("scoreValue"),
  passValue: document.getElementById("passValue"),
  successList: document.getElementById("successList"),
  errorList: document.getElementById("errorList"),
  contextList: document.getElementById("contextList"),
  feedbackText: document.getElementById("feedbackText"),
  submitButton: document.getElementById("submitButton"),
};

document.addEventListener("DOMContentLoaded", async () => {
  bindEvents();
  setSubmissionMode("structured");
  await Promise.all([loadHealth(), loadClasses()]);
  seedDefaultEntries();
});

function bindEvents() {
  elements.addEntryButton.addEventListener("click", () => addEntry());
  elements.resetButton.addEventListener("click", resetForm);
  elements.form.addEventListener("submit", handleSubmit);
  elements.fileInput.addEventListener("change", renderSelectedFiles);
  elements.classSelect.addEventListener("change", () => syncClassSelection(false));

  document.querySelectorAll(".switch-pill").forEach((button) => {
    button.addEventListener("click", () => setSubmissionMode(button.dataset.target));
  });

  document.querySelectorAll("[data-preset]").forEach((button) => {
    button.addEventListener("click", () => applyPreset(button.dataset.preset));
  });
}

async function loadHealth() {
  try {
    const response = await fetch("/health");
    const payload = await response.json();
    elements.healthBadge.textContent = payload.ok ? "API operativa" : "API sin respuesta";
  } catch (error) {
    elements.healthBadge.textContent = "API no disponible";
  }
}

async function loadClasses() {
  try {
    const response = await fetch("/classes");
    if (!response.ok) {
      throw new Error("No se pudo consultar /classes");
    }
    state.classes = await response.json();
    renderClassOptions();
    renderClassCatalog();
  } catch (error) {
    elements.classCount.textContent = "Sin catalogo";
    elements.classCatalog.innerHTML = '<div class="response-state surface-muted">No pudimos cargar las clases.</div>';
  }
}

function renderClassOptions() {
  const sortedClasses = [...state.classes].sort((left, right) => {
    const leftPriority = left.language === "data" ? 0 : 1;
    const rightPriority = right.language === "data" ? 0 : 1;
    if (leftPriority !== rightPriority) {
      return leftPriority - rightPriority;
    }
    return `${left.title} ${left.class_id}`.localeCompare(`${right.title} ${right.class_id}`);
  });

  const options = ['<option value="">Seleccionar clase...</option>'];
  for (const item of sortedClasses) {
    const extraTitles = (item.resource_titles || []).slice(0, 2).join(" / ");
    options.push(
      `<option value="${escapeHtml(item.class_id)}" data-language="${escapeHtml(item.language)}">${escapeHtml(
        item.title,
      )} - ${escapeHtml(item.class_id)} - ${escapeHtml(item.language)}${extraTitles ? ` - ${escapeHtml(extraTitles)}` : ""}</option>`,
    );
  }

  elements.classSelect.innerHTML = options.join("");
  elements.classCount.textContent = `${state.classes.length} clases disponibles`;

  const defaultClass = sortedClasses.find((item) => item.language === "data") || sortedClasses[0];
  if (defaultClass) {
    elements.classSelect.value = defaultClass.class_id;
    syncClassSelection(false);
  }
}

function renderClassCatalog() {
  if (!state.classes.length) {
    elements.classCatalog.innerHTML = '<div class="response-state surface-muted">No hay clases disponibles.</div>';
    return;
  }

  const highlighted = [...state.classes]
    .sort((left, right) => {
      const leftPriority = left.language === "data" ? 0 : 1;
      const rightPriority = right.language === "data" ? 0 : 1;
      if (leftPriority !== rightPriority) {
        return leftPriority - rightPriority;
      }
      return left.class_id.localeCompare(right.class_id);
    });

  elements.classCatalog.innerHTML = highlighted
    .map(
      (item) => `
        <article class="catalog-item">
          <strong>${escapeHtml(item.title)}</strong>
          <p>${escapeHtml(item.class_id)} - ${escapeHtml(item.language)}</p>
          ${
            item.resource_titles && item.resource_titles.length
              ? `<p>${escapeHtml(item.resource_titles.join(" / "))}</p>`
              : ""
          }
          <div class="catalog-meta">
            ${item.allowed_topics.slice(0, 4).map((topic) => `<span class="catalog-tag">${escapeHtml(topic)}</span>`).join("")}
          </div>
        </article>
      `,
    )
    .join("");
}

function syncClassSelection(autofillExample) {
  const option = elements.classSelect.selectedOptions[0];
  if (!option) {
    return;
  }

  const language = option.dataset.language;
  if (language) {
    elements.languageInput.value = language;
  }

  if (!autofillExample) {
    return;
  }

  if (language === "data") {
    applyPreset("data-sheet");
  }
}

function seedDefaultEntries() {
  if (state.classes.some((item) => item.language === "data")) {
    applyPreset("data-sheet");
    return;
  }

  elements.entriesContainer.innerHTML = "";
  state.entryCount = 0;
  addEntry({
    name: "entrega.txt",
    kind: "text",
    mimeType: "text/plain",
    content: "Resumen de entrega.",
  });
}

function addEntry(initialValues = {}) {
  state.entryCount += 1;
  const fragment = elements.entryTemplate.content.cloneNode(true);
  const card = fragment.querySelector(".entry-card");
  const title = fragment.querySelector(".entry-title");
  const nameInput = fragment.querySelector(".entry-name");
  const kindInput = fragment.querySelector(".entry-kind");
  const mimeInput = fragment.querySelector(".entry-mime");
  const contentInput = fragment.querySelector(".entry-content");
  const urlInput = fragment.querySelector(".entry-url");
  const contentField = fragment.querySelector(".entry-content-field");
  const urlField = fragment.querySelector(".entry-url-field");
  const removeButton = fragment.querySelector(".entry-remove");

  title.textContent = `Entrada ${state.entryCount}`;
  nameInput.value = initialValues.name || "";
  kindInput.value = initialValues.kind || "file";
  mimeInput.value = initialValues.mimeType || "";
  contentInput.value = initialValues.content || "";
  urlInput.value = initialValues.url || "";

  const updateKind = () => {
    const isLink = kindInput.value === "link";
    contentField.classList.toggle("is-hidden", isLink);
    urlField.classList.toggle("is-hidden", !isLink);
  };

  kindInput.addEventListener("change", updateKind);
  removeButton.addEventListener("click", () => {
    card.remove();
    if (!elements.entriesContainer.children.length) {
      addEntry();
    }
  });

  updateKind();
  elements.entriesContainer.appendChild(fragment);
}

function setSubmissionMode(target) {
  state.activeMode = target;
  elements.structuredPanel.classList.toggle("is-hidden", target !== "structured");
  elements.uploadPanel.classList.toggle("is-hidden", target !== "upload");

  document.querySelectorAll(".switch-pill").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.target === target);
  });
}

function renderSelectedFiles() {
  const files = Array.from(elements.fileInput.files || []);
  if (!files.length) {
    elements.fileList.textContent = "Todavia no hay archivos seleccionados.";
    return;
  }

  elements.fileList.innerHTML = files
    .map((file) => `${escapeHtml(file.name)} - ${(file.size / 1024).toFixed(1)} KB`)
    .join("<br>");
}

function resetForm() {
  elements.form.reset();
  setSubmissionMode("structured");
  elements.fileList.textContent = "Todavia no hay archivos seleccionados.";
  hideResponse();

  const defaultClass = state.classes.find((item) => item.language === "data") || state.classes[0];
  if (defaultClass) {
    elements.classSelect.value = defaultClass.class_id;
    elements.languageInput.value = defaultClass.language;
  } else {
    elements.languageInput.value = "data";
  }

  seedDefaultEntries();
}

async function handleSubmit(event) {
  event.preventDefault();
  const classId = elements.classSelect.value.trim();
  const mode = elements.modeSelect.value;
  const language = elements.languageInput.value.trim();

  if (!classId) {
    showState("Elegi una clase antes de enviar la correccion.");
    return;
  }

  if (!language) {
    showState("Indica el trayecto o tipo de entrega.");
    return;
  }

  elements.submitButton.disabled = true;
  elements.submitButton.textContent = "Corrigiendo...";
  showState("Consultando la API y esperando feedback...");

  try {
    const payload =
      state.activeMode === "upload"
        ? await submitUpload({ classId, mode, language })
        : await submitStructured({ classId, mode, language });
    renderResponse(payload);
  } catch (error) {
    showState(error.message || "No se pudo completar la correccion.");
  } finally {
    elements.submitButton.disabled = false;
    elements.submitButton.textContent = "Enviar a correccion";
  }
}

async function submitStructured({ classId, mode, language }) {
  const files = Array.from(elements.entriesContainer.querySelectorAll(".entry-card")).map((card) => {
    const kind = card.querySelector(".entry-kind").value;
    return {
      name: card.querySelector(".entry-name").value.trim() || "entrega",
      kind,
      mime_type: card.querySelector(".entry-mime").value.trim() || null,
      content: kind === "link" ? "" : card.querySelector(".entry-content").value,
      url: kind === "link" ? card.querySelector(".entry-url").value.trim() : null,
    };
  });

  const response = await fetch("/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      class_id: classId,
      mode,
      language,
      files,
    }),
  });

  return parseApiResponse(response);
}

async function submitUpload({ classId, mode, language }) {
  const files = Array.from(elements.fileInput.files || []);
  if (!files.length) {
    throw new Error("Selecciona al menos un archivo para usar la subida real.");
  }

  const formData = new FormData();
  formData.append("class_id", classId);
  formData.append("mode", mode);
  formData.append("language", language);
  for (const file of files) {
    formData.append("files", file);
  }

  const response = await fetch("/feedback/upload", {
    method: "POST",
    body: formData,
  });

  return parseApiResponse(response);
}

async function parseApiResponse(response) {
  let payload;
  try {
    payload = await response.json();
  } catch (error) {
    throw new Error("La API respondio con un formato inesperado.");
  }

  if (!response.ok) {
    throw new Error(payload.detail || "La API devolvio un error.");
  }

  return payload;
}

function renderResponse(payload) {
  elements.responsePanel.classList.remove("is-hidden");
  elements.responseState.classList.add("is-hidden");
  elements.scoreValue.textContent = String(payload.score ?? 0);
  elements.passValue.textContent = payload.passed ? "Aprobado" : "Revisar";
  elements.successList.innerHTML = renderList(payload.successes, "No se detectaron logros todavia.");
  elements.errorList.innerHTML = renderList(payload.errors, "No aparecieron observaciones.");
  elements.contextList.innerHTML = (payload.context_used || [])
    .map((item) => `<span class="context-chip">${escapeHtml(item)}</span>`)
    .join("");
  elements.feedbackText.innerHTML = formatFeedback(payload.feedback || "Sin feedback.");
}

function hideResponse() {
  elements.responsePanel.classList.add("is-hidden");
  elements.responseState.classList.remove("is-hidden");
  elements.responseState.textContent =
    "Todavia no enviamos ninguna entrega. Completa el formulario y proba una correccion.";
}

function showState(message) {
  elements.responsePanel.classList.add("is-hidden");
  elements.responseState.classList.remove("is-hidden");
  elements.responseState.textContent = message;
}

function renderList(items, fallback) {
  if (!items || !items.length) {
    return `<li>${escapeHtml(fallback)}</li>`;
  }
  return items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

function formatFeedback(text) {
  return escapeHtml(text).replace(/\n/g, "<br>");
}

function applyPreset(name) {
  elements.entriesContainer.innerHTML = "";
  state.entryCount = 0;
  elements.modeSelect.value = "graded";
  elements.languageInput.value = "data";
  setSubmissionMode("structured");

  if (name === "data-sheet") {
    elements.classSelect.value = pickFirstDataClass([
      "data-1000-c04",
      "data-2001-c02",
      "data-2001-c03",
      "data-4000-c01",
    ]);
    addEntry({
      name: "ventas-supermercado.csv",
      kind: "file",
      mimeType: "text/csv",
      content:
        "categoria,producto,precio,cantidad,total\nBebidas,Agua,120,4,=C2*D2\nLimpieza,Detergente,950,2,=C3*D3\nAlmacen,Arroz,700,3,=C4*D4",
    });
    return;
  }

  if (name === "data-dashboard") {
    elements.classSelect.value = pickFirstDataClass([
      "data-3001-c01",
      "data-6000-c02",
      "data-6100-c04",
    ]);
    addEntry({
      name: "dashboard_descripcion.md",
      kind: "text",
      mimeType: "text/markdown",
      content:
        "Dashboard de ventas con metricas de facturacion, ticket promedio y cantidad de productos. Incluye filtro por categoria, region y mes. Usa graficos de barras, serie temporal y tabla dinamica con drill down por sucursal.",
    });
    return;
  }

  if (name === "data-link") {
    elements.classSelect.value = pickFirstDataClass([
      "data-6000-c01",
      "data-6100-c01",
      "data-3001-c01",
    ]);
    addEntry({
      name: "dashboard-publico",
      kind: "link",
      url: "https://lookerstudio.google.com/reporting/demo-public-link",
    });
    return;
  }

  addEntry({
    name: "entrega.txt",
    kind: "text",
    mimeType: "text/plain",
    content: "Resumen de entrega.",
  });
}

function pickFirstDataClass(preferredIds) {
  for (const classId of preferredIds) {
    if (state.classes.some((item) => item.class_id === classId)) {
      return classId;
    }
  }

  const firstData = state.classes.find((item) => item.language === "data");
  return firstData ? firstData.class_id : "";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
