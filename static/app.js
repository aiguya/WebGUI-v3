const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".panel");
const toast = document.querySelector("#toast");
const libraryPrefsKey = "webgork.libraryPrefs.v1";

function loadLibraryPrefs() {
  try {
    return JSON.parse(localStorage.getItem(libraryPrefsKey) || "{}") || {};
  } catch {
    return {};
  }
}

function saveLibraryPrefs() {
  try {
    localStorage.setItem(libraryPrefsKey, JSON.stringify({
      view: libraryView,
      thumbSize: libraryThumbSize,
      pageSize: libraryPageSize,
    }));
  } catch {
    // Ignore storage failures; the library still works with in-memory defaults.
  }
}

function validLibraryView(value) {
  return ["grid", "timeline", "chain"].includes(value) ? value : "grid";
}

function validLibraryThumbSize(value) {
  return ["small", "medium", "large"].includes(value) ? value : "medium";
}

const libraryPrefs = loadLibraryPrefs();
const selectedItems = new Set();
let dragSelecting = false;
let dragSelectMode = true;
let libraryBoxSelect = null;
let pickerTargetForm = null;
let pickerItems = [];
let pickerMediaType = "image";
let pickerFavoriteFilter = "all";
let pickerOperationFilter = "all";
let pickerSearch = "";
let pickerSort = "newest";
let pickerDateFilter = "all";
let pickerDateValue = "";
let pickerThumbSize = "medium";
let libraryFilter = "all";
let libraryOperationFilter = "all";
let librarySearch = "";
let librarySort = "newest";
let libraryDateFilter = "all";
let libraryDateValue = "";
let libraryView = validLibraryView(libraryPrefs.view);
let libraryThumbSize = validLibraryThumbSize(libraryPrefs.thumbSize);
let libraryCachedItems = [];
let libraryPageSize = pageSizeFromValue(libraryPrefs.pageSize, 80);
let libraryVisibleCount = libraryPageSize;
let promptItems = [];
let promptSelectedId = "";
let promptSearch = "";
let promptTaskFilter = "all";
let promptFavoriteFilter = "all";
let promptAutoValue = "";
let templateItems = [];
let templateSelectedId = "";
let templateSearch = "";
let templateFavoriteOnly = false;
let templateBlocks = [];
let templateBlockSearch = "";
let templateBlockFavoriteOnly = false;
let templateShotFocusTimer = null;
let templateShotAutoScrollFrame = null;
let templateShotAutoScrollVelocity = 0;
let templateShotAutoScrollTarget = null;
let templatePickerSlotKey = "";
const templateRunState = {
  variables: {},
  slots: {},
  mode: "auto",
};
let pickerVisibleCount = 80;
let pickerPageSize = 80;
const multiImageSources = new WeakMap();
const multiVideoSources = new WeakMap();
const jobQueue = [];
let activeJobs = 0;
const maxActiveJobs = 30;
const maxQueueCopies = 20;
const repeatableQueueEndpoints = new Set([
  "/api/t2i",
  "/api/i2i",
  "/api/i2v",
  "/api/v2v-extend",
  "/api/v2v-frame-extend",
]);
const batchMaxImages = 500;
let pendingErrorLog = null;
let lastQuotaRefresh = 0;
const promptPlannerForms = new Set([
  "/api/t2i",
  "/api/i2i",
  "/api/i2v",
  "/api/v2v-extend",
  "/api/v2v-frame-extend",
  "/api/manga-batch",
]);
const promptPlannerCache = new WeakMap();
const promptTaskLabels = {
  image: "이미지 생성",
  edit: "이미지 편집",
  video: "이미지→영상",
  extend: "공식 연장",
  frame: "프레임 연장",
  manga: "망가 실사화·역식",
  general: "범용",
};
const promptTaskTarget = {
  image: "t2i",
  edit: "i2i",
  video: "i2v",
  extend: "v2v",
  frame: "v2vFrame",
  manga: "mangaBatch",
  general: "t2i",
};

const iconSvg = paths => `
  <svg class="tab-svg" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
    ${paths}
  </svg>`;

const tabIcons = {
  t2i: {
    label: "이미지 생성",
    html: iconSvg(`<rect x="3" y="4" width="18" height="16" rx="1.5"></rect><circle cx="8.5" cy="9" r="1.6"></circle><path d="m4 17 5.2-5.2 3.8 3.8 2.4-2.4L20 17"></path>`),
  },
  i2i: {
    label: "이미지 편집",
    html: iconSvg(`<rect x="3" y="4" width="18" height="16" rx="1.5"></rect><circle cx="8.5" cy="9" r="1.6"></circle><path d="m4 17 5.1-5.1 2.8 2.8"></path><path d="m14.2 18.4 4.9-4.9 1.4 1.4-4.9 4.9-2 .6.6-2Z"></path>`),
  },
  i2v: {
    label: "이미지 영상",
    html: iconSvg(`<rect x="3" y="5" width="13.5" height="14" rx="1.5"></rect><circle cx="7.4" cy="9" r="1.3"></circle><path d="m4.2 16 4.1-4.1 3.1 3.1 1.8-1.8 2.4 2.8"></path><rect x="17.5" y="9" width="4" height="6" rx="1"></rect><path d="m19 10.8 1.7 1.2-1.7 1.2Z"></path>`),
  },
  v2v: {
    label: "공식 연장",
    html: iconSvg(`<path d="M8 3H4v4"></path><path d="M4 4.5 10 10.5"></path><path d="M16 3h4v4"></path><path d="m20 4.5-6 6"></path><path d="M8 21H4v-4"></path><path d="m4 19.5 6-6"></path><path d="M16 21h4v-4"></path><path d="m20 19.5-6-6"></path>`),
  },
  v2vFrame: {
    label: "프레임 연장",
    html: iconSvg(`<path d="M8 3H4v4"></path><path d="M4 4.5 10 10.5"></path><path d="M16 21h4v-4"></path><path d="m20 19.5-6-6"></path><rect x="12.5" y="4.5" width="7" height="7" rx="1" stroke-dasharray="2 2"></rect><rect x="4.5" y="12.5" width="7" height="7" rx="1"></rect>`),
  },
  videoEdit: {
    label: "영상 편집",
    html: iconSvg(`<path d="M4 6h16"></path><path d="M4 18h16"></path><rect x="5" y="8" width="14" height="8" rx="1.5"></rect><path d="M8 8v8M16 8v8"></path><path d="m10.5 11 3 1.5-3 1.5Z"></path>`),
  },
  mangaBatch: {
    label: "망가 실사화·역식",
    html: iconSvg(`<rect x="4" y="3" width="12" height="18" rx="1.5"></rect><path d="M16 7h4v12a2 2 0 0 1-2 2h-2"></path><path d="M7 8h6"></path><path d="M7 12h6"></path><path d="M7 16h3"></path><path d="m14.5 14 2 2 3-4"></path>`),
  },
  reverse: {
    label: "그림 프롬프트",
    html: iconSvg(`<path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4Z"></path><path d="M8 8h8"></path><path d="M8 12h5"></path>`),
  },
  prompts: {
    label: "프롬프트",
    html: iconSvg(`<path d="M5 4h14v16H5z"></path><path d="M8 8h8"></path><path d="M8 12h8"></path><path d="M8 16h5"></path><path d="m16 16 1.2 1.2L20 14"></path>`),
  },
  templates: {
    label: "영상 템플릿",
    html: iconSvg(`<path d="M4 5h16v14H4z"></path><path d="M8 5v14M16 5v14"></path><path d="M4 9h4M4 15h4M16 9h4M16 15h4"></path><path d="m10.5 10 3 2-3 2Z"></path>`),
  },
  library: {
    label: "라이브러리",
    html: iconSvg(`<rect x="4" y="3" width="4" height="18"></rect><rect x="10" y="3" width="4" height="18"></rect><rect x="16" y="3" width="4" height="18"></rect><path d="M4 8h4M10 8h4M16 8h4M4 17h4M10 17h4M16 17h4"></path>`),
  },
  settings: {
    label: "설정",
    html: iconSvg(`<circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2 2-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6V20h-3v-.2a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1-2-2 .1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.6-1H4v-3h.2a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1 2-2 .1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.6V4h3v.2a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1 2 2-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v3h-.2a1.7 1.7 0 0 0-1.6 1Z"></path>`),
  },
};

tabs.forEach(tab => {
  const config = tabIcons[tab.dataset.tab];
  if (!config) return;
  tab.innerHTML = config.html;
  tab.setAttribute("aria-label", config.label);
  tab.dataset.tooltip = config.label;
  tab.classList.toggle("tab-combo", Boolean(config.combo));
});

function updateWorkspaceHeight() {
  const layout = document.querySelector(".layout");
  if (!layout) return;
  const viewportHeight = window.visualViewport?.height || window.innerHeight || document.documentElement.clientHeight;
  const top = layout.getBoundingClientRect().top;
  const bottomGap = window.matchMedia("(max-width: 920px)").matches ? 96 : 12;
  const height = Math.max(320, Math.floor(viewportHeight - top - bottomGap));
  document.documentElement.style.setProperty("--workspace-height", `${height}px`);
}

function scheduleWorkspaceHeight() {
  requestAnimationFrame(updateWorkspaceHeight);
}

const appStaticVersion = "20260603-v3-23";
const appShellCacheName = "webgui-shell-v3-23";

window.addEventListener("load", () => {
  if ("caches" in window) {
    caches.keys()
      .then(keys => Promise.all(
        keys
          .filter(key => key.startsWith("webgui-shell-") && key !== appShellCacheName)
          .map(key => caches.delete(key))
      ))
      .catch(() => {});
  }

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register(`/sw.js?v=${appStaticVersion}`, { updateViaCache: "none" })
      .then(registration => registration.update?.())
      .catch(() => {});
  }
});

window.addEventListener("load", scheduleWorkspaceHeight);
window.addEventListener("resize", scheduleWorkspaceHeight);
window.visualViewport?.addEventListener("resize", scheduleWorkspaceHeight);
window.visualViewport?.addEventListener("scroll", scheduleWorkspaceHeight);

function showToast(message, isError = false) {
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => toast.hidden = true, 4200);
  if (isError) {
    const errorLog = pendingErrorLog || {
      time: new Date().toISOString(),
      message: String(message || "오류가 발생했습니다."),
      detail: "",
    };
    pendingErrorLog = null;
    openErrorLog(errorLog);
  }
}

function rememberApiError(data, fallback = "요청 실패") {
  pendingErrorLog = {
    time: new Date().toISOString(),
    message: data.error || fallback,
    detail: data.detail || data.next || "",
  };
  throw new Error(data.error || data.detail || fallback);
}

function activateTab(id) {
  tabs.forEach(tab => tab.classList.toggle("active", tab.dataset.tab === id));
  panels.forEach(panel => panel.classList.toggle("active", panel.id === id));
  if (id === "library") loadLibrary();
  if (id === "prompts") loadPromptManager();
  if (id === "templates") loadTemplateManager();
  if (id === "settings") {
    loadHealth();
  }
  scheduleWorkspaceHeight();
}

tabs.forEach(tab => tab.addEventListener("click", () => activateTab(tab.dataset.tab)));

function isGrokImageModel(model) {
  return String(model || "").startsWith("grok-imagine-image");
}

function updateGrokResolutionControls(form) {
  const model = form.querySelector("[name='image_model']")?.value || "";
  const enabled = isGrokImageModel(model);
  form.querySelectorAll("[data-grok-resolution-field]").forEach(element => {
    element.hidden = !enabled;
    if (element.matches("select")) {
      element.disabled = !enabled;
      if (!enabled) element.value = "auto";
    }
  });
}

function plannerEligible(form) {
  return promptPlannerForms.has(form.dataset.endpoint) && Boolean(form.querySelector("textarea[name='prompt']"));
}

function installPromptPlannerControls(form) {
  if (!plannerEligible(form) || form.querySelector("[data-prompt-planner-box]")) return;
  const promptField = form.querySelector("textarea[name='prompt']");
  const box = document.createElement("div");
  box.className = "prompt-planner-box";
  box.dataset.promptPlannerBox = "true";
  box.innerHTML = `
    <div class="prompt-planner-head">
      <label class="check-row prompt-planner-toggle">
        <input type="checkbox" name="use_prompt_planner" value="true" data-prompt-planner-toggle>
        <span>Grok 4.2 프롬프트 플래너</span>
      </label>
      <button type="button" class="secondary compact-btn" data-preview-prompt-plan>미리보기</button>
      <button type="button" class="secondary compact-btn" data-save-current-prompt>저장</button>
    </div>
    <div class="prompt-compare" data-prompt-compare hidden>
      <div>
        <label>원본</label>
        <textarea data-original-prompt readonly></textarea>
      </div>
      <div>
        <label>생성 요청 프롬프트</label>
        <textarea data-planned-prompt readonly></textarea>
      </div>
      <div class="prompt-compare-actions">
        <span data-planner-model>planner</span>
        <button type="button" class="secondary compact-btn" data-copy-planned-prompt>최종 복사</button>
      </div>
    </div>`;
  promptField.insertAdjacentElement("afterend", box);
  box.querySelector("[data-preview-prompt-plan]")?.addEventListener("click", async () => {
    const toggle = box.querySelector("[data-prompt-planner-toggle]");
    if (toggle) toggle.checked = true;
    try {
      const prompt = promptField.value || "";
      if (!prompt.trim()) throw new Error("플래너에 보낼 프롬프트를 입력해 주세요.");
      await maybePlanPrompt(form, prompt, true);
      showToast("플래너 프롬프트를 미리보기로 만들었습니다.");
    } catch (error) {
      showToast(error.message, true);
    }
  });
  box.querySelector("[data-copy-planned-prompt]")?.addEventListener("click", async () => {
    const planned = box.querySelector("[data-planned-prompt]")?.value || "";
    if (!planned.trim()) {
      showToast("복사할 최종 프롬프트가 없습니다.", true);
      return;
    }
    await navigator.clipboard.writeText(planned);
    showToast("최종 프롬프트를 복사했습니다.");
  });
  box.querySelector("[data-save-current-prompt]")?.addEventListener("click", () => draftPromptFromForm(form));
  promptField.addEventListener("input", () => {
    promptPlannerCache.delete(form);
    const compare = form.querySelector("[data-prompt-compare]");
    if (compare) compare.hidden = true;
  });
}

function plannerContextForForm(form) {
  const sourceCount =
    getMultiImageSources(form).length
    || getMultiVideoSources(form).length
    || form.querySelector("input[type='file']")?.files?.length
    || form.querySelectorAll("[name='library_image_paths'], [name='library_video_paths']").length
    || "";
  return {
    endpoint: form.dataset.endpoint,
    task: endpointLabel(form.dataset.endpoint),
    target_model: form.querySelector("[name='image_model']")?.value || form.querySelector("[name='video_model']")?.value || "",
    aspect_ratio: form.querySelector("[name='aspect_ratio']")?.value || "",
    resolution: form.querySelector("[name='image_resolution']")?.value || form.querySelector("[name='resolution']")?.value || "",
    duration: form.querySelector("[name='duration']")?.value || "",
    source_count: String(sourceCount || ""),
  };
}

function updatePromptCompare(form, plan) {
  const compare = form.querySelector("[data-prompt-compare]");
  if (!compare || !plan?.applied) return;
  compare.hidden = false;
  compare.querySelector("[data-original-prompt]").value = plan.originalPrompt || "";
  compare.querySelector("[data-planned-prompt]").value = plan.prompt || "";
  const model = compare.querySelector("[data-planner-model]");
  if (model) model.textContent = plan.model || "planner";
}

async function maybePlanPrompt(form, prompt, force = false) {
  const toggle = form.querySelector("[data-prompt-planner-toggle]");
  if (!toggle?.checked) {
    return { applied: false, prompt, originalPrompt: prompt };
  }
  const context = plannerContextForForm(form);
  const cacheKey = JSON.stringify({ prompt, context });
  const cached = promptPlannerCache.get(form);
  if (!force && cached?.key === cacheKey) return cached.plan;
  const response = await fetch("/api/prompt-plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, ...context }),
  });
  const data = await response.json();
  if (!data.ok) rememberApiError(data, "프롬프트 플래너 실행 실패");
  const planned = (data.planned_prompt || "").trim();
  if (!planned) throw new Error("프롬프트 플래너가 빈 프롬프트를 반환했습니다.");
  const plan = {
    applied: true,
    prompt: planned,
    originalPrompt: data.original_prompt || prompt,
    model: data.model || "grok-4.20-0309-reasoning",
    context: data.context || context,
    changed: data.changed !== false,
  };
  promptPlannerCache.set(form, { key: cacheKey, plan });
  updatePromptCompare(form, plan);
  return plan;
}

function plannerFields(plan) {
  if (!plan?.applied) return {};
  return {
    prompt_planner_enabled: "true",
    original_prompt: plan.originalPrompt || "",
    planned_prompt: plan.prompt || "",
    prompt_planner_model: plan.model || "",
    prompt_planner_context: JSON.stringify(plan.context || {}),
  };
}

function appendPlannerFields(body, plan) {
  const fields = plannerFields(plan);
  if (!Object.keys(fields).length) return;
  for (const [key, value] of Object.entries(fields)) body.set(key, value);
}

function createProgress(panel, label = "진행 중") {
  if (!panel) return { set() {}, setCount() {}, done() {} };
  const overlay = document.createElement("div");
  overlay.className = "progress-overlay";
  overlay.innerHTML = `
    <div class="progress-card">
      <div class="progress-title"><span>${label}</span><span data-percent>0%</span></div>
      <div class="progress-detail" data-progress-detail hidden></div>
      <div class="progress-bar"><span></span></div>
    </div>`;
  panel.appendChild(overlay);
  const bar = overlay.querySelector(".progress-bar span");
  const percent = overlay.querySelector("[data-percent]");
  const detail = overlay.querySelector("[data-progress-detail]");
  let value = 0;
  const timer = setInterval(() => {
    value = Math.min(92, value + Math.max(1, Math.round((95 - value) * 0.08)));
    bar.style.width = `${value}%`;
    percent.textContent = `${value}%`;
    if (value >= 92) {
      overlay.querySelector(".progress-bar").classList.add("progress-indeterminate");
      percent.textContent = "진행 중";
    }
  }, 700);
  return {
    set(next) {
      value = Math.max(value, Math.min(100, next));
      bar.style.width = `${value}%`;
      percent.textContent = `${value}%`;
    },
    setCount(done, total, failed = 0, running = 0) {
      clearInterval(timer);
      value = total ? Math.round((done / total) * 100) : 0;
      bar.style.width = `${value}%`;
      percent.textContent = `${value}%`;
      detail.hidden = false;
      detail.textContent = `${done}/${total} 처리 완료${running ? ` · ${running}개 처리 중` : ""}${failed ? ` · 실패 ${failed}` : ""}`;
    },
    done() {
      clearInterval(timer);
      bar.style.width = "100%";
      percent.textContent = "100%";
      setTimeout(() => overlay.remove(), 260);
    },
  };
}

function previewItem(target, item) {
  const box = document.querySelector(target);
  const path = item.file_path;
  const isVideo = item.kind === "video" && path.toLowerCase().endsWith(".mp4");
  box.innerHTML = isVideo
    ? `<video src="${path}" controls playsinline loop></video>`
    : `<img src="${path}" alt="generated result">`;
}

function previewBatchItems(target, items = []) {
  const box = document.querySelector(target);
  if (!box) return;
  if (!items.length) {
    box.innerHTML = `<div class="empty-state">처리된 결과가 없습니다.</div>`;
    return;
  }
  box.innerHTML = `
    <div class="batch-result-grid">
      ${items.slice(0, 40).map(item => `
        <button type="button" class="batch-result-item" data-src="${item.file_path}">
          <img src="${item.file_path}" alt="" loading="lazy" decoding="async">
        </button>`).join("")}
    </div>`;
}

function stopPanelMedia(panel) {
  panel?.querySelectorAll("video").forEach(video => {
    video.pause();
    video.removeAttribute("src");
    video.load();
  });
}

function clearPreviewPanel(panel, referenceUrl = null) {
  if (!panel) return;
  stopPanelMedia(panel);
  if (referenceUrl) {
    panel.innerHTML = `<img class="reference-backdrop" src="${referenceUrl}" alt="reference frame">`;
  } else {
    panel.innerHTML = `<div class="empty-state">생성 중입니다.</div>`;
  }
}

function resetPreviewPanel(panel) {
  if (!panel) return;
  stopPanelMedia(panel);
  const messages = {
    i2iPreview: "편집 결과물이 여기에 표시됩니다.",
    t2iPreview: "결과물이 여기에 표시됩니다.",
    i2vPreview: "영상 결과물이 여기에 표시됩니다.",
    v2vPreview: "연장된 영상 결과물이 여기에 표시됩니다.",
    v2vFramePreview: "프레임 기반 연장 결과물이 여기에 표시됩니다.",
    videoEditPreview: "편집된 영상 결과물이 여기에 표시됩니다.",
  };
  panel.innerHTML = `<div class="empty-state">${messages[panel.id] || "결과물이 여기에 표시됩니다."}</div>`;
}

function setReverseOutput(prompt) {
  let output = document.querySelector("#reverseOutput");
  if (!output) {
    let panel = document.querySelector("#reverse .prompt-result")
      || document.querySelector("#reverse .result-panel")
      || document.querySelector(".prompt-result");
    const reverseSurface = document.querySelector("#reverse .studio-surface") || document.querySelector("#reverse");
    if (!panel && reverseSurface) {
      panel = document.createElement("div");
      panel.className = "result-panel prompt-result";
      reverseSurface.prepend(panel);
    }
    if (!panel) {
      throw new Error("프롬프트 출력 패널을 만들 수 없습니다. 새로고침 후 다시 시도해 주세요.");
    }
    output = document.createElement("textarea");
    output.id = "reverseOutput";
    output.readOnly = true;
    output.placeholder = "추출된 프롬프트가 여기에 표시됩니다.";
    panel.prepend(output);
    if (!panel.querySelector("#copyReverseOutput")) {
      const row = document.createElement("div");
      row.className = "button-row";
      const copyButton = document.createElement("button");
      copyButton.type = "button";
      copyButton.id = "copyReverseOutput";
      copyButton.textContent = "복사";
      copyButton.addEventListener("click", copyReversePrompt);
      row.appendChild(copyButton);
      panel.appendChild(row);
    }
  }
  output.value = prompt || "";
}

function openMediaViewer(src, mediaType = "image") {
  const viewer = document.querySelector("#mediaViewer");
  const stage = viewer.querySelector(".media-viewer-stage");
  stage.innerHTML = mediaType === "video"
    ? `<video src="${src}" controls autoplay playsinline loop></video>`
    : `<img src="${src}" alt="">`;
  viewer.classList.add("open");
  if (!viewer.open) viewer.showModal();
}

function closeMediaViewer() {
  const viewer = document.querySelector("#mediaViewer");
  if (!viewer) return;
  viewer.classList.remove("open");
  viewer.querySelector(".media-viewer-stage").innerHTML = "";
  if (viewer.open) viewer.close();
}

function waitForMediaEvent(element, eventName) {
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      element.removeEventListener(eventName, onEvent);
      element.removeEventListener("error", onError);
    };
    const onEvent = () => {
      cleanup();
      resolve();
    };
    const onError = () => {
      cleanup();
      reject(new Error("영상 프레임을 읽을 수 없습니다."));
    };
    element.addEventListener(eventName, onEvent, { once: true });
    element.addEventListener("error", onError, { once: true });
  });
}

async function captureLastFrame(form) {
  const fileInput = form.querySelector("input[name='video']");
  const libraryPath = form.querySelector("[name='library_video_path']")?.value;
  const file = fileInput?.files?.[0];
  const source = file ? URL.createObjectURL(file) : libraryPath;
  if (!source) return null;

  const video = document.createElement("video");
  video.preload = "auto";
  video.muted = true;
  video.playsInline = true;
  video.crossOrigin = "anonymous";
  video.src = source;
  await waitForMediaEvent(video, "loadedmetadata");
  const duration = Number.isFinite(video.duration) ? video.duration : 0;
  video.currentTime = Math.max(0, duration - 0.08);
  await waitForMediaEvent(video, "seeked");

  const width = video.videoWidth || 1280;
  const height = video.videoHeight || 720;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  canvas.getContext("2d").drawImage(video, 0, 0, width, height);
  const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/png"));
  if (file) URL.revokeObjectURL(source);
  if (!blob) throw new Error("마지막 프레임 이미지를 만들 수 없습니다.");
  return new File([blob], "last-frame.png", { type: "image/png" });
}

async function captureLastFramePreview(form) {
  const frame = await captureLastFrame(form);
  return {
    frame,
    referenceUrl: frame ? URL.createObjectURL(frame) : null,
  };
}

async function submitForm(form) {
  const button = form.querySelector("button[type='submit']");
  const previewSelector = form.dataset.preview;
  const previewPanel = previewSelector ? document.querySelector(previewSelector) : document.querySelector(".prompt-result");
  const progress = createProgress(previewPanel, button.textContent);
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "진행 중";
  try {
    let body;
    let options = { method: "POST" };
    if (form.dataset.kind === "json") {
      body = JSON.stringify({
        prompt: form.querySelector("[name='prompt']").value,
        aspect_ratio: form.querySelector("[name='aspect_ratio']").value,
        image_model: form.querySelector("[name='image_model']")?.value || "",
        image_resolution: form.querySelector("[name='image_resolution']")?.value || "auto",
      });
      options.headers = { "Content-Type": "application/json" };
    } else {
      body = new FormData(form);
      if (form.dataset.endpoint === "/api/v2v-frame-extend") {
        body.set("upscale_frame", form.querySelector("[name='upscale_frame']")?.checked ? "true" : "false");
        const { frame } = await captureLastFramePreview(form);
        if (frame) body.set("last_frame", frame);
      }
    }
    options.body = body;
    const response = await fetch(form.dataset.endpoint, options);
    const data = await response.json();
    if (!data.ok) rememberApiError(data);
    if (!data.ok) throw new Error(data.error || "요청 실패");
    progress.set(100);
    if (data.item) {
      previewItem(form.dataset.preview, data.item);
      loadLibrary();
    }
    if (data.source_item) {
      loadLibrary();
    }
    if (data.prompt) setReverseOutput(data.prompt);
    showToast("완료되었습니다.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    progress.done();
    button.disabled = false;
    button.textContent = original;
    loadHealth();
    refreshQuota(true);
  }
}

function endpointLabel(endpoint) {
  return ({
    "/api/t2i": "이미지 생성",
    "/api/i2i": "이미지 편집",
    "/api/i2v": "이미지 → 영상",
    "/api/v2v-extend": "공식 연장",
    "/api/v2v-frame-extend": "프레임 연장",
    "/api/video-edit": "영상 편집",
    "/api/manga-batch": "망가 실사화·역식",
    "/api/reverse-prompt": "그림 → 프롬프트",
  })[endpoint] || "작업";
}

function tabIdForEndpoint(endpoint) {
  return ({
    "/api/t2i": "t2i",
    "/api/i2i": "i2i",
    "/api/i2v": "i2v",
    "/api/v2v-extend": "v2v",
    "/api/v2v-frame-extend": "v2vFrame",
    "/api/video-edit": "videoEdit",
    "/api/manga-batch": "mangaBatch",
    "/api/reverse-prompt": "reverse",
  })[endpoint] || null;
}

function showJobResult(job) {
  if (!job?.result) return false;
  if (!job.previewSelector) {
    const item = job.result?.item || job.result?.items?.[0];
    if (!item?.file_path) return false;
    openMediaViewer(item.file_path, item.kind === "video" ? "video" : "image");
    return true;
  }
  if (job.result?.items?.length) {
    previewBatchItems(job.previewSelector, job.result.items);
  } else if (job.result?.item) {
    previewItem(job.previewSelector, job.result.item);
  } else {
    return false;
  }
  const tabId = tabIdForEndpoint(job.endpoint);
  if (tabId) activateTab(tabId);
  document.querySelector(job.previewSelector)?.scrollIntoView({ block: "center", behavior: "smooth" });
  return true;
}

function statusLabel(status) {
  return ({
    queued: "대기 중",
    running: "진행 중",
    review: "확인 대기",
    done: "완료",
    failed: "실패",
    cancelled: "취소됨",
  })[status] || status;
}

function queueSummaryText() {
  const running = jobQueue.filter(job => job.status === "running").length;
  const review = jobQueue.filter(job => job.status === "review").length;
  const waiting = jobQueue.filter(job => job.status === "queued").length;
  const done = jobQueue.filter(job => job.status === "done").length;
  const failed = jobQueue.filter(job => job.status === "failed").length;
  if (!jobQueue.length) return "대기 중인 작업이 없습니다.";
  return `${running} running${review ? ` · ${review} review` : ""} · ${waiting} waiting · ${done} done${failed ? ` · ${failed} failed` : ""}`;
}

function renderQueue() {
  const list = document.querySelector("#queueList");
  const summary = document.querySelector("#queueSummary");
  if (!list || !summary) return;
  summary.textContent = queueSummaryText();
  list.innerHTML = jobQueue.length ? "" : `<div class="queue-empty">작업을 큐에 추가하면 여기에 표시됩니다.</div>`;
  for (const job of jobQueue) {
    const node = document.createElement("article");
    node.className = `queue-job is-${job.status}`;
    node.dataset.id = job.id;
    node.tabIndex = 0;
    const resultItem = job.result?.item || job.result?.items?.[0] || null;
    const media = resultItem?.file_path
      ? (resultItem.kind === "video"
        ? `<video src="${resultItem.file_path}" muted playsinline loop></video>`
        : `<img src="${resultItem.file_path}" alt="">`)
      : `<span>${escapeHtml(job.shortType)}</span>`;
    const progress = Number.isFinite(job.progressPercent) ? job.progressPercent : (job.status === "done" ? 100 : job.status === "running" ? 72 : job.status === "failed" ? 100 : 0);
    const promptText = job.progressText || job.prompt || "프롬프트 없음";
    const progressLabel = `${Math.max(0, Math.min(100, Math.round(progress)))}%`;
    const review = job.templateRun?.review || {};
    const reviewNextLabel = review.isLast ? "완료" : "다음 컷";
    node.innerHTML = `
      <button type="button" class="queue-thumb" data-view-job aria-label="작업 결과 보기">${media}</button>
      <div class="queue-body">
        <div class="queue-title">
          <span class="queue-dot" aria-hidden="true"></span>
          <span>${escapeHtml(job.type)}</span>
          <span class="queue-percent">${progressLabel}</span>
        </div>
        <div class="queue-meta">
          <span class="queue-status">${statusLabel(job.status)}</span>
          <span class="queue-prompt" title="${escapeHtml(promptText)}">${escapeHtml(promptText)}</span>
        </div>
        <div class="queue-progress"><span style="width:${progress}%"></span></div>
        <div class="queue-actions">
          ${job.status === "queued" ? `<button type="button" data-cancel-job>취소</button>` : ""}
          ${job.status === "review" ? `<button type="button" data-template-review-next>${reviewNextLabel}</button><button type="button" class="secondary" data-template-review-retry>재시도</button><button type="button" class="secondary" data-cancel-job>중단</button>` : ""}
          ${job.status === "done" && (job.result?.item || job.result?.items?.length) ? `<button type="button" data-view-job>보기</button>` : ""}
          ${(job.status === "done" || job.status === "failed" || job.status === "cancelled") ? `<button type="button" class="secondary" data-remove-job>정리</button>` : ""}
        </div>
      </div>`;
    list.appendChild(node);
  }
}

function updateJob(job, patch) {
  Object.assign(job, patch);
  renderQueue();
}

function installQueueCountControl(form) {
  if (!repeatableQueueEndpoints.has(form.dataset.endpoint) || form.querySelector("[data-queue-count-box]")) return;
  const submitButton = form.querySelector("button[type='submit']");
  if (!submitButton) return;
  const box = document.createElement("div");
  box.className = "queue-count-box";
  box.dataset.queueCountBox = "true";
  box.innerHTML = `
    <label>동시 생성</label>
    <select name="queue_count" data-queue-count></select>`;
  const select = box.querySelector("[data-queue-count]");
  for (let value = 1; value <= maxQueueCopies; value += 1) {
    const option = document.createElement("option");
    option.value = String(value);
    option.textContent = `${value}개`;
    select.appendChild(option);
  }
  submitButton.insertAdjacentElement("beforebegin", box);
}

function queueCopyCount(form) {
  const field = form.querySelector("[data-queue-count]");
  const count = Number.parseInt(field?.value || "1", 10);
  const clamped = Math.max(1, Math.min(maxQueueCopies, Number.isFinite(count) ? count : 1));
  if (field) field.value = String(clamped);
  return clamped;
}

function cloneJobOptions(options) {
  const cloned = {
    method: options.method,
    headers: options.headers ? { ...options.headers } : undefined,
  };
  if (options.body instanceof FormData) {
    const body = new FormData();
    options.body.forEach((value, key) => {
      if (value instanceof File) {
        body.append(key, value, value.name);
      } else {
        body.append(key, value);
      }
    });
    cloned.body = body;
  } else {
    cloned.body = options.body;
  }
  return cloned;
}

async function buildJobRequest(form) {
  let body;
  let referenceUrl = null;
  const options = { method: "POST" };
  const originalPrompt = form.querySelector("[name='prompt']")?.value || form.querySelector("[name='title']")?.value || "";
  const plan = await maybePlanPrompt(form, originalPrompt);
  const prompt = plan.prompt || originalPrompt;
  if (form.dataset.kind === "json") {
    body = JSON.stringify({
      prompt,
      aspect_ratio: form.querySelector("[name='aspect_ratio']").value,
      image_model: form.querySelector("[name='image_model']")?.value || "",
      image_resolution: form.querySelector("[name='image_resolution']")?.value || "auto",
      ...plannerFields(plan),
    });
    options.headers = { "Content-Type": "application/json" };
  } else {
    if (isMultiImageVideoForm(form)) enforceI2vReferenceLimit(form);
    if (isMultiImageSourceForm(form)) {
      body = new FormData();
      body.set("prompt", prompt);
      body.set("aspect_ratio", form.querySelector("[name='aspect_ratio']").value);
      form.querySelectorAll("input, select, textarea").forEach(field => {
        if (!field.name || ["prompt", "aspect_ratio", "image", "library_image_path", "library_image_paths", "image_source_order", "queue_count"].includes(field.name)) return;
        if (field.type === "checkbox") {
          if (field.checked) body.set(field.name, field.value || "true");
          return;
        }
        body.set(field.name, field.value);
      });
      getMultiImageSources(form).forEach(source => {
        if (source.kind === "file") {
          body.append("image_source_order", "file");
          body.append("image", source.file, source.file.name);
        }
        if (source.kind === "library") {
          body.append("image_source_order", `library:${source.path}`);
          body.append("library_image_paths", source.path);
        }
      });
    } else if (isVideoEditForm(form)) {
      body = new FormData(form);
      body.delete("videos");
      body.delete("library_video_paths");
      body.delete("video_source_order");
      body.delete("video_clip_settings");
      body.set("mute", form.querySelector("[name='mute']")?.checked ? "true" : "false");
      const clipSettings = [];
      getMultiVideoSources(form).forEach(source => {
        if (source.kind === "file") {
          body.append("video_source_order", "file");
          body.append("videos", source.file, source.file.name);
        }
        if (source.kind === "library") {
          body.append("video_source_order", `library:${source.path}`);
          body.append("library_video_paths", source.path);
        }
        clipSettings.push({ start: source.start ?? 0, end: source.end ?? "" });
      });
      body.set("video_clip_settings", JSON.stringify(clipSettings));
    } else if (form.dataset.endpoint === "/api/manga-batch") {
      body = new FormData(form);
    } else {
      body = new FormData(form);
    }
    if (form.querySelector("[name='prompt']")) body.set("prompt", prompt);
    appendPlannerFields(body, plan);
    if (form.dataset.endpoint === "/api/v2v-frame-extend") {
      body.set("mute", form.querySelector("[name='mute']")?.checked ? "true" : "false");
      body.set("upscale_frame", form.querySelector("[name='upscale_frame']")?.checked ? "true" : "false");
      const captured = await captureLastFramePreview(form);
      const frame = captured.frame;
      referenceUrl = captured.referenceUrl;
      if (frame) body.set("last_frame", frame);
    }
  }
  if (body instanceof FormData) body.delete("queue_count");
  options.body = body;
  return { options, prompt, referenceUrl };
}

async function enqueueForm(form) {
  const button = form.querySelector("button[type='submit']");
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "큐에 추가 중";
  try {
    const count = queueCopyCount(form);
    const request = await buildJobRequest(form);
    const type = endpointLabel(form.dataset.endpoint);
    for (let index = 1; index <= count; index += 1) {
      const jobType = count > 1 ? `${type} ${index}/${count}` : type;
      const job = {
        id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
        type: jobType,
        shortType: type.split(" ")[0],
        status: "queued",
        endpoint: form.dataset.endpoint,
        previewSelector: form.dataset.preview,
        referenceUrl: request.referenceUrl,
        options: cloneJobOptions(request.options),
        prompt: request.prompt,
        result: null,
        error: null,
      };
      jobQueue.unshift(job);
    }
    renderQueue();
    processQueue();
    showToast(count > 1 ? `큐에 ${count}개 추가했습니다.` : "큐에 추가했습니다.");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

function processQueue() {
  while (activeJobs < maxActiveJobs) {
    const job = jobQueue.slice().reverse().find(item => item.status === "queued");
    if (!job) return;
    runJob(job);
  }
}

async function runJob(job) {
  if (job.templateRun) {
    await runTemplateJob(job);
    return;
  }
  activeJobs += 1;
  updateJob(job, { status: "running" });
  const previewPanel = job.previewSelector ? document.querySelector(job.previewSelector) : document.querySelector(".prompt-result");
  clearPreviewPanel(previewPanel, job.referenceUrl);
  const progress = createProgress(previewPanel, job.type);
  try {
    const response = await fetch(job.endpoint, job.options);
    const data = await response.json();
    if (!data.ok) rememberApiError(data);
    if (!data.ok) throw new Error(data.error || "요청 실패");
    if (job.endpoint === "/api/manga-batch" && data.job_id) {
      const status = await pollMangaBatch(job, data.job_id, progress);
      if (status.status === "failed" && !(status.completed || 0)) throw new Error(status.error || "배치 처리 실패");
      progress.set(100);
      if (status.items && job.previewSelector) previewBatchItems(job.previewSelector, status.items);
      if (status.items?.length) loadLibrary();
      updateJob(job, { status: "done", result: status, progressPercent: 100, progressText: `${(status.completed || 0) + (status.failed || 0)}/${status.total || 0} 처리 완료` });
      showToast(`${job.type} 완료`);
      return;
    }
    progress.set(100);
    if (data.items && job.previewSelector) {
      previewBatchItems(job.previewSelector, data.items);
    } else if (data.item && job.previewSelector) {
      previewItem(job.previewSelector, data.item);
    }
    if (data.prompt) setReverseOutput(data.prompt);
    if (data.item || data.items || data.source_item) {
      loadLibrary();
    }
    updateJob(job, { status: "done", result: data });
    showToast(`${job.type} 완료`);
  } catch (error) {
    updateJob(job, { status: "failed", error: error.message });
    showToast(error.message, true);
  } finally {
    progress.done();
    activeJobs -= 1;
    loadHealth();
    refreshQuota(true);
    processQueue();
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function pollMangaBatch(job, batchId, progress) {
  let latest = null;
  while (true) {
    const response = await fetch(`/api/manga-batch/${batchId}`);
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "배치 상태 조회 실패");
    latest = data;
    const done = (data.completed || 0) + (data.failed || 0);
    const total = data.total || 0;
    const running = data.status === "running" ? Math.min(data.parallel || 0, Math.max(0, total - done)) : 0;
    const percent = total ? Math.round((done / total) * 100) : 0;
    const text = `${done}/${total} 처리 완료${running ? ` · ${running}개 처리 중` : ""}${data.failed ? ` · 실패 ${data.failed}` : ""}`;
    progress.setCount(done, total, data.failed || 0, running);
    updateJob(job, { progressPercent: percent, progressText: text, result: data });
    if (data.items && job.previewSelector) previewBatchItems(job.previewSelector, data.items);
    if (data.status === "done" || data.status === "failed") break;
    await sleep(1000);
  }
  return latest;
}

function templateRunPlanText() {
  const payload = templateRuntimePayload();
  return payload.shots.map((shot, index) => [
    `# ${String(index + 1).padStart(2, "0")} ${shot.title || "컷"}`,
    `방식: ${templateMethodLabels[shot.method] || shot.method}`,
    `길이: ${shot.duration || payload.settings.default_shot_duration || 6}초`,
    `참조: ${shot.reference_slot || "이전 결과 또는 첫 슬롯"}`,
    templateShotPromptText(payload, shot),
  ].filter(Boolean).join("\n")).join("\n\n");
}

function templateSlotMatchesKind(slot, expectedKind = "image") {
  if (!slot?.path) return false;
  if (expectedKind === "video") return slot.kind === "video";
  return slot.kind !== "video";
}

function templateSlotEntry(key, expectedKind = "image", slotState = templateRunState.slots) {
  if (key && templateSlotMatchesKind(slotState[key], expectedKind)) return slotState[key];
  return Object.values(slotState).find(slot => {
    return templateSlotMatchesKind(slot, expectedKind);
  }) || null;
}

function templateImageSourcePath(shot, previous, slotState) {
  const slot = templateSlotEntry(shot.reference_slot, "image", slotState);
  if (slot?.path) return slot.path;
  return previous.lastImagePath || "";
}

function templateVideoSourcePath(shot, previous, slotState) {
  const slot = templateSlotEntry(shot.reference_slot, "video", slotState);
  if (slot?.path) return slot.path;
  return previous.lastVideoPath || "";
}

function appendTemplateImageReference(body, path) {
  if (!path) throw new Error("이 컷에 사용할 이미지 레퍼런스가 없습니다.");
  body.append("image_source_order", `library:${path}`);
  body.append("library_image_paths", path);
}

function buildTemplateShotRequest(payload, shot, previous, slotState = templateRunState.slots) {
  const prompt = templateShotPromptText(payload, shot);
  const duration = String(shot.duration || payload.settings.default_shot_duration || 6);
  const aspectRatio = payload.settings.aspect_ratio || "9:16";
  const resolution = payload.settings.resolution || "720p";
  if (shot.method === "image") {
    return {
      endpoint: "/api/t2i",
      prompt,
      options: {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, aspect_ratio: aspectRatio }),
      },
    };
  }
  if (shot.method === "edit") {
    const body = new FormData();
    body.set("prompt", prompt);
    body.set("aspect_ratio", aspectRatio);
    body.set("image_resolution", "auto");
    body.set("edit_input_mode", "multi");
    appendTemplateImageReference(body, templateImageSourcePath(shot, previous, slotState));
    return { endpoint: "/api/i2i", prompt, options: { method: "POST", body } };
  }
  if (shot.method === "i2v") {
    const body = new FormData();
    body.set("prompt", prompt);
    body.set("duration", duration);
    body.set("aspect_ratio", aspectRatio);
    body.set("resolution", resolution);
    appendTemplateImageReference(body, templateImageSourcePath(shot, previous, slotState));
    return { endpoint: "/api/i2v", prompt, options: { method: "POST", body } };
  }
  if (shot.method === "official" || shot.method === "frame") {
    const source = templateVideoSourcePath(shot, previous, slotState);
    if (!source) throw new Error("이 컷에는 영상 레퍼런스가 필요합니다. 앞 컷에서 영상을 생성하거나 영상 슬롯을 연결해 주세요.");
    const body = new FormData();
    body.set("prompt", prompt);
    body.set("duration", duration);
    body.set("aspect_ratio", aspectRatio);
    body.set("resolution", resolution);
    body.set("library_video_path", source);
    if (shot.method === "frame") body.set("mute", "false");
    return {
      endpoint: shot.method === "official" ? "/api/v2v-extend" : "/api/v2v-frame-extend",
      prompt,
      options: { method: "POST", body },
    };
  }
  throw new Error(`지원하지 않는 템플릿 컷 방식입니다: ${shot.method}`);
}

async function fetchTemplateShot(request) {
  const response = await fetch(request.endpoint, request.options);
  const data = await response.json();
  if (!data.ok) rememberApiError(data);
  if (!data.ok) throw new Error(data.error || data.detail || "템플릿 컷 실행에 실패했습니다.");
  return data;
}

function updateTemplatePreviousResult(previous, data) {
  const item = data.item || data.items?.[0];
  if (!item?.file_path) return;
  if (item.kind === "video") {
    previous.lastVideoPath = item.file_path;
  } else {
    previous.lastImagePath = item.file_path;
  }
}

function templateResultItems(data) {
  if (data?.items?.length) return data.items;
  if (data?.item) return [data.item];
  return [];
}

function resolveTemplateReview(job, action) {
  const review = job.templateRun?.review;
  if (!review?.resolve) return false;
  job.templateRun.review = null;
  review.resolve(action);
  return true;
}

function waitForTemplateReview(job, detail) {
  return new Promise(resolve => {
    job.templateRun.review = { ...detail, resolve };
    updateJob(job, {
      status: "review",
      progressPercent: detail.progressPercent,
      progressText: `${detail.label} 확인 대기`,
      prompt: detail.prompt,
      result: { ok: true, items: detail.items },
    });
  });
}

function enqueueTemplateRun() {
  const payload = templateRuntimePayload();
  if (!payload.title.trim()) {
    showToast("템플릿 이름을 입력해 주세요.", true);
    return;
  }
  if (!payload.shots.length) {
    showToast("실행할 컷 블록이 없습니다.", true);
    return;
  }
  const job = {
    id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
    type: `템플릿 · ${payload.title}`,
    shortType: "템플릿",
    status: "queued",
    endpoint: "template-run",
    previewSelector: "",
    templateRun: {
      payload,
      slotState: JSON.parse(JSON.stringify(templateRunState.slots)),
      mode: templateRunState.mode === "manual" ? "manual" : "auto",
    },
    prompt: `${payload.shots.length}개 컷 순차 실행`,
    result: null,
    error: null,
  };
  jobQueue.unshift(job);
  renderQueue();
  processQueue();
  showToast("템플릿 실행 작업을 큐에 추가했습니다.");
}

async function runTemplateJob(job) {
  activeJobs += 1;
  updateJob(job, { status: "running", progressPercent: 0, progressText: "템플릿 실행 시작" });
  const progress = createProgress(document.querySelector("#templateRunner"), job.type);
  const payload = job.templateRun.payload;
  const slotState = job.templateRun.slotState || {};
  const previous = { lastImagePath: "", lastVideoPath: "" };
  const items = [];
  const manualMode = job.templateRun.mode === "manual" || payload.run_mode === "manual";
  try {
    for (let index = 0; index < payload.shots.length; index += 1) {
      const shot = payload.shots[index];
      const label = `${index + 1}/${payload.shots.length} · ${shot.title || "컷"}`;
      const committedCount = items.length;
      const previousBeforeShot = { ...previous };
      let accepted = false;
      while (!accepted) {
        if (job.status === "cancelled") throw new Error("템플릿 실행이 취소되었습니다.");
        const request = buildTemplateShotRequest(payload, shot, previousBeforeShot, slotState);
        progress.setCount(index, payload.shots.length, 0, 1);
        updateJob(job, {
          status: "running",
          progressPercent: Math.round((index / payload.shots.length) * 100),
          progressText: `${label} 실행 중`,
          prompt: request.prompt,
        });
        const data = await fetchTemplateShot(request);
        if (job.status === "cancelled") throw new Error("템플릿 실행이 취소되었습니다.");
        const produced = templateResultItems(data);
        items.splice(committedCount, items.length - committedCount, ...produced);
        const nextPrevious = { ...previousBeforeShot };
        updateTemplatePreviousResult(nextPrevious, data);
        progress.setCount(index + 1, payload.shots.length, 0, 0);
        updateJob(job, {
          result: { ok: true, items: [...items] },
          progressPercent: Math.round(((index + 1) / payload.shots.length) * 100),
          progressText: `${index + 1}/${payload.shots.length} 컷 완료`,
        });
        loadLibrary();
        if (manualMode) {
          const action = await waitForTemplateReview(job, {
            index,
            isLast: index + 1 >= payload.shots.length,
            label,
            prompt: request.prompt,
            items: [...items],
            progressPercent: Math.round(((index + 1) / payload.shots.length) * 100),
          });
          if (action === "cancel") throw new Error("템플릿 실행이 취소되었습니다.");
          if (action === "retry") {
            items.splice(committedCount);
            previous.lastImagePath = previousBeforeShot.lastImagePath;
            previous.lastVideoPath = previousBeforeShot.lastVideoPath;
            showToast(`${shot.title || "컷"} 재시도`);
            continue;
          }
        }
        previous.lastImagePath = nextPrevious.lastImagePath;
        previous.lastVideoPath = nextPrevious.lastVideoPath;
        accepted = true;
      }
    }
    progress.set(100);
    updateJob(job, { status: "done", result: { ok: true, items }, progressPercent: 100, progressText: "템플릿 실행 완료" });
    showToast("템플릿 실행이 완료되었습니다.");
  } catch (error) {
    updateJob(job, { status: job.status === "cancelled" ? "cancelled" : "failed", error: error.message, progressText: error.message });
    showToast(error.message, true);
  } finally {
    progress.done();
    activeJobs -= 1;
    loadHealth();
    refreshQuota(true);
    processQueue();
  }
}

document.querySelectorAll("form[data-endpoint]").forEach(form => {
  installPromptPlannerControls(form);
  installQueueCountControl(form);
  updateGrokResolutionControls(form);
  form.querySelector("[name='image_model']")?.addEventListener("change", () => updateGrokResolutionControls(form));
  form.querySelector("[name='video_model']")?.addEventListener("change", () => enforceI2vReferenceLimit(form, true));
  form.addEventListener("submit", event => {
    event.preventDefault();
    enqueueForm(form);
  });
});

function setFileInput(input, file) {
  const transfer = new DataTransfer();
  transfer.items.add(file);
  input.files = transfer.files;
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function setFileInputFiles(input, files) {
  const transfer = new DataTransfer();
  const selected = [...files].slice(0, batchMaxImages);
  selected.forEach(file => transfer.items.add(file));
  input.files = transfer.files;
  input.dispatchEvent(new Event("change", { bubbles: true }));
  if (files.length > batchMaxImages) {
    showToast(`최대 ${batchMaxImages}장까지만 등록했습니다.`, true);
  }
}

function updateBatchFileList(form) {
  const list = form.querySelector("[data-batch-file-list]");
  const input = form.querySelector("input[name='images']");
  if (!list || !input) return;
  const files = [...input.files];
  list.innerHTML = files.length
    ? files.slice(0, batchMaxImages).map((file, index) => `
      <div class="batch-file-row" data-batch-file-index="${index}">
        <span>${index + 1}</span>
        <strong>${escapeHtml(file.name)}</strong>
        <small>${Math.round(file.size / 1024)} KB</small>
        <button type="button" class="icon-button" data-remove-batch-file aria-label="등록 취소">×</button>
      </div>`).join("")
    : `<div class="video-track-empty">선택된 이미지가 없습니다.</div>`;
}

function removeBatchFile(form, index) {
  const input = form.querySelector("input[name='images']");
  if (!input) return;
  const files = [...input.files].filter((_, fileIndex) => fileIndex !== index);
  setFileInputFiles(input, files);
}

function clearBatchFiles(form) {
  const input = form.querySelector("input[name='images']");
  if (!input) return;
  setFileInputFiles(input, []);
}

function mediaTypeForForm(form) {
  return form?.querySelector("[data-file-drop]")?.dataset.mediaType || "image";
}

function isMultiImageEditForm(form) {
  return form?.dataset.endpoint === "/api/i2i";
}

function isMultiImageVideoForm(form) {
  return form?.dataset.endpoint === "/api/i2v";
}

function isMultiImageSourceForm(form) {
  return isMultiImageEditForm(form) || isMultiImageVideoForm(form);
}

function isSingleReferenceVideoModel(model) {
  return String(model || "").includes("1.5");
}

function isSingleReferenceI2vForm(form) {
  return isMultiImageVideoForm(form) && isSingleReferenceVideoModel(form.querySelector("[name='video_model']")?.value);
}

function isVideoEditForm(form) {
  return form?.dataset.endpoint === "/api/video-edit";
}

function getMultiImageSources(form) {
  if (!multiImageSources.has(form)) multiImageSources.set(form, []);
  return multiImageSources.get(form);
}

function getMultiVideoSources(form) {
  if (!multiVideoSources.has(form)) multiVideoSources.set(form, []);
  return multiVideoSources.get(form);
}

function secondsValue(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, Math.round(number * 10) / 10) : fallback;
}

function formatSeconds(value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0) return "--";
  return `${(Math.round(number * 10) / 10).toFixed(1)}s`;
}

function moveArrayItem(items, from, to) {
  if (from === to || from < 0 || to < 0 || from >= items.length || to >= items.length) return;
  const [item] = items.splice(from, 1);
  items.splice(to, 0, item);
}

function syncMultiImageHiddenInputs(form) {
  const box = form.querySelector("[data-library-image-paths]");
  if (!box) return;
  box.innerHTML = "";
  getMultiImageSources(form).filter(source => source.kind === "library").forEach(source => {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = "library_image_paths";
    input.value = source.path;
    box.appendChild(input);
  });
}

function releaseImageSource(source) {
  if (source?.kind === "file" && source.src?.startsWith("blob:")) URL.revokeObjectURL(source.src);
}

function enforceI2vReferenceLimit(form, notify = false) {
  if (!isSingleReferenceI2vForm(form)) return;
  const sources = getMultiImageSources(form);
  if (sources.length <= 1) return;
  sources.slice(1).forEach(releaseImageSource);
  sources.splice(1);
  renderMultiImageSources(form);
  if (notify) showToast("1.5 영상 모델은 레퍼런스 이미지를 1장만 사용합니다.");
}

function renderMultiImageSources(form) {
  const sources = getMultiImageSources(form);
  const zone = form.querySelector("[data-file-drop]");
  const preview = zone.querySelector(".selected-preview");
  const thumbs = form.querySelector("[data-source-thumbs]");
  const fileInput = form.querySelector("input[type='file']");
  zone.classList.toggle("has-file", sources.length > 0);
  fileInput.required = sources.length === 0;
  if (!sources.length) {
    preview.innerHTML = emptyDropPreview("image");
    if (thumbs) thumbs.innerHTML = "";
    syncMultiImageHiddenInputs(form);
    return;
  }
  const main = sources[0];
  preview.innerHTML = `<img src="${main.src}" alt="selected image"><small>${escapeHtml(main.label)}</small>`;
  if (thumbs) {
    thumbs.innerHTML = sources.map((source, index) => `
      <button type="button" class="source-thumb${index === 0 ? " active" : ""}" data-source-index="${index}">
        <img src="${source.src}" alt="">
        <span>${index + 1}</span>
        <i data-remove-source aria-label="삭제">×</i>
      </button>`).join("");
  }
  syncMultiImageHiddenInputs(form);
}

function addMultiImageFiles(form, files) {
  const sources = getMultiImageSources(form);
  const imageFiles = [...files].filter(file => file.type.startsWith("image/"));
  if (isSingleReferenceI2vForm(form)) {
    const file = imageFiles[0];
    if (!file) return;
    sources.forEach(releaseImageSource);
    sources.splice(0, sources.length, { kind: "file", file, src: URL.createObjectURL(file), label: file.name });
    renderMultiImageSources(form);
    return;
  }
  imageFiles.forEach(file => {
    if (sources.length >= 3) return;
    sources.push({ kind: "file", file, src: URL.createObjectURL(file), label: file.name });
  });
  renderMultiImageSources(form);
}

function addMultiImageLibrarySource(form, path, label = path) {
  const sources = getMultiImageSources(form);
  if (isSingleReferenceI2vForm(form)) {
    sources.forEach(releaseImageSource);
    sources.splice(0, sources.length, { kind: "library", path, src: path, label });
    renderMultiImageSources(form);
    return;
  }
  if (sources.length >= 3) {
    showToast("이미지는 최대 3개까지 사용할 수 있습니다.", true);
    return;
  }
  sources.push({ kind: "library", path, src: path, label });
  renderMultiImageSources(form);
}

function removeMultiImageSource(form, index) {
  const sources = getMultiImageSources(form);
  const [removed] = sources.splice(index, 1);
  releaseImageSource(removed);
  renderMultiImageSources(form);
}

function clearMultiImageSources(form) {
  getMultiImageSources(form).forEach(releaseImageSource);
  multiImageSources.set(form, []);
  const input = form.querySelector("input[type='file']");
  if (input) input.value = "";
  renderMultiImageSources(form);
}

function syncMultiVideoHiddenInputs(form) {
  const container = form.querySelector("[data-library-video-paths]");
  if (!container) return;
  container.innerHTML = "";
  getMultiVideoSources(form)
    .filter(source => source.kind === "library")
    .forEach(source => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "library_video_paths";
      input.value = source.path;
      container.appendChild(input);
    });
}

function renderVideoTimelineSources(form) {
  const sources = getMultiVideoSources(form);
  const list = form.querySelector("[data-video-track-list]");
  const zone = form.querySelector("[data-file-drop]");
  const input = form.querySelector("input[type='file']");
  zone?.classList.toggle("has-file", sources.length > 0);
  if (input) input.required = sources.length === 0;
  if (list) {
    list.innerHTML = sources.length ? sources.map((source, index) => `
      <article class="video-track video-clip" data-video-index="${index}" draggable="true">
        <div class="clip-grip" aria-hidden="true">::</div>
        <button type="button" class="clip-order-button" data-move-video-source="-1" aria-label="위로 이동">↑</button>
        <button type="button" class="clip-order-button" data-move-video-source="1" aria-label="아래로 이동">↓</button>
        <video src="${source.src}" muted playsinline loop data-clip-video></video>
        <div class="clip-main">
          <strong>${index + 1}. ${escapeHtml(source.label)}</strong>
          <small>${source.kind === "library" ? "라이브러리" : "업로드"} · ${formatSeconds(source.duration)}</small>
          <div class="clip-trim-grid">
            <label>시작
              <input type="number" min="0" step="0.1" value="${source.start ?? 0}" data-video-trim-start>
            </label>
            <label>끝
              <input type="number" min="0" step="0.1" value="${source.end ?? ""}" placeholder="${source.duration ? formatSeconds(source.duration) : "끝"}" data-video-trim-end>
            </label>
            <button type="button" class="secondary" data-use-current-start>현재→시작</button>
            <button type="button" class="secondary" data-use-current-end>현재→끝</button>
          </div>
        </div>
        <button type="button" class="icon-button clip-remove" data-remove-video-source aria-label="삭제">×</button>
      </article>`).join("") : `<div class="video-track-empty">영상을 순서대로 추가해 주세요.</div>`;
    list.querySelectorAll("[data-clip-video]").forEach(video => {
      const track = video.closest("[data-video-index]");
      const source = sources[Number(track.dataset.videoIndex)];
      const configure = () => {
        const duration = secondsValue(video.duration, 0);
        if (!duration) return;
        source.duration = duration;
        if (source.end == null || source.end === "" || source.end > duration) source.end = duration;
        source.start = Math.min(secondsValue(source.start, 0), Math.max(0, duration - 0.1));
        const startInput = track.querySelector("[data-video-trim-start]");
        const endInput = track.querySelector("[data-video-trim-end]");
        const small = track.querySelector(".clip-main small");
        if (startInput) {
          startInput.max = String(duration);
          startInput.value = String(source.start ?? 0);
        }
        if (endInput) {
          endInput.max = String(duration);
          endInput.placeholder = formatSeconds(duration);
          endInput.value = String(source.end ?? "");
        }
        if (small) small.textContent = `${source.kind === "library" ? "라이브러리" : "업로드"} · ${formatSeconds(duration)}`;
      };
      video.addEventListener("loadedmetadata", configure, { once: true });
      if (video.readyState >= 1) configure();
    });
  }
  const preview = zone?.querySelector(".selected-preview");
  if (preview) {
    preview.innerHTML = sources.length
      ? `<span class="drop-title">${sources.length}개 영상 선택됨</span><small>타임라인 순서대로 자르고 붙입니다.</small>`
      : emptyDropPreview("video");
  }
  syncMultiVideoHiddenInputs(form);
}

function renderMultiVideoSources(form) {
  return renderVideoTimelineSources(form);
  const sources = getMultiVideoSources(form);
  const list = form.querySelector("[data-video-track-list]");
  const zone = form.querySelector("[data-file-drop]");
  const input = form.querySelector("input[type='file']");
  zone?.classList.toggle("has-file", sources.length > 0);
  if (input) input.required = sources.length === 0;
  if (list) {
    list.innerHTML = sources.length ? sources.map((source, index) => `
      <article class="video-track" data-video-index="${index}">
        <video src="${source.src}" muted playsinline loop></video>
        <div>
          <strong>${index + 1}. ${escapeHtml(source.label)}</strong>
          <small>${source.kind === "library" ? "라이브러리" : "업로드"}</small>
        </div>
        <button type="button" class="secondary" data-remove-video-source>삭제</button>
      </article>`).join("") : `<div class="video-track-empty">영상을 순서대로 추가해 주세요.</div>`;
  }
  const preview = zone?.querySelector(".selected-preview");
  if (preview) {
    preview.innerHTML = sources.length
      ? `<span class="drop-title">${sources.length}개 영상 선택됨</span><small>목록 순서대로 병합됩니다.</small>`
      : emptyDropPreview("video");
  }
  syncMultiVideoHiddenInputs(form);
}

function addMultiVideoFiles(form, files) {
  const sources = getMultiVideoSources(form);
  [...files].filter(file => file.type.startsWith("video/")).forEach(file => {
    if (sources.length >= 12) return;
    sources.push({ kind: "file", file, src: URL.createObjectURL(file), label: file.name, start: 0, end: "" });
  });
  renderMultiVideoSources(form);
}

function addMultiVideoLibrarySource(form, path, label = path) {
  const sources = getMultiVideoSources(form);
  if (sources.length >= 12) {
    showToast("영상은 최대 12개까지 편집할 수 있습니다.", true);
    return;
  }
  sources.push({ kind: "library", path, src: path, label, start: 0, end: "" });
  renderMultiVideoSources(form);
}

function removeMultiVideoSource(form, index) {
  const sources = getMultiVideoSources(form);
  const [removed] = sources.splice(index, 1);
  if (removed?.kind === "file" && removed.src?.startsWith("blob:")) URL.revokeObjectURL(removed.src);
  renderMultiVideoSources(form);
}

function clearMultiVideoSources(form) {
  getMultiVideoSources(form).forEach(source => {
    if (source.kind === "file" && source.src?.startsWith("blob:")) URL.revokeObjectURL(source.src);
  });
  multiVideoSources.set(form, []);
  const input = form.querySelector("input[type='file']");
  if (input) input.value = "";
  renderMultiVideoSources(form);
  resetPreviewPanel(document.querySelector(form.dataset.preview));
}

function setSourcePreview(form, src, label, mediaType = mediaTypeForForm(form)) {
  if (isMultiImageSourceForm(form) && mediaType === "image") {
    addMultiImageLibrarySource(form, src, label);
    return;
  }
  const zone = form.querySelector("[data-file-drop]");
  if (!zone) return;
  const preview = zone.querySelector(".selected-preview");
  zone.classList.add("has-file");
  const media = mediaType === "video"
    ? `<video src="${src}" controls playsinline muted loop></video>`
    : `<img src="${src}" alt="selected image">`;
  preview.innerHTML = `${media}<small>${escapeHtml(label)}</small>`;
  if (mediaType === "video") setupConnectPicker(form, preview.querySelector("video"));
}

function setupConnectPicker(form, video) {
  const picker = form.querySelector("[data-connect-picker]");
  if (!picker || !video) return;
  const slider = picker.querySelector("[data-connect-slider]");
  const number = picker.querySelector("[name='connect_time']");
  const label = picker.querySelector("[data-connect-label]");
  const useCurrent = picker.querySelector("[data-use-current-time]");

  const setLabel = value => {
    if (!value) {
      label.textContent = "영상 끝";
      return;
    }
    label.textContent = `${Number(value).toFixed(1)}초`;
  };

  const configure = () => {
    const duration = Number.isFinite(video.duration) ? Math.floor(video.duration * 10) / 10 : 0;
    slider.max = String(Math.max(0, duration));
    slider.value = String(Math.max(0, duration));
    slider.disabled = duration <= 0;
    number.max = duration ? String(duration) : "";
    number.value = "";
    setLabel("");
  };

  video.addEventListener("loadedmetadata", configure, { once: true });
  if (video.readyState >= 1) configure();

  slider.oninput = () => {
    number.value = Number(slider.value).toFixed(1);
    video.currentTime = Number(slider.value);
    setLabel(number.value);
  };

  number.oninput = () => {
    const value = Number(number.value);
    if (!Number.isFinite(value)) {
      setLabel("");
      return;
    }
    const clamped = Math.max(0, Math.min(Number(slider.max) || value, value));
    slider.value = String(clamped);
    video.currentTime = clamped;
    setLabel(clamped);
  };

  useCurrent.onclick = () => {
    const current = Math.round((video.currentTime || 0) * 10) / 10;
    number.value = current.toFixed(1);
    slider.value = String(current);
    setLabel(current);
  };
}

function emptyDropPreview(mediaType = "image") {
  const title = mediaType === "video" ? "영상을 드래그하거나 선택" : "이미지를 드래그하거나 붙여넣기";
  return `
    <span class="drop-title">${title}</span>
    <small>파일 업로드 또는 라이브러리에서 선택</small>`;
}

document.querySelectorAll("[data-file-drop]").forEach(zone => {
  const input = zone.querySelector("input[type='file']");
  const mediaType = zone.dataset.mediaType || "image";
  if (zone.hasAttribute("data-click-file")) {
    zone.addEventListener("click", event => {
      if (event.target.closest("input, button, a, img, video")) return;
      input.click();
    });
  }
  zone.addEventListener("dragover", event => {
    event.preventDefault();
    zone.classList.add("dragover");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
  zone.addEventListener("drop", event => {
    event.preventDefault();
    zone.classList.remove("dragover");
    const files = [...event.dataTransfer.files].filter(item => item.type.startsWith(`${mediaType}/`));
    const form = zone.closest("form");
    if (zone.hasAttribute("data-batch-images") && files.length) {
      setFileInputFiles(input, files);
    } else if (isMultiImageSourceForm(form) && mediaType === "image") {
      addMultiImageFiles(zone.closest("form"), files);
    } else if (isVideoEditForm(form) && mediaType === "video") {
      addMultiVideoFiles(form, files);
    } else if (files[0]) {
      setFileInput(input, files[0]);
    }
  });
  input.addEventListener("change", () => {
    const form = zone.closest("form");
    if (zone.hasAttribute("data-batch-images")) {
      updateBatchFileList(form);
      zone.classList.toggle("has-file", input.files.length > 0);
      return;
    }
    if (isMultiImageSourceForm(form) && mediaType === "image") {
      addMultiImageFiles(form, input.files);
      input.value = "";
      return;
    }
    if (isVideoEditForm(form) && mediaType === "video") {
      addMultiVideoFiles(form, input.files);
      input.value = "";
      return;
    }
    const file = input.files[0];
    if (file) {
      const hidden = form?.querySelector(`[name='library_${mediaType}_path']`);
      if (hidden) hidden.value = "";
      input.required = true;
      setSourcePreview(form, URL.createObjectURL(file), file.name, mediaType);
    }
    zone.classList.toggle("has-file", Boolean(file));
    if (!file) {
      zone.querySelector(".selected-preview").innerHTML = emptyDropPreview(mediaType);
    }
  });
});

document.addEventListener("click", event => {
  const image = event.target.closest(".selected-preview img, .result-panel img, .batch-result-item img");
  if (image) {
    openMediaViewer(image.currentSrc || image.src, "image");
    return;
  }
  const video = event.target.closest(".selected-preview video");
  if (video) {
    if (video.paused) video.play();
    else video.pause();
  }
});

document.addEventListener("click", event => {
  const clearBatch = event.target.closest("[data-clear-batch-files]");
  if (clearBatch) {
    clearBatchFiles(clearBatch.closest("form"));
    return;
  }
  const removeBatch = event.target.closest("[data-remove-batch-file]");
  if (removeBatch) {
    const row = removeBatch.closest("[data-batch-file-index]");
    removeBatchFile(removeBatch.closest("form"), Number(row.dataset.batchFileIndex));
    return;
  }
  const moveVideo = event.target.closest("[data-move-video-source]");
  if (moveVideo) {
    const form = moveVideo.closest("form");
    const track = moveVideo.closest("[data-video-index]");
    const from = Number(track.dataset.videoIndex);
    const to = from + Number(moveVideo.dataset.moveVideoSource);
    moveArrayItem(getMultiVideoSources(form), from, to);
    renderMultiVideoSources(form);
    return;
  }
  const useClipTime = event.target.closest("[data-use-current-start], [data-use-current-end]");
  if (useClipTime) {
    const form = useClipTime.closest("form");
    const track = useClipTime.closest("[data-video-index]");
    const source = getMultiVideoSources(form)[Number(track.dataset.videoIndex)];
    const video = track.querySelector("[data-clip-video]");
    const current = secondsValue(video?.currentTime, 0);
    if (useClipTime.matches("[data-use-current-start]")) source.start = current;
    if (useClipTime.matches("[data-use-current-end]")) source.end = current;
    renderMultiVideoSources(form);
    return;
  }
  const removeVideo = event.target.closest("[data-remove-video-source]");
  if (removeVideo) {
    const form = removeVideo.closest("form");
    const track = removeVideo.closest("[data-video-index]");
    removeMultiVideoSource(form, Number(track.dataset.videoIndex));
    return;
  }
  const remove = event.target.closest("[data-remove-source]");
  if (remove) {
    const form = remove.closest("form");
    const thumb = remove.closest("[data-source-index]");
    removeMultiImageSource(form, Number(thumb.dataset.sourceIndex));
    return;
  }
  const thumb = event.target.closest(".source-thumb");
  if (thumb) {
    const image = thumb.querySelector("img");
    if (image) openMediaViewer(image.currentSrc || image.src, "image");
  }
});

document.addEventListener("input", event => {
  const trimInput = event.target.closest("[data-video-trim-start], [data-video-trim-end]");
  if (!trimInput) return;
  const form = trimInput.closest("form");
  const track = trimInput.closest("[data-video-index]");
  const source = getMultiVideoSources(form)[Number(track.dataset.videoIndex)];
  const value = trimInput.value === "" ? "" : secondsValue(trimInput.value, 0);
  if (trimInput.matches("[data-video-trim-start]")) source.start = value || 0;
  if (trimInput.matches("[data-video-trim-end]")) source.end = value;
});

document.addEventListener("dragstart", event => {
  const track = event.target.closest(".video-track[draggable='true']");
  if (!track) return;
  event.dataTransfer.setData("text/plain", track.dataset.videoIndex);
  event.dataTransfer.effectAllowed = "move";
  track.classList.add("is-dragging");
});

document.addEventListener("dragend", event => {
  event.target.closest(".video-track")?.classList.remove("is-dragging");
});

document.addEventListener("dragover", event => {
  if (!event.target.closest("[data-video-track-list]")) return;
  event.preventDefault();
  event.dataTransfer.dropEffect = "move";
});

document.addEventListener("drop", event => {
  const list = event.target.closest("[data-video-track-list]");
  const target = event.target.closest(".video-track[data-video-index]");
  if (!list || !target) return;
  event.preventDefault();
  const form = list.closest("form");
  const from = Number(event.dataTransfer.getData("text/plain"));
  const to = Number(target.dataset.videoIndex);
  moveArrayItem(getMultiVideoSources(form), from, to);
  renderMultiVideoSources(form);
});

document.querySelectorAll("[data-clear-multi-images]").forEach(button => {
  button.addEventListener("click", () => {
    const form = button.closest("form");
    clearMultiImageSources(form);
    resetPreviewPanel(document.querySelector(form.dataset.preview));
  });
});

document.querySelectorAll("[data-clear-video-edit]").forEach(button => {
  button.addEventListener("click", () => clearMultiVideoSources(button.closest("form")));
});

document.querySelectorAll("[data-trigger-file]").forEach(button => {
  button.addEventListener("click", () => {
    button.closest("form").querySelector("input[type='file']").click();
  });
});

document.addEventListener("paste", event => {
  const activePanel = document.querySelector(".panel.active");
  const input = activePanel?.querySelector("[data-file-drop] input[type='file']");
  if (!input) return;
  const zone = input.closest("[data-file-drop]");
  if ((zone?.dataset.mediaType || "image") !== "image") return;
  const file = [...event.clipboardData.files].find(item => item.type.startsWith("image/"));
  if (file) {
    const form = zone.closest("form");
    if (isMultiImageEditForm(form)) {
      addMultiImageFiles(form, [file]);
    } else {
      setFileInput(input, file);
    }
    showToast("클립보드 이미지를 첨부했습니다.");
  }
});

document.querySelectorAll("[data-send]").forEach(button => {
  button.addEventListener("click", () => {
    const prompt = document.querySelector("#reverseOutput")?.value || "";
    const target = document.querySelector(`#${button.dataset.send}`);
    if (!target) {
      showToast("보낼 입력창을 찾을 수 없습니다.", true);
      return;
    }
    target.value = prompt;
    showToast("프롬프트를 보냈습니다.");
  });
});

async function copyReversePrompt() {
  const prompt = document.querySelector("#reverseOutput")?.value || "";
  if (!prompt.trim()) {
    showToast("복사할 프롬프트가 없습니다.", true);
    return;
  }
  await navigator.clipboard.writeText(prompt);
  showToast("프롬프트를 복사했습니다.");
}

document.querySelector("#copyReverseOutput")?.addEventListener("click", copyReversePrompt);

function promptTaskForEndpoint(endpoint) {
  return ({
    "/api/t2i": "image",
    "/api/i2i": "edit",
    "/api/i2v": "video",
    "/api/v2v-extend": "extend",
    "/api/v2v-frame-extend": "frame",
    "/api/manga-batch": "manga",
  })[endpoint] || "general";
}

function managedPromptForm() {
  return document.querySelector("#promptManagerForm");
}

function promptStructuredInputs() {
  return Array.from(document.querySelectorAll("[data-prompt-structured]"));
}

function managedPromptTextarea() {
  return document.querySelector("#managedPromptText");
}

function structuredPromptFromEditor() {
  const structured = {};
  promptStructuredInputs().forEach(input => {
    const key = input.dataset.promptStructured;
    const value = (input.value || "").trim();
    if (key && value) structured[key] = value;
  });
  return structured;
}

function composePrompt(structured) {
  const labels = {
    subject: "대상",
    scene: "장면",
    style: "스타일",
    lighting: "조명",
    camera: "카메라",
    keep: "유지",
    change: "변경",
    negative: "제외",
    extra: "추가 지시",
  };
  return Object.entries(labels)
    .map(([key, label]) => structured[key] ? `${label}: ${structured[key]}` : "")
    .filter(Boolean)
    .join("\n");
}

function syncManagedPromptFromStructured() {
  const text = managedPromptTextarea();
  if (!text) return;
  const next = composePrompt(structuredPromptFromEditor());
  if (!text.value.trim() || text.value === promptAutoValue) {
    text.value = next;
    promptAutoValue = next;
  }
}

function promptPayloadFromEditor() {
  const form = managedPromptForm();
  const structured = structuredPromptFromEditor();
  return {
    id: form?.elements.id?.value || "",
    title: form?.elements.title?.value || "",
    task: form?.elements.task?.value || "general",
    tags: form?.elements.tags?.value || "",
    favorite: Boolean(form?.elements.favorite?.checked),
    prompt: managedPromptTextarea()?.value || "",
    structured,
  };
}

function formatPromptTime(value) {
  const date = new Date(value || 0);
  if (!Number.isFinite(date.getTime())) return "";
  return date.toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function setPromptEditorItem(item = {}) {
  const form = managedPromptForm();
  if (!form) return;
  form.elements.id.value = item.id || "";
  form.elements.title.value = item.title || "";
  form.elements.task.value = item.task || "image";
  form.elements.tags.value = (item.tags || []).join(", ");
  form.elements.favorite.checked = Boolean(item.favorite);
  const structured = item.structured || {};
  promptStructuredInputs().forEach(input => {
    input.value = structured[input.dataset.promptStructured] || "";
  });
  const prompt = item.prompt || composePrompt(structured);
  const text = managedPromptTextarea();
  if (text) text.value = prompt;
  promptAutoValue = composePrompt(structured);
  promptSelectedId = item.id || "";
  document.querySelector("#promptSendTarget").value = promptTaskTarget[item.task || "general"] || "t2i";
  const meta = document.querySelector("#promptEditorMeta");
  if (meta) {
    const versionCount = item.version_count ?? (item.versions || []).length ?? 0;
    meta.textContent = item.id
      ? `저장됨 · ${promptTaskLabels[item.task] || item.task || "범용"} · 버전 ${versionCount} · 사용 ${item.usage_count || 0}회 · ${formatPromptTime(item.updated_at)}`
      : "새 프롬프트";
  }
  renderPromptList();
}

function resetPromptEditor(seed = {}) {
  setPromptEditorItem({
    id: "",
    title: seed.title || "",
    task: seed.task || "image",
    tags: seed.tags || [],
    favorite: Boolean(seed.favorite),
    prompt: seed.prompt || "",
    structured: seed.structured || {},
    version_count: 0,
    usage_count: 0,
  });
}

function filteredPrompts() {
  const query = promptSearch.trim().toLowerCase();
  return promptItems
    .filter(item => promptTaskFilter === "all" || item.task === promptTaskFilter)
    .filter(item => promptFavoriteFilter !== "favorite" || item.favorite)
    .filter(item => {
      if (!query) return true;
      const haystack = [
        item.title,
        item.prompt,
        item.task_label,
        ...(item.tags || []),
      ].filter(Boolean).join(" ").toLowerCase();
      return query.split(/\s+/).every(token => haystack.includes(token));
    })
    .sort((a, b) => Number(Boolean(b.favorite)) - Number(Boolean(a.favorite)) || new Date(b.updated_at || 0) - new Date(a.updated_at || 0));
}

function renderPromptList() {
  const list = document.querySelector("#promptList");
  if (!list) return;
  const items = filteredPrompts();
  const stats = document.querySelector("#promptStats");
  if (stats) stats.textContent = `${items.length} / ${promptItems.length}개`;
  if (!items.length) {
    list.innerHTML = `<p class="prompt-empty">저장된 프롬프트가 없습니다.</p>`;
    return;
  }
  list.innerHTML = items.map(item => `
    <article class="prompt-card${item.id === promptSelectedId ? " active" : ""}" data-prompt-id="${escapeHtml(item.id)}">
      <button type="button" class="favorite-button prompt-favorite${item.favorite ? " active" : ""}" data-prompt-favorite aria-label="즐겨찾기" aria-pressed="${item.favorite ? "true" : "false"}"></button>
      <div class="prompt-card-body">
        <strong>${escapeHtml(item.title || "프롬프트")}</strong>
        <small>${escapeHtml(promptTaskLabels[item.task] || item.task || "범용")} · ${formatPromptTime(item.updated_at)}</small>
        <p>${escapeHtml(item.prompt || "")}</p>
        <div class="prompt-tags">${(item.tags || []).slice(0, 5).map(tag => `<span>${escapeHtml(tag)}</span>`).join("")}</div>
      </div>
      <button type="button" class="secondary compact-btn" data-prompt-send>보내기</button>
    </article>
  `).join("");
}

async function loadPromptManager(force = false) {
  if (promptItems.length && !force) {
    renderPromptList();
    return;
  }
  const response = await fetch("/api/prompts");
  const data = await response.json();
  if (!data.ok) rememberApiError(data, "프롬프트 조회 실패");
  promptItems = data.items || [];
  renderPromptList();
  if (!promptSelectedId && promptItems.length) setPromptEditorItem(promptItems[0]);
}

async function savePromptEditor() {
  const payload = promptPayloadFromEditor();
  if (!payload.prompt.trim()) {
    showToast("저장할 프롬프트를 입력해 주세요.", true);
    return null;
  }
  const data = await postJson("/api/prompts", payload);
  const index = promptItems.findIndex(item => item.id === data.item.id);
  if (index >= 0) promptItems[index] = data.item;
  else promptItems.unshift(data.item);
  setPromptEditorItem(data.item);
  showToast(data.created ? "프롬프트를 저장했습니다." : "프롬프트를 업데이트했습니다.");
  return data.item;
}

function selectPromptById(id) {
  const item = promptItems.find(entry => entry.id === id);
  if (item) setPromptEditorItem(item);
}

async function deleteManagedPrompt() {
  const id = managedPromptForm()?.elements.id?.value || "";
  if (!id) {
    resetPromptEditor();
    return;
  }
  const data = await postJson("/api/prompts/delete", { ids: [id] });
  promptItems = promptItems.filter(item => item.id !== id);
  resetPromptEditor();
  renderPromptList();
  showToast(`${data.deleted || 0}개 프롬프트를 삭제했습니다.`);
}

async function togglePromptFavorite(id, button) {
  const item = promptItems.find(entry => entry.id === id);
  if (!item) return;
  const next = !item.favorite;
  setFavoriteButtonState(button, next, true);
  const data = await postJson("/api/prompts/favorite", { id, favorite: next });
  item.favorite = Boolean(data.favorite);
  item.updated_at = new Date().toISOString();
  setFavoriteButtonState(button, item.favorite, false);
  if (promptSelectedId === id) setPromptEditorItem(item);
  else renderPromptList();
}

async function markPromptUsed(id) {
  if (!id) return;
  try {
    const data = await postJson("/api/prompts/use", { id });
    const index = promptItems.findIndex(item => item.id === id);
    if (index >= 0) promptItems[index] = data.item;
  } catch {
    // Usage counters are helpful metadata, not required for sending prompts.
  }
}

async function sendPromptToTarget(targetId, prompt, itemId = "") {
  if (!String(prompt || "").trim()) {
    showToast("보낼 프롬프트가 없습니다.", true);
    return;
  }
  const targetPanel = document.querySelector(`#${targetId}`);
  const field = targetPanel?.querySelector("textarea[name='prompt']");
  if (!field) {
    showToast("프롬프트를 보낼 입력창을 찾을 수 없습니다.", true);
    return;
  }
  field.value = prompt;
  field.dispatchEvent(new Event("input", { bubbles: true }));
  await markPromptUsed(itemId);
  activateTab(targetId);
  showToast("프롬프트를 작업 화면으로 보냈습니다.");
}

async function saveCurrentPromptFromForm(form) {
  const field = form?.querySelector("textarea[name='prompt']");
  const prompt = field?.value || "";
  if (!prompt.trim()) {
    showToast("저장할 프롬프트를 입력해 주세요.", true);
    return;
  }
  const task = promptTaskForEndpoint(form.dataset.endpoint);
  const titleSeed = prompt.split(/\s+/).slice(0, 8).join(" ");
  const data = await postJson("/api/prompts", {
    title: `${promptTaskLabels[task] || "프롬프트"} · ${titleSeed}`.trim(),
    task,
    prompt,
    tags: [task],
  });
  const index = promptItems.findIndex(item => item.id === data.item.id);
  if (index >= 0) promptItems[index] = data.item;
  else promptItems.unshift(data.item);
  setPromptEditorItem(data.item);
  activateTab("prompts");
  showToast("현재 프롬프트를 보관했습니다.");
}

function draftPromptFromForm(form) {
  saveCurrentPromptFromForm(form).catch(error => showToast(error.message, true));
}

async function savePromptFromViewer() {
  const prompt = document.querySelector("#promptViewerText")?.textContent || "";
  if (!prompt.trim()) {
    showToast("저장할 프롬프트가 없습니다.", true);
    return;
  }
  const data = await postJson("/api/prompts", {
    title: prompt.split(/\s+/).slice(0, 8).join(" "),
    task: "general",
    prompt,
    tags: ["library"],
  });
  promptItems.unshift(data.item);
  setPromptEditorItem(data.item);
  closePromptViewer();
  activateTab("prompts");
  showToast("프롬프트를 보관했습니다.");
}

async function savePromptFromLibraryItem(item) {
  const data = await postJson("/api/prompts/from-library", { id: item.dataset.id });
  promptItems.unshift(data.item);
  setPromptEditorItem(data.item);
  activateTab("prompts");
  showToast("라이브러리 프롬프트를 보관했습니다.");
}

document.querySelector("#promptList")?.addEventListener("click", async event => {
  const card = event.target.closest(".prompt-card");
  if (!card) return;
  const id = card.dataset.promptId;
  const favorite = event.target.closest("[data-prompt-favorite]");
  if (favorite) {
    event.stopPropagation();
    try {
      await togglePromptFavorite(id, favorite);
    } catch (error) {
      showToast(error.message, true);
    }
    return;
  }
  if (event.target.closest("[data-prompt-send]")) {
    event.stopPropagation();
    const item = promptItems.find(entry => entry.id === id);
    if (item) await sendPromptToTarget(promptTaskTarget[item.task] || "t2i", item.prompt || "", item.id);
    return;
  }
  selectPromptById(id);
});

document.querySelector("#promptSearch")?.addEventListener("input", event => {
  promptSearch = event.target.value || "";
  renderPromptList();
});

document.querySelector("#promptTaskFilter")?.addEventListener("change", event => {
  promptTaskFilter = event.target.value || "all";
  renderPromptList();
});

document.querySelector("#promptFavoriteFilter")?.addEventListener("change", event => {
  promptFavoriteFilter = event.target.value || "all";
  renderPromptList();
});

promptStructuredInputs().forEach(input => input.addEventListener("input", syncManagedPromptFromStructured));

managedPromptTextarea()?.addEventListener("input", event => {
  if (event.target.value !== promptAutoValue) promptAutoValue = "";
});

managedPromptForm()?.addEventListener("submit", async event => {
  event.preventDefault();
  try {
    await savePromptEditor();
  } catch (error) {
    showToast(error.message, true);
  }
});

document.querySelector("#newPromptItem")?.addEventListener("click", () => resetPromptEditor());

document.querySelector("#duplicatePromptItem")?.addEventListener("click", () => {
  const payload = promptPayloadFromEditor();
  payload.id = "";
  payload.title = `${payload.title || "프롬프트"} 복사본`;
  resetPromptEditor(payload);
});

document.querySelector("#deletePromptItem")?.addEventListener("click", () => {
  deleteManagedPrompt().catch(error => showToast(error.message, true));
});

document.querySelector("#copyManagedPrompt")?.addEventListener("click", async () => {
  const prompt = managedPromptTextarea()?.value || "";
  if (!prompt.trim()) {
    showToast("복사할 프롬프트가 없습니다.", true);
    return;
  }
  await navigator.clipboard.writeText(prompt);
  showToast("프롬프트를 복사했습니다.");
});

document.querySelector("#sendManagedPrompt")?.addEventListener("click", () => {
  const prompt = managedPromptTextarea()?.value || "";
  const id = managedPromptForm()?.elements.id?.value || "";
  const target = document.querySelector("#promptSendTarget")?.value || "t2i";
  sendPromptToTarget(target, prompt, id).catch(error => showToast(error.message, true));
});

document.querySelector("#savePromptViewer")?.addEventListener("click", event => {
  event.stopPropagation();
  savePromptFromViewer().catch(error => showToast(error.message, true));
});

const templateMethodLabels = {
  i2v: "이미지→영상",
  frame: "프레임 연장",
  official: "공식 연장",
  image: "이미지 생성",
  edit: "이미지 편집",
};

const templateMethodUi = {
  image: {
    fields: new Set(["prompt", "retry", "notes"]),
    hint: "텍스트 프롬프트로 이미지를 생성하고, 다음 컷의 이미지 입력으로 넘깁니다.",
  },
  edit: {
    fields: new Set(["reference", "prompt", "retry", "notes"]),
    hint: "이미지 슬롯 또는 직전 이미지 결과를 편집합니다. 길이와 전환은 사용하지 않습니다.",
    referenceLabel: "이미지 슬롯",
    referencePlaceholder: "main_actor",
  },
  i2v: {
    fields: new Set(["duration", "reference", "transition", "prompt", "camera", "retry", "notes"]),
    hint: "이미지 슬롯 또는 직전 이미지 결과를 바탕으로 영상을 생성합니다.",
    referenceLabel: "이미지 슬롯",
    referencePlaceholder: "main_actor",
  },
  official: {
    fields: new Set(["duration", "reference", "transition", "prompt", "camera", "retry", "notes"]),
    hint: "영상 슬롯 또는 직전 영상 결과를 공식 연장으로 이어갑니다.",
    referenceLabel: "영상 슬롯",
    referencePlaceholder: "source_video",
  },
  frame: {
    fields: new Set(["duration", "reference", "transition", "prompt", "camera", "retry", "notes"]),
    hint: "영상 슬롯 또는 직전 영상 결과의 마지막 프레임을 기준으로 새 구간을 생성합니다.",
    referenceLabel: "영상 슬롯",
    referencePlaceholder: "source_video",
  },
};

const templateTransitionLabels = {
  cut: "컷",
  fade: "페이드",
  crossfade: "크로스페이드",
  fade_in: "페이드 인",
  fade_out: "페이드 아웃",
};

function videoTemplateForm() {
  return document.querySelector("#videoTemplateForm");
}

function templateDefaultItem(seed = {}) {
  return {
    id: seed.id || "",
    title: seed.title || "",
    description: seed.description || "",
    genre: seed.genre || "",
    tags: seed.tags || [],
    favorite: Boolean(seed.favorite),
    global_prompt: seed.global_prompt || "배우의 얼굴, 헤어스타일, 체형, 의상 톤을 일관되게 유지한다. 영화적인 조명과 자연스러운 움직임을 사용한다.",
    negative_prompt: seed.negative_prompt || "얼굴 변형, 다른 인물로 변경, 과도한 손가락 왜곡, 어색한 눈과 치아, 갑작스러운 의상 변경을 피한다.",
    variables: seed.variables || [
      { key: "mood", label: "분위기", default: "몽환적인" },
      { key: "location", label: "장소", default: "네온이 비치는 밤거리" },
      { key: "outfit", label: "의상", default: "검은 코트" },
    ],
    slots: seed.slots || [
      { key: "main_actor", label: "주연 배우", kind: "image", note: "얼굴과 헤어스타일 기준 사진" },
      { key: "location_ref", label: "장소 레퍼런스", kind: "image", note: "장소 분위기 참고 이미지" },
    ],
    shots: seed.shots || [
      {
        id: "",
        title: "오프닝 클로즈업",
        method: "i2v",
        duration: 6,
        reference_slot: "main_actor",
        prompt: "{{main_actor}}가 {{location}}에서 카메라를 바라본다. {{mood}} 분위기, {{outfit}}.",
        camera: "천천히 앞으로 다가가는 클로즈업",
        transition: "fade_in",
        retry_prompt: "",
        notes: "",
      },
      {
        id: "",
        title: "움직임 연결",
        method: "frame",
        duration: 6,
        reference_slot: "main_actor",
        prompt: "이전 장면의 감정과 자세를 이어서, {{main_actor}}가 천천히 걸어간다.",
        camera: "측면 트래킹 샷",
        transition: "crossfade",
        retry_prompt: "",
        notes: "",
      },
    ],
    settings: {
      target_duration: seed.settings?.target_duration || 60,
      aspect_ratio: seed.settings?.aspect_ratio || "9:16",
      resolution: seed.settings?.resolution || "720p",
      default_method: seed.settings?.default_method || "i2v",
      default_shot_duration: seed.settings?.default_shot_duration || 6,
    },
  };
}

function templateOptionList(labels, selected) {
  return Object.entries(labels)
    .map(([value, label]) => `<option value="${escapeHtml(value)}"${value === selected ? " selected" : ""}>${escapeHtml(label)}</option>`)
    .join("");
}

function templateMethodConfig(method) {
  return templateMethodUi[method] || templateMethodUi.i2v;
}

function applyTemplateShotMethodUi(row) {
  if (!row) return;
  const method = row.querySelector("[data-shot-method]")?.value || "i2v";
  const config = templateMethodConfig(method);
  row.dataset.templateMethod = method;
  row.querySelectorAll("[data-shot-field]").forEach(field => {
    field.hidden = !config.fields.has(field.dataset.shotField);
  });
  const hint = row.querySelector("[data-shot-method-hint]");
  if (hint) hint.textContent = config.hint;
  const referenceLabel = row.querySelector("[data-shot-reference-label]");
  if (referenceLabel) referenceLabel.textContent = config.referenceLabel || "참조 슬롯";
  const referenceInput = row.querySelector("[data-shot-reference]");
  if (referenceInput) referenceInput.placeholder = config.referencePlaceholder || "main_actor";
}

function syncTemplateShotMethodUi(root = document) {
  root.querySelectorAll("[data-template-shot]").forEach(applyTemplateShotMethodUi);
}

function renderTemplateVariables(items = []) {
  const list = document.querySelector("#templateVariables");
  if (!list) return;
  list.innerHTML = items.map(item => `
    <div class="template-mini-row" data-template-variable>
      <input type="text" data-var-key placeholder="key" value="${escapeHtml(item.key || "")}">
      <input type="text" data-var-label placeholder="라벨" value="${escapeHtml(item.label || "")}">
      <input type="text" data-var-default placeholder="기본값" value="${escapeHtml(item.default || "")}">
      <button type="button" class="icon-button" data-remove-template-row aria-label="삭제">×</button>
    </div>
  `).join("");
}

function renderTemplateSlots(items = []) {
  const list = document.querySelector("#templateSlots");
  if (!list) return;
  list.innerHTML = items.map(item => `
    <div class="template-mini-row template-slot-row" data-template-slot>
      <input type="text" data-slot-key placeholder="slot_key" value="${escapeHtml(item.key || "")}">
      <input type="text" data-slot-label placeholder="슬롯 이름" value="${escapeHtml(item.label || "")}">
      <select data-slot-kind>
        <option value="image"${(item.kind || "image") === "image" ? " selected" : ""}>이미지</option>
        <option value="video"${item.kind === "video" ? " selected" : ""}>영상</option>
        <option value="text"${item.kind === "text" ? " selected" : ""}>텍스트</option>
      </select>
      <input type="text" data-slot-note placeholder="설명" value="${escapeHtml(item.note || "")}">
      <button type="button" class="icon-button" data-remove-template-row aria-label="삭제">×</button>
    </div>
  `).join("");
}

function renderTemplateShots(items = []) {
  const list = document.querySelector("#templateShots");
  if (!list) return;
  list.innerHTML = items.map((item, index) => `
    <article class="template-shot-card" data-template-shot>
      <input type="hidden" data-shot-id value="${escapeHtml(item.id || "")}">
      <div class="template-shot-head">
        <span>${String(index + 1).padStart(2, "0")}</span>
        <input type="text" data-shot-title placeholder="컷 이름" value="${escapeHtml(item.title || `컷 ${index + 1}`)}">
        <button type="button" class="icon-button template-shot-drag" data-shot-drag-handle draggable="true" aria-label="드래그로 순서 변경">↕</button>
        <button type="button" class="icon-button" data-move-shot-up aria-label="위로">↑</button>
        <button type="button" class="icon-button" data-move-shot-down aria-label="아래로">↓</button>
        <button type="button" class="secondary shot-save-block" data-save-shot-block>블록 저장</button>
        <button type="button" class="icon-button" data-duplicate-shot aria-label="복제">⧉</button>
        <button type="button" class="icon-button" data-remove-template-row aria-label="삭제">×</button>
      </div>
      <div class="template-shot-grid">
        <div>
          <label>방식</label>
          <select data-shot-method>${templateOptionList(templateMethodLabels, item.method || "i2v")}</select>
        </div>
        <div data-shot-field="duration">
          <label>길이</label>
          <input type="number" data-shot-duration min="1" max="15" step="0.1" value="${escapeHtml(item.duration || 6)}">
        </div>
        <div data-shot-field="reference">
          <label data-shot-reference-label>참조 슬롯</label>
          <input type="text" data-shot-reference placeholder="main_actor" value="${escapeHtml(item.reference_slot || "")}">
        </div>
        <div data-shot-field="transition">
          <label>전환</label>
          <select data-shot-transition>${templateOptionList(templateTransitionLabels, item.transition || "cut")}</select>
        </div>
      </div>
      <p class="template-shot-method-hint" data-shot-method-hint></p>
      <div class="template-shot-field" data-shot-field="prompt">
        <label>컷 프롬프트</label>
        <textarea data-shot-prompt placeholder="{{main_actor}}가 {{location}}에서 움직인다.">${escapeHtml(item.prompt || "")}</textarea>
      </div>
      <div class="template-shot-field" data-shot-field="camera">
        <label>카메라</label>
        <input type="text" data-shot-camera placeholder="예: 느린 돌리 인, 핸드헬드, 측면 트래킹" value="${escapeHtml(item.camera || "")}">
      </div>
      <div class="template-shot-field" data-shot-field="retry">
        <label>실패 시 재시도 프롬프트</label>
        <textarea data-shot-retry placeholder="실패한 컷을 재시도할 때 쓸 대체 지시">${escapeHtml(item.retry_prompt || "")}</textarea>
      </div>
      <div class="template-shot-field" data-shot-field="notes">
        <label>메모</label>
        <textarea data-shot-notes placeholder="작업자가 기억할 참고 사항">${escapeHtml(item.notes || "")}</textarea>
      </div>
    </article>
  `).join("");
  syncTemplateShotMethodUi(list);
}

function collectTemplateVariables() {
  return Array.from(document.querySelectorAll("[data-template-variable]")).map(row => ({
    key: row.querySelector("[data-var-key]")?.value || "",
    label: row.querySelector("[data-var-label]")?.value || "",
    default: row.querySelector("[data-var-default]")?.value || "",
  })).filter(item => item.key.trim() || item.label.trim() || item.default.trim());
}

function collectTemplateSlots() {
  return Array.from(document.querySelectorAll("[data-template-slot]")).map(row => ({
    key: row.querySelector("[data-slot-key]")?.value || "",
    label: row.querySelector("[data-slot-label]")?.value || "",
    kind: row.querySelector("[data-slot-kind]")?.value || "image",
    note: row.querySelector("[data-slot-note]")?.value || "",
  })).filter(item => item.key.trim() || item.label.trim() || item.note.trim());
}

function collectTemplateShots() {
  return Array.from(document.querySelectorAll("[data-template-shot]")).map((row, index) => ({
    id: row.querySelector("[data-shot-id]")?.value || "",
    order: index + 1,
    title: row.querySelector("[data-shot-title]")?.value || `컷 ${index + 1}`,
    method: row.querySelector("[data-shot-method]")?.value || "i2v",
    duration: Number.parseFloat(row.querySelector("[data-shot-duration]")?.value || "6") || 6,
    reference_slot: row.querySelector("[data-shot-reference]")?.value || "",
    transition: row.querySelector("[data-shot-transition]")?.value || "cut",
    prompt: row.querySelector("[data-shot-prompt]")?.value || "",
    camera: row.querySelector("[data-shot-camera]")?.value || "",
    retry_prompt: row.querySelector("[data-shot-retry]")?.value || "",
    notes: row.querySelector("[data-shot-notes]")?.value || "",
  })).filter(item => item.title.trim() || item.prompt.trim());
}

function templatePayloadFromEditor() {
  const form = videoTemplateForm();
  const settings = {
    target_duration: Number.parseInt(form?.elements.target_duration?.value || "60", 10) || 60,
    aspect_ratio: form?.elements.aspect_ratio?.value || "9:16",
    resolution: form?.elements.resolution?.value || "720p",
    default_method: form?.elements.default_method?.value || "i2v",
    default_shot_duration: Number.parseFloat(form?.elements.default_shot_duration?.value || "6") || 6,
  };
  return {
    id: form?.elements.id?.value || "",
    title: form?.elements.title?.value || "",
    description: form?.elements.description?.value || "",
    genre: form?.elements.genre?.value || "",
    tags: form?.elements.tags?.value || "",
    favorite: Boolean(form?.elements.favorite?.checked),
    global_prompt: form?.elements.global_prompt?.value || "",
    negative_prompt: form?.elements.negative_prompt?.value || "",
    settings,
    variables: collectTemplateVariables(),
    slots: collectTemplateSlots(),
    shots: collectTemplateShots(),
  };
}

function substituteTemplateText(text, variables, slots) {
  const variableMap = Object.fromEntries(variables.map(item => [String(item.key || "").trim(), item.default || ""]));
  const slotMap = Object.fromEntries(slots.map(item => [String(item.key || "").trim(), item.label || item.key || "레퍼런스"]));
  return String(text || "").replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (match, key) => {
    if (Object.prototype.hasOwnProperty.call(variableMap, key)) return variableMap[key] || match;
    if (Object.prototype.hasOwnProperty.call(slotMap, key)) return `[${slotMap[key]}]`;
    return match;
  });
}

function templateShotPromptText(payload, shot) {
  const variables = payload.variables || [];
  const slots = payload.slots || [];
  const chunks = [
    payload.global_prompt,
    shot.prompt,
    shot.camera ? `카메라: ${shot.camera}` : "",
    shot.reference_slot ? `참조 슬롯: {{${shot.reference_slot}}}` : "",
    payload.negative_prompt ? `제외/주의: ${payload.negative_prompt}` : "",
  ].filter(Boolean);
  return substituteTemplateText(chunks.join("\n"), variables, slots);
}

function templateSlotLabel(slot, selected) {
  if (selected?.label) return selected.label;
  if (selected?.path) return selected.path.split("/").pop();
  return slot.label || slot.key || "slot";
}

function syncTemplateRunDefaults(payload = templatePayloadFromEditor()) {
  (payload.variables || []).forEach(variable => {
    if (!variable.key) return;
    if (!Object.prototype.hasOwnProperty.call(templateRunState.variables, variable.key)) {
      templateRunState.variables[variable.key] = variable.default || "";
    }
  });
}

function resetTemplateRunState(payload = templatePayloadFromEditor()) {
  templateRunState.variables = {};
  templateRunState.slots = {};
  templateRunState.mode = "auto";
  (payload.variables || []).forEach(variable => {
    if (variable.key) templateRunState.variables[variable.key] = variable.default || "";
  });
}

function templateRuntimePayload() {
  const payload = templatePayloadFromEditor();
  syncTemplateRunDefaults(payload);
  const variables = (payload.variables || []).map(variable => ({
    ...variable,
    default: templateRunState.variables[variable.key] ?? variable.default ?? "",
  }));
  const slots = (payload.slots || []).map(slot => {
    const selected = templateRunState.slots[slot.key];
    return {
      ...slot,
      label: templateSlotLabel(slot, selected),
      selected_path: selected?.path || "",
      selected_kind: selected?.kind || slot.kind || "image",
    };
  });
  return { ...payload, variables, slots, run_mode: templateRunState.mode === "manual" ? "manual" : "auto" };
}

function renderTemplateRunPanel() {
  const payload = templatePayloadFromEditor();
  syncTemplateRunDefaults(payload);
  const variables = document.querySelector("#templateRunVariables");
  const slots = document.querySelector("#templateRunSlots");
  const note = document.querySelector("#templateRunNote");
  const mode = document.querySelector("#templateRunMode");
  if (mode) mode.value = templateRunState.mode === "manual" ? "manual" : "auto";
  if (variables) {
    variables.innerHTML = (payload.variables || []).length
      ? payload.variables.map(variable => `
        <label class="template-run-var">
          <span>${escapeHtml(variable.label || variable.key)}</span>
          <input type="text" data-template-run-var="${escapeHtml(variable.key)}" value="${escapeHtml(templateRunState.variables[variable.key] ?? variable.default ?? "")}">
        </label>`).join("")
      : `<p class="template-empty">변수가 없습니다. 기본 프롬프트 그대로 실행됩니다.</p>`;
  }
  if (slots) {
    slots.innerHTML = (payload.slots || []).length
      ? payload.slots.map(slot => {
        const selected = templateRunState.slots[slot.key];
        const kind = slot.kind === "video" ? "video" : "image";
        const preview = selected
          ? (kind === "video"
            ? `<video src="${selected.path}" muted playsinline loop></video>`
            : `<img src="${selected.path}" alt="">`)
          : `<span class="template-slot-empty">${kind === "video" ? "영상 미선택" : "이미지 미선택"}</span>`;
        return `
          <article class="template-run-slot" data-template-run-slot="${escapeHtml(slot.key)}">
            <button type="button" class="template-slot-preview" data-template-slot-preview ${selected ? "" : "disabled"}>${preview}</button>
            <div>
              <strong>${escapeHtml(slot.label || slot.key)}</strong>
              <small>${escapeHtml(slot.key)} · ${kind}${slot.note ? ` · ${escapeHtml(slot.note)}` : ""}</small>
              <div class="template-slot-actions">
                <button type="button" class="secondary" data-template-slot-pick data-template-slot-kind="${kind}">라이브러리</button>
                <button type="button" class="secondary" data-template-slot-clear ${selected ? "" : "disabled"}>해제</button>
              </div>
            </div>
          </article>`;
      }).join("")
      : `<p class="template-empty">레퍼런스 슬롯이 없습니다. 이전 컷 결과 위주로 실행됩니다.</p>`;
  }
  if (note) {
    const first = payload.shots?.[0];
    const needsReference = first && ["edit", "i2v", "official", "frame"].includes(first.method);
    note.textContent = payload.shots?.length
      ? `${payload.shots.length}개 컷을 ${templateRunState.mode === "manual" ? "수동 확인" : "자동"}으로 순차 실행합니다.${needsReference ? " 첫 컷에 필요한 이미지/영상 슬롯이 없으면 실행 시 오류가 납니다." : ""}`
      : "컷을 추가하면 실행할 수 있습니다.";
  }
}

function renderTemplatePreview() {
  const payload = templatePayloadFromEditor();
  const stats = document.querySelector("#templatePreviewStats");
  const preview = document.querySelector("#templatePreview");
  const totalDuration = payload.shots.reduce((sum, shot) => sum + (Number(shot.duration) || 0), 0);
  if (stats) {
    stats.innerHTML = `
      <span>${payload.shots.length} 컷</span>
      <span>${Math.round(totalDuration * 10) / 10}초</span>
      <span>요청 ${payload.shots.length}개 예상</span>
      <span>${escapeHtml(payload.settings.aspect_ratio)} · ${escapeHtml(payload.settings.resolution)}</span>
    `;
  }
  if (!preview) return;
  if (!payload.shots.length) {
    preview.innerHTML = `<p class="template-empty">컷을 추가하면 적용 미리보기가 표시됩니다.</p>`;
    renderTemplateRunPanel();
    return;
  }
  preview.innerHTML = payload.shots.map((shot, index) => {
    const prompt = templateShotPromptText(payload, shot);
    return `
      <article class="template-preview-shot" data-template-preview-shot="${index}" role="button" tabindex="0" aria-label="${escapeHtml(`${index + 1}번 컷 편집 위치로 이동`)}">
        <header>
          <strong>${String(index + 1).padStart(2, "0")} · ${escapeHtml(shot.title || "컷")}</strong>
          <span>${escapeHtml(templateMethodLabels[shot.method] || shot.method)} · ${escapeHtml(String(shot.duration || 0))}초 · ${escapeHtml(templateTransitionLabels[shot.transition] || shot.transition)}</span>
          <i class="template-preview-drag" data-preview-drag-handle draggable="true" aria-label="드래그로 컷 순서 변경">↕</i>
        </header>
        <pre>${escapeHtml(prompt)}</pre>
      </article>
    `;
  }).join("");
  renderTemplateRunPanel();
}

function focusTemplateShot(index) {
  const shots = Array.from(document.querySelectorAll("[data-template-shot]"));
  const shot = shots[index];
  if (!shot) {
    showToast("편집할 컷을 찾을 수 없습니다.", true);
    return;
  }
  shots.forEach(node => node.classList.remove("is-focused"));
  shot.classList.add("is-focused");
  shot.scrollIntoView({ behavior: "smooth", block: "center" });
  shot.querySelector("[data-shot-title]")?.focus({ preventScroll: true });
  if (templateShotFocusTimer) clearTimeout(templateShotFocusTimer);
  templateShotFocusTimer = setTimeout(() => {
    shot.classList.remove("is-focused");
    templateShotFocusTimer = null;
  }, 1800);
}

function templateShotDragTarget(list, clientY) {
  const selector = list?.id === "templatePreview" ? "[data-template-preview-shot]" : "[data-template-shot]";
  return Array.from(list.querySelectorAll(`${selector}:not(.is-dragging)`)).find(card => {
    const box = card.getBoundingClientRect();
    return clientY < box.top + (box.height / 2);
  });
}

function templateShotRects(list) {
  const selector = list?.id === "templatePreview" ? "[data-template-preview-shot]" : "[data-template-shot]";
  const rects = new Map();
  list?.querySelectorAll(selector).forEach(card => {
    rects.set(card, card.getBoundingClientRect());
  });
  return rects;
}

function animateTemplateShotMove(list, beforeRects) {
  if (!list || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const selector = list.id === "templatePreview" ? "[data-template-preview-shot]" : "[data-template-shot]";
  list.querySelectorAll(`${selector}:not(.is-dragging)`).forEach(card => {
    const before = beforeRects.get(card);
    if (!before) return;
    const after = card.getBoundingClientRect();
    const deltaX = before.left - after.left;
    const deltaY = before.top - after.top;
    if (Math.abs(deltaX) < 1 && Math.abs(deltaY) < 1) return;
    card.getAnimations?.().forEach(animation => animation.cancel());
    card.animate([
      { transform: `translate(${deltaX}px, ${deltaY}px)` },
      { transform: "translate(0, 0)" },
    ], {
      duration: 180,
      easing: "cubic-bezier(.2, .8, .2, 1)",
    });
  });
}

function moveTemplateShotWithAnimation(list, move) {
  const before = templateShotRects(list);
  move();
  animateTemplateShotMove(list, before);
}

function templateShotScrollParent(node) {
  let current = node?.parentElement;
  while (current && current !== document.body) {
    const style = getComputedStyle(current);
    if (/(auto|scroll)/.test(style.overflowY) && current.scrollHeight > current.clientHeight) {
      return current;
    }
    current = current.parentElement;
  }
  return document.scrollingElement || document.documentElement;
}

function stopTemplateShotAutoScroll(list) {
  templateShotAutoScrollVelocity = 0;
  templateShotAutoScrollTarget = null;
  list?.classList.remove("is-autoscroll-up", "is-autoscroll-down");
  if (templateShotAutoScrollFrame) {
    cancelAnimationFrame(templateShotAutoScrollFrame);
    templateShotAutoScrollFrame = null;
  }
}

function startTemplateShotAutoScroll() {
  if (templateShotAutoScrollFrame) return;
  const tick = () => {
    if (!templateShotAutoScrollTarget || !templateShotAutoScrollVelocity) {
      templateShotAutoScrollFrame = null;
      return;
    }
    templateShotAutoScrollTarget.scrollTop += templateShotAutoScrollVelocity;
    templateShotAutoScrollFrame = requestAnimationFrame(tick);
  };
  templateShotAutoScrollFrame = requestAnimationFrame(tick);
}

function updateTemplateShotAutoScroll(list, clientY) {
  const scroller = templateShotScrollParent(list);
  const box = scroller === document.scrollingElement || scroller === document.documentElement
    ? { top: 0, bottom: window.innerHeight }
    : scroller.getBoundingClientRect();
  const edge = Math.min(96, Math.max(48, (box.bottom - box.top) * 0.18));
  const topDistance = clientY - box.top;
  const bottomDistance = box.bottom - clientY;
  let velocity = 0;
  if (topDistance < edge) velocity = -Math.ceil((1 - Math.max(0, topDistance) / edge) * 22);
  else if (bottomDistance < edge) velocity = Math.ceil((1 - Math.max(0, bottomDistance) / edge) * 22);
  templateShotAutoScrollTarget = scroller;
  templateShotAutoScrollVelocity = velocity;
  list?.classList.toggle("is-autoscroll-up", velocity < 0);
  list?.classList.toggle("is-autoscroll-down", velocity > 0);
  if (velocity) startTemplateShotAutoScroll();
  else stopTemplateShotAutoScroll(list);
}

function finishTemplateShotDrag(list) {
  if (!list) return;
  const dragging = list.querySelector("[data-template-shot].is-dragging");
  stopTemplateShotAutoScroll(list);
  list.classList.remove("is-drop-active");
  dragging?.classList.remove("is-dragging");
  renderTemplateShots(collectTemplateShots());
  renderTemplatePreview();
}

function templatePreviewOrder() {
  return Array.from(document.querySelectorAll("#templatePreview [data-template-preview-shot]"))
    .map(node => Number.parseInt(node.dataset.templatePreviewShot || "-1", 10))
    .filter(index => Number.isInteger(index) && index >= 0);
}

function applyTemplatePreviewOrder() {
  const order = templatePreviewOrder();
  const shots = collectTemplateShots();
  if (order.length !== shots.length) {
    renderTemplatePreview();
    return;
  }
  const used = new Set();
  const reordered = [];
  order.forEach(index => {
    if (used.has(index) || !shots[index]) return;
    used.add(index);
    reordered.push(shots[index]);
  });
  if (reordered.length !== shots.length) {
    renderTemplatePreview();
    return;
  }
  renderTemplateShots(reordered);
  renderTemplatePreview();
}

function finishTemplatePreviewDrag(list) {
  if (!list) return;
  const dragging = list.querySelector("[data-template-preview-shot].is-dragging");
  stopTemplateShotAutoScroll(list);
  list.classList.remove("is-drop-active");
  dragging?.classList.remove("is-dragging");
  if (dragging) applyTemplatePreviewOrder();
}

function setTemplateEditorItem(item = {}) {
  const form = videoTemplateForm();
  if (!form) return;
  const data = templateDefaultItem(item);
  resetTemplateRunState(data);
  form.elements.id.value = data.id || "";
  form.elements.title.value = data.title || "";
  form.elements.description.value = data.description || "";
  form.elements.genre.value = data.genre || "";
  form.elements.tags.value = (data.tags || []).join(", ");
  form.elements.favorite.checked = Boolean(data.favorite);
  form.elements.target_duration.value = data.settings.target_duration || 60;
  form.elements.default_shot_duration.value = data.settings.default_shot_duration || 6;
  form.elements.aspect_ratio.value = data.settings.aspect_ratio || "9:16";
  form.elements.resolution.value = data.settings.resolution || "720p";
  form.elements.default_method.value = data.settings.default_method || "i2v";
  form.elements.global_prompt.value = data.global_prompt || "";
  form.elements.negative_prompt.value = data.negative_prompt || "";
  renderTemplateVariables(data.variables || []);
  renderTemplateSlots(data.slots || []);
  renderTemplateShots(data.shots || []);
  templateSelectedId = data.id || "";
  const meta = document.querySelector("#templateEditorMeta");
  if (meta) {
    const total = data.stats?.total_duration ?? (data.shots || []).reduce((sum, shot) => sum + (Number(shot.duration) || 0), 0);
    meta.textContent = data.id
      ? `저장됨 · ${data.shots?.length || 0}컷 · ${Math.round(total * 10) / 10}초 · ${formatPromptTime(data.updated_at)}`
      : "새 템플릿";
  }
  renderTemplateList();
  renderTemplatePreview();
}

function resetTemplateEditor(seed = {}) {
  setTemplateEditorItem(templateDefaultItem(seed));
}

function filteredTemplates() {
  const query = templateSearch.trim().toLowerCase();
  return templateItems
    .filter(item => !templateFavoriteOnly || item.favorite)
    .filter(item => {
      if (!query) return true;
      const haystack = [
        item.title,
        item.description,
        item.genre,
        item.global_prompt,
        ...(item.tags || []),
        ...(item.shots || []).map(shot => `${shot.title} ${shot.prompt}`),
      ].filter(Boolean).join(" ").toLowerCase();
      return query.split(/\s+/).every(token => haystack.includes(token));
    })
    .sort((a, b) => Number(Boolean(b.favorite)) - Number(Boolean(a.favorite)) || new Date(b.updated_at || 0) - new Date(a.updated_at || 0));
}

function renderTemplateList() {
  const list = document.querySelector("#templateList");
  if (!list) return;
  const items = filteredTemplates();
  const stats = document.querySelector("#templateStats");
  const favoriteFilter = document.querySelector("#templateFavoriteOnly");
  if (favoriteFilter) {
    favoriteFilter.classList.toggle("active", templateFavoriteOnly);
    favoriteFilter.setAttribute("aria-pressed", templateFavoriteOnly ? "true" : "false");
    favoriteFilter.title = templateFavoriteOnly ? "전체 템플릿 보기" : "즐겨찾기만 보기";
  }
  if (stats) stats.textContent = templateFavoriteOnly
    ? `즐겨찾기 ${items.length} / 전체 ${templateItems.length}개`
    : `${items.length} / ${templateItems.length}개`;
  if (!items.length) {
    list.innerHTML = `<p class="prompt-empty">${templateFavoriteOnly ? "즐겨찾기 템플릿이 없습니다." : "저장된 영상 템플릿이 없습니다."}</p>`;
    return;
  }
  list.innerHTML = items.map(item => `
    <article class="template-card${item.id === templateSelectedId ? " active" : ""}" data-template-id="${escapeHtml(item.id)}">
      <button type="button" class="favorite-button template-favorite${item.favorite ? " active" : ""}" data-template-favorite aria-label="즐겨찾기" aria-pressed="${item.favorite ? "true" : "false"}"></button>
      <div class="template-card-body">
        <strong>${escapeHtml(item.title || "영상 템플릿")}</strong>
        <small>${escapeHtml(item.genre || "장르 없음")} · ${item.stats?.shot_count || 0}컷 · ${Math.round((item.stats?.total_duration || 0) * 10) / 10}초 · ${formatPromptTime(item.updated_at)}</small>
        <p>${escapeHtml(item.description || item.global_prompt || "")}</p>
        <div class="prompt-tags">${(item.tags || []).slice(0, 5).map(tag => `<span>${escapeHtml(tag)}</span>`).join("")}</div>
      </div>
    </article>
  `).join("");
}

function templateBlockToShot(block = {}) {
  return {
    id: "",
    title: block.title || "컷 블록",
    method: block.method || "i2v",
    duration: block.duration || 6,
    reference_slot: block.reference_slot || "",
    transition: block.transition || "cut",
    prompt: block.prompt || "",
    camera: block.camera || "",
    retry_prompt: block.retry_prompt || "",
    notes: block.notes || "",
  };
}

function filteredTemplateBlocks() {
  const query = templateBlockSearch.trim().toLowerCase();
  return templateBlocks
    .filter(item => !templateBlockFavoriteOnly || item.favorite)
    .filter(item => {
      if (!query) return true;
      const haystack = [
        item.title,
        item.method_label,
        item.reference_slot,
        item.prompt,
        item.camera,
        item.notes,
        item.source_template_title,
        ...(item.tags || []),
      ].filter(Boolean).join(" ").toLowerCase();
      return query.split(/\s+/).every(token => haystack.includes(token));
    })
    .sort((a, b) => Number(Boolean(b.favorite)) - Number(Boolean(a.favorite)) || new Date(b.updated_at || 0) - new Date(a.updated_at || 0));
}

function renderTemplateBlocks() {
  const list = document.querySelector("#templateBlockList");
  if (!list) return;
  const items = filteredTemplateBlocks();
  const stats = document.querySelector("#templateBlockStats");
  const favoriteFilter = document.querySelector("#templateBlockFavoriteOnly");
  if (favoriteFilter) {
    favoriteFilter.classList.toggle("active", templateBlockFavoriteOnly);
    favoriteFilter.setAttribute("aria-pressed", templateBlockFavoriteOnly ? "true" : "false");
    favoriteFilter.title = templateBlockFavoriteOnly ? "전체 블록 보기" : "즐겨찾기만 보기";
  }
  if (stats) stats.textContent = templateBlockFavoriteOnly
    ? `즐겨찾기 ${items.length} / 전체 ${templateBlocks.length}개`
    : `${items.length} / ${templateBlocks.length}개`;
  if (!items.length) {
    list.innerHTML = `<p class="prompt-empty">${templateBlockFavoriteOnly ? "즐겨찾기 블록이 없습니다." : "저장된 블록이 없습니다. 컷 카드에서 블록 저장을 눌러 추가하세요."}</p>`;
    return;
  }
  list.innerHTML = items.map(item => `
    <article class="template-block-card" data-template-block-id="${escapeHtml(item.id)}">
      <button type="button" class="favorite-button template-block-favorite${item.favorite ? " active" : ""}" data-template-block-favorite aria-label="즐겨찾기" aria-pressed="${item.favorite ? "true" : "false"}"></button>
      <div class="template-block-body">
        <strong>${escapeHtml(item.title || "컷 블록")}</strong>
        <small>${escapeHtml(item.method_label || item.method || "방식 없음")} · ${escapeHtml(item.reference_slot || "참조 없음")} · ${Math.round((Number(item.duration) || 0) * 10) / 10}초</small>
        <p>${escapeHtml(item.prompt || item.camera || item.notes || "")}</p>
      </div>
      <div class="template-block-actions">
        <button type="button" class="secondary" data-template-block-add>추가</button>
        <button type="button" class="danger-btn" data-template-block-delete>삭제</button>
      </div>
    </article>
  `).join("");
}

async function loadTemplateManager(force = false) {
  loadTemplateBlocks(force).catch(error => showToast(error.message, true));
  if (templateItems.length && !force) {
    renderTemplateList();
    if (!templateSelectedId) resetTemplateEditor();
    return;
  }
  const response = await fetch("/api/video-templates");
  const data = await response.json();
  if (!data.ok) rememberApiError(data, "영상 템플릿 조회 실패");
  templateItems = data.items || [];
  renderTemplateList();
  if (!templateSelectedId && templateItems.length) setTemplateEditorItem(templateItems[0]);
  if (!templateItems.length) resetTemplateEditor();
}

async function loadTemplateBlocks(force = false) {
  if (templateBlocks.length && !force) {
    renderTemplateBlocks();
    return;
  }
  const response = await fetch("/api/video-template-blocks");
  const data = await response.json();
  if (!data.ok) rememberApiError(data, "템플릿 블록 조회 실패");
  templateBlocks = data.items || [];
  renderTemplateBlocks();
}

async function saveTemplateEditor() {
  const payload = templatePayloadFromEditor();
  if (!payload.title.trim()) {
    showToast("템플릿 이름을 입력해 주세요.", true);
    return null;
  }
  if (!payload.shots.length) {
    showToast("컷 블록을 1개 이상 추가해 주세요.", true);
    return null;
  }
  const data = await postJson("/api/video-templates", payload);
  const index = templateItems.findIndex(item => item.id === data.item.id);
  if (index >= 0) templateItems[index] = data.item;
  else templateItems.unshift(data.item);
  setTemplateEditorItem(data.item);
  showToast(data.created ? "영상 템플릿을 저장했습니다." : "영상 템플릿을 업데이트했습니다.");
  return data.item;
}

async function saveTemplatePayload(payload, quiet = false) {
  const data = await postJson("/api/video-templates", payload);
  const index = templateItems.findIndex(item => item.id === data.item.id);
  if (index >= 0) templateItems[index] = data.item;
  else templateItems.unshift(data.item);
  if (templateSelectedId === data.item.id) setTemplateEditorItem(data.item);
  else renderTemplateList();
  if (!quiet) showToast(data.created ? "영상 템플릿을 저장했습니다." : "영상 템플릿을 업데이트했습니다.");
  return data.item;
}

async function toggleTemplateFavorite(id, button) {
  const item = templateItems.find(entry => entry.id === id);
  if (!item) return;
  const next = !item.favorite;
  setFavoriteButtonState(button, next, true);
  const updated = await saveTemplatePayload({ ...item, favorite: next }, true);
  setFavoriteButtonState(button, Boolean(updated.favorite), false);
  if (templateSelectedId === id) setTemplateEditorItem(updated);
  else renderTemplateList();
}

function templateShotBlockPayload(shot, index) {
  const payload = templatePayloadFromEditor();
  const tags = [...(payload.tags || [])];
  if (payload.genre) tags.push(payload.genre);
  return {
    id: "",
    title: shot.title || `컷 ${index + 1}`,
    method: shot.method || payload.settings.default_method || "i2v",
    duration: shot.duration || payload.settings.default_shot_duration || 6,
    reference_slot: shot.reference_slot || "",
    transition: shot.transition || "cut",
    prompt: shot.prompt || "",
    camera: shot.camera || "",
    retry_prompt: shot.retry_prompt || "",
    notes: shot.notes || "",
    tags,
    favorite: false,
    source_template_id: payload.id || "",
    source_template_title: payload.title || "",
    source_shot_id: shot.id || "",
  };
}

async function saveTemplateShotBlock(index, button) {
  const shots = collectTemplateShots();
  const shot = shots[index];
  if (!shot) {
    showToast("저장할 컷을 찾을 수 없습니다.", true);
    return;
  }
  const previousDisabled = button?.disabled;
  if (button) button.disabled = true;
  try {
    const data = await postJson("/api/video-template-blocks", templateShotBlockPayload(shot, index));
    const existing = templateBlocks.findIndex(item => item.id === data.item.id);
    if (existing >= 0) templateBlocks[existing] = data.item;
    else templateBlocks.unshift(data.item);
    renderTemplateBlocks();
    showToast("컷 블록을 보관했습니다.");
  } finally {
    if (button) button.disabled = previousDisabled;
  }
}

async function toggleTemplateBlockFavorite(id, button) {
  const item = templateBlocks.find(entry => entry.id === id);
  if (!item) return;
  const next = !item.favorite;
  setFavoriteButtonState(button, next, true);
  const data = await postJson("/api/video-template-blocks", { ...item, favorite: next });
  const index = templateBlocks.findIndex(entry => entry.id === id);
  if (index >= 0) templateBlocks[index] = data.item;
  setFavoriteButtonState(button, Boolean(data.item.favorite), false);
  renderTemplateBlocks();
}

async function deleteTemplateBlock(id) {
  const data = await postJson("/api/video-template-blocks/delete", { ids: [id] });
  templateBlocks = templateBlocks.filter(item => item.id !== id);
  renderTemplateBlocks();
  showToast(`${data.deleted || 0}개 블록을 삭제했습니다.`);
}

function addTemplateBlockToEditor(id) {
  const block = templateBlocks.find(item => item.id === id);
  if (!block) {
    showToast("추가할 블록을 찾을 수 없습니다.", true);
    return;
  }
  renderTemplateShots([...collectTemplateShots(), templateBlockToShot(block)]);
  renderTemplatePreview();
  showToast("블록을 현재 템플릿에 추가했습니다.");
}

async function deleteTemplateEditor() {
  const id = videoTemplateForm()?.elements.id?.value || "";
  if (!id) {
    resetTemplateEditor();
    return;
  }
  const data = await postJson("/api/video-templates/delete", { ids: [id] });
  templateItems = templateItems.filter(item => item.id !== id);
  templateSelectedId = "";
  if (templateItems.length) setTemplateEditorItem(templateItems[0]);
  else resetTemplateEditor();
  renderTemplateList();
  showToast(`${data.deleted || 0}개 템플릿을 삭제했습니다.`);
}

function sanitizeTemplateFileName(title) {
  const safe = String(title || "webgui-template")
    .replace(/[\\/:*?"<>|]+/g, "-")
    .replace(/\s+/g, "_")
    .replace(/_+/g, "_")
    .slice(0, 80);
  return safe || "webgui-template";
}

function exportCurrentTemplate() {
  const payload = templatePayloadFromEditor();
  if (!payload.title.trim()) {
    showToast("내보낼 템플릿 이름을 입력해 주세요.", true);
    return;
  }
  const exportData = {
    format: "webgui.v3.video_template",
    exported_at: new Date().toISOString(),
    template: payload,
  };
  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${sanitizeTemplateFileName(payload.title)}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  showToast("템플릿 JSON을 내보냈습니다.");
}

function templatesFromImportData(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.templates)) return data.templates;
  if (data?.template && typeof data.template === "object") return [data.template];
  if (data?.item && typeof data.item === "object") return [data.item];
  if (data && typeof data === "object") return [data];
  return [];
}

async function importTemplateFile(file) {
  if (!file) return;
  const text = await file.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch (error) {
    throw new Error("JSON 템플릿 파일을 읽을 수 없습니다.");
  }
  const imported = templatesFromImportData(data).filter(item => item && typeof item === "object");
  if (!imported.length) throw new Error("가져올 템플릿이 없습니다.");
  const saved = [];
  for (const item of imported) {
    const copy = {
      ...item,
      id: "",
      title: item.title ? `${item.title}` : "가져온 영상 템플릿",
    };
    saved.push(await saveTemplatePayload(copy, true));
  }
  if (saved.length) setTemplateEditorItem(saved[0]);
  renderTemplateList();
  showToast(`${saved.length}개 템플릿을 불러왔습니다.`);
}

function templatePreviewPlainText() {
  const payload = templatePayloadFromEditor();
  return payload.shots.map((shot, index) => [
    `# ${String(index + 1).padStart(2, "0")} ${shot.title || "컷"}`,
    `방식: ${templateMethodLabels[shot.method] || shot.method}`,
    `길이: ${shot.duration || 0}초`,
    `전환: ${templateTransitionLabels[shot.transition] || shot.transition}`,
    templateShotPromptText(payload, shot),
  ].filter(Boolean).join("\n")).join("\n\n");
}

document.querySelector("#templateList")?.addEventListener("click", event => {
  const card = event.target.closest("[data-template-id]");
  if (!card) return;
  const favorite = event.target.closest("[data-template-favorite]");
  if (favorite) {
    event.stopPropagation();
    toggleTemplateFavorite(card.dataset.templateId, favorite).catch(error => showToast(error.message, true));
    return;
  }
  const item = templateItems.find(entry => entry.id === card.dataset.templateId);
  if (item) setTemplateEditorItem(item);
});

document.querySelector("#templateSearch")?.addEventListener("input", event => {
  templateSearch = event.target.value || "";
  renderTemplateList();
});

document.querySelector("#templateFavoriteOnly")?.addEventListener("click", event => {
  templateFavoriteOnly = !templateFavoriteOnly;
  event.currentTarget.classList.toggle("active", templateFavoriteOnly);
  event.currentTarget.setAttribute("aria-pressed", templateFavoriteOnly ? "true" : "false");
  renderTemplateList();
});

document.querySelector("#templateBlockSearch")?.addEventListener("input", event => {
  templateBlockSearch = event.target.value || "";
  renderTemplateBlocks();
});

document.querySelector("#templateBlockFavoriteOnly")?.addEventListener("click", event => {
  templateBlockFavoriteOnly = !templateBlockFavoriteOnly;
  event.currentTarget.classList.toggle("active", templateBlockFavoriteOnly);
  event.currentTarget.setAttribute("aria-pressed", templateBlockFavoriteOnly ? "true" : "false");
  renderTemplateBlocks();
});

document.querySelector("#refreshTemplateBlocks")?.addEventListener("click", () => {
  loadTemplateBlocks(true).catch(error => showToast(error.message, true));
});

document.querySelector("#templateBlockList")?.addEventListener("click", event => {
  const card = event.target.closest("[data-template-block-id]");
  if (!card) return;
  const id = card.dataset.templateBlockId;
  if (event.target.closest("[data-template-block-favorite]")) {
    event.stopPropagation();
    toggleTemplateBlockFavorite(id, event.target.closest("[data-template-block-favorite]")).catch(error => showToast(error.message, true));
    return;
  }
  if (event.target.closest("[data-template-block-add]")) {
    addTemplateBlockToEditor(id);
    return;
  }
  if (event.target.closest("[data-template-block-delete]")) {
    deleteTemplateBlock(id).catch(error => showToast(error.message, true));
  }
});

videoTemplateForm()?.addEventListener("input", renderTemplatePreview);
videoTemplateForm()?.addEventListener("change", event => {
  if (event.target.matches("[data-shot-method]")) {
    applyTemplateShotMethodUi(event.target.closest("[data-template-shot]"));
  }
  renderTemplatePreview();
});
videoTemplateForm()?.addEventListener("submit", event => {
  event.preventDefault();
  saveTemplateEditor().catch(error => showToast(error.message, true));
});

document.querySelector("#newVideoTemplate")?.addEventListener("click", () => resetTemplateEditor());
document.querySelector("#importVideoTemplate")?.addEventListener("click", () => {
  document.querySelector("#templateImportFile")?.click();
});
document.querySelector("#templateImportFile")?.addEventListener("change", event => {
  const file = event.target.files?.[0];
  importTemplateFile(file).catch(error => showToast(error.message, true)).finally(() => {
    event.target.value = "";
  });
});
document.querySelector("#exportVideoTemplate")?.addEventListener("click", exportCurrentTemplate);
document.querySelector("#addTemplateVariable")?.addEventListener("click", () => {
  renderTemplateVariables([...collectTemplateVariables(), { key: "", label: "", default: "" }]);
  renderTemplatePreview();
});
document.querySelector("#addTemplateSlot")?.addEventListener("click", () => {
  renderTemplateSlots([...collectTemplateSlots(), { key: "", label: "", kind: "image", note: "" }]);
  renderTemplatePreview();
});
document.querySelector("#addTemplateShot")?.addEventListener("click", () => {
  const form = videoTemplateForm();
  renderTemplateShots([...collectTemplateShots(), {
    title: `컷 ${collectTemplateShots().length + 1}`,
    method: form?.elements.default_method?.value || "i2v",
    duration: form?.elements.default_shot_duration?.value || 6,
    reference_slot: collectTemplateSlots()[0]?.key || "",
    transition: "cut",
    prompt: "",
    camera: "",
    retry_prompt: "",
    notes: "",
  }]);
  renderTemplatePreview();
});

document.querySelector("#duplicateVideoTemplate")?.addEventListener("click", () => {
  const payload = templatePayloadFromEditor();
  payload.id = "";
  payload.title = `${payload.title || "영상 템플릿"} 복사본`;
  resetTemplateEditor(payload);
});

document.querySelector("#deleteVideoTemplate")?.addEventListener("click", () => {
  deleteTemplateEditor().catch(error => showToast(error.message, true));
});

document.querySelector("#copyTemplatePreview")?.addEventListener("click", async () => {
  const text = templatePreviewPlainText();
  if (!text.trim()) {
    showToast("복사할 미리보기가 없습니다.", true);
    return;
  }
  await navigator.clipboard.writeText(text);
  showToast("템플릿 미리보기를 복사했습니다.");
});

document.querySelector("#templateRunVariables")?.addEventListener("input", event => {
  const input = event.target.closest("[data-template-run-var]");
  if (!input) return;
  templateRunState.variables[input.dataset.templateRunVar] = input.value;
});

document.querySelector("#templateRunSlots")?.addEventListener("click", event => {
  const row = event.target.closest("[data-template-run-slot]");
  if (!row) return;
  const key = row.dataset.templateRunSlot;
  if (event.target.closest("[data-template-slot-pick]")) {
    const kind = event.target.closest("[data-template-slot-pick]").dataset.templateSlotKind || "image";
    openTemplateSlotPicker(key, kind);
    return;
  }
  if (event.target.closest("[data-template-slot-clear]")) {
    delete templateRunState.slots[key];
    renderTemplateRunPanel();
    showToast("템플릿 슬롯 연결을 해제했습니다.");
    return;
  }
  if (event.target.closest("[data-template-slot-preview]")) {
    const slot = templateRunState.slots[key];
    if (slot?.path) openMediaViewer(slot.path, slot.kind === "video" ? "video" : "image");
  }
});

document.querySelector("#resetTemplateRun")?.addEventListener("click", () => {
  resetTemplateRunState();
  renderTemplatePreview();
  showToast("템플릿 실행값을 초기화했습니다.");
});

document.querySelector("#templateRunMode")?.addEventListener("change", event => {
  templateRunState.mode = event.target.value === "manual" ? "manual" : "auto";
  renderTemplateRunPanel();
});

document.querySelector("#queueTemplateRun")?.addEventListener("click", enqueueTemplateRun);

document.querySelector("#copyTemplateRunPlan")?.addEventListener("click", async () => {
  const text = templateRunPlanText();
  if (!text.trim()) {
    showToast("복사할 실행 계획이 없습니다.", true);
    return;
  }
  await navigator.clipboard.writeText(text);
  showToast("템플릿 실행 계획을 복사했습니다.");
});

document.querySelector("#templatePreview")?.addEventListener("click", event => {
  if (event.target.closest("[data-preview-drag-handle]")) return;
  const item = event.target.closest("[data-template-preview-shot]");
  if (!item) return;
  focusTemplateShot(Number.parseInt(item.dataset.templatePreviewShot || "0", 10));
});

document.querySelector("#templatePreview")?.addEventListener("keydown", event => {
  if (event.key !== "Enter" && event.key !== " ") return;
  if (event.target.closest("[data-preview-drag-handle]")) return;
  const item = event.target.closest("[data-template-preview-shot]");
  if (!item) return;
  event.preventDefault();
  focusTemplateShot(Number.parseInt(item.dataset.templatePreviewShot || "0", 10));
});

["#templateVariables", "#templateSlots", "#templateShots"].forEach(selector => {
  document.querySelector(selector)?.addEventListener("click", event => {
    const remove = event.target.closest("[data-remove-template-row]");
    const shot = event.target.closest("[data-template-shot]");
    if (remove) {
      event.target.closest("[data-template-variable], [data-template-slot], [data-template-shot]")?.remove();
      renderTemplatePreview();
      return;
    }
    if (!shot) return;
    if (event.target.closest("[data-save-shot-block]")) {
      const index = Array.from(document.querySelectorAll("[data-template-shot]")).indexOf(shot);
      saveTemplateShotBlock(index, event.target.closest("[data-save-shot-block]")).catch(error => showToast(error.message, true));
      return;
    }
    if (event.target.closest("[data-duplicate-shot]")) {
      const shots = collectTemplateShots();
      const index = Array.from(document.querySelectorAll("[data-template-shot]")).indexOf(shot);
      const copy = { ...shots[index], id: "", title: `${shots[index]?.title || "컷"} 복사본` };
      shots.splice(index + 1, 0, copy);
      renderTemplateShots(shots);
      renderTemplatePreview();
      return;
    }
    if (event.target.closest("[data-move-shot-up]") && shot.previousElementSibling) {
      shot.parentElement.insertBefore(shot, shot.previousElementSibling);
      renderTemplateShots(collectTemplateShots());
      renderTemplatePreview();
      return;
    }
    if (event.target.closest("[data-move-shot-down]") && shot.nextElementSibling) {
      shot.parentElement.insertBefore(shot.nextElementSibling, shot);
      renderTemplateShots(collectTemplateShots());
      renderTemplatePreview();
    }
  });
});

document.querySelector("#templateShots")?.addEventListener("dragstart", event => {
  const handle = event.target.closest("[data-shot-drag-handle]");
  if (!handle) return;
  const shot = handle.closest("[data-template-shot]");
  if (!shot) return;
  shot.classList.add("is-dragging");
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", "template-shot");
});

document.querySelector("#templateShots")?.addEventListener("dragover", event => {
  const list = event.currentTarget;
  const dragging = list.querySelector("[data-template-shot].is-dragging");
  if (!dragging) return;
  event.preventDefault();
  list.classList.add("is-drop-active");
  event.dataTransfer.dropEffect = "move";
  updateTemplateShotAutoScroll(list, event.clientY);
  const target = templateShotDragTarget(list, event.clientY);
  if (!target && dragging.nextElementSibling) {
    moveTemplateShotWithAnimation(list, () => list.appendChild(dragging));
  } else if (target && target !== dragging.nextElementSibling) {
    moveTemplateShotWithAnimation(list, () => list.insertBefore(dragging, target));
  }
});

document.querySelector("#templateShots")?.addEventListener("drop", event => {
  const list = event.currentTarget;
  if (!list.querySelector("[data-template-shot].is-dragging")) return;
  event.preventDefault();
  finishTemplateShotDrag(list);
});

document.querySelector("#templateShots")?.addEventListener("dragend", event => {
  if (!event.target.closest("[data-shot-drag-handle]")) return;
  finishTemplateShotDrag(event.currentTarget);
});

document.querySelector("#templatePreview")?.addEventListener("dragstart", event => {
  const handle = event.target.closest("[data-preview-drag-handle]");
  if (!handle) return;
  const card = handle.closest("[data-template-preview-shot]");
  if (!card) return;
  card.classList.add("is-dragging");
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", "template-preview-shot");
});

document.querySelector("#templatePreview")?.addEventListener("dragover", event => {
  const list = event.currentTarget;
  const dragging = list.querySelector("[data-template-preview-shot].is-dragging");
  if (!dragging) return;
  event.preventDefault();
  list.classList.add("is-drop-active");
  event.dataTransfer.dropEffect = "move";
  updateTemplateShotAutoScroll(list, event.clientY);
  const target = templateShotDragTarget(list, event.clientY);
  if (!target && dragging.nextElementSibling) {
    moveTemplateShotWithAnimation(list, () => list.appendChild(dragging));
  } else if (target && target !== dragging.nextElementSibling) {
    moveTemplateShotWithAnimation(list, () => list.insertBefore(dragging, target));
  }
});

document.querySelector("#templatePreview")?.addEventListener("drop", event => {
  const list = event.currentTarget;
  if (!list.querySelector("[data-template-preview-shot].is-dragging")) return;
  event.preventDefault();
  finishTemplatePreviewDrag(list);
});

document.querySelector("#templatePreview")?.addEventListener("dragend", event => {
  if (!event.target.closest("[data-preview-drag-handle]")) return;
  finishTemplatePreviewDrag(event.currentTarget);
});

async function loadLibrary(resetVisible = true) {
  const grid = document.querySelector("#libraryGrid");
  const response = await fetch("/api/library");
  const data = await response.json();
  if (!data.ok) {
    pendingErrorLog = {
      time: new Date().toISOString(),
      message: data.error || "요청 실패",
      detail: data.detail || data.next || "",
    };
    throw new Error(data.error || data.detail || "요청 실패");
  }
  const allItems = data.items || [];
  const items = allItems.filter(item => {
    if (libraryFilter === "all") return true;
    if (libraryFilter === "image") return item.kind !== "video";
    if (libraryFilter === "video") return item.kind === "video";
    if (libraryFilter === "favorite") return Boolean(item.favorite);
    return true;
  });
  if (resetVisible) libraryVisibleCount = libraryPageSize;
  selectedItems.clear();
  renderLibraryGrid(grid, allItems, items);
}

async function loadLibrary(resetVisible = true, useCache = false) {
  const grid = document.querySelector("#libraryGrid");
  if (!grid) return;
  if (!useCache) {
    const response = await fetch("/api/library");
    const data = await response.json();
    if (!data.ok) {
      pendingErrorLog = {
        time: new Date().toISOString(),
        message: data.error || "라이브러리 조회 실패",
        detail: data.detail || data.next || "",
      };
      throw new Error(data.error || data.detail || "라이브러리 조회 실패");
    }
    libraryCachedItems = data.items || [];
    populateLibraryOperationFilter(libraryCachedItems);
  }
  if (resetVisible) libraryVisibleCount = libraryPageSize;
  selectedItems.clear();
  renderLibraryView(grid, libraryCachedItems, applyLibraryFilters(libraryCachedItems));
}

function rerenderLibrary(resetVisible = true) {
  return loadLibrary(resetVisible, true);
}

function pageSizeFromValue(value, fallback = 80) {
  const next = Number(value);
  if (!Number.isFinite(next)) return fallback;
  return Math.max(20, Math.min(500, Math.round(next)));
}

function syncLibraryPreferenceControls() {
  const view = document.querySelector("#libraryView");
  const thumb = document.querySelector("#libraryThumbSize");
  const pageSize = document.querySelector("#libraryPageSize");
  if (view) view.value = libraryView;
  if (thumb) thumb.value = libraryThumbSize;
  if (pageSize) pageSize.value = String(libraryPageSize);
}

function libraryOperation(item) {
  const extra = item.extra || {};
  if (extra.generation_type) return extra.generation_type;
  if (item.kind === "video" && /edit/i.test(item.model || "")) return "video_edit";
  if (item.kind === "video") return "video";
  if (item.kind === "edit") return "image_edit";
  return "image_generation";
}

function isMangaOperation(value) {
  return ["manga_live_translate", "manga_panel_realize"].includes(value);
}

function libraryOperationLabel(value) {
  return ({
    image_generation: "이미지 생성",
    image_edit: "이미지 편집",
    i2v: "이미지→영상",
    v2v_extend: "영상 연장",
    video_edit: "영상 편집",
    manga_live_translate: "망가 실사화·역식",
    manga_panel_realize: "컷 분리 실사화",
    video: "미분류 영상",
  })[value] || value;
}

function populateLibraryOperationFilter(items) {
  const select = document.querySelector("#libraryOperationFilter");
  if (!select) return;
  const current = select.value || "all";
  const operations = [...new Set(items.map(libraryOperation).filter(Boolean))]
    .sort((a, b) => libraryOperationLabel(a).localeCompare(libraryOperationLabel(b), "ko"));
  select.innerHTML = `<option value="all">모든 작업</option>${operations.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(libraryOperationLabel(value))}</option>`).join("")}`;
  select.value = operations.includes(current) ? current : "all";
  libraryOperationFilter = select.value;
}

function itemSearchText(item) {
  const extra = item.extra || {};
  return [
    item.prompt,
    item.file_path,
    item.model,
    item.kind,
    libraryOperationLabel(libraryOperation(item)),
    extra.generation_type,
    extra.batch_mode,
    extra.source_original_name,
    extra.source_page_name,
    extra.resolution,
    extra.requested_resolution,
  ].filter(Boolean).join(" ").toLowerCase();
}

function sameLocalDate(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}

function passesDateFilter(item) {
  if (libraryDateFilter === "all") return true;
  const created = new Date(item.created_at || 0);
  if (!Number.isFinite(created.getTime())) return false;
  const now = new Date();
  if (libraryDateFilter === "today") return sameLocalDate(created, now);
  if (libraryDateFilter === "yesterday") {
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    return sameLocalDate(created, yesterday);
  }
  if (libraryDateFilter === "7d") return created >= new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  if (libraryDateFilter === "month") return created.getFullYear() === now.getFullYear() && created.getMonth() === now.getMonth();
  if (libraryDateFilter === "custom" && libraryDateValue) {
    const [year, month, day] = libraryDateValue.split("-").map(Number);
    return sameLocalDate(created, new Date(year, month - 1, day));
  }
  return true;
}

function itemFilename(item) {
  return String(item.file_path || "").split(/[\\/]/).pop() || "";
}

function itemResolutionValue(item) {
  const text = String(item.extra?.resolution || item.extra?.requested_resolution || "");
  const match = text.match(/\d+/);
  return match ? Number(match[0]) : 0;
}

function applyLibraryFilters(items) {
  const query = librarySearch.trim().toLowerCase();
  const filtered = items.filter(item => {
    const operation = libraryOperation(item);
    const mangaItem = isMangaOperation(operation);
    if (libraryFilter === "manga" && !mangaItem) return false;
    if (libraryFilter !== "manga" && libraryOperationFilter === "all" && mangaItem) return false;
    if (libraryFilter === "image" && item.kind === "video") return false;
    if (libraryFilter === "video" && item.kind !== "video") return false;
    if (libraryFilter === "favorite" && !item.favorite) return false;
    if (libraryOperationFilter !== "all" && operation !== libraryOperationFilter) return false;
    if (!passesDateFilter(item)) return false;
    if (query && !query.split(/\s+/).every(token => itemSearchText(item).includes(token))) return false;
    return true;
  });
  filtered.sort((a, b) => {
    if (librarySort === "oldest") return new Date(a.created_at || 0) - new Date(b.created_at || 0);
    if (librarySort === "filename") return itemFilename(a).localeCompare(itemFilename(b), "ko", { numeric: true });
    if (librarySort === "favorite") return Number(Boolean(b.favorite)) - Number(Boolean(a.favorite)) || new Date(b.created_at || 0) - new Date(a.created_at || 0);
    if (librarySort === "resolution") return itemResolutionValue(b) - itemResolutionValue(a) || new Date(b.created_at || 0) - new Date(a.created_at || 0);
    return new Date(b.created_at || 0) - new Date(a.created_at || 0);
  });
  return filtered;
}

function updateLibraryStats(total, shown, rendered) {
  const node = document.querySelector("#libraryStats");
  if (!node) return;
  node.textContent = `${shown} / ${total}개${shown > rendered ? ` · ${rendered}개 표시` : ""}`;
}

function renderLibraryView(grid, allItems, items) {
  grid.className = `grid library-view-${libraryView} thumb-${libraryThumbSize}`;
  if (libraryView === "timeline") renderLibraryTimeline(grid, allItems, items);
  else if (libraryView === "chain") renderLibraryChains(grid, allItems, items);
  else renderLibraryGrid(grid, allItems, items);
  updateLibraryStats(allItems.length, items.length, Math.min(items.length, libraryVisibleCount));
}

function isPlayableVideo(item) {
  return item.kind === "video" && /\.(mp4|webm|mov)$/i.test(item.file_path || "");
}

function mediaThumbHtml(item) {
  if (isPlayableVideo(item)) {
    const thumb = `/api/video-thumbnail?path=${encodeURIComponent(item.file_path)}`;
    return `
      <div class="video-thumb-frame" role="button" tabindex="0" aria-label="영상 크게 보기">
        <img src="${thumb}" alt="" loading="lazy" decoding="async">
        <span class="video-thumb-overlay">
          <span class="video-play-symbol" aria-hidden="true"></span>
        </span>
      </div>`;
  }
  return `<img src="${item.file_path}" alt="" loading="lazy" decoding="async">`;
}

function videoPickerThumbHtml(path) {
  const thumb = `/api/video-thumbnail?path=${encodeURIComponent(path)}`;
  return `
    <div class="video-thumb-frame picker-video-thumb">
      <img src="${thumb}" alt="" loading="lazy" decoding="async">
      <span class="video-thumb-overlay">
        <span class="video-play-symbol" aria-hidden="true"></span>
      </span>
    </div>`;
}

function renderLibraryGrid(grid, allItems, items) {
  const visibleItems = items.slice(0, libraryVisibleCount);
  grid.innerHTML = items.length ? "" : `<p>${allItems.length ? "필터에 맞는 결과가 없습니다." : "아직 저장된 결과가 없습니다."}</p>`;
  for (const item of visibleItems) {
    const media = mediaThumbHtml(item);
    const node = document.createElement("article");
    node.className = "item";
    node.dataset.id = item.id;
    node.dataset.prompt = item.prompt;
    node.dataset.filePath = item.file_path;
    node.dataset.kind = item.kind;
    node.dataset.isFavorite = item.favorite ? "true" : "false";
    const resolution = item.kind === "video" ? (item.extra?.resolution || item.extra?.requested_resolution || "") : "";
    const favoriteClass = item.favorite ? " active" : "";
    const favoritePressed = item.favorite ? "true" : "false";
    node.innerHTML = `
      <input class="item-select" type="checkbox" aria-label="선택">
      <button type="button" class="favorite-button${favoriteClass}" data-favorite aria-label="즐겨찾기" aria-pressed="${favoritePressed}"></button>
      ${resolution ? `<span class="resolution-badge">${escapeHtml(resolution)}</span>` : ""}
      <div class="thumb">${media}</div>
      <div class="meta">
        <strong>${item.kind} · ${item.model}</strong>
        <div>${new Date(item.created_at).toLocaleString()}</div>
        <button type="button" class="prompt-text" data-view-prompt>${escapeHtml(item.prompt)}</button>
        <div class="item-actions">
          <button type="button" class="danger-btn" data-delete>삭제</button>
          <div class="item-menu">
            <button type="button" class="icon-button" data-menu-toggle aria-label="파일 옵션">⋯</button>
            <div class="item-menu-panel" hidden>
              <button type="button" data-menu-action="open-file">기본 앱으로 열기</button>
              <button type="button" data-menu-action="copy-file">파일 복사</button>
              <button type="button" data-menu-action="copy-path">파일 경로 저장</button>
              <button type="button" data-menu-action="save-prompt">프롬프트 저장</button>
            </div>
          </div>
        </div>
      </div>`;
    grid.appendChild(node);
  }
  if (items.length > visibleItems.length) {
    const more = document.createElement("button");
    more.type = "button";
    more.className = "load-more";
    more.dataset.loadMoreLibrary = "true";
    more.textContent = `더 보기 (${visibleItems.length} / ${items.length})`;
    grid.appendChild(more);
  }
}

function createLibraryItemNode(item) {
  const media = mediaThumbHtml(item);
  const node = document.createElement("article");
  node.className = "item";
  node.dataset.id = item.id;
  node.dataset.prompt = item.prompt || "";
  node.dataset.filePath = item.file_path;
  node.dataset.kind = item.kind;
  node.dataset.isFavorite = item.favorite ? "true" : "false";
  const resolution = item.kind === "video" ? (item.extra?.resolution || item.extra?.requested_resolution || "") : "";
  const favoriteClass = item.favorite ? " active" : "";
  const favoritePressed = item.favorite ? "true" : "false";
  node.innerHTML = `
    <input class="item-select" type="checkbox" aria-label="선택">
    <button type="button" class="favorite-button${favoriteClass}" data-favorite aria-label="즐겨찾기" aria-pressed="${favoritePressed}"></button>
    ${resolution ? `<span class="resolution-badge">${escapeHtml(resolution)}</span>` : ""}
    <div class="thumb">${media}</div>
    <div class="meta">
      <strong>${escapeHtml(item.kind)} · ${escapeHtml(item.model || "")}</strong>
      <div>${new Date(item.created_at).toLocaleString()}</div>
      <small>${escapeHtml(libraryOperationLabel(libraryOperation(item)))}</small>
      <button type="button" class="prompt-text" data-view-prompt>${escapeHtml(item.prompt || "")}</button>
      <div class="item-actions">
        <button type="button" class="danger-btn" data-delete>삭제</button>
        <div class="item-menu">
          <button type="button" class="icon-button" data-menu-toggle aria-label="파일 옵션">...</button>
          <div class="item-menu-panel" hidden>
            <button type="button" data-menu-action="open-file">기본 앱으로 열기</button>
            <button type="button" data-menu-action="copy-file">파일 복사</button>
            <button type="button" data-menu-action="copy-path">파일 경로 복사</button>
            <button type="button" data-menu-action="save-prompt">프롬프트 저장</button>
          </div>
        </div>
      </div>
    </div>`;
  return node;
}

function appendLibraryLoadMore(grid, items) {
  if (items.length <= libraryVisibleCount) return;
  const more = document.createElement("button");
  more.type = "button";
  more.className = "load-more";
  more.dataset.loadMoreLibrary = "true";
  more.textContent = `더 보기 (${Math.min(libraryVisibleCount, items.length)} / ${items.length})`;
  grid.appendChild(more);
}

function dayKey(value) {
  const date = new Date(value || 0);
  if (!Number.isFinite(date.getTime())) return "날짜 없음";
  return date.toLocaleDateString("ko-KR", { year: "numeric", month: "2-digit", day: "2-digit", weekday: "short" });
}

function renderLibraryTimeline(grid, allItems, items) {
  const visibleItems = items.slice(0, libraryVisibleCount);
  grid.innerHTML = items.length ? "" : `<p>${allItems.length ? "필터에 맞는 결과가 없습니다." : "아직 저장된 결과가 없습니다."}</p>`;
  const grouped = new Map();
  visibleItems.forEach(item => {
    const key = dayKey(item.created_at);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(item);
  });
  for (const [day, dayItems] of grouped) {
    const section = document.createElement("section");
    section.className = "library-day";
    section.innerHTML = `<h3>${escapeHtml(day)} <span>${dayItems.length}</span></h3>`;
    const list = document.createElement("div");
    list.className = "library-day-list";
    dayItems.forEach(item => list.appendChild(createLibraryItemNode(item)));
    section.appendChild(list);
    grid.appendChild(section);
  }
  appendLibraryLoadMore(grid, items);
}

function chainKeyForItem(item) {
  const extra = item.extra || {};
  const paths = [
    extra.original_start_image_path,
    extra.start_image_path,
    extra.source_image_path,
    extra.source_video_path,
    extra.source_page_path,
    item.source_path,
    item.file_path,
  ].filter(Boolean);
  return paths[0] || item.id;
}

function chainLabel(key) {
  const name = String(key || "").split(/[\\/]/).pop();
  return name || "관련 작업";
}

function renderLibraryChains(grid, allItems, items) {
  const visibleItems = items.slice(0, libraryVisibleCount);
  grid.innerHTML = items.length ? "" : `<p>${allItems.length ? "필터에 맞는 결과가 없습니다." : "아직 저장된 결과가 없습니다."}</p>`;
  const groups = new Map();
  visibleItems.forEach(item => {
    const key = chainKeyForItem(item);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  });
  const ordered = [...groups.entries()].sort((a, b) => {
    const latestA = Math.max(...a[1].map(item => new Date(item.created_at || 0).getTime()));
    const latestB = Math.max(...b[1].map(item => new Date(item.created_at || 0).getTime()));
    return latestB - latestA;
  });
  ordered.forEach(([key, groupItems]) => {
    const section = document.createElement("section");
    section.className = "library-chain";
    section.innerHTML = `<h3>${escapeHtml(chainLabel(key))} <span>${groupItems.length}</span></h3>`;
    const row = document.createElement("div");
    row.className = "library-chain-row";
    groupItems
      .sort((a, b) => new Date(a.created_at || 0) - new Date(b.created_at || 0))
      .forEach(item => row.appendChild(createLibraryItemNode(item)));
    section.appendChild(row);
    grid.appendChild(section);
  });
  appendLibraryLoadMore(grid, items);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));
}

function syncSelection(node, checked) {
  node.classList.toggle("selected", checked);
  const checkbox = node.querySelector(".item-select");
  if (checkbox) checkbox.checked = checked;
  if (checked) selectedItems.add(node.dataset.id);
  else selectedItems.delete(node.dataset.id);
}

function rectsOverlap(a, b) {
  return a.left <= b.right && a.right >= b.left && a.top <= b.bottom && a.bottom >= b.top;
}

function ensureLibrarySelectionBox() {
  let box = document.querySelector("#librarySelectionBox");
  if (!box) {
    box = document.createElement("div");
    box.id = "librarySelectionBox";
    box.className = "library-selection-box";
    document.body.appendChild(box);
  }
  return box;
}

function updateLibraryBoxSelect(clientX, clientY) {
  if (!libraryBoxSelect) return;
  const distance = Math.hypot(clientX - libraryBoxSelect.startX, clientY - libraryBoxSelect.startY);
  if (!libraryBoxSelect.active && distance < 6) return;
  if (!libraryBoxSelect.active) {
    libraryBoxSelect.active = true;
    libraryBoxSelect.box = ensureLibrarySelectionBox();
    document.body.classList.add("is-library-box-selecting");
  }

  const left = Math.min(libraryBoxSelect.startX, clientX);
  const top = Math.min(libraryBoxSelect.startY, clientY);
  const right = Math.max(libraryBoxSelect.startX, clientX);
  const bottom = Math.max(libraryBoxSelect.startY, clientY);
  const rect = { left, top, right, bottom };
  Object.assign(libraryBoxSelect.box.style, {
    left: `${left}px`,
    top: `${top}px`,
    width: `${right - left}px`,
    height: `${bottom - top}px`,
  });

  document.querySelectorAll("#libraryGrid .item").forEach(node => {
    const original = libraryBoxSelect.originalStates.get(node.dataset.id) || false;
    const inside = rectsOverlap(rect, node.getBoundingClientRect());
    syncSelection(node, inside ? libraryBoxSelect.mode : original);
  });
}

function finishLibraryBoxSelect() {
  if (!libraryBoxSelect) return;
  if (libraryBoxSelect.box) libraryBoxSelect.box.remove();
  document.body.classList.remove("is-library-box-selecting");
  libraryBoxSelect = null;
}

document.querySelector("#libraryGrid").addEventListener("pointerdown", event => {
  if (!event.target.matches(".item-select") || event.button !== 0) return;
  const item = event.target.closest(".item");
  if (!item) return;
  event.preventDefault();
  event.stopPropagation();
  const items = Array.from(document.querySelectorAll("#libraryGrid .item"));
  libraryBoxSelect = {
    active: false,
    box: null,
    mode: !selectedItems.has(item.dataset.id),
    originalStates: new Map(items.map(node => [node.dataset.id, selectedItems.has(node.dataset.id)])),
    startX: event.clientX,
    startY: event.clientY,
  };
  syncSelection(item, libraryBoxSelect.mode);
});

document.querySelector("#libraryGrid").addEventListener("mouseover", event => {
  if (!dragSelecting) return;
  const node = event.target.closest(".item");
  if (node) syncSelection(node, dragSelectMode);
});

document.addEventListener("mouseup", () => { dragSelecting = false; });

document.addEventListener("pointermove", event => {
  if (!libraryBoxSelect) return;
  event.preventDefault();
  updateLibraryBoxSelect(event.clientX, event.clientY);
});

document.addEventListener("pointerup", event => {
  if (!libraryBoxSelect) return;
  updateLibraryBoxSelect(event.clientX, event.clientY);
  finishLibraryBoxSelect();
});

document.addEventListener("pointercancel", finishLibraryBoxSelect);

document.querySelector("#libraryGrid").addEventListener("click", event => {
  if (!event.target.matches(".item-select")) return;
  event.preventDefault();
  event.stopPropagation();
}, true);

document.querySelector("#libraryGrid").addEventListener("change", event => {
  if (!event.target.matches(".item-select")) return;
  const item = event.target.closest(".item");
  if (item) syncSelection(item, event.target.checked);
});

async function postJson(url, payload = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!data.ok) {
    pendingErrorLog = {
      time: new Date().toISOString(),
      message: data.error || "요청 실패",
      detail: data.detail || data.next || "",
    };
    throw new Error(data.error || data.detail || "요청 실패");
  }
  if (!data.ok) throw new Error(data.error || "요청 실패");
  return data;
}

const libraryMenuActions = {
  async "open-file"(item) {
    await postJson("/api/library/open-file", { id: item.dataset.id });
    showToast("기본 앱으로 파일을 열었습니다.");
  },
  async "copy-file"(item) {
    const data = await postJson("/api/library/copy-file", { id: item.dataset.id });
    if (data.clipboard_supported === false) {
      await navigator.clipboard.writeText(data.path);
      showToast("이 환경에서는 파일 자체 복사 대신 경로를 복사했습니다.");
      return;
    }
    showToast("파일을 클립보드에 복사했습니다.");
  },
  async "copy-path"(item) {
    const data = await postJson("/api/library/item-path", { id: item.dataset.id });
    await navigator.clipboard.writeText(data.path);
    showToast("파일 경로를 복사했습니다.");
  },
  async "save-prompt"(item) {
    await savePromptFromLibraryItem(item);
  },
};

function closeItemMenus(except = null) {
  document.querySelectorAll(".item-menu-panel").forEach(panel => {
    if (panel !== except) panel.hidden = true;
  });
}

function setFavoriteButtonState(button, active, pending = false) {
  button.classList.toggle("active", Boolean(active));
  button.classList.toggle("is-pending", Boolean(pending));
  button.setAttribute("aria-pressed", active ? "true" : "false");
  button.title = active ? "즐겨찾기 해제" : "즐겨찾기 추가";
}

function openPromptViewer(prompt) {
  const viewer = document.querySelector("#promptViewer");
  const text = document.querySelector("#promptViewerText");
  if (!viewer || !text) return;
  text.textContent = prompt || "";
  viewer.hidden = false;
}

function closePromptViewer() {
  const viewer = document.querySelector("#promptViewer");
  if (viewer) viewer.hidden = true;
}

document.querySelector("#promptViewer")?.addEventListener("click", event => {
  if (event.target.id === "promptViewer") closePromptViewer();
});

document.querySelector("#copyPromptViewer")?.addEventListener("click", async event => {
  event.stopPropagation();
  const prompt = document.querySelector("#promptViewerText")?.textContent || "";
  if (!prompt.trim()) {
    showToast("복사할 프롬프트가 없습니다.", true);
    return;
  }
  await navigator.clipboard.writeText(prompt);
  showToast("프롬프트를 복사했습니다.");
});

document.addEventListener("keydown", event => {
  if (event.key === "Escape") closePromptViewer();
});

document.querySelector("#libraryGrid").addEventListener("click", async event => {
  const loadMore = event.target.closest("[data-load-more-library]");
  if (loadMore) {
    libraryVisibleCount += libraryPageSize;
    await rerenderLibrary(false);
    return;
  }
  const item = event.target.closest(".item");
  if (!item) return;
  const favorite = event.target.closest(".favorite-button[data-favorite]");
  if (favorite) {
    event.preventDefault();
    event.stopPropagation();
    const previousFavorite = favorite.getAttribute("aria-pressed") === "true";
    const nextFavorite = !previousFavorite;
    setFavoriteButtonState(favorite, nextFavorite, true);
    item.dataset.isFavorite = nextFavorite ? "true" : "false";
    try {
      const data = await postJson("/api/library/favorite", { id: item.dataset.id, favorite: nextFavorite });
      if (data.id && data.id !== item.dataset.id) {
        selectedItems.delete(item.dataset.id);
        item.dataset.id = data.id;
      }
      item.dataset.isFavorite = data.favorite ? "true" : "false";
      setFavoriteButtonState(favorite, Boolean(data.favorite), false);
      if (libraryFilter === "favorite" && !data.favorite) {
        selectedItems.delete(item.dataset.id);
        item.remove();
      }
      showToast(data.favorite ? "즐겨찾기에 추가했습니다." : "즐겨찾기를 해제했습니다.");
    } catch (error) {
      item.dataset.isFavorite = previousFavorite ? "true" : "false";
      setFavoriteButtonState(favorite, previousFavorite, false);
      showToast(error.message, true);
    }
    return;
  }
  const toggle = event.target.closest("[data-menu-toggle]");
  if (toggle) {
    const panel = toggle.closest(".item-menu").querySelector(".item-menu-panel");
    const nextHidden = !panel.hidden;
    closeItemMenus(panel);
    panel.hidden = nextHidden;
    return;
  }
  const menuButton = event.target.closest("[data-menu-action]");
  if (menuButton) {
    closeItemMenus();
    try {
      await libraryMenuActions[menuButton.dataset.menuAction]?.(item);
    } catch (error) {
      showToast(error.message, true);
    }
    return;
  }
  const promptButton = event.target.closest("[data-view-prompt]");
  if (promptButton) {
    openPromptViewer(item.dataset.prompt || "");
    return;
  }
  const thumb = event.target.closest(".thumb");
  if (thumb && item.dataset.kind === "video") {
    openMediaViewer(item.dataset.filePath, "video");
    return;
  }
  const thumbImage = event.target.closest(".thumb img");
  if (thumbImage) {
    openMediaViewer(thumbImage.currentSrc || thumbImage.src, "image");
    return;
  }
  if (event.target.matches(".item-select")) {
    return;
  }
  if (event.target.matches("[data-copy]")) {
    await navigator.clipboard.writeText(item.dataset.prompt || "");
    showToast("프롬프트를 복사했습니다.");
  }
  if (event.target.matches("[data-delete]")) {
    await deleteItems([item.dataset.id]);
  }
});

document.addEventListener("click", event => {
  if (!event.target.closest(".item-menu")) closeItemMenus();
});

async function deleteItems(ids) {
  if (!ids.length) {
    showToast("삭제할 항목을 선택해 주세요.", true);
    return;
  }
  const response = await fetch("/api/library/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  });
  const data = await response.json();
  if (!data.ok) {
    showToast(data.error || "삭제 실패", true);
    return;
  }
  showToast(`${data.deleted}개 항목을 삭제했습니다.`);
  await loadLibrary();
}

document.querySelector("#deleteSelected").addEventListener("click", () => deleteItems([...selectedItems]));
document.querySelector("#refreshLibrary").addEventListener("click", () => loadLibrary(true, false));
document.querySelector("#libraryFilter").addEventListener("change", event => {
  libraryFilter = event.target.value;
  rerenderLibrary();
});
document.querySelector("#librarySearch")?.addEventListener("input", event => {
  librarySearch = event.target.value || "";
  rerenderLibrary();
});
document.querySelector("#libraryOperationFilter")?.addEventListener("change", event => {
  libraryOperationFilter = event.target.value;
  rerenderLibrary();
});
document.querySelector("#libraryDateFilter")?.addEventListener("change", event => {
  libraryDateFilter = event.target.value;
  const input = document.querySelector("#libraryDateInput");
  if (input) input.hidden = libraryDateFilter !== "custom";
  rerenderLibrary();
});
document.querySelector("#libraryDateInput")?.addEventListener("change", event => {
  libraryDateValue = event.target.value || "";
  if (libraryDateValue) {
    libraryDateFilter = "custom";
    const select = document.querySelector("#libraryDateFilter");
    if (select) select.value = "custom";
  }
  rerenderLibrary();
});
document.querySelector("#librarySort")?.addEventListener("change", event => {
  librarySort = event.target.value;
  rerenderLibrary();
});
document.querySelector("#libraryView")?.addEventListener("change", event => {
  libraryView = event.target.value;
  saveLibraryPrefs();
  rerenderLibrary();
});
document.querySelector("#libraryThumbSize")?.addEventListener("change", event => {
  libraryThumbSize = event.target.value;
  saveLibraryPrefs();
  rerenderLibrary(false);
});
document.querySelector("#libraryPageSize")?.addEventListener("change", event => {
  libraryPageSize = pageSizeFromValue(event.target.value, libraryPageSize);
  libraryVisibleCount = libraryPageSize;
  saveLibraryPrefs();
  rerenderLibrary(false);
});
document.querySelector("#libraryJumpStart")?.addEventListener("click", () => {
  librarySort = "oldest";
  const sort = document.querySelector("#librarySort");
  if (sort) sort.value = "oldest";
  rerenderLibrary();
  document.querySelector("#libraryGrid")?.scrollIntoView({ block: "start" });
});
document.querySelector("#libraryJumpEnd")?.addEventListener("click", () => {
  librarySort = "newest";
  const sort = document.querySelector("#librarySort");
  if (sort) sort.value = "newest";
  rerenderLibrary();
  document.querySelector("#libraryGrid")?.scrollIntoView({ block: "start" });
});
document.querySelector("#openMediaFolder").addEventListener("click", async () => {
  try {
    await postJson("/api/library/open-folder");
    showToast("저장 폴더를 열었습니다.");
  } catch (error) {
    showToast(error.message, true);
  }
});

function resetPickerControls() {
  pickerFavoriteFilter = "all";
  pickerOperationFilter = "all";
  pickerSearch = "";
  pickerSort = "newest";
  pickerDateFilter = "all";
  pickerDateValue = "";
  pickerThumbSize = "medium";
  pickerVisibleCount = pickerPageSize;
  const search = document.querySelector("#pickerSearch");
  const favorite = document.querySelector("#pickerFavoriteFilter");
  const operation = document.querySelector("#pickerOperationFilter");
  const dateFilter = document.querySelector("#pickerDateFilter");
  const dateInput = document.querySelector("#pickerDateInput");
  const sort = document.querySelector("#pickerSort");
  const thumb = document.querySelector("#pickerThumbSize");
  const pageSize = document.querySelector("#pickerPageSize");
  if (search) search.value = "";
  if (favorite) favorite.value = "all";
  if (operation) operation.value = "all";
  if (dateFilter) dateFilter.value = "all";
  if (dateInput) {
    dateInput.value = "";
    dateInput.hidden = true;
  }
  if (sort) sort.value = "newest";
  if (thumb) thumb.value = "medium";
  if (pageSize) pageSize.value = String(pickerPageSize);
}

function populatePickerOperationFilter(items) {
  const select = document.querySelector("#pickerOperationFilter");
  if (!select) return;
  const operations = [...new Set(items.map(libraryOperation))].sort((a, b) => libraryOperationLabel(a).localeCompare(libraryOperationLabel(b), "ko"));
  select.innerHTML = `<option value="all">모든 작업</option>${operations.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(libraryOperationLabel(value))}</option>`).join("")}`;
  select.value = operations.includes(pickerOperationFilter) ? pickerOperationFilter : "all";
  pickerOperationFilter = select.value;
}

function passesPickerDateFilter(item) {
  if (pickerDateFilter === "all") return true;
  const created = new Date(item.created_at || 0);
  if (!Number.isFinite(created.getTime())) return false;
  const now = new Date();
  if (pickerDateFilter === "today") return sameLocalDate(created, now);
  if (pickerDateFilter === "yesterday") {
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    return sameLocalDate(created, yesterday);
  }
  if (pickerDateFilter === "7d") return created >= new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  if (pickerDateFilter === "month") return created.getFullYear() === now.getFullYear() && created.getMonth() === now.getMonth();
  if (pickerDateFilter === "custom" && pickerDateValue) {
    const [year, month, day] = pickerDateValue.split("-").map(Number);
    return sameLocalDate(created, new Date(year, month - 1, day));
  }
  return true;
}

function applyPickerFilters() {
  const query = pickerSearch.trim().toLowerCase();
  const filtered = pickerItems.filter(item => {
    const operation = libraryOperation(item);
    if (pickerOperationFilter === "all" && isMangaOperation(operation)) return false;
    if (pickerFavoriteFilter === "favorite" && !item.favorite) return false;
    if (pickerOperationFilter !== "all" && operation !== pickerOperationFilter) return false;
    if (!passesPickerDateFilter(item)) return false;
    if (query && !query.split(/\s+/).every(token => itemSearchText(item).includes(token))) return false;
    return true;
  });
  filtered.sort((a, b) => {
    if (pickerSort === "oldest") return new Date(a.created_at || 0) - new Date(b.created_at || 0);
    if (pickerSort === "filename") return itemFilename(a).localeCompare(itemFilename(b), "ko", { numeric: true });
    if (pickerSort === "favorite") return Number(Boolean(b.favorite)) - Number(Boolean(a.favorite)) || new Date(b.created_at || 0) - new Date(a.created_at || 0);
    if (pickerSort === "resolution") return itemResolutionValue(b) - itemResolutionValue(a) || new Date(b.created_at || 0) - new Date(a.created_at || 0);
    return new Date(b.created_at || 0) - new Date(a.created_at || 0);
  });
  return filtered;
}

function pickerMediaHtml(item) {
  if (pickerMediaType === "video") return videoPickerThumbHtml(item.file_path);
  return `
    <span class="picker-image-thumb">
      <img src="${item.file_path}" alt="" loading="lazy" decoding="async">
      <span class="picker-zoom-symbol" aria-hidden="true"></span>
    </span>`;
}

function renderLibraryPicker() {
  const grid = document.querySelector("#libraryPickerGrid");
  const stats = document.querySelector("#pickerStats");
  if (!grid) return;
  const items = applyPickerFilters();
  const visibleItems = items.slice(0, pickerVisibleCount);
  grid.className = `picker-grid picker-thumb-${pickerThumbSize}`;
  grid.innerHTML = items.length ? "" : `<p>${pickerItems.length ? "필터에 맞는 항목이 없습니다." : `불러올 ${pickerMediaType === "video" ? "영상" : "이미지"}이 없습니다.`}</p>`;
  for (const item of visibleItems) {
    const node = document.createElement("article");
    node.className = "picker-item";
    node.dataset.id = item.id;
    node.dataset.path = item.file_path;
    node.dataset.mediaType = pickerMediaType;
    node.dataset.prompt = item.prompt || "";
    const resolution = item.kind === "video" ? (item.extra?.resolution || item.extra?.requested_resolution || "") : "";
    const favoriteClass = item.favorite ? " active" : "";
    const favoritePressed = item.favorite ? "true" : "false";
    node.innerHTML = `
      <button type="button" class="favorite-button picker-favorite${favoriteClass}" data-picker-favorite aria-label="즐겨찾기" aria-pressed="${favoritePressed}"></button>
      ${resolution ? `<span class="resolution-badge picker-resolution">${escapeHtml(resolution)}</span>` : ""}
      ${pickerMediaHtml(item)}
      <span class="picker-label">${escapeHtml(item.prompt || item.file_path)}</span>`;
    grid.appendChild(node);
  }
  if (items.length > visibleItems.length) {
    const more = document.createElement("button");
    more.type = "button";
    more.className = "load-more picker-load-more";
    more.dataset.loadMorePicker = "true";
    more.textContent = `더 보기 (${visibleItems.length} / ${items.length})`;
    grid.appendChild(more);
  }
  if (stats) {
    const rendered = Math.min(items.length, pickerVisibleCount);
    stats.textContent = `${items.length} / ${pickerItems.length}${items.length > rendered ? ` · ${rendered}개 표시` : ""}`;
  }
}

function rerenderPicker(resetVisible = true) {
  if (resetVisible) pickerVisibleCount = pickerPageSize;
  renderLibraryPicker();
}

function updateFavoriteInItems(items, oldId, data) {
  const index = items.findIndex(item => item.id === oldId || item.id === data.old_id || item.id === data.id);
  if (index < 0) return;
  if (data.item) {
    items[index] = { ...items[index], ...data.item };
    return;
  }
  items[index] = { ...items[index], id: data.id || oldId, favorite: Boolean(data.favorite) };
}

async function togglePickerFavorite(node, button) {
  const previousFavorite = button.getAttribute("aria-pressed") === "true";
  const nextFavorite = !previousFavorite;
  const previousId = node.dataset.id;
  setFavoriteButtonState(button, nextFavorite, true);
  try {
    const data = await postJson("/api/library/favorite", { id: previousId, favorite: nextFavorite });
    node.dataset.id = data.id || previousId;
    setFavoriteButtonState(button, Boolean(data.favorite), false);
    updateFavoriteInItems(pickerItems, previousId, data);
    updateFavoriteInItems(libraryCachedItems, previousId, data);
    if (pickerFavoriteFilter === "favorite" && !data.favorite) renderLibraryPicker();
    showToast(data.favorite ? "즐겨찾기에 추가했습니다." : "즐겨찾기를 해제했습니다.");
  } catch (error) {
    setFavoriteButtonState(button, previousFavorite, false);
    showToast(error.message, true);
  }
}

async function openLibraryPicker(form, options = {}) {
  pickerTargetForm = form;
  const modal = document.querySelector("#libraryPickerModal");
  const grid = document.querySelector("#libraryPickerGrid");
  templatePickerSlotKey = options.templateSlotKey || "";
  pickerMediaType = options.mediaType || mediaTypeForForm(form);
  resetPickerControls();
  document.querySelector("#libraryPickerTitle").textContent = pickerMediaType === "video" ? "라이브러리 영상 선택" : "라이브러리 이미지 선택";
  grid.innerHTML = "<p>불러오는 중입니다.</p>";
  const response = await fetch("/api/library");
  const data = await response.json();
  pickerItems = (data.items || []).filter(item => {
    if (pickerMediaType === "video") return item.kind === "video";
    return item.kind === "image" || item.kind === "edit";
  });
  populatePickerOperationFilter(pickerItems);
  renderLibraryPicker();
  modal.showModal();
}

function previewPickerMedia(path, mediaType) {
  if (!pickerTargetForm) return;
  openMediaViewer(path, mediaType);
}

function openTemplateSlotPicker(slotKey, mediaType = "image") {
  openLibraryPicker(videoTemplateForm(), {
    templateSlotKey: slotKey,
    mediaType,
  }).catch(error => showToast(error.message, true));
}

document.querySelectorAll("[data-open-library-picker]").forEach(button => {
  button.addEventListener("click", () => openLibraryPicker(button.closest("form")));
});

document.querySelector("#closeLibraryPicker").addEventListener("click", () => {
  document.querySelector("#libraryPickerModal").close();
});

document.querySelector("#libraryPickerModal")?.addEventListener("click", event => {
  if (event.target.id === "libraryPickerModal") {
    event.currentTarget.close();
  }
});

document.querySelector("#libraryPickerModal")?.addEventListener("close", () => {
  pickerTargetForm = null;
  pickerItems = [];
  templatePickerSlotKey = "";
});

document.querySelector("#pickerSearch")?.addEventListener("input", event => {
  pickerSearch = event.target.value || "";
  rerenderPicker();
});
document.querySelector("#pickerFavoriteFilter")?.addEventListener("change", event => {
  pickerFavoriteFilter = event.target.value;
  rerenderPicker();
});
document.querySelector("#pickerOperationFilter")?.addEventListener("change", event => {
  pickerOperationFilter = event.target.value;
  rerenderPicker();
});
document.querySelector("#pickerDateFilter")?.addEventListener("change", event => {
  pickerDateFilter = event.target.value;
  const input = document.querySelector("#pickerDateInput");
  if (input) input.hidden = pickerDateFilter !== "custom";
  rerenderPicker();
});
document.querySelector("#pickerDateInput")?.addEventListener("change", event => {
  pickerDateValue = event.target.value || "";
  if (pickerDateValue) {
    pickerDateFilter = "custom";
    const select = document.querySelector("#pickerDateFilter");
    if (select) select.value = "custom";
  }
  rerenderPicker();
});
document.querySelector("#pickerSort")?.addEventListener("change", event => {
  pickerSort = event.target.value;
  rerenderPicker();
});
document.querySelector("#pickerThumbSize")?.addEventListener("change", event => {
  pickerThumbSize = event.target.value;
  renderLibraryPicker();
});
document.querySelector("#pickerPageSize")?.addEventListener("change", event => {
  pickerPageSize = pageSizeFromValue(event.target.value, pickerPageSize);
  pickerVisibleCount = pickerPageSize;
  renderLibraryPicker();
});

function syncMangaBuiltinPromptControls() {
  const toggle = document.querySelector("[data-manga-builtin-toggle]");
  const prompt = document.querySelector("[data-manga-builtin-prompt]");
  if (!toggle || !prompt) return;
  prompt.disabled = !toggle.checked;
  prompt.closest(".prompt-panel")?.classList.toggle("builtin-prompt-disabled", !toggle.checked);
}

document.querySelector("[data-manga-builtin-toggle]")?.addEventListener("change", syncMangaBuiltinPromptControls);
document.querySelector("#loadMangaBuiltinPrompt")?.addEventListener("click", async () => {
  const form = document.querySelector("[data-endpoint='/api/manga-batch']");
  const prompt = document.querySelector("[data-manga-builtin-prompt]");
  const toggle = document.querySelector("[data-manga-builtin-toggle]");
  if (!form || !prompt) return;
  if (toggle) {
    toggle.checked = true;
    syncMangaBuiltinPromptControls();
  }
  const mode = encodeURIComponent(form.querySelector("[name='mode']")?.value || "live_translate");
  const targetLanguage = encodeURIComponent(form.querySelector("[name='target_language']")?.value || "Korean");
  try {
    const response = await fetch(`/api/manga-builtin-prompt?mode=${mode}&target_language=${targetLanguage}`);
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "내장 프롬프트를 불러오지 못했습니다.");
    prompt.value = data.prompt || "";
    showToast("내장 프롬프트를 불러왔습니다.");
  } catch (error) {
    showToast(error.message, true);
  }
});
document.querySelector("#clearMangaBuiltinPrompt")?.addEventListener("click", () => {
  const prompt = document.querySelector("[data-manga-builtin-prompt]");
  if (prompt) prompt.value = "";
  showToast("내장 프롬프트 수정 내용을 비웠습니다.");
});
syncMangaBuiltinPromptControls();

document.querySelector("#libraryPickerGrid").addEventListener("click", async event => {
  const loadMore = event.target.closest("[data-load-more-picker]");
  if (loadMore) {
    pickerVisibleCount += pickerPageSize;
    renderLibraryPicker();
    return;
  }
  const item = event.target.closest(".picker-item");
  if (!item || !pickerTargetForm) return;
  event.preventDefault();
  event.stopPropagation();
  const favorite = event.target.closest("[data-picker-favorite]");
  if (favorite) {
    await togglePickerFavorite(item, favorite);
    return;
  }
  const mediaType = item.dataset.mediaType || mediaTypeForForm(pickerTargetForm);
  if (mediaType === "video" && event.target.closest(".video-play-symbol")) {
    previewPickerMedia(item.dataset.path, "video");
    return;
  }
  if (mediaType !== "video" && event.target.closest(".picker-zoom-symbol")) {
    previewPickerMedia(item.dataset.path, "image");
    return;
  }
  if (templatePickerSlotKey) {
    templateRunState.slots[templatePickerSlotKey] = {
      path: item.dataset.path,
      label: item.querySelector(".picker-label")?.textContent || item.dataset.path,
      kind: mediaType,
    };
    renderTemplateRunPanel();
    document.querySelector("#libraryPickerModal").close();
    showToast("템플릿 슬롯에 라이브러리 항목을 연결했습니다.");
    return;
  }
  try {
    if (isMultiImageSourceForm(pickerTargetForm) && mediaType === "image") {
      addMultiImageLibrarySource(pickerTargetForm, item.dataset.path, item.dataset.path);
      document.querySelector("#libraryPickerModal").close();
      showToast("라이브러리 이미지를 추가했습니다.");
      return;
    }
    if (isVideoEditForm(pickerTargetForm) && mediaType === "video") {
      addMultiVideoLibrarySource(pickerTargetForm, item.dataset.path, item.dataset.path);
      document.querySelector("#libraryPickerModal").close();
      showToast("라이브러리 영상을 추가했습니다.");
      return;
    }
    let hidden = pickerTargetForm.querySelector(`[name='library_${mediaType}_path']`);
    if (!hidden) {
      hidden = document.createElement("input");
      hidden.type = "hidden";
      hidden.name = `library_${mediaType}_path`;
      pickerTargetForm.appendChild(hidden);
    }
    const fileInput = pickerTargetForm.querySelector("input[type='file']");
    hidden.value = item.dataset.path;
    if (fileInput) {
      fileInput.required = false;
      fileInput.value = "";
    }
    setSourcePreview(pickerTargetForm, item.dataset.path, item.dataset.path, mediaType);
    document.querySelector("#libraryPickerModal").close();
    showToast(`라이브러리 ${mediaType === "video" ? "영상" : "이미지"}을 불러왔습니다.`);
  } catch (error) {
    showToast(error.message || "라이브러리 항목을 선택하지 못했습니다.", true);
  }
});

async function loadHealth() {
  const response = await fetch("/health");
  const data = await response.json();
  renderStatus(data);
  refreshQuota();
}

function formatQuotaValue(value) {
  if (!Number.isFinite(value)) return "--";
  return new Intl.NumberFormat("ko-KR").format(value);
}

function quotaPercent(quota) {
  if (!quota || !quota.available_via_api || !Number.isFinite(quota.remaining_percent)) return null;
  return Math.max(0, Math.min(100, quota.remaining_percent));
}

function renderQuota(quota, error = "") {
  const percent = quotaPercent(quota);
  const percentText = percent === null ? "--%" : `${Math.round(percent)}%`;
  const label = `credit ${percentText}`;
  const used = quota?.used;
  const limit = quota?.monthly_limit;
  const remaining = quota?.remaining;
  const detail = percent === null
    ? (error || quota?.message || "OAuth billing 확인 전")
    : `남음 ${formatQuotaValue(remaining)} / 총 ${formatQuotaValue(limit)} · 사용 ${formatQuotaValue(used)}`;
  document.querySelectorAll("[data-quota-label]").forEach(node => {
    node.textContent = label;
  });
  document.querySelectorAll("[data-quota-detail]").forEach(node => {
    node.textContent = detail;
  });
  document.querySelectorAll("[data-quota-bar]").forEach(node => {
    node.style.width = `${percent === null ? 0 : percent}%`;
  });
  const pill = document.querySelector("#quotaPill");
  if (pill) {
    pill.innerHTML = `
      <span class="quota-credit-label">credit</span>
      <span class="quota-battery" aria-hidden="true">
        <span style="width:${percent === null ? 0 : percent}%"></span>
        <strong>${percentText}</strong>
      </span>`;
    pill.title = detail;
    pill.classList.toggle("is-low", percent !== null && percent <= 10 && percent > 5);
    pill.classList.toggle("is-critical", percent !== null && percent <= 5);
    pill.classList.toggle("is-warning", percent !== null && percent < 25);
    pill.classList.toggle("is-empty", percent === null);
  }
}

async function refreshQuota(force = false) {
  const now = Date.now();
  if (!force && now - lastQuotaRefresh < 15000) return;
  lastQuotaRefresh = now;
  try {
    const response = await fetch("/api/oauth/quota");
    const data = await response.json();
    if (!data.ok) throw new Error(data.detail || data.error || "billing 조회 실패");
    renderQuota(data.quota);
  } catch (error) {
    renderQuota(null, error.message);
  }
}

function renderStatus(data) {
  const hermesReady = Boolean(data.hermes_logged_in && data.hermes_proxy_running);
  const codexReady = Boolean(data.codex_proxy_running);
  const statusPill = document.querySelector("#statusPill");
  if (!statusPill) return;
  statusPill.classList.toggle("is-live", hermesReady || codexReady);
  statusPill.classList.toggle("is-mock", !(hermesReady || codexReady));
  statusPill.innerHTML = `
    <span class="mini-service ${hermesReady ? "is-live" : "is-off"}" title="Hermes ${hermesReady ? "연결됨" : "연결안됨"}">
      <span class="status-dot"></span><span>H</span>
    </span>
    <span class="mini-service ${codexReady ? "is-live" : "is-off"}" title="Codex ${codexReady ? "연결됨" : "연결안됨"}">
      <span class="status-dot"></span><span>C</span>
    </span>`;
  const list = document.querySelector("#settingsList");
  const mediaInput = document.querySelector("#mediaRootInput");
  const providerMode = document.querySelector("#providerMode");
  const hermesBaseUrl = document.querySelector("#hermesBaseUrl");
  const codexProxyBaseUrl = document.querySelector("#codexProxyBaseUrl");
  if (mediaInput && data.media_root && !mediaInput.matches(":focus")) mediaInput.value = data.media_root;
  if (providerMode && data.provider && !providerMode.matches(":focus")) providerMode.value = data.provider;
  if (hermesBaseUrl && data.hermes_base_url && !hermesBaseUrl.matches(":focus")) hermesBaseUrl.value = data.hermes_base_url;
  if (codexProxyBaseUrl && data.codex_proxy_base_url && !codexProxyBaseUrl.matches(":focus")) codexProxyBaseUrl.value = data.codex_proxy_base_url;
  if (list) list.innerHTML = `
    <dt>모드</dt><dd>${data.mode}</dd>
    <dt>Provider</dt><dd>${data.provider || "direct"}</dd>
    <dt>Hermes Proxy</dt><dd>${data.hermes_configured ? data.hermes_base_url : "없음"}</dd>
    <dt>Codex Proxy</dt><dd>${data.codex_proxy_running ? `실행 중 · ${data.codex_proxy_base_url || ""}` : (data.codex_proxy_configured ? `대기 · ${data.codex_proxy_base_url || ""}` : "없음")}</dd>
    <dt>OAuth</dt><dd>${data.oauth_configured ? "연결됨" : "없음"}</dd>
    <dt>만료 시각</dt><dd>${data.oauth_expires_at ? new Date(data.oauth_expires_at * 1000).toLocaleString() : "없음"}</dd>
    <dt>API 키</dt><dd>${data.api_key_configured ? (data.session_login ? "세션 로그인" : "환경변수") : "없음"}</dd>
    <dt>관리 키</dt><dd>${data.management_configured ? "설정됨" : "없음"}</dd>
    <dt>이미지 모델</dt><dd>${data.models.image}</dd>
    <dt>Codex 이미지</dt><dd>${data.models.codex_image || "gpt-5.4-mini"}</dd>
    <dt>영상 모델</dt><dd>${data.models.video}</dd>
    <dt>비전 모델</dt><dd>${data.models.vision}</dd>
    <dt>저장 경로</dt><dd>${data.media_root || "기본값"}</dd>
    <dt>최근 오류</dt><dd>${data.last_error ? data.last_error.message : "없음"}</dd>`;
}

const renderStatusBase = renderStatus;
renderStatus = function renderStatus(data) {
  renderStatusBase(data);
  const list = document.querySelector("#settingsList");
  if (list) {
    const proxyText = data.hermes_proxy_running
      ? `실행 중 · ${data.hermes_base_url || ""}`
      : (data.hermes_configured ? `꺼짐 · ${data.hermes_base_url || ""}` : "없음");
    const rows = Array.from(list.querySelectorAll("dt"));
    const proxyRow = rows.find(node => node.textContent.includes("Hermes Proxy"));
    if (proxyRow?.nextElementSibling) proxyRow.nextElementSibling.textContent = proxyText;
    if (!rows.some(node => node.textContent.includes("Hermes OAuth"))) {
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = "Hermes OAuth";
      dd.textContent = data.hermes_logged_in ? "연결됨" : "없음";
      list.insertBefore(dt, proxyRow || list.firstChild);
      list.insertBefore(dd, proxyRow || list.firstChild);
    }
  }
};

document.querySelector("#providerForm")?.addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());
  payload.clear_hermes_api_key = formData.has("clear_hermes_api_key");
  payload.clear_codex_proxy_base_url = formData.has("clear_codex_proxy_base_url");
  try {
    const response = await fetch("/api/settings/provider", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "Provider 설정 실패");
    form.querySelector("[name='hermes_api_key']").value = "";
    form.querySelector("[name='clear_hermes_api_key']").checked = false;
    form.querySelector("[name='clear_codex_proxy_base_url']").checked = false;
    showToast("Provider 설정을 저장했습니다.");
    await loadHealth();
  } catch (error) {
    showToast(error.message, true);
  }
});

document.querySelector("#startCodexProxy")?.addEventListener("click", async () => {
  const button = document.querySelector("#startCodexProxy");
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "시작 중";
  try {
    const response = await fetch("/api/codex-proxy/start", { method: "POST" });
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || data.detail || "Codex Proxy 시작 실패");
    showToast(data.message || "Codex Proxy를 시작했습니다.");
    await loadHealth();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
});

document.querySelector("#testHermesProxy")?.addEventListener("click", async () => {
  try {
    const response = await fetch("/api/settings/hermes-test", { method: "POST" });
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || data.detail || "Hermes 연결 실패");
    showToast(`Hermes 응답 확인: ${data.status_code}`);
  } catch (error) {
    showToast(error.message, true);
  }
});

document.querySelector("#loginForm").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = Object.fromEntries(new FormData(form).entries());
  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "로그인 실패");
    form.reset();
    showToast("연결되었습니다.");
    await loadAuthStatus();
  } catch (error) {
    showToast(error.message, true);
  }
});

document.querySelector("#logoutButton").addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST" });
  showToast("로그아웃되었습니다.");
  await loadAuthStatus();
});

document.querySelector("#mediaRootForm").addEventListener("submit", async event => {
  event.preventDefault();
  const media_root = document.querySelector("#mediaRootInput").value.trim();
  try {
    const response = await fetch("/api/settings/media-root", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ media_root }),
    });
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "저장 경로 설정 실패");
    showToast("저장 경로를 적용했습니다.");
    await loadHealth();
    await loadLibrary();
  } catch (error) {
    showToast(error.message, true);
  }
});

document.querySelector("#browseMediaRoot").addEventListener("click", async () => {
  const button = document.querySelector("#browseMediaRoot");
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "선택 중";
  try {
    const response = await fetch("/api/settings/browse-media-root", { method: "POST" });
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "폴더 선택 실패");
    if (!data.cancelled) showToast("저장 경로를 적용했습니다.");
    await loadHealth();
    await loadLibrary();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
});

async function loadAuthStatus() {
  const response = await fetch("/api/auth/status");
  const data = await response.json();
  renderStatus({ ...data, last_error: null });
}

async function openErrorLog(errorLog = null) {
  const modal = document.querySelector("#errorModal");
  const output = document.querySelector("#errorLogText");
  if (errorLog) {
    output.value = JSON.stringify(errorLog, null, 2);
    if (!modal.open) modal.showModal();
    return;
  }
  try {
    const response = await fetch("/api/error-log");
    const data = await response.json();
    output.value = data.last_error ? JSON.stringify(data.last_error, null, 2) : "최근 오류가 없습니다.";
  } catch (error) {
    output.value = String(error);
  }
  if (!modal.open) modal.showModal();
}

document.querySelector("#showErrorLog").addEventListener("click", openErrorLog);
document.querySelector("#closeErrorModal").addEventListener("click", () => document.querySelector("#errorModal").close());
document.querySelector("#copyErrorLog").addEventListener("click", async () => {
  await navigator.clipboard.writeText(document.querySelector("#errorLogText").value);
  showToast("오류 로그를 복사했습니다.");
});
document.querySelector("#mediaViewer")?.addEventListener("click", event => {
  if (event.target.closest("video")) return;
  closeMediaViewer();
});

document.querySelector("#mediaViewer")?.addEventListener("close", event => {
  event.currentTarget.classList.remove("open");
  event.currentTarget.querySelector(".media-viewer-stage").innerHTML = "";
});

document.addEventListener("keydown", event => {
  if (event.key === "Escape") closeMediaViewer();
});

document.querySelector("#queueList")?.addEventListener("click", event => {
  const node = event.target.closest(".queue-job");
  if (!node) return;
  const job = jobQueue.find(item => item.id === node.dataset.id);
  if (!job) return;
  if (event.target.closest("[data-template-review-next]")) {
    resolveTemplateReview(job, "next");
    return;
  }
  if (event.target.closest("[data-template-review-retry]")) {
    resolveTemplateReview(job, "retry");
    return;
  }
  if (event.target.closest("[data-cancel-job]")) {
    updateJob(job, { status: "cancelled" });
    resolveTemplateReview(job, "cancel");
    return;
  }
  if (event.target.closest("[data-remove-job]")) {
    const index = jobQueue.findIndex(item => item.id === job.id);
    if (index >= 0) jobQueue.splice(index, 1);
    renderQueue();
    return;
  }
  if (event.target.closest("[data-view-job]") || (!event.target.closest("button") && job.status === "done")) {
    if (!showJobResult(job)) {
      showToast("표시할 결과물이 없습니다.", true);
    }
  }
});
document.querySelector("#clearDoneJobs")?.addEventListener("click", () => {
  for (let index = jobQueue.length - 1; index >= 0; index -= 1) {
    if (["done", "failed", "cancelled"].includes(jobQueue[index].status)) {
      jobQueue.splice(index, 1);
    }
  }
  renderQueue();
});

function installHermesAuthPanel() {
  const grid = document.querySelector("#settings .settings-grid");
  if (!grid || document.querySelector("#hermesAuthPanel")) return;
  const card = document.createElement("div");
  card.className = "settings-card";
  card.id = "hermesAuthPanel";
  card.innerHTML = `
    <h2>Hermes xAI OAuth</h2>
    <p class="note">터미널 없이 Hermes 인증을 진행합니다. 인증 시작 후 열린 xAI/Grok 화면의 코드를 복사해 아래에 붙여넣으세요.</p>
    <div class="button-row">
      <button type="button" id="startHermesAuth">인증 시작</button>
      <button type="button" id="startHermesProxy" class="secondary">Proxy 시작</button>
      <button type="button" id="resetHermesAuth" class="secondary">상태 리셋</button>
      <button type="button" id="logoutHermesAuth" class="secondary danger-btn">로그아웃</button>
    </div>
    <div id="hermesAuthBox" class="auth-code-box" hidden>
      <a id="hermesAuthUrl" class="button-link login-wide secondary" href="#" target="_blank" rel="noreferrer">xAI 인증 페이지 열기</a>
      <label>인증 코드</label>
      <input type="text" id="hermesAuthCode" autocomplete="off" placeholder="xAI 화면에 표시된 코드를 붙여넣기">
      <div class="button-row">
        <button type="button" id="submitHermesCode">코드로 로그인 완료</button>
      </div>
    </div>
    <p class="note" id="hermesAuthStatus">상태 확인 전</p>
  `;
  grid.insertBefore(card, grid.children[1] || null);
  bindHermesAuthPanel();
}

function setHermesAuthStatus(message, isError = false) {
  const status = document.querySelector("#hermesAuthStatus");
  if (!status) return;
  status.textContent = message;
  status.classList.toggle("error-text", isError);
}

function setConnectionBadge(service, connected, text) {
  const row = document.querySelector(`[data-connection-service="${service}"]`);
  if (!row) return;
  row.classList.toggle("is-connected", Boolean(connected));
  row.classList.toggle("is-disconnected", !connected);
  const label = row.querySelector("[data-connection-label]");
  if (label) label.textContent = text || (connected ? "연결됨" : "연결안됨");
}

let pendingHermesAuthAutoOpen = false;
let lastOpenedHermesAuthUrl = "";

function showHermesAuthUrl(url, openOnce = false) {
  const box = document.querySelector("#hermesAuthBox");
  const link = document.querySelector("#hermesAuthUrl");
  if (!box || !link || !url) return;
  box.hidden = false;
  link.href = url;
  if (openOnce && url !== lastOpenedHermesAuthUrl) {
    lastOpenedHermesAuthUrl = url;
    pendingHermesAuthAutoOpen = false;
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

async function refreshHermesAuthPanel() {
  try {
    const response = await fetch("/api/hermes/auth/status");
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "Hermes 상태 확인 실패");
    if (data.logged_in) {
      setConnectionBadge("hermes", Boolean(data.proxy_running), data.proxy_running ? "연결됨" : "Proxy 꺼짐");
      setHermesAuthStatus(data.proxy_running ? "Hermes OAuth 연결됨 · Proxy 실행 중" : "Hermes OAuth 연결됨 · Proxy 대기 중");
      return;
    }
    setConnectionBadge("hermes", false, data.running ? "인증 중" : "연결안됨");
    if (data.running) {
      setHermesAuthStatus(data.auth_url ? "인증 페이지에서 코드를 복사해 붙여넣으세요." : "Hermes 인증 URL을 준비 중입니다.");
      if (data.auth_url) showHermesAuthUrl(data.auth_url, pendingHermesAuthAutoOpen);
      return;
    }
    setHermesAuthStatus("Hermes OAuth 로그인이 필요합니다.");
  } catch (error) {
    setConnectionBadge("hermes", false, "확인 실패");
    setHermesAuthStatus(error.message, true);
  }
}

function bindHermesAuthPanel() {
  document.querySelector("#startHermesAuth")?.addEventListener("click", async () => {
    const button = document.querySelector("#startHermesAuth");
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "준비 중";
    pendingHermesAuthAutoOpen = true;
    try {
      const response = await fetch("/api/hermes/auth/start", { method: "POST" });
      const data = await response.json();
      if (!data.ok) throw new Error(data.error || data.detail || "Hermes 인증 시작 실패");
      if (data.already_logged_in) {
        pendingHermesAuthAutoOpen = false;
        setHermesAuthStatus("이미 Hermes OAuth에 연결되어 있습니다.");
        showToast("Hermes OAuth가 이미 연결되어 있습니다.");
      } else if (data.auth_url) {
        showHermesAuthUrl(data.auth_url, true);
        setHermesAuthStatus("브라우저 인증 화면의 코드를 복사해 아래에 붙여넣으세요.");
      } else {
        setHermesAuthStatus("인증 URL을 준비 중입니다. 잠시 후 다시 확인합니다.");
      }
    } catch (error) {
      pendingHermesAuthAutoOpen = false;
      showToast(error.message, true);
      setHermesAuthStatus(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  });

  document.querySelector("#submitHermesCode")?.addEventListener("click", async () => {
    const input = document.querySelector("#hermesAuthCode");
    const code = input.value.trim();
    if (!code) {
      showToast("인증 코드를 붙여넣어 주세요.", true);
      return;
    }
    const button = document.querySelector("#submitHermesCode");
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "확인 중";
    try {
      const response = await fetch("/api/hermes/auth/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      });
      const data = await response.json();
      if (!data.ok) throw new Error(data.error || data.detail || data.status || "Hermes 로그인 실패");
      input.value = "";
      setHermesAuthStatus(data.proxy_started ? "Hermes OAuth 연결됨 · Proxy 실행 중" : "Hermes OAuth 연결됨");
      showToast("Hermes OAuth 로그인이 완료되었습니다.");
      await loadHealth();
    } catch (error) {
      showToast(error.message, true);
      setHermesAuthStatus(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  });

  document.querySelector("#startHermesProxy")?.addEventListener("click", async () => {
    try {
      const response = await fetch("/api/hermes/proxy/start", { method: "POST" });
      const data = await response.json();
      if (!data.ok) throw new Error(data.error || data.detail || "Hermes Proxy 시작 실패");
      setHermesAuthStatus("Hermes Proxy 실행 중");
      showToast(data.message || "Hermes Proxy를 시작했습니다.");
      await loadHealth();
    } catch (error) {
      showToast(error.message, true);
      setHermesAuthStatus(error.message, true);
    }
  });

  document.querySelector("#logoutHermesAuth")?.addEventListener("click", async () => {
    const button = document.querySelector("#logoutHermesAuth");
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "로그아웃 중";
    try {
      const response = await fetch("/api/hermes/auth/logout", { method: "POST" });
      const data = await response.json();
      if (!data.ok) throw new Error(data.error || data.detail || "Hermes 로그아웃 실패");
      document.querySelector("#hermesAuthCode").value = "";
      document.querySelector("#hermesAuthBox").hidden = true;
      setHermesAuthStatus(data.proxy_running ? "Hermes OAuth 로그아웃됨 · Proxy 재시작 필요" : "Hermes OAuth 로그아웃됨");
      showToast("Hermes OAuth에서 로그아웃했습니다.");
      await loadHealth();
    } catch (error) {
      showToast(error.message, true);
      setHermesAuthStatus(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  });

  document.querySelector("#resetHermesAuth")?.addEventListener("click", async () => {
    const button = document.querySelector("#resetHermesAuth");
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "리셋 중";
    try {
      const response = await fetch("/api/hermes/auth/reset", { method: "POST" });
      const data = await response.json();
      if (!data.ok) throw new Error(data.error || data.detail || "Hermes 상태 리셋 실패");
      if (data.logged_in) {
        setHermesAuthStatus(data.proxy_running ? "Hermes OAuth 상태 리셋됨 · Proxy 실행 중" : "Hermes OAuth 상태 리셋됨");
        showToast("Hermes OAuth 상태를 리셋했습니다.");
      } else {
        setHermesAuthStatus("Hermes OAuth 상태 리셋됨 · 다시 인증이 필요합니다.");
        showToast("상태를 리셋했습니다. 다시 인증해 주세요.", true);
      }
      await loadHealth();
    } catch (error) {
      showToast(error.message, true);
      setHermesAuthStatus(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  });

  refreshHermesAuthPanel();
  setInterval(refreshHermesAuthPanel, 5000);
}

function installCodexProxyPanel() {
  const grid = document.querySelector("#settings .settings-grid");
  if (!grid || document.querySelector("#codexProxyPanel")) return;
  const card = document.createElement("div");
  card.className = "settings-card";
  card.id = "codexProxyPanel";
  card.innerHTML = `
    <h2>Codex / ChatGPT OAuth</h2>
    <p class="note">Codex OAuth 로컬 프록시 연결 상태를 확인합니다. 이미지 생성/편집에서 gpt-5 모델을 쓰려면 Provider를 Codex/ChatGPT OAuth Local Proxy로 선택하세요.</p>
    <div class="button-row">
      <button type="button" id="codexProxyStartPanel">Codex Proxy 시작</button>
      <button type="button" id="codexProxyRefresh" class="secondary">상태 새로고침</button>
    </div>
    <dl class="status-list" id="codexProxyStatusList">
      <dt>상태</dt><dd>확인 전</dd>
    </dl>
    <p class="note" id="codexProxyStatusText">상태 확인 전</p>
  `;
  grid.insertBefore(card, document.querySelector("#hermesAuthPanel") || grid.children[1] || null);
  bindCodexProxyPanel();
}

function setCodexProxyStatus(message, isError = false) {
  const status = document.querySelector("#codexProxyStatusText");
  if (!status) return;
  status.textContent = message;
  status.classList.toggle("error-text", isError);
}

async function refreshCodexProxyPanel() {
  const list = document.querySelector("#codexProxyStatusList");
  try {
    const response = await fetch("/api/codex-proxy/status");
    const data = await response.json();
    if (!data.ok) throw new Error(data.error || "Codex Proxy 상태 확인 실패");
    const connected = Boolean(data.running && data.oauth_status === "ready");
    setConnectionBadge("codex", connected, connected ? "연결됨" : (data.running ? "OAuth 확인 중" : "연결안됨"));
    if (list) list.innerHTML = `
      <dt>상태</dt><dd>${data.running ? "실행 중" : "꺼짐"}</dd>
      <dt>Provider</dt><dd>${data.provider || "없음"}</dd>
      <dt>OAuth</dt><dd>${data.oauth_status || "없음"}</dd>
      <dt>URL</dt><dd>${data.backend_url || data.base_url || "없음"}</dd>
      <dt>버전</dt><dd>${data.version || "없음"}</dd>`;
    if (data.running) {
      setCodexProxyStatus(data.oauth_status ? `Codex OAuth Proxy 실행 중 · ${data.oauth_status}` : "Codex OAuth Proxy 실행 중");
    } else {
      setCodexProxyStatus(data.configured ? "Codex Proxy가 꺼져 있습니다." : "Codex Proxy URL이 설정되지 않았습니다.", !data.configured);
    }
  } catch (error) {
    setConnectionBadge("codex", false, "확인 실패");
    setCodexProxyStatus(error.message, true);
  }
}

function bindCodexProxyPanel() {
  document.querySelector("#codexProxyStartPanel")?.addEventListener("click", async () => {
    const button = document.querySelector("#codexProxyStartPanel");
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "시작 중";
    try {
      const response = await fetch("/api/codex-proxy/start", { method: "POST" });
      const data = await response.json();
      if (!data.ok) throw new Error(data.error || data.detail || "Codex Proxy 시작 실패");
      showToast(data.message || "Codex Proxy를 시작했습니다.");
      await refreshCodexProxyPanel();
      await loadHealth();
    } catch (error) {
      showToast(error.message, true);
      setCodexProxyStatus(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  });
  document.querySelector("#codexProxyRefresh")?.addEventListener("click", refreshCodexProxyPanel);
  refreshCodexProxyPanel();
  setInterval(refreshCodexProxyPanel, 5000);
}

function removeCardContaining(selector) {
  const node = document.querySelector(selector);
  const card = node?.closest(".settings-card");
  if (card) card.remove();
}

function compactSettingsLayout() {
  removeCardContaining("#providerForm");
  removeCardContaining("#loginForm");
  removeCardContaining("#settingsList");
  const oldUsageLink = document.querySelector("a[href='https://grok.com/?_s=usage']");
  const oldUsageCard = oldUsageLink?.closest(".settings-card");
  if (oldUsageCard && !oldUsageCard.id) oldUsageCard.remove();
}

function installQuotaPanel() {
  const grid = document.querySelector("#settings .settings-grid");
  if (!grid || document.querySelector("#quotaPanel")) return;
  const card = document.createElement("div");
  card.className = "settings-card quota-card";
  card.id = "quotaPanel";
  card.innerHTML = `
    <div class="settings-card-head">
      <h2>무료 크레딧</h2>
      <button type="button" id="refreshQuotaButton" class="secondary compact-button">새로고침</button>
    </div>
    <div class="quota-meter">
      <div class="quota-meter-head">
        <strong data-quota-label>잔량 --%</strong>
        <span>Grok OAuth billing</span>
      </div>
      <div class="quota-track"><span data-quota-bar></span></div>
      <p class="note" data-quota-detail>OAuth billing 확인 전</p>
    </div>
    <a class="button-link login-wide secondary" href="https://grok.com/?_s=usage" target="_blank" rel="noreferrer">공식 Usage 페이지 열기</a>
  `;
  const connection = document.querySelector("#connectionStatusPanel");
  grid.insertBefore(card, connection?.nextSibling || grid.firstChild);
  document.querySelector("#refreshQuotaButton")?.addEventListener("click", () => refreshQuota(true));
}

function installConnectionStatusPanel() {
  const grid = document.querySelector("#settings .settings-grid");
  const existing = document.querySelector("#connectionStatusPanel");
  if (!grid) return;
  if (existing) {
    bindHermesAuthPanel();
    bindCodexProxyPanel();
    return;
  }
  const card = document.createElement("div");
  card.className = "settings-card connection-card";
  card.id = "connectionStatusPanel";
  card.innerHTML = `
    <h2>연결 상태</h2>
    <div class="connection-list">
      <div class="connection-row is-disconnected" data-connection-service="hermes">
        <span class="connection-icon" aria-hidden="true"></span>
        <div class="connection-main">
          <strong>Hermes xAI</strong>
          <small id="hermesAuthStatus">상태 확인 전</small>
        </div>
        <span class="connection-state" data-connection-label>연결안됨</span>
        <div class="connection-actions">
          <button type="button" id="startHermesAuth" class="secondary">인증</button>
          <button type="button" id="startHermesProxy" class="secondary">Proxy</button>
          <button type="button" id="resetHermesAuth" class="secondary">리셋</button>
          <button type="button" id="logoutHermesAuth" class="secondary danger-btn">로그아웃</button>
        </div>
      </div>
      <div id="hermesAuthBox" class="auth-code-box compact-auth" hidden>
        <a id="hermesAuthUrl" class="button-link login-wide secondary" href="#" target="_blank" rel="noreferrer">xAI 인증 페이지 열기</a>
        <label>인증 코드</label>
        <input type="text" id="hermesAuthCode" autocomplete="off" placeholder="xAI 화면의 코드를 붙여넣기">
        <button type="button" id="submitHermesCode">코드로 로그인 완료</button>
      </div>
      <div class="connection-row is-disconnected" data-connection-service="codex">
        <span class="connection-icon" aria-hidden="true"></span>
        <div class="connection-main">
          <strong>Codex / ChatGPT</strong>
          <small id="codexProxyStatusText">상태 확인 전</small>
        </div>
        <span class="connection-state" data-connection-label>연결안됨</span>
        <div class="connection-actions">
          <button type="button" id="codexProxyStartPanel" class="secondary">시작</button>
          <button type="button" id="codexProxyRefresh" class="secondary">새로고침</button>
        </div>
      </div>
      <dl class="status-list visually-hidden" id="codexProxyStatusList"></dl>
    </div>
  `;
  grid.insertBefore(card, grid.firstChild);
  bindHermesAuthPanel();
  bindCodexProxyPanel();
}

compactSettingsLayout();
installConnectionStatusPanel();
installQuotaPanel();
syncLibraryPreferenceControls();
renderQueue();
loadHealth();
loadLibrary();
