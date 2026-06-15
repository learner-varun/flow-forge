// ─── Suite State ─────────────────────────────────────────────────────────────
// Always starts empty. State is auto-saved to localStorage on every change
// and restored on normal page load. A hard refresh (Ctrl+Shift+R) wipes the
// saved state so the app opens completely fresh.
const STORAGE_KEY = 'suiteBuilderState';

const EMPTY_SUITE = () => ({
  name: "",
  environment: "",
  base_url: "",
  timeout_seconds: 10,
  verify_ssl: true,
  defaults: { repeat: 1, min_success_rate: 100 },
  cases: []
});

let suite = EMPTY_SUITE();

// Global active tabs for cards
let cardActiveTabs = {};
let cardCollapsed = {};

// DOM Elements
document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

function initApp() {
  // Event listeners for top actions
  document.getElementById("btn-reset-flow").addEventListener("click", resetFlow);
  document.getElementById("btn-settings").addEventListener("click", openSettingsModal);
  document.getElementById("btn-import-file").addEventListener("change", handleFileImport);
  document.getElementById("btn-copy-json").addEventListener("click", copyJsonToClipboard);
  document.getElementById("btn-download-json").addEventListener("click", downloadSuiteJson);
  document.getElementById("btn-add-case").addEventListener("click", addNewCase);
  
  // Settings modal controls
  document.getElementById("settings-close").addEventListener("click", closeSettingsModal);
  document.getElementById("btn-cancel-settings").addEventListener("click", closeSettingsModal);
  document.getElementById("settings-form").addEventListener("submit", saveSettings);
  
  // Live JSON drawer controls
  document.getElementById("btn-toggle-json").addEventListener("click", toggleJsonDrawer);
  document.getElementById("drawer-close").addEventListener("click", closeJsonDrawer);
  
  // cURL import modal controls
  document.getElementById("btn-import-curl").addEventListener("click", openCurlModal);
  document.getElementById("curl-close").addEventListener("click", closeCurlModal);
  document.getElementById("btn-cancel-curl").addEventListener("click", closeCurlModal);
  document.getElementById("curl-form").addEventListener("submit", handleCurlImport);
  
  // Custom confirmation controls
  document.getElementById("btn-confirm-cancel").addEventListener("click", () => {
    document.getElementById("confirm-modal").classList.remove("active");
    if (confirmModalResolve) {
      confirmModalResolve(false);
      confirmModalResolve = null;
    }
  });
  document.getElementById("btn-confirm-ok").addEventListener("click", () => {
    document.getElementById("confirm-modal").classList.remove("active");
    if (confirmModalResolve) {
      confirmModalResolve(true);
      confirmModalResolve = null;
    }
  });
  
  // Initialize theme
  initTheme();

  // Restore suite from localStorage (skipped on hard refresh)
  loadSuiteFromStorage();

  // Initialize state views
  renderSuiteMeta();
  renderCases();
  updateLiveJsonPreview();

  // Variable autocomplete ({{ trigger)
  initVarAutocomplete();
}

// ─── localStorage persistence ─────────────────────────────────────────────────

/**
 * Detect hard refresh via sessionStorage flag.
 * On hard refresh the browser clears sessionStorage, so the flag is gone.
 * We set it right after checking — subsequent soft reloads keep it.
 */
function loadSuiteFromStorage() {
  const isHardRefresh = !sessionStorage.getItem('_sbLoaded');
  sessionStorage.setItem('_sbLoaded', '1');

  if (isHardRefresh) {
    // Wipe saved state and start completely empty
    localStorage.removeItem(STORAGE_KEY);
    suite = EMPTY_SUITE();
    return;
  }

  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const parsed = JSON.parse(saved);
      // Merge to ensure all required keys exist
      suite = Object.assign(EMPTY_SUITE(), parsed);
      // Ensure defaults sub-object is complete
      suite.defaults = Object.assign({ repeat: 1, min_success_rate: 100 }, parsed.defaults || {});
      suite.cases = Array.isArray(parsed.cases) ? parsed.cases : [];
    }
  } catch (e) {
    console.warn('Suite Builder: failed to restore state from localStorage', e);
    suite = EMPTY_SUITE();
  }
}

function resetFlow() {
  showConfirm("Are you sure you want to reset all data and start over? This cannot be undone.", "Reset", true).then(confirmed => {
    if (confirmed) {
      localStorage.removeItem(STORAGE_KEY);
      sessionStorage.removeItem('_sbLoaded');
      window.location.reload();
    }
  });
}

function saveSuiteToStorage(compiled) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(compiled));
  } catch (e) {
    // Quota exceeded or private browsing — silently skip
    console.warn('Suite Builder: localStorage save failed', e);
  }
}

// Render Suite Metadata tags
function renderSuiteMeta() {
  document.getElementById("display-suite-name").textContent = suite.name || "Untitled Suite";
  
  const tagsContainer = document.getElementById("suite-meta-tags");
  tagsContainer.innerHTML = `
    <span class="badge badge-primary badge-outline gap-1 text-[11px] font-mono py-2.5 px-3">🌍 env: <strong>${suite.environment || "None"}</strong></span>
    <span class="badge badge-neutral badge-outline gap-1 text-[11px] font-mono py-2.5 px-3">🔗 base: <strong>${suite.base_url || "Not set"}</strong></span>
    <span class="badge badge-neutral badge-outline gap-1 text-[11px] font-mono py-2.5 px-3">⏱️ timeout: <strong>${suite.timeout_seconds}s</strong></span>
    <span class="badge badge-neutral badge-outline gap-1 text-[11px] font-mono py-2.5 px-3">🔒 ssl: <strong>${suite.verify_ssl ? 'on' : 'off'}</strong></span>
    <span class="badge badge-neutral badge-outline gap-1 text-[11px] font-mono py-2.5 px-3">🔁 repeat: <strong>${suite.defaults.repeat}</strong></span>
    <span class="badge badge-neutral badge-outline gap-1 text-[11px] font-mono py-2.5 px-3">📈 success rate: <strong>${suite.defaults.min_success_rate}%</strong></span>
  `;
}

// Render API cards list
function renderCases() {
  const casesListContainer = document.getElementById("cases-list");
  casesListContainer.innerHTML = "";
  
  if (suite.cases.length === 0) {
    casesListContainer.innerHTML = `
      <div class="text-center p-12 bg-base-100 rounded-lg border border-dashed border-base-300 text-base-content/50">
        No API Cases defined yet. Click the "+ Add API Case" button below to start.
      </div>
    `;
    analyzeVariables();
    return;
  }
  
  suite.cases.forEach((c, index) => {
    const isCollapsed = cardCollapsed[index] || false;
    const activeTab = cardActiveTabs[index] || "headers";
    const isCompleted = c.completed || false;
    
    const card = document.createElement("div");
    card.className = `case-card card bg-base-100 border border-base-200 shadow-sm overflow-hidden ${isCollapsed ? 'collapsed' : ''} ${isCompleted ? 'completed-glow' : ''}`;
    card.dataset.index = index;
    
    const methodClass = c.method;
    
    card.innerHTML = `
      <div class="flex items-center gap-2 px-4 py-2.5 bg-base-200/50 border-b border-base-200 cursor-pointer card-header">
        <span class="text-xs font-semibold text-base-content/40 min-w-[20px]">#${index + 1}</span>
        
        <select class="select select-bordered select-xs font-bold w-24 card-method-select ${methodClass}" data-index="${index}">
          <option value="GET" ${c.method === 'GET' ? 'selected' : ''}>GET</option>
          <option value="POST" ${c.method === 'POST' ? 'selected' : ''}>POST</option>
          <option value="PUT" ${c.method === 'PUT' ? 'selected' : ''}>PUT</option>
          <option value="DELETE" ${c.method === 'DELETE' ? 'selected' : ''}>DELETE</option>
          <option value="PATCH" ${c.method === 'PATCH' ? 'selected' : ''}>PATCH</option>
        </select>
        <input type="text" class="input input-bordered input-xs font-mono flex-1 card-endpoint-input" placeholder="/api/v1/resource" value="${escapeHtml(c.endpoint)}" data-index="${index}">
        <input type="text" class="input input-bordered input-xs font-mono w-40 card-id-input" placeholder="case_id (unique)" value="${escapeHtml(c.id)}" data-index="${index}">
        
        <div class="flex items-center gap-1 card-actions">
          <button class="btn btn-ghost btn-xs btn-square btn-toggle-collapse" title="Collapse/Expand" data-index="${index}">
            ${isCollapsed ? '▼' : '▲'}
          </button>
          <button class="btn btn-ghost btn-xs btn-square btn-duplicate" title="Duplicate Case" data-index="${index}">📋</button>
          <button class="btn btn-ghost btn-xs btn-square btn-move-up" title="Move Up" data-index="${index}" ${index === 0 ? 'disabled' : ''}>↑</button>
          <button class="btn btn-ghost btn-xs btn-square btn-move-down" title="Move Down" data-index="${index}" ${index === suite.cases.length - 1 ? 'disabled' : ''}>↓</button>
          <button class="btn btn-ghost btn-xs btn-square text-error hover:bg-error/10 btn-delete-card" title="Delete Case" data-index="${index}">🗑️</button>
        </div>
      </div>
      
      <div class="card-body p-4 flex flex-col gap-4">
        <div class="form-control w-full">
          <label class="label py-0.5"><span class="label-text-alt uppercase font-bold text-base-content/50 text-[10px]">Case Name / Description</span></label>
          <input type="text" class="input input-bordered input-sm w-full card-name-input" placeholder="e.g. Authenticate user to obtain token" value="${escapeHtml(c.name || '')}" data-index="${index}">
        </div>
        
        <!-- Tabs Header -->
        <div class="tabs tabs-bordered w-full mb-1" role="tablist">
          <button class="tab tab-bordered text-xs font-semibold ${activeTab === 'headers' ? 'tab-active text-primary font-bold' : 'text-base-content/60'} font-heading card-tab-btn" role="tab" data-index="${index}" data-tab="headers">Headers & Params</button>
          <button class="tab tab-bordered text-xs font-semibold ${activeTab === 'body' ? 'tab-active text-primary font-bold' : 'text-base-content/60'} font-heading card-tab-btn" role="tab" data-index="${index}" data-tab="body">Request Body</button>
          <button class="tab tab-bordered text-xs font-semibold ${activeTab === 'assertions' ? 'tab-active text-primary font-bold' : 'text-base-content/60'} font-heading card-tab-btn" role="tab" data-index="${index}" data-tab="assertions">Assertions</button>
          <button class="tab tab-bordered text-xs font-semibold ${activeTab === 'extract' ? 'tab-active text-primary font-bold' : 'text-base-content/60'} font-heading card-tab-btn" role="tab" data-index="${index}" data-tab="extract">Variable Extractions</button>
        </div>
        
        <!-- Tab Content: Headers & Params -->
        <div class="card-tab-content ${activeTab === 'headers' ? '' : 'hidden'}" id="tab-headers-${index}">
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="flex flex-col gap-2">
              <span class="text-[10px] uppercase font-bold tracking-wider text-base-content/50">Request Headers</span>
              <div class="flex flex-col gap-2" id="headers-list-${index}">
                <!-- Dynamic rows -->
              </div>
              <button class="btn btn-outline btn-xs btn-block btn-row-add mt-1" data-index="${index}" data-type="headers">+ Add Header</button>
            </div>
            
            <div class="flex flex-col gap-2">
              <span class="text-[10px] uppercase font-bold tracking-wider text-base-content/50">Query Parameters</span>
              <div class="flex flex-col gap-2" id="params-list-${index}">
                <!-- Dynamic rows -->
              </div>
              <button class="btn btn-outline btn-xs btn-block btn-row-add mt-1" data-index="${index}" data-type="params">+ Add Parameter</button>
            </div>
          </div>
        </div>
        
        <!-- Tab Content: Request Body -->
        <div class="card-tab-content ${activeTab === 'body' ? '' : 'hidden'}" id="tab-body-${index}">
          <div class="flex flex-wrap gap-4 border-b border-base-200 pb-2 mb-2">
            <label class="flex items-center gap-1.5 cursor-pointer text-xs font-medium">
              <input type="radio" name="body-type-${index}" value="none" ${(!c.bodyType || c.bodyType === 'none') ? 'checked' : ''} data-index="${index}" class="radio radio-primary radio-xs"> None
            </label>
            <label class="flex items-center gap-1.5 cursor-pointer text-xs font-medium">
              <input type="radio" name="body-type-${index}" value="json" ${c.bodyType === 'json' ? 'checked' : ''} data-index="${index}" class="radio radio-primary radio-xs"> JSON (Payload)
            </label>
            <label class="flex items-center gap-1.5 cursor-pointer text-xs font-medium">
              <input type="radio" name="body-type-${index}" value="body" ${c.bodyType === 'body' ? 'checked' : ''} data-index="${index}" class="radio radio-primary radio-xs"> Raw Text
            </label>
            <label class="flex items-center gap-1.5 cursor-pointer text-xs font-medium">
              <input type="radio" name="body-type-${index}" value="form" ${c.bodyType === 'form' ? 'checked' : ''} data-index="${index}" class="radio radio-primary radio-xs"> Form URL-Encoded
            </label>
            <label class="flex items-center gap-1.5 cursor-pointer text-xs font-medium">
              <input type="radio" name="body-type-${index}" value="multipart" ${c.bodyType === 'multipart' ? 'checked' : ''} data-index="${index}" class="radio radio-primary radio-xs"> Multipart Form
            </label>
            <label class="flex items-center gap-1.5 cursor-pointer text-xs font-medium">
              <input type="radio" name="body-type-${index}" value="files" ${c.bodyType === 'files' ? 'checked' : ''} data-index="${index}" class="radio radio-primary radio-xs"> Multipart Files
            </label>
          </div>
          
          <div id="body-content-container-${index}" class="mt-2">
            <!-- Conditional inputs based on body type -->
          </div>
        </div>
        
        <!-- Tab Content: Assertions -->
        <div class="card-tab-content ${activeTab === 'assertions' ? '' : 'hidden'}" id="tab-assertions-${index}">
          <div class="flex flex-col gap-2" id="assertions-list-${index}">
            <!-- Dynamic assertion rows -->
          </div>
          <button class="btn btn-outline btn-xs btn-block btn-assertion-add mt-1" data-index="${index}">+ Add Assertion</button>
        </div>
        
        <!-- Tab Content: Extractions -->
        <div class="card-tab-content ${activeTab === 'extract' ? '' : 'hidden'}" id="tab-extract-${index}">
          <span class="text-[10px] uppercase font-bold tracking-wider text-base-content/50 block mb-2">Extract Response JSON path to Variables</span>
          <div class="flex flex-col gap-2" id="extract-list-${index}">
            <!-- Dynamic rows -->
          </div>
          <button class="btn btn-outline btn-xs btn-block btn-row-add mt-1" data-index="${index}" data-type="extract">+ Add Variable Extraction</button>
        </div>
      </div>
    `;
    
    casesListContainer.appendChild(card);
    
    // Render the dynamic rows
    renderHeadersRows(index);
    renderParamsRows(index);
    renderBodyFields(index);
    renderAssertionsRows(index);
    renderExtractRows(index);
  });
  
  // Attach event handlers for elements inside cases
  attachCardEvents();
  analyzeVariables();
}

function renderHeadersRows(caseIdx) {
  const container = document.getElementById(`headers-list-${caseIdx}`);
  container.innerHTML = "";
  const headersObj = suite.cases[caseIdx].headers || {};
  
  Object.keys(headersObj).forEach(key => {
    const row = document.createElement("div");
    row.className = "flex gap-2 items-center key-value-row";
    row.innerHTML = `
      <input type="text" class="input input-bordered input-sm flex-1 min-w-0 font-mono text-xs font-semibold kv-key" placeholder="Key" value="${escapeHtml(key)}" data-case="${caseIdx}">
      <input type="text" class="input input-bordered input-sm flex-1 min-w-0 font-mono text-xs kv-val" placeholder="Value" value="${escapeHtml(headersObj[key])}" data-case="${caseIdx}">
      <button class="btn btn-ghost btn-xs btn-circle text-base-content/40 hover:text-error btn-kv-delete flex-shrink-0" title="Delete Header" data-case="${caseIdx}" data-type="headers" data-key="${escapeHtml(key)}">✕</button>
    `;
    container.appendChild(row);
  });
  
  attachKvRowChangeHandlers(container, caseIdx, "headers");
}

function renderParamsRows(caseIdx) {
  const container = document.getElementById(`params-list-${caseIdx}`);
  container.innerHTML = "";
  const paramsObj = suite.cases[caseIdx].params || {};
  
  Object.keys(paramsObj).forEach(key => {
    const row = document.createElement("div");
    row.className = "flex gap-2 items-center key-value-row";
    row.innerHTML = `
      <input type="text" class="input input-bordered input-sm flex-1 min-w-0 font-mono text-xs font-semibold kv-key" placeholder="Key" value="${escapeHtml(key)}" data-case="${caseIdx}">
      <input type="text" class="input input-bordered input-sm flex-1 min-w-0 font-mono text-xs kv-val" placeholder="Value" value="${escapeHtml(paramsObj[key])}" data-case="${caseIdx}">
      <button class="btn btn-ghost btn-xs btn-circle text-base-content/40 hover:text-error btn-kv-delete flex-shrink-0" title="Delete Parameter" data-case="${caseIdx}" data-type="params" data-key="${escapeHtml(key)}">✕</button>
    `;
    container.appendChild(row);
  });
  
  attachKvRowChangeHandlers(container, caseIdx, "params");
}

function renderExtractRows(caseIdx) {
  const container = document.getElementById(`extract-list-${caseIdx}`);
  container.innerHTML = "";
  const extractObj = suite.cases[caseIdx].extract || {};
  
  Object.keys(extractObj).forEach(key => {
    const row = document.createElement("div");
    row.className = "flex gap-2 items-center key-value-row";
    row.innerHTML = `
      <input type="text" class="input input-bordered input-sm flex-1 min-w-0 font-mono text-xs font-semibold kv-key" placeholder="Variable Name" value="${escapeHtml(key)}" data-case="${caseIdx}">
      <input type="text" class="input input-bordered input-sm flex-1 min-w-0 font-mono text-xs kv-val" placeholder="JSON Path" value="${escapeHtml(extractObj[key])}" data-case="${caseIdx}">
      <button class="btn btn-ghost btn-xs btn-circle text-base-content/40 hover:text-error btn-kv-delete flex-shrink-0" title="Delete Extraction" data-case="${caseIdx}" data-type="extract" data-key="${escapeHtml(key)}">✕</button>
    `;
    container.appendChild(row);
  });
  
  attachKvRowChangeHandlers(container, caseIdx, "extract");
}

function renderBodyFields(caseIdx) {
  const c = suite.cases[caseIdx];
  const container = document.getElementById(`body-content-container-${caseIdx}`);
  container.innerHTML = "";
  
  const type = c.bodyType || "none";
  
  if (type === "none") {
    container.innerHTML = `<p class="text-xs text-base-content/40 py-2">No Request Body payload is sent with this method.</p>`;
  } 
  else if (type === "json") {
    let jsonStr = "";
    if (c.json) {
      jsonStr = typeof c.json === "string" ? c.json : JSON.stringify(c.json, null, 2);
    }
    container.innerHTML = `
      <textarea class="textarea textarea-bordered w-full h-36 font-mono text-xs body-json-textarea shadow-inner" placeholder="{ \n  &quot;email&quot;: &quot;user@example.com&quot;\n}" data-index="${caseIdx}">${escapeHtml(jsonStr)}</textarea>
      <p class="text-[10px] text-base-content/40 mt-1">Must be valid JSON formatting.</p>
    `;
    
    container.querySelector(".body-json-textarea").addEventListener("input", (e) => {
      suite.cases[caseIdx].json = e.target.value;
      updateLiveJsonPreview();
      analyzeVariables();
    });
  } 
  else if (type === "body") {
    container.innerHTML = `
      <textarea class="textarea textarea-bordered w-full h-36 font-mono text-xs body-raw-textarea shadow-inner" placeholder="Enter raw request body content..." data-index="${caseIdx}">${escapeHtml(c.body || '')}</textarea>
    `;
    
    container.querySelector(".body-raw-textarea").addEventListener("input", (e) => {
      suite.cases[caseIdx].body = e.target.value;
      updateLiveJsonPreview();
      analyzeVariables();
    });
  } 
  else if (type === "form") {
    container.innerHTML = `
      <div class="flex flex-col gap-2" id="form-kv-${caseIdx}"></div>
      <button class="btn btn-outline btn-xs btn-block btn-body-row-add mt-1" data-index="${caseIdx}" data-type="form">+ Add Form Parameter</button>
    `;
    
    renderBodyKvRows(caseIdx, "form");
  } 
  else if (type === "multipart") {
    container.innerHTML = `
      <div class="flex flex-col gap-2" id="multipart-kv-${caseIdx}"></div>
      <button class="btn btn-outline btn-xs btn-block btn-body-row-add mt-1" data-index="${caseIdx}" data-type="multipart">+ Add Multipart Field</button>
    `;
    
    renderBodyKvRows(caseIdx, "multipart");
  } 
  else if (type === "files") {
    container.innerHTML = `
      <div class="flex flex-col gap-4">
        <div>
          <span class="text-[10px] uppercase font-bold tracking-wider text-base-content/50 block mb-1">Multipart Text Fields (Key-Value)</span>
          <div class="flex flex-col gap-2" id="multipart-kv-${caseIdx}"></div>
          <button class="btn btn-outline btn-xs btn-block btn-body-row-add mt-1.5" data-index="${caseIdx}" data-type="multipart">+ Add Form Field</button>
        </div>
        <div class="border-t border-base-200 pt-3">
          <span class="text-[10px] uppercase font-bold tracking-wider text-base-content/50 block mb-1">Multipart File Uploads (Key-Filepath/Object)</span>
          <div class="flex flex-col gap-2" id="files-kv-${caseIdx}"></div>
          <button class="btn btn-outline btn-xs btn-block btn-body-row-add mt-1.5" data-index="${caseIdx}" data-type="files">+ Add File Upload</button>
        </div>
      </div>
    `;
    
    renderBodyKvRows(caseIdx, "multipart");
    renderBodyKvRows(caseIdx, "files");
  }
}

function renderBodyKvRows(caseIdx, type) {
  const container = document.getElementById(`${type}-kv-${caseIdx}`);
  container.innerHTML = "";
  const obj = suite.cases[caseIdx][type] || {};
  
  Object.keys(obj).forEach(key => {
    const val = obj[key];
    const valStr = typeof val === "string" ? val : (val.path || "");
    
    const row = document.createElement("div");
    row.className = "flex gap-2 items-center key-value-row";
    row.innerHTML = `
      <input type="text" class="input input-bordered input-sm flex-1 min-w-0 font-mono text-xs font-semibold kv-key" placeholder="Key" value="${escapeHtml(key)}" data-case="${caseIdx}">
      <input type="text" class="input input-bordered input-sm flex-1 min-w-0 font-mono text-xs kv-val" placeholder="${type === 'files' ? 'File path' : 'Value'}" value="${escapeHtml(valStr)}" data-case="${caseIdx}">
      <button class="btn btn-ghost btn-xs btn-circle text-base-content/40 hover:text-error btn-kv-delete flex-shrink-0" title="Delete Parameter" data-case="${caseIdx}" data-type="${type}" data-key="${escapeHtml(key)}">✕</button>
    `;
    container.appendChild(row);
  });
  
  attachKvRowChangeHandlers(container, caseIdx, type);
  
  const btnAdd = container.nextElementSibling;
  btnAdd.onclick = () => {
    if (!suite.cases[caseIdx][type]) suite.cases[caseIdx][type] = {};
    suite.cases[caseIdx][type][""] = "";
    renderBodyKvRows(caseIdx, type);
    updateLiveJsonPreview();
    analyzeVariables();
  };
}

function renderAssertionsRows(caseIdx) {
  const container = document.getElementById(`assertions-list-${caseIdx}`);
  container.innerHTML = "";
  const assertions = suite.cases[caseIdx].assertions || [];
  
  assertions.forEach((assertion, aIdx) => {
    const row = document.createElement("div");
    row.className = "flex gap-2 items-center assertion-row";
    
    let innerFields = "";
    const type = assertion.type;
    
    if (type === "status_code" || type === "response_time_under_ms" || type === "body_contains") {
      innerFields = `
        <input type="text" class="input input-bordered input-sm flex-1 font-mono text-xs assert-expected" placeholder="Expected Value" value="${escapeHtml(assertion.expected || '')}" data-case="${caseIdx}" data-assert="${aIdx}">
      `;
    } 
    else if (type === "header_contains") {
      innerFields = `
        <input type="text" class="input input-bordered input-sm flex-1 font-mono text-xs assert-path" placeholder="Header Name" value="${escapeHtml(assertion.path || '')}" data-case="${caseIdx}" data-assert="${aIdx}">
        <input type="text" class="input input-bordered input-sm flex-1 font-mono text-xs assert-expected" placeholder="Expected Value" value="${escapeHtml(assertion.expected || '')}" data-case="${caseIdx}" data-assert="${aIdx}">
      `;
    } 
    else if (type === "json_path_exists") {
      innerFields = `
        <input type="text" class="input input-bordered input-sm flex-1 font-mono text-xs assert-path" placeholder="JSON Path" value="${escapeHtml(assertion.path || '')}" data-case="${caseIdx}" data-assert="${aIdx}">
      `;
    } 
    else if (type === "json_path_equals" || type === "json_path_contains" || type === "json_path_type") {
      innerFields = `
        <input type="text" class="input input-bordered input-sm flex-1 font-mono text-xs assert-path" placeholder="JSON Path" value="${escapeHtml(assertion.path || '')}" data-case="${caseIdx}" data-assert="${aIdx}">
        <input type="text" class="input input-bordered input-sm flex-1 font-mono text-xs assert-expected" placeholder="Expected Value" value="${escapeHtml(assertion.expected || '')}" data-case="${caseIdx}" data-assert="${aIdx}">
      `;
    }
    
    row.innerHTML = `
      <select class="select select-bordered select-sm w-44 assert-type-select text-xs font-semibold" data-case="${caseIdx}" data-assert="${aIdx}">
        <option value="status_code" ${type === 'status_code' ? 'selected' : ''}>status_code</option>
        <option value="response_time_under_ms" ${type === 'response_time_under_ms' ? 'selected' : ''}>response_time_under_ms</option>
        <option value="json_path_exists" ${type === 'json_path_exists' ? 'selected' : ''}>json_path_exists</option>
        <option value="json_path_equals" ${type === 'json_path_equals' ? 'selected' : ''}>json_path_equals</option>
        <option value="json_path_contains" ${type === 'json_path_contains' ? 'selected' : ''}>json_path_contains</option>
        <option value="json_path_type" ${type === 'json_path_type' ? 'selected' : ''}>json_path_type</option>
        <option value="header_contains" ${type === 'header_contains' ? 'selected' : ''}>header_contains</option>
        <option value="body_contains" ${type === 'body_contains' ? 'selected' : ''}>body_contains</option>
      </select>
      ${innerFields}
      <button class="btn btn-ghost btn-xs btn-circle text-base-content/40 hover:text-error btn-assertion-delete" title="Delete assertion" data-case="${caseIdx}" data-assert="${aIdx}">✕</button>
    `;
    
    container.appendChild(row);
  });
  
  attachAssertionHandlers(container, caseIdx);
}

// Attach event listeners for dynamic Key-Value lists
function attachKvRowChangeHandlers(container, caseIdx, arrayType) {
  const rows = container.querySelectorAll(".key-value-row");
  
  rows.forEach((row) => {
    const keyInput = row.querySelector(".kv-key");
    const valInput = row.querySelector(".kv-val");
    const deleteBtn = row.querySelector(".btn-kv-delete");
    
    // Key and value listeners
    const updateValues = () => {
      const oldKey = deleteBtn.dataset.key;
      const newKey = keyInput.value.trim();
      const newVal = valInput.value;
      
      const obj = suite.cases[caseIdx][arrayType] || {};
      
      // Remove old key, write new key
      if (oldKey !== undefined && oldKey !== newKey) {
        delete obj[oldKey];
      }
      
      if (newKey !== "") {
        obj[newKey] = newVal;
      }
      
      deleteBtn.dataset.key = newKey;
      suite.cases[caseIdx][arrayType] = obj;
      updateLiveJsonPreview();
      analyzeVariables();
    };
    
    keyInput.addEventListener("change", updateValues);
    valInput.addEventListener("input", updateValues);
    
    // Delete row
    deleteBtn.addEventListener("click", () => {
      const key = deleteBtn.dataset.key;
      if (suite.cases[caseIdx][arrayType]) {
        delete suite.cases[caseIdx][arrayType][key];
      }
      
      if (arrayType === "headers") renderHeadersRows(caseIdx);
      else if (arrayType === "params") renderParamsRows(caseIdx);
      else if (arrayType === "extract") renderExtractRows(caseIdx);
      else renderBodyKvRows(caseIdx, arrayType);
      
      updateLiveJsonPreview();
      analyzeVariables();
    });
  });
}

// Attach Assertion row event handlers
function attachAssertionHandlers(container, caseIdx) {
  const rows = container.querySelectorAll(".assertion-row");
  
  rows.forEach((row) => {
    const select = row.querySelector(".assert-type-select");
    const pathInput = row.querySelector(".assert-path");
    const expectedInput = row.querySelector(".assert-expected");
    const deleteBtn = row.querySelector(".btn-assertion-delete");
    const aIdx = parseInt(deleteBtn.dataset.assert);
    
    select.addEventListener("change", (e) => {
      const type = e.target.value;
      const assertion = suite.cases[caseIdx].assertions[aIdx];
      assertion.type = type;
      
      // Clean path/expected depending on type defaults
      if (type === "status_code" || type === "response_time_under_ms" || type === "body_contains") {
        delete assertion.path;
        assertion.expected = assertion.expected || "";
      } else if (type === "json_path_exists") {
        assertion.path = assertion.path || "";
        delete assertion.expected;
      } else {
        assertion.path = assertion.path || "";
        assertion.expected = assertion.expected || "";
      }
      
      renderAssertionsRows(caseIdx);
      updateLiveJsonPreview();
      analyzeVariables();
    });
    
    if (pathInput) {
      pathInput.addEventListener("input", (e) => {
        suite.cases[caseIdx].assertions[aIdx].path = e.target.value;
        updateLiveJsonPreview();
        analyzeVariables();
      });
    }
    
    if (expectedInput) {
      expectedInput.addEventListener("input", (e) => {
        const val = e.target.value;
        // Try parsing numbers/bools in assertions expected, otherwise keep string
        let parsedVal = val;
        if (val === "true") parsedVal = true;
        else if (val === "false") parsedVal = false;
        else if (val !== "" && !isNaN(val)) parsedVal = Number(val);
        
        suite.cases[caseIdx].assertions[aIdx].expected = parsedVal;
        updateLiveJsonPreview();
        analyzeVariables();
      });
    }
    
    deleteBtn.addEventListener("click", () => {
      suite.cases[caseIdx].assertions.splice(aIdx, 1);
      renderAssertionsRows(caseIdx);
      updateLiveJsonPreview();
      analyzeVariables();
    });
  });
}

// Attach general card buttons and input listeners
function attachCardEvents() {
  // Method select listener
  document.querySelectorAll(".card-method-select").forEach(select => {
    select.addEventListener("change", (e) => {
      const index = parseInt(e.target.dataset.index);
      suite.cases[index].method = e.target.value;
      
      // Update styling
      e.target.className = `card-method-select ${e.target.value}`;
      updateLiveJsonPreview();
    });
  });
  
  // Endpoint text input listener
  document.querySelectorAll(".card-endpoint-input").forEach(input => {
    input.addEventListener("input", (e) => {
      const index = parseInt(e.target.dataset.index);
      suite.cases[index].endpoint = e.target.value;
      updateLiveJsonPreview();
      analyzeVariables();
    });
  });
  
  // ID input listener
  document.querySelectorAll(".card-id-input").forEach(input => {
    input.addEventListener("input", (e) => {
      const index = parseInt(e.target.dataset.index);
      suite.cases[index].id = e.target.value;
      updateLiveJsonPreview();
      analyzeVariables();
    });
  });
  
  // Case description name listener
  document.querySelectorAll(".card-name-input").forEach(input => {
    input.addEventListener("input", (e) => {
      const index = parseInt(e.target.dataset.index);
      suite.cases[index].name = e.target.value;
      updateLiveJsonPreview();
    });
  });
  
  // Card collapsible toggle
  document.querySelectorAll(".btn-toggle-collapse").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const index = parseInt(e.target.dataset.index);
      const card = e.target.closest(".case-card");
      const isCollapsed = card.classList.contains("collapsed");
      
      if (isCollapsed) {
        card.classList.remove("collapsed");
        e.target.textContent = "▲";
        cardCollapsed[index] = false;
      } else {
        card.classList.add("collapsed");
        e.target.textContent = "▼";
        cardCollapsed[index] = true;
      }
    });
  });
  
  // Tab switcher
  document.querySelectorAll(".card-tab-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const idx = parseInt(e.target.dataset.index);
      const tab = e.target.dataset.tab;
      
      // Update active tab state
      cardActiveTabs[idx] = tab;
      
      // Toggle CSS active state
      const card = e.target.closest(".case-card");
      card.querySelectorAll(".card-tab-btn").forEach(b => {
        b.classList.remove("tab-active", "text-primary", "font-bold");
        b.classList.add("text-base-content/60");
      });
      card.querySelectorAll(".card-tab-content").forEach(c => c.classList.add("hidden"));
      
      e.target.classList.remove("text-base-content/60");
      e.target.classList.add("tab-active", "text-primary", "font-bold");
      card.querySelector(`#tab-${tab}-${idx}`).classList.remove("hidden");
    });
  });
  
  // Add KV row button
  document.querySelectorAll(".btn-row-add").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const index = parseInt(e.target.dataset.index);
      const type = e.target.dataset.type;
      
      if (!suite.cases[index][type]) {
        suite.cases[index][type] = {};
      }
      
      // Add empty row
      suite.cases[index][type][""] = "";
      
      if (type === "headers") renderHeadersRows(index);
      else if (type === "params") renderParamsRows(index);
      else if (type === "extract") renderExtractRows(index);
      
      updateLiveJsonPreview();
      analyzeVariables();
    });
  });
  
  // Body Type Radio Change listener
  document.querySelectorAll(".body-type-label input").forEach(radio => {
    radio.addEventListener("change", (e) => {
      const index = parseInt(e.target.dataset.index);
      const bodyType = e.target.value;
      const c = suite.cases[index];
      c.bodyType = bodyType;
      
      // Clear alternative body contents to avoid multi-body format error
      delete c.json;
      delete c.body;
      delete c.form;
      
      if (bodyType === "json") {
        delete c.multipart;
        delete c.files;
        c.json = "{}";
      } else if (bodyType === "body") {
        delete c.multipart;
        delete c.files;
        c.body = "";
      } else if (bodyType === "form") {
        delete c.multipart;
        delete c.files;
        c.form = {};
      } else if (bodyType === "multipart") {
        delete c.files;
        c.multipart = c.multipart || {};
      } else if (bodyType === "files") {
        c.files = c.files || {};
        c.multipart = c.multipart || {};
      }
      
      renderBodyFields(index);
      updateLiveJsonPreview();
      analyzeVariables();
    });
  });
  
  // Add Assertion Row Button
  document.querySelectorAll(".btn-assertion-add").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const index = parseInt(e.target.dataset.index);
      if (!suite.cases[index].assertions) {
        suite.cases[index].assertions = [];
      }
      
      suite.cases[index].assertions.push({
        type: "status_code",
        expected: "200"
      });
      
      renderAssertionsRows(index);
      updateLiveJsonPreview();
      analyzeVariables();
    });
  });
  
  // Duplicate Card Action
  document.querySelectorAll(".btn-duplicate").forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();
      const index = parseInt(e.target.dataset.index);
      const original = suite.cases[index];
      
      // deep copy
      const copy = JSON.parse(JSON.stringify(original));
      copy.id = `${copy.id}_copy`;
      copy.name = `${copy.name} (Copy)`;
      
      suite.cases.splice(index + 1, 0, copy);
      renderCases();
      updateLiveJsonPreview();
    };
  });
  
  // Move Up
  document.querySelectorAll(".btn-move-up").forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();
      const index = parseInt(e.target.dataset.index);
      if (index > 0) {
        const temp = suite.cases[index];
        suite.cases[index] = suite.cases[index - 1];
        suite.cases[index - 1] = temp;
        
        // Swap tab active states
        const activeTemp = cardActiveTabs[index];
        cardActiveTabs[index] = cardActiveTabs[index - 1];
        cardActiveTabs[index - 1] = activeTemp;
        
        const collapseTemp = cardCollapsed[index];
        cardCollapsed[index] = cardCollapsed[index - 1];
        cardCollapsed[index - 1] = collapseTemp;
        
        renderCases();
        updateLiveJsonPreview();
      }
    };
  });
  
  // Move Down
  document.querySelectorAll(".btn-move-down").forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();
      const index = parseInt(e.target.dataset.index);
      if (index < suite.cases.length - 1) {
        const temp = suite.cases[index];
        suite.cases[index] = suite.cases[index + 1];
        suite.cases[index + 1] = temp;
        
        // Swap tab active states
        const activeTemp = cardActiveTabs[index];
        cardActiveTabs[index] = cardActiveTabs[index + 1];
        cardActiveTabs[index + 1] = activeTemp;
        
        const collapseTemp = cardCollapsed[index];
        cardCollapsed[index] = cardCollapsed[index + 1];
        cardCollapsed[index + 1] = collapseTemp;
        
        renderCases();
        updateLiveJsonPreview();
      }
    };
  });
  
  // Delete card action
  document.querySelectorAll(".btn-delete-card").forEach(btn => {
    btn.onclick = (e) => {
      e.stopPropagation();
      const index = parseInt(e.target.dataset.index);
      
      showConfirm(`Are you sure you want to delete Case #${index + 1} (${suite.cases[index].id || 'unnamed'})?`, "Delete", true).then(confirmed => {
        if (confirmed) {
          suite.cases.splice(index, 1);
          renderCases();
          updateLiveJsonPreview();
          showToast("Case deleted successfully!", "success");
        }
      });
    };
  });
}

// Add New Case
function addNewCase() {
  const newIdx = suite.cases.length;
  const newCase = {
    id: `case_${newIdx + 1}`,
    name: `API Case ${newIdx + 1}`,
    method: "GET",
    endpoint: "",
    headers: {},
    bodyType: "none",
    assertions: [
      { type: "status_code", expected: "200" }
    ],
    extract: {},
    completed: false
  };
  
  suite.cases.push(newCase);
  renderCases();
  updateLiveJsonPreview();
  
  // Scroll to new case card
  setTimeout(() => {
    const cards = document.querySelectorAll(".case-card");
    const lastCard = cards[cards.length - 1];
    if (lastCard) {
      lastCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, 100);
}

// Variable Dependency Analyzer Engine
let variablesDebounceTimer;
function analyzeVariables() {
  clearTimeout(variablesDebounceTimer);
  variablesDebounceTimer = setTimeout(() => {
    const producers = {}; // var_name -> [caseIdx, caseId]
    const consumers = {}; // var_name -> [[caseIdx, caseId], ...]
    
    // Scan all cases
    suite.cases.forEach((c, index) => {
    const caseId = c.id || `unnamed_#${index + 1}`;
    
    // 1. Compile Producers (Extractions)
    if (c.extract) {
      Object.keys(c.extract).forEach(varName => {
        if (varName.trim() !== "") {
          producers[varName] = [index, caseId];
        }
      });
    }
    
    // 2. Compile Consumers (Placeholders like {{var_name}})
    const textToScan = [];
    
    // Scan endpoint, name
    textToScan.push(c.endpoint || "");
    textToScan.push(c.name || "");
    
    // Scan headers values
    if (c.headers) {
      Object.values(c.headers).forEach(val => textToScan.push(String(val)));
    }
    
    // Scan params values
    if (c.params) {
      Object.values(c.params).forEach(val => textToScan.push(String(val)));
    }
    
    // Scan bodies based on type
    if (c.bodyType === "json" && c.json) {
      textToScan.push(typeof c.json === "string" ? c.json : JSON.stringify(c.json));
    } else if (c.bodyType === "body" && c.body) {
      textToScan.push(c.body);
    } else if (c.bodyType === "form" && c.form) {
      Object.values(c.form).forEach(val => textToScan.push(String(val)));
    } else if (c.bodyType === "multipart" && c.multipart) {
      Object.values(c.multipart).forEach(val => textToScan.push(String(val)));
    } else if (c.bodyType === "files" && c.files) {
      Object.values(c.files).forEach(val => textToScan.push(typeof val === "string" ? val : JSON.stringify(val)));
    }
    
    // Scan assertions (paths and expected)
    if (c.assertions) {
      c.assertions.forEach(assertion => {
        if (assertion.path) textToScan.push(String(assertion.path));
        if (assertion.expected) textToScan.push(String(assertion.expected));
      });
    }
    
    // Regex scanner for {{var}}
    const regex = /\{\{([^}]+)\}\}/g;
    textToScan.forEach(text => {
      let match;
      while ((match = regex.exec(text)) !== null) {
        const varName = match[1].trim();
        if (!consumers[varName]) {
          consumers[varName] = [];
        }
        // Avoid duplicate consumer logs for the same case
        if (!consumers[varName].some(item => item[0] === index)) {
          consumers[varName].push([index, caseId]);
        }
      }
    });
  });
  
  // Merge all unique variables names
  const allVars = new Set([...Object.keys(producers), ...Object.keys(consumers)]);
  const variablesListContainer = document.getElementById("variables-list");
  variablesListContainer.innerHTML = "";
  
  if (allVars.size === 0) {
    variablesListContainer.innerHTML = `<p style="color: var(--text-muted); font-size: 0.8125rem; text-align: center; margin-top: 1rem;">No dynamic variables detected (e.g. extracts or placeholders like <code>{{var}}</code>).</p>`;
    return;
  }
  
  allVars.forEach(varName => {
    const producer = producers[varName];
    const consumerList = consumers[varName] || [];
    
    const isDefined = !!producer;
    const isConsumed = consumerList.length > 0;
    
    // Validation: Is variable consumed but never defined? Or defined after it's consumed?
    let hasError = false;
    let errorMsg = "";
    
    if (isConsumed && !isDefined) {
      hasError = true;
      errorMsg = "Variable is used but never extracted/defined in this suite.";
    } 
    else if (isConsumed && isDefined) {
      const prodIdx = producer[0];
      const earliestConsIdx = Math.min(...consumerList.map(c => c[0]));
      if (prodIdx > earliestConsIdx) {
        hasError = true;
        errorMsg = `Variable is used in card #${earliestConsIdx + 1} but extracted later in card #${prodIdx + 1}.`;
      }
    }
    
    const varCard = document.createElement("div");
    if (hasError) {
      varCard.className = "card bg-error/5 border border-error/20 p-2.5 flex flex-col gap-1 text-[11px] text-error";
    } else {
      varCard.className = "card bg-base-200 border border-base-300 p-2.5 flex flex-col gap-1 text-[11px]";
    }
    
    let flowHtml = "";
    
    if (isDefined) {
      flowHtml += `
        <div class="flex gap-1 items-start">
          <span class="text-base-content/50 font-medium w-12 flex-shrink-0">Defined:</span>
          <span class="flex flex-wrap gap-1">
            <span class="badge badge-outline badge-xs font-mono py-1.5" title="Card #${producer[0] + 1}">#${producer[0] + 1} ${escapeHtml(producer[1])}</span>
          </span>
        </div>
      `;
    }
    
    if (isConsumed) {
      flowHtml += `
        <div class="flex gap-1 items-start mt-0.5">
          <span class="text-base-content/50 font-medium w-12 flex-shrink-0">Used in:</span>
          <span class="flex flex-wrap gap-1">
            ${consumerList.map(c => `<span class="badge badge-outline badge-xs font-mono py-1.5" title="Card #${c[0] + 1}">#${c[0] + 1} ${escapeHtml(c[1])}</span>`).join('')}
          </span>
        </div>
      `;
    }
    
    varCard.innerHTML = `
      <div class="flex justify-between items-center font-semibold mb-0.5">
        <span class="font-mono text-primary select-all">{{${escapeHtml(varName)}}}</span>
        <span class="badge ${isDefined ? 'badge-success' : 'badge-error'} badge-xs font-bold uppercase tracking-wider text-[9px] py-1.5 px-2 font-heading">
          ${isDefined ? 'Defined' : 'Missing'}
        </span>
      </div>
      <div class="flex flex-col gap-0.5 text-base-content/70">
        ${flowHtml}
        ${hasError ? `<div class="text-[10px] font-bold text-error mt-1">⚠️ ${errorMsg}</div>` : ''}
      </div>
    `;
    
    variablesListContainer.appendChild(varCard);
  });
  }, 100);
}

// Generate the output JSON compliant with the testing framework
function compileSuiteJson() {
  const output = {
    name: suite.name,
    environment: suite.environment,
    base_url: suite.base_url,
    timeout_seconds: suite.timeout_seconds,
    verify_ssl: suite.verify_ssl,
    defaults: {
      repeat: suite.defaults.repeat,
      min_success_rate: suite.defaults.min_success_rate
    },
    cases: []
  };
  
  // Optional max_p95_ms defaults check
  if (suite.defaults.max_p95_ms !== undefined && suite.defaults.max_p95_ms !== "") {
    output.defaults.max_p95_ms = Number(suite.defaults.max_p95_ms);
  }
  
  suite.cases.forEach(c => {
    const caseObj = {
      id: c.id,
      name: c.name,
      method: c.method,
      endpoint: c.endpoint
    };
    
    // Headers (remove empty string keys)
    if (c.headers) {
      const headersFiltered = {};
      Object.keys(c.headers).forEach(k => {
        if (k.trim() !== "") headersFiltered[k] = c.headers[k];
      });
      if (Object.keys(headersFiltered).length > 0) {
        caseObj.headers = headersFiltered;
      }
    }
    
    // Params (remove empty string keys)
    if (c.params) {
      const paramsFiltered = {};
      Object.keys(c.params).forEach(k => {
        if (k.trim() !== "") paramsFiltered[k] = c.params[k];
      });
      if (Object.keys(paramsFiltered).length > 0) {
        caseObj.params = paramsFiltered;
      }
    }
    
    // Body types
    if (c.bodyType === "json" && c.json !== undefined && c.json !== "") {
      try {
        caseObj.json = typeof c.json === "string" ? JSON.parse(c.json) : c.json;
      } catch (err) {
        // Fallback to raw string if JSON parsing fails to prevent UI crash
        caseObj.json = c.json;
      }
    } 
    else if (c.bodyType === "body" && c.body !== undefined && c.body !== "") {
      caseObj.body = c.body;
    } 
    else if (c.bodyType === "form" && c.form) {
      const formFiltered = {};
      Object.keys(c.form).forEach(k => {
        if (k.trim() !== "") formFiltered[k] = c.form[k];
      });
      if (Object.keys(formFiltered).length > 0) caseObj.form = formFiltered;
    } 
    else if (c.bodyType === "multipart" && c.multipart) {
      const multipartFiltered = {};
      Object.keys(c.multipart).forEach(k => {
        if (k.trim() !== "") multipartFiltered[k] = c.multipart[k];
      });
      if (Object.keys(multipartFiltered).length > 0) caseObj.multipart = multipartFiltered;
    } 
    else if (c.bodyType === "files") {
      if (c.files) {
        const filesFiltered = {};
        Object.keys(c.files).forEach(k => {
          if (k.trim() !== "") filesFiltered[k] = c.files[k];
        });
        if (Object.keys(filesFiltered).length > 0) caseObj.files = filesFiltered;
      }
      if (c.multipart) {
        const multFiltered = {};
        Object.keys(c.multipart).forEach(k => {
          if (k.trim() !== "") multFiltered[k] = c.multipart[k];
        });
        if (Object.keys(multFiltered).length > 0) caseObj.multipart = multFiltered;
      }
    }
    
    // Extract
    if (c.extract) {
      const extractFiltered = {};
      Object.keys(c.extract).forEach(k => {
        if (k.trim() !== "") extractFiltered[k] = c.extract[k];
      });
      if (Object.keys(extractFiltered).length > 0) {
        caseObj.extract = extractFiltered;
      }
    }
    
    // Assertions
    if (c.assertions && c.assertions.length > 0) {
      caseObj.assertions = c.assertions.map(a => {
        const aObj = { type: a.type };
        if (a.path !== undefined) aObj.path = a.path;
        if (a.expected !== undefined && a.expected !== "") {
          aObj.expected = a.expected;
        }
        return aObj;
      });
    }
    
    output.cases.push(caseObj);
  });
  
  return output;
}

// Live JSON compile and update view
let previewDebounceTimer;
function updateLiveJsonPreview() {
  clearTimeout(previewDebounceTimer);
  previewDebounceTimer = setTimeout(() => {
    const jsonCodeEl = document.getElementById("live-json-preview");
    const compiled = compileSuiteJson();
    if (jsonCodeEl) {
      jsonCodeEl.textContent = JSON.stringify(compiled, null, 2);
    }
    // Auto-save to localStorage on every change
    saveSuiteToStorage(compiled);
  }, 100);
}

// Top Action Controls: Settings Modal
function openSettingsModal() {
  document.getElementById("modal-suite-name").value = suite.name;
  document.getElementById("modal-suite-env").value = suite.environment;
  document.getElementById("modal-suite-base").value = suite.base_url;
  document.getElementById("modal-suite-timeout").value = suite.timeout_seconds;
  document.getElementById("modal-suite-ssl").checked = suite.verify_ssl;
  document.getElementById("modal-suite-repeat").value = suite.defaults.repeat;
  document.getElementById("modal-suite-success").value = suite.defaults.min_success_rate;
  document.getElementById("modal-suite-p95").value = suite.defaults.max_p95_ms || "";
  
  document.getElementById("settings-modal").classList.add("active");
}

function closeSettingsModal() {
  document.getElementById("settings-modal").classList.remove("active");
}

function openCurlModal() {
  document.getElementById("modal-curl-textarea").value = "";
  document.getElementById("curl-modal").classList.add("active");
}

function closeCurlModal() {
  document.getElementById("curl-modal").classList.remove("active");
}

let confirmModalResolve = null;

function showConfirm(message, confirmText = "Confirm", isDangerous = true) {
  return new Promise((resolve) => {
    confirmModalResolve = resolve;
    
    document.getElementById("confirm-modal-message").textContent = message;
    
    const okBtn = document.getElementById("btn-confirm-ok");
    okBtn.textContent = confirmText;
    
    if (isDangerous) {
      okBtn.className = "btn btn-error btn-sm";
    } else {
      okBtn.className = "btn btn-primary btn-sm";
    }
    
    document.getElementById("confirm-modal").classList.add("active");
  });
}

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  
  const toast = document.createElement("div");
  let alertClass = "alert-info";
  let icon = "ℹ️";
  if (type === "success") {
    alertClass = "alert-success";
    icon = "✅";
  } else if (type === "error") {
    alertClass = "alert-error";
    icon = "❌";
  } else if (type === "warning") {
    alertClass = "alert-warning";
    icon = "⚠️";
  }
  
  toast.className = `alert ${alertClass} shadow-lg border border-base-content/10 font-heading text-xs font-semibold py-3 px-4 rounded-xl flex items-center gap-2 modal-box-glass translate-y-2 opacity-0 transition-all duration-300`;
  toast.innerHTML = `
    <span>${icon}</span>
    <span>${message}</span>
  `;
  container.appendChild(toast);
  
  requestAnimationFrame(() => {
    toast.classList.remove("translate-y-2", "opacity-0");
  });
  
  setTimeout(() => {
    toast.classList.add("translate-y-2", "opacity-0");
    setTimeout(() => {
      toast.remove();
    }, 300);
  }, 3500);
}

function handleCurlImport(e) {
  e.preventDefault();
  const curlCmd = document.getElementById("modal-curl-textarea").value.trim();
  if (!curlCmd) return;
  
  try {
    const parsed = parseCurl(curlCmd);
    
    // Generate a unique ID based on endpoint and method
    let shortId = "case";
    if (parsed.endpoint) {
      let segments = parsed.endpoint.split('?')[0].split('/');
      let last = segments.filter(s => s !== "").pop();
      if (last) {
        shortId = last.toLowerCase().replace(/[^a-z0-9_-]/g, "");
      }
    }
    const uniqueId = shortId + "_" + Math.random().toString(36).substring(2, 7);
    
    // Build new case object
    const newCase = {
      id: uniqueId,
      name: `Imported ${parsed.method} case for ${parsed.endpoint.split('?')[0]}`,
      method: parsed.method,
      endpoint: parsed.endpoint,
      headers: parsed.headers,
      bodyType: parsed.bodyType,
      assertions: [
        { type: "status_code", expected: "200" }
      ],
      completed: false
    };
    
    if (parsed.json) newCase.json = parsed.json;
    if (parsed.body) newCase.body = parsed.body;
    if (parsed.form) newCase.form = parsed.form;
    if (parsed.multipart) newCase.multipart = parsed.multipart;
    if (parsed.files) newCase.files = parsed.files;
    if (parsed.params) newCase.params = parsed.params;
    
    suite.cases.push(newCase);
    
    // Re-render
    renderCases();
    updateLiveJsonPreview();
    analyzeVariables();
    
    // Close modal
    closeCurlModal();
    
    showToast("cURL command imported successfully!", "success");
    
    // Scroll to the end to show the imported card
    setTimeout(() => {
      const cards = document.querySelectorAll(".case-card");
      if (cards.length > 0) {
        cards[cards.length - 1].scrollIntoView({ behavior: "smooth" });
      }
    }, 100);
    
  } catch (err) {
    showToast("Failed to parse cURL command: " + err.message, "error");
  }
}

function parseCurl(curlCommand) {
  // Clean line continuations
  let cleaned = curlCommand.replace(/\\\s*\n/g, ' ');
  
  // Split arguments considering single and double quotes
  let args = [];
  let current = '';
  let inDoubleQuote = false;
  let inSingleQuote = false;
  
  for (let i = 0; i < cleaned.length; i++) {
    let char = cleaned[i];
    if (char === '"' && !inSingleQuote) {
      inDoubleQuote = !inDoubleQuote;
    } else if (char === "'" && !inDoubleQuote) {
      inSingleQuote = !inSingleQuote;
    } else if (char === ' ' && !inDoubleQuote && !inSingleQuote) {
      if (current.trim() !== '') {
        args.push(current.trim());
        current = '';
      }
    } else {
      current += char;
    }
  }
  if (current.trim() !== '') {
    args.push(current.trim());
  }

  // Parse arguments
  let method = 'GET';
  let url = '';
  let headers = {};
  let data = null;
  let multipart = {};
  let form = {};
  let isMultipart = false;
  let isUrlEncoded = false;

  for (let i = 0; i < args.length; i++) {
    let arg = args[i];
    
    // Ignore 'curl' at start
    if (i === 0 && arg === 'curl') continue;

    if (arg === '-X' || arg === '--request') {
      method = args[++i] || 'GET';
      method = method.toUpperCase();
    } else if (arg === '-H' || arg === '--header') {
      let headerStr = args[++i] || '';
      let colonIdx = headerStr.indexOf(':');
      if (colonIdx !== -1) {
        let key = headerStr.slice(0, colonIdx).trim();
        let val = headerStr.slice(colonIdx + 1).trim();
        headers[key] = val;
      }
    } else if (arg === '-d' || arg === '--data' || arg === '--data-raw' || arg === '--data-binary') {
      data = args[++i] || '';
      if (data.startsWith("'") && data.endsWith("'")) data = data.slice(1, -1);
      if (data.startsWith('"') && data.endsWith('"')) data = data.slice(1, -1);
    } else if (arg === '-F' || arg === '--form') {
      isMultipart = true;
      let formStr = args[++i] || '';
      let eqIdx = formStr.indexOf('=');
      if (eqIdx !== -1) {
        let key = formStr.slice(0, eqIdx).trim();
        let val = formStr.slice(eqIdx + 1).trim();
        multipart[key] = val;
      }
    } else if (arg === '--data-urlencode') {
      isUrlEncoded = true;
      let formStr = args[++i] || '';
      let eqIdx = formStr.indexOf('=');
      if (eqIdx !== -1) {
        let key = formStr.slice(0, eqIdx).trim();
        let val = formStr.slice(eqIdx + 1).trim();
        form[key] = val;
      }
    } else if (arg.startsWith('http://') || arg.startsWith('https://')) {
      url = arg;
    } else if (arg.startsWith('"http') && arg.endsWith('"')) {
      url = arg.slice(1, -1);
    } else if (arg.startsWith("'http") && arg.endsWith("'")) {
      url = arg.slice(1, -1);
    } else if (!url && (arg.includes('/') || arg.includes('.'))) {
      url = arg;
    }
  }

  if (data && method === 'GET') {
    method = 'POST';
  }

  let endpoint = url;
  let params = {};
  if (url.startsWith('http://') || url.startsWith('https://')) {
    try {
      let urlObj = new URL(url);
      endpoint = urlObj.pathname;
      urlObj.searchParams.forEach((value, key) => {
        params[key] = value;
      });
    } catch (e) {
      // Fallback
    }
  } else {
    let qIdx = url.indexOf('?');
    if (qIdx !== -1) {
      endpoint = url.slice(0, qIdx);
      let search = url.slice(qIdx + 1);
      let searchParams = new URLSearchParams(search);
      searchParams.forEach((value, key) => {
        params[key] = value;
      });
    }
  }

  let bodyType = 'none';
  let jsonPayload = null;
  let bodyPayload = '';
  let filesPayload = {};

  if (isMultipart) {
    bodyType = 'multipart';
    let hasFiles = false;
    let actualFiles = {};
    let actualMultipart = {};
    Object.keys(multipart).forEach(k => {
      let val = multipart[k];
      if (val.startsWith('@')) {
        hasFiles = true;
        actualFiles[k] = val.slice(1);
      } else {
        actualMultipart[k] = val;
      }
    });
    if (hasFiles) {
      bodyType = 'files';
      filesPayload = actualFiles;
      multipart = actualMultipart;
    }
  } else if (isUrlEncoded) {
    bodyType = 'form';
  } else if (data) {
    bodyType = 'json';
    try {
      jsonPayload = JSON.parse(data);
      bodyType = 'json';
    } catch (e) {
      bodyType = 'body';
      bodyPayload = data;
    }
  }

  return {
    method,
    endpoint,
    headers,
    params: Object.keys(params).length > 0 ? params : undefined,
    bodyType,
    json: jsonPayload ? JSON.stringify(jsonPayload, null, 2) : undefined,
    body: bodyPayload || undefined,
    form: isUrlEncoded ? form : undefined,
    multipart: bodyType === 'multipart' || bodyType === 'files' ? multipart : undefined,
    files: bodyType === 'files' ? filesPayload : undefined
  };
}

function saveSettings(e) {
  e.preventDefault();
  
  suite.name = document.getElementById("modal-suite-name").value;
  suite.environment = document.getElementById("modal-suite-env").value;
  suite.base_url = document.getElementById("modal-suite-base").value;
  suite.timeout_seconds = Number(document.getElementById("modal-suite-timeout").value);
  suite.verify_ssl = document.getElementById("modal-suite-ssl").checked;
  suite.defaults.repeat = Number(document.getElementById("modal-suite-repeat").value);
  suite.defaults.min_success_rate = Number(document.getElementById("modal-suite-success").value);
  
  const p95Val = document.getElementById("modal-suite-p95").value;
  if (p95Val !== "") {
    suite.defaults.max_p95_ms = Number(p95Val);
  } else {
    delete suite.defaults.max_p95_ms;
  }
  
  renderSuiteMeta();
  updateLiveJsonPreview();
  analyzeVariables();
  closeSettingsModal();
  showToast("Suite global settings updated successfully!", "success");
}

// Code Drawer toggle
function toggleJsonDrawer() {
  document.getElementById("json-drawer").classList.toggle("active");
}

function closeJsonDrawer() {
  document.getElementById("json-drawer").classList.remove("active");
}

// Copy JSON
function copyJsonToClipboard() {
  const jsonStr = JSON.stringify(compileSuiteJson(), null, 2);
  navigator.clipboard.writeText(jsonStr).then(() => {
    const btn = document.getElementById("btn-copy-json");
    const originalText = btn.innerHTML;
    btn.innerHTML = "✓ Copied!";
    btn.style.backgroundColor = "var(--accent-success)";
    
    showToast("Suite JSON copied to clipboard!", "success");
    
    setTimeout(() => {
      btn.innerHTML = originalText;
      btn.style.backgroundColor = "";
    }, 2000);
  }).catch(err => {
    showToast("Failed to copy JSON to clipboard: " + err, "error");
  });
}

// Download JSON
function downloadSuiteJson() {
  const filename = `${suite.name.toLowerCase().replace(/[^a-z0-9]+/g, '_')}_suite.json`;
  const jsonStr = JSON.stringify(compileSuiteJson(), null, 2);
  
  const blob = new Blob([jsonStr], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Handle JSON File Import
function handleFileImport(e) {
  const file = e.target.files[0];
  if (!file) return;
  
  const reader = new FileReader();
  reader.onload = function(evt) {
    try {
      const imported = JSON.parse(evt.target.result);
      
      // Basic validations
      if (!imported.name || !Array.isArray(imported.cases)) {
        throw new Error("Invalid suite format. Missing 'name' or 'cases' array.");
      }
      
      // Format parser mapping into builder state
      suite.name = imported.name;
      suite.environment = imported.environment || "local";
      suite.base_url = imported.base_url || "";
      suite.timeout_seconds = imported.timeout_seconds || 10;
      suite.verify_ssl = imported.verify_ssl !== undefined ? imported.verify_ssl : true;
      suite.defaults = imported.defaults || { repeat: 1, min_success_rate: 100 };
      
      suite.cases = imported.cases.map(c => {
        const parsedCase = {
          id: c.id || `case_${Math.random().toString(36).substr(2, 5)}`,
          name: c.name || c.id || "API Case",
          method: c.method || "GET",
          endpoint: c.endpoint || "",
          headers: c.headers || {},
          params: c.params || {},
          extract: c.extract || {},
          assertions: c.assertions || [],
          completed: c.completed || false
        };
        
        // Map body type based on what body options exist in input case
        if (c.json) {
          parsedCase.bodyType = "json";
          parsedCase.json = typeof c.json === "string" ? c.json : JSON.stringify(c.json, null, 2);
        } else if (c.body) {
          parsedCase.bodyType = "body";
          parsedCase.body = c.body;
        } else if (c.form) {
          parsedCase.bodyType = "form";
          parsedCase.form = c.form;
        } else if (c.files) {
          parsedCase.bodyType = "files";
          parsedCase.files = c.files;
          if (c.multipart) parsedCase.multipart = c.multipart;
        } else if (c.multipart) {
          parsedCase.bodyType = "multipart";
          parsedCase.multipart = c.multipart;
        } else {
          parsedCase.bodyType = "none";
        }
        
        return parsedCase;
      });
      
      cardCollapsed = {};
      cardActiveTabs = {};
      
      renderSuiteMeta();
      renderCases();
      updateLiveJsonPreview();
      
      showToast("Suite JSON imported successfully!", "success");
    } catch(err) {
      showToast("Failed to parse JSON: " + err.message, "error");
    }
  };
  
  reader.readAsText(file);
  // Clear input
  e.target.value = "";
}

// Utility HTML escape
function escapeHtml(str) {
  if (typeof str !== "string") return str;
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Theme management
function initTheme() {
  setTheme("corporate");
}

function setTheme(theme) {
  document.documentElement.setAttribute("data-theme", "corporate");
  localStorage.setItem("theme", "corporate");
}

// ─── Variable Autocomplete ────────────────────────────────────────────────────

let _varAcDropdown = null;
let _varAcTarget   = null;

/** Return all variable names currently produced by any case's extract fields. */
function getExtractedVarNames() {
  const vars = new Set();
  suite.cases.forEach(c => {
    if (c.extract) {
      Object.keys(c.extract).forEach(k => { if (k.trim()) vars.add(k.trim()); });
    }
  });
  return Array.from(vars).sort();
}

function initVarAutocomplete() {
  // Create the singleton dropdown element
  _varAcDropdown = document.createElement('div');
  _varAcDropdown.id = 'var-autocomplete';
  _varAcDropdown.style.display = 'none';
  document.body.appendChild(_varAcDropdown);

  // Listen for typing in any text input / textarea on the page
  document.addEventListener('input', _varAcOnInput, true);
  // Keyboard nav inside the dropdown
  document.addEventListener('keydown', _varAcOnKeydown, true);
  // Dismiss when clicking elsewhere
  document.addEventListener('mousedown', _varAcOnBlur, true);
}

function _varAcOnInput(e) {
  const el = e.target;
  if (!el.matches('input[type="text"], textarea')) { _varAcHide(); return; }

  const cursor = el.selectionStart;
  const before = el.value.slice(0, cursor);

  // Match an unclosed {{ optionally followed by a partial name
  const m = before.match(/\{\{([^}]*)$/);
  if (!m) { _varAcHide(); return; }

  const all = getExtractedVarNames();
  // If no variables are defined at all, don't show an empty dropdown
  if (all.length === 0) { _varAcHide(); return; }

  const query = m[1].toLowerCase();
  const hits  = all.filter(v => v.toLowerCase().includes(query));

  _varAcTarget = el;
  _varAcShow(el, hits, query);
}

function _varAcShow(el, hits, query) {
  const dd = _varAcDropdown;

  // Build inner HTML
  let html = `<div class="var-ac-header">Variables &mdash; type to filter</div>`;

  if (hits.length === 0) {
    html += `<div class="var-ac-empty">No matching variables found</div>`;
  } else {
    hits.forEach((v, i) => {
      // Bold-highlight the matched portion
      const lo = v.toLowerCase();
      const idx = query ? lo.indexOf(query) : -1;
      let label = v;
      if (idx !== -1 && query) {
        label = v.slice(0, idx)
          + `<strong>${v.slice(idx, idx + query.length)}</strong>`
          + v.slice(idx + query.length);
      }
      html += `
        <div class="var-ac-item${i === 0 ? ' active' : ''}" data-var="${escapeHtml(v)}">
          <span class="var-ac-pill">{{ }}</span>
          <span class="var-ac-name">${label}</span>
          <span class="var-ac-hint">↵</span>
        </div>`;
    });
  }

  dd.innerHTML = html;

  // Attach mousedown listeners (mousedown fires before blur)
  dd.querySelectorAll('.var-ac-item').forEach(item => {
    item.addEventListener('mousedown', e => {
      e.preventDefault();
      _varAcInsert(_varAcTarget, item.dataset.var);
    });
  });

  // Position below the field using viewport coords (position:fixed)
  const rect = el.getBoundingClientRect();
  const dropH = Math.min(220, hits.length * 36 + 28); // estimated height
  const spaceBelow = window.innerHeight - rect.bottom;
  const spaceAbove = rect.top;

  dd.style.display = 'block';
  dd.style.width   = Math.max(rect.width, 220) + 'px';
  dd.style.left    = rect.left + 'px';

  if (spaceBelow >= dropH || spaceBelow >= spaceAbove) {
    // Show below
    dd.style.top    = (rect.bottom + 4) + 'px';
    dd.style.bottom = 'auto';
  } else {
    // Flip above
    dd.style.top    = 'auto';
    dd.style.bottom = (window.innerHeight - rect.top + 4) + 'px';
  }

  // Reset animation by forcing reflow
  dd.style.animation = 'none';
  void dd.offsetWidth;
  dd.style.animation = '';
}

function _varAcHide() {
  if (_varAcDropdown) _varAcDropdown.style.display = 'none';
  _varAcTarget = null;
}

function _varAcOnBlur(e) {
  if (_varAcDropdown && _varAcDropdown.contains(e.target)) return;
  _varAcHide();
}

function _varAcOnKeydown(e) {
  if (!_varAcDropdown || _varAcDropdown.style.display === 'none') return;

  const items  = Array.from(_varAcDropdown.querySelectorAll('.var-ac-item'));
  if (!items.length) { if (e.key === 'Escape') _varAcHide(); return; }

  const active = _varAcDropdown.querySelector('.var-ac-item.active');
  const idx    = items.indexOf(active);

  if (e.key === 'ArrowDown') {
    e.preventDefault();
    active?.classList.remove('active');
    items[(idx + 1) % items.length].classList.add('active');
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    active?.classList.remove('active');
    items[(idx - 1 + items.length) % items.length].classList.add('active');
  } else if (e.key === 'Enter' || e.key === 'Tab') {
    if (active) {
      e.preventDefault();
      _varAcInsert(_varAcTarget, active.dataset.var);
    }
  } else if (e.key === 'Escape') {
    e.preventDefault();
    _varAcHide();
  }
}

function _varAcInsert(el, varName) {
  if (!el) return;
  const val    = el.value;
  const cursor = el.selectionStart;
  const before = val.slice(0, cursor);

  // Find start of the opening {{
  const m = before.match(/\{\{([^}]*)$/);
  if (!m) return;

  const insertStart = cursor - m[0].length;
  const replacement = `{{${varName}}}`;
  el.value = val.slice(0, insertStart) + replacement + val.slice(cursor);

  const newPos = insertStart + replacement.length;
  el.setSelectionRange(newPos, newPos);

  // Fire input so existing state listeners update the suite model
  el.dispatchEvent(new Event('input', { bubbles: true }));

  _varAcHide();
  el.focus();
}
