"use strict";

let pyBridge = null;
let appSettings = {};
let videoRecording = false;
let preferenceTimer = null;

const canvas = document.getElementById("main-canvas");
// "ctx" troca de canvas por um instante durante a exportação (ver exportDataUrl).
let ctx = canvas.getContext("2d");
const canvasContainer = document.getElementById("canvas-container");
const emptyState = document.getElementById("empty-state");
const workspace = document.getElementById("workspace");

let bgImage = null;
let annotations = [];
let currentTool = "Mover";
let isDrawing = false;
let startPoint = null;
let preview = null;
let currentPoints = [];
// Mesma lista, ja suavizada. E mantida ponto a ponto durante o traco: refazer a
// suavizacao inteira a cada movimento do mouse deixava o risco cada vez mais
// lento conforme ele crescia.
let currentSmooth = [];
const strokeWidths = {Caneta: 4, MarcaTexto: 16};
// Cada ferramenta guarda o seu proprio tamanho, e o campo da faixa mostra o da
// ferramenta ativa: fonte do texto e das cotas, diametro do balao, altura do
// triangulo de revisao, ponta da seta e raio do festonado da nuvem.
const toolSizes = {Texto: 28, Chamada: 24, CotaLivre: 22, CotaAngulo: 22, Seta: 22, Balao: 28, Revisao: 28, Nuvem: 9};
// A setinha dos menus: o mesmo triângulo cheio dos seletores do programa.
const CARET_SVG = '<svg class="caret-glyph" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 10l5 5 5-5z"/></svg>';
const sizeLabels = {Texto: "Fonte", Chamada: "Fonte", CotaLivre: "Fonte", CotaAngulo: "Fonte", Seta: "Ponta", Balao: "Balão", Revisao: "Triângulo", Nuvem: "Raio"};
let recentColors = [];
let activeFormatPopover = null;
let formatPopoverAnchor = null;
let selectedIndex = -1;
let interactionMode = null;
let dragOffset = {x: 0, y: 0};
let zoomLevel = 1;
let activeTextEditor = null;
let orthogonalPath = null;
const labelTools = new Set(["CotaLivre", "CotaAngulo", "Chamada"]);
const boxResizeTools = new Set(["Retangulo", "Circulo", "Cobrir", "Nuvem", "Texto"]);
const strokeResizeTools = new Set(["Caneta", "MarcaTexto"]);
// A cota livre e a cota de angulo tambem ganham alcas nas pontas: depois de
// desenhadas da para mudar comprimento e angulo sem refazer a marcacao.
const lineResizeTools = new Set(["Linha", "Seta", "Chamada", "CotaLivre", "CotaAngulo"]);
// Quem se beneficia de ficar exatamente na horizontal ou na vertical. A cota é
// o caso que mais pede: uma medida tem que sair reta, e na mão nunca sai. Na
// cota de ângulo, encaixar nos eixos a partir do vértice é o mesmo que travar
// em 90, 180, 270 e 360 graus.
const axisSnapTools = new Set(["Linha", "Seta", "Chamada", "CotaLivre", "CotaAngulo"]);
// Balao e triangulo de revisao: qualquer uma das oito alcas escala a marcacao
// inteira a partir do centro.
const markerResizeTools = new Set(["Balao", "Revisao"]);
const CLOUD_DEFAULT_RADIUS = 9;
const DEFAULT_DIM_EXTENSION = 34;
// Distancia minima entre pontos do traco a mao livre, antes da suavizacao.
const STROKE_MIN_DISTANCE = 1.8;
// O canvas e rasterizado acima da resolucao da tela e reduzido pelo navegador:
// e isso que tira o serrilhado da borda do traco.
const RENDER_OVERSAMPLE = 2;
// Nuvem de revisao desenhada a mao livre, em vez de retangular.
let cloudFreeMode = false;
// Balão e triângulo avançam o número sozinhos a cada marcação. Desligado pelo
// menu da própria ferramenta, o valor digitado fica fixo e repete.
let autoSequence = {Balao: true, Revisao: true};
// Ferramenta do menu aberto: quem mexe na faixa precisa redesenhar o menu.
let openToolConfig = null;
let workspaceMode = "home";
let homeBgImage = null;
let homeAnnotations = annotations;
let editionAnnotations = [];
let editionItems = [];
let editionCanvasSize = {width: 1600, height: 1000};
let selectedEditionItemIndex = -1;
let pendingCaptureTarget = "home";
let redrawPending = false;
// Tamanho do documento (a imagem capturada ou a página da guia Edição), em
// pixels da própria imagem. É nesse sistema que ficam todas as marcações.
// O canvas visível é criado no tamanho em que o desenho aparece na tela, e o
// desenho é feito com uma escala: assim cada traço é rasterizado no tamanho
// exibido, sem o serrilhado de esticar/encolher um bitmap já pronto.
let docWidth = 1600;
let docHeight = 1000;
// Teto de memória do canvas visível; acima disso o zoom volta a ampliar o
// bitmap (uma imagem 4K com zoom alto passaria de centenas de MB).
const MAX_RENDER_PIXELS = 16000000;
let exportCanvas = null;
let exportCtx = null;
// Cópia da imagem de fundo já reduzida, usada quando o zoom é bem pequeno.
let bgProxyCanvas = null;
let bgProxySource = null;
let bgProxyWidth = 0;
let resizeCorner = null;
// Histórico de desfazer/refazer (Ctrl+Z / Ctrl+Y).
const HISTORY_LIMIT = 60;
let historyStack = [];
let redoStack = [];
let pendingHistorySnapshot = null;
let pendingHistorySignature = "";
// Área de transferência interna: copiar/colar de marcações e imagens (Ctrl+C / Ctrl+V).
let elementClipboard = null;
// Cliques repetidos no mesmo ponto percorrem os elementos sobrepostos.
let hitCycleState = {x: null, y: null, key: "", position: 0};

function byId(id) {
    return document.getElementById(id);
}

function initializeGreeting(name) {
    const hour = new Date().getHours();
    const greeting = hour >= 5 && hour < 12 ? "Bom dia" : (hour < 18 ? "Boa tarde" : "Boa noite");
    const displayName = String(name || appSettings.user?.name || "Calavort").trim() || "Calavort";
    byId("greeting-text").textContent = `${greeting}, ${displayName}`;
}

function setStatus(message) {
    byId("status-text").textContent = message || "Pronto.";
}

function updateReleaseState(state) {
    byId("update-version").textContent = `Versao ${state.version}`;
    byId("update-status").textContent = state.message;
    byId("update-status").title = state.message;
    byId("btn-check-update").disabled = state.busy;
    byId("btn-install-update").disabled = state.busy || !state.available;
}

function serializeUpdateSession() {
    try {
        finishActiveCommand(true);
        clearTimeout(preferenceTimer);
        clearTimeout(clipboardSyncTimer);
        if (pyBridge) pyBridge.savePreferences(JSON.stringify(readPreferences()));
        const imageData = image => {
            if (!image) return null;
            const buffer = document.createElement("canvas");
            buffer.width = image.naturalWidth || image.width;
            buffer.height = image.naturalHeight || image.height;
            buffer.getContext("2d").drawImage(image, 0, 0);
            return buffer.toDataURL("image/png");
        };
        const state = snapshotState();
        return JSON.stringify({
            schema: 1, workspaceMode,
            homeAnnotations: state.homeAnnotations,
            editionAnnotations: state.editionAnnotations,
            editionCanvasSize: state.editionCanvasSize,
            bgImage: imageData(state.bgImage),
            editionItems: state.editionItems.map(item => {
                const {image, source, ...rest} = item;
                return {...rest, source: imageData(image)};
            })
        });
    } catch (error) {
        return JSON.stringify({error: `Nao foi possivel preservar a edicao: ${error.message}`});
    }
}

async function restoreUpdateSession(state) {
    try {
        if (state.schema !== 1) throw new Error("Formato desconhecido.");
        const load = source => new Promise((resolve, reject) => {
            if (!source) return resolve(null);
            const image = new Image();
            image.onload = () => resolve(image);
            image.onerror = () => reject(new Error("Imagem indisponivel."));
            image.src = source;
        });
        const restored = {...state, bgImage: await load(state.bgImage)};
        restored.editionItems = await Promise.all(state.editionItems.map(async item => ({
            ...item, image: await load(item.source)
        })));
        workspaceMode = state.workspaceMode === "edition" ? "edition" : "home";
        restoreState(restored);
        const tabId = workspaceMode === "edition" ? "tab-edicao" : "tab-home";
        const tab = document.querySelector(`.ribbon-tab[onclick*="'${tabId}'"]`);
        if (tab) switchTab(tabId, tab);
        fitToWorkspace();
        if (pyBridge) pyBridge.acknowledgeUpdateSession();
    } catch (error) {
        setStatus(`A edicao anterior nao foi recuperada: ${error.message}`);
    }
}

function switchTab(tabId, element) {
    document.querySelectorAll(".ribbon-tab").forEach(tab => tab.classList.remove("active"));
    document.querySelectorAll(".ribbon-content").forEach(content => content.classList.remove("active"));
    element.classList.add("active");
    byId(tabId).classList.add("active");
    setWorkspaceMode(tabId === "tab-edicao" ? "edition" : "home");
}

function appBridge(action) {
    if (pyBridge && typeof pyBridge[action] === "function") {
        pyBridge[action]();
    } else {
        setStatus("A interface com o programa ainda não está disponível.");
    }
}

function initializeBridge() {
    if (typeof qt === "undefined" || !qt.webChannelTransport || typeof QWebChannel === "undefined") {
        initializeGreeting();
        return;
    }
    new QWebChannel(qt.webChannelTransport, channel => {
        pyBridge = channel.objects.bridge;
        // O programa chama loadImageData, setStatus, applySettings,
        // updateVideoState e updateMaximizeIcon diretamente.
        pyBridge.requestSettings();
    });
}

function setInputValue(id, value) {
    const input = byId(id);
    if (input && value !== undefined && value !== null) input.value = value;
}

function compactPath(path) {
    const parts = String(path || "").replaceAll("\\", "/").split("/").filter(Boolean);
    return parts.length > 2 ? `.../${parts.slice(-2).join("/")}` : String(path || "");
}

function applySettings(settings) {
    appSettings = settings || {};
    const user = appSettings.user || {};
    setInputValue("user-name", user.name || "");
    setInputValue("user-email", user.email || "");
    initializeGreeting(user.name);

    setInputValue("cfg-delay", appSettings.delay ?? 0);
    byId("cfg-autocopy").checked = Boolean(appSettings.auto_copy);
    byId("cfg-autosave").checked = Boolean(appSettings.auto_save);
    setInputValue("cfg-video-format", appSettings.video_format || "mp4");
    setInputValue("cfg-video-fps", appSettings.video_fps || 30);
    setInputValue("cfg-video-audio", appSettings.video_audio || "none");
    setInputValue("cfg-cor", appSettings.color || "#107C41");
    setInputValue("cfg-espessura", appSettings.thickness || 4);
    strokeWidths.Caneta = Math.max(1, Math.min(20, Number(appSettings.pen_thickness) || 4));
    strokeWidths.MarcaTexto = Math.max(4, Math.min(80, Number(appSettings.highlighter_thickness) || 16));
    recentColors = Array.isArray(appSettings.recent_colors)
        ? appSettings.recent_colors.filter(color => /^#[0-9a-f]{6}$/i.test(color)).slice(0, 10) : [];
    const savedSizes = appSettings.tool_sizes && typeof appSettings.tool_sizes === "object" ? appSettings.tool_sizes : {};
    Object.keys(toolSizes).forEach(tool => {
        if (savedSizes[tool] !== undefined) toolSizes[tool] = clampToolSize(tool, savedSizes[tool]);
    });
    if (appSettings.font_size) toolSizes.Texto = clampToolSize("Texto", appSettings.font_size);
    setInputValue("cfg-fonte", toolSizes.Texto);
    setInputValue("cfg-numero", appSettings.number ?? 1);
    cloudFreeMode = Boolean(appSettings.cloud_free);
    const savedSequence = appSettings.auto_sequence;
    if (savedSequence && typeof savedSequence === "object") {
        autoSequence = {Balao: savedSequence.Balao !== false, Revisao: savedSequence.Revisao !== false};
    }
    if (byId("cfg-balao-fill")) byId("cfg-balao-fill").checked = appSettings.balloon_fill !== false;
    if (byId("cfg-balao-line")) byId("cfg-balao-line").checked = Boolean(appSettings.balloon_line);
    if (byId("cfg-revisao-fill")) byId("cfg-revisao-fill").checked = Boolean(appSettings.review_fill);
    if (byId("cfg-nuvem-livre")) byId("cfg-nuvem-livre").checked = cloudFreeMode;
    if (byId("cfg-texto-auto")) byId("cfg-texto-auto").checked = appSettings.text_autogrow !== false;
    byId("btn-bold").classList.toggle("active", Boolean(appSettings.bold));
    byId("btn-italic").classList.toggle("active", Boolean(appSettings.italic));
    byId("btn-underline").classList.toggle("active", Boolean(appSettings.underline));

    const shortcuts = appSettings.shortcuts || {};
    setInputValue("hk-area", shortcuts.area || "Alt+P");
    setInputValue("hk-copy", shortcuts.copy || "Ctrl+C");
    setInputValue("hk-save", shortcuts.save || "Ctrl+S");
    setInputValue("hk-undo", shortcuts.undo || "Ctrl+Z");
    setInputValue("image-folder", compactPath(appSettings.image_folder || ".../capturas"));
    setInputValue("video-folder", compactPath(appSettings.video_folder || ".../videos"));
    syncEditionFormatControlsFromMain();
}

function readPreferences() {
    return {
        delay: Number(byId("cfg-delay").value) || 0,
        auto_copy: byId("cfg-autocopy").checked,
        auto_save: byId("cfg-autosave").checked,
        video_format: byId("cfg-video-format").value,
        video_fps: Number(byId("cfg-video-fps").value) || 30,
        video_audio: byId("cfg-video-audio").value,
        color: byId("cfg-cor").value,
        thickness: Number(byId("cfg-espessura").value) || 4,
        pen_thickness: strokeWidths.Caneta,
        highlighter_thickness: strokeWidths.MarcaTexto,
        recent_colors: recentColors,
        font_size: toolSizes.Texto,
        tool_sizes: {...toolSizes},
        number: String(byId("cfg-numero").value || "1"),
        cloud_free: cloudFreeMode,
        auto_sequence: {...autoSequence},
        balloon_fill: byId("cfg-balao-fill") ? byId("cfg-balao-fill").checked : true,
        balloon_line: byId("cfg-balao-line") ? byId("cfg-balao-line").checked : false,
        review_fill: byId("cfg-revisao-fill") ? byId("cfg-revisao-fill").checked : false,
        text_autogrow: byId("cfg-texto-auto") ? byId("cfg-texto-auto").checked : true,
        bold: byId("btn-bold").classList.contains("active"),
        italic: byId("btn-italic").classList.contains("active"),
        underline: byId("btn-underline").classList.contains("active")
    };
}

function persistPreferences() {
    clearTimeout(preferenceTimer);
    preferenceTimer = setTimeout(() => {
        if (pyBridge) pyBridge.savePreferences(JSON.stringify(readPreferences()));
    }, 180);
}

let clipboardSyncTimer = null;
function scheduleClipboardSync() {
    if (!pyBridge) return;
    clearTimeout(clipboardSyncTimer);
    clipboardSyncTimer = setTimeout(syncClipboardNow, 200);
}

function syncClipboardNow() {
    if (!pyBridge) return;
    // NUNCA sincronizar durante uma edição ativa: exportDataUrl chama
    // finishActiveCommand, o que fecharia o editor de texto aberto (a caixa
    // "fechava sozinha" ~200ms após abrir) ou cancelaria um desenho em curso.
    // O commit da edição agenda um novo sync, então nada se perde ao pular.
    if (activeTextEditor || orthogonalPath || isDrawing) return;
    const hasContent = workspaceMode === "edition"
        ? (editionItems.length > 0 || editionAnnotations.length > 0)
        : Boolean(bgImage);
    if (!hasContent) return;
    const data = exportDataUrl();
    if (data) pyBridge.copyImage(data, false);
}

function saveUser() {
    if (pyBridge) pyBridge.saveUser(byId("user-name").value, byId("user-email").value);
}

function updateShortcuts() {
    if (!pyBridge) return;
    pyBridge.updateShortcuts(
        byId("hk-area").value,
        byId("hk-copy").value,
        byId("hk-save").value,
        byId("hk-undo").value
    );
}

function requestCapture(kind) {
    if (!pyBridge) {
        setStatus("Abra esta interface pelo aplicativo Super Captura para capturar a tela.");
        return;
    }
    pendingCaptureTarget = "home";
    setWorkspaceMode("home");
    finishActiveCommand(true);
    const preferences = readPreferences();
    preferences.auto_copy = true;
    byId("cfg-autocopy").checked = true;
    clearTimeout(preferenceTimer);
    pyBridge.savePreferences(JSON.stringify(preferences));
    const method = kind === "screen" ? "captureScreen" : "captureArea";
    pyBridge[method](preferences.delay, preferences.auto_copy, preferences.auto_save);
}

function requestCaptureToEdition(kind) {
    if (!pyBridge) {
        setStatus("Abra esta interface pelo aplicativo Super Captura para capturar a tela.");
        return;
    }
    setWorkspaceMode("edition");
    finishActiveCommand(true);
    pendingCaptureTarget = "edition";
    const preferences = readPreferences();
    preferences.auto_copy = true;
    byId("cfg-autocopy").checked = true;
    clearTimeout(preferenceTimer);
    pyBridge.savePreferences(JSON.stringify(preferences));
    const method = kind === "screen" ? "captureScreen" : "captureArea";
    pyBridge[method](preferences.delay, preferences.auto_copy, preferences.auto_save);
}

function pasteImageFromClipboard() {
    setWorkspaceMode("edition");
    if (pyBridge && typeof pyBridge.pasteClipboardImageToEdition === "function") {
        pyBridge.pasteClipboardImageToEdition();
        return;
    }
    setStatus("Pressione Ctrl+V na guia Edição para colar uma imagem.");
}

function toggleVideoRecording() {
    if (!pyBridge) return;
    if (videoRecording) {
        pyBridge.stopVideoRecording();
        return;
    }
    const preferences = readPreferences();
    persistPreferences();
    pyBridge.startVideoRecording(preferences.video_format, preferences.video_fps, preferences.video_audio);
}

function updateVideoState(recording, detail) {
    videoRecording = Boolean(recording);
    const button = byId("video-record-btn");
    button.classList.toggle("recording", videoRecording);
    button.querySelector(".material-symbols-outlined").textContent = videoRecording ? "stop_circle" : "videocam";
    button.lastChild.textContent = videoRecording ? " Parar Vídeo" : " Gravar Vídeo";
    button.title = detail || "";
}

function updateMaximizeIcon(maximized) {
    const icon = document.querySelector(".window-controls .win-btn:nth-child(2) .material-symbols-outlined");
    if (icon) icon.textContent = maximized ? "filter_none" : "crop_square";
    document.body.classList.toggle("is-maximized", Boolean(maximized));
}

function selectTool(toolName, announce = true) {
    closeFormatPopover();
    document.querySelectorAll(".tool-btn").forEach(item => {
        item.classList.toggle("active", item.dataset.tool === toolName);
    });
    const button = document.querySelector(`.tool-btn[data-tool="${toolName}"]`);
    currentTool = toolName;
    selectedIndex = -1;
    selectedEditionItemIndex = -1;
    interactionMode = null;
    if (strokeResizeTools.has(toolName)) byId("cfg-espessura").value = strokeWidths[toolName];
    else byId("cfg-espessura").value = Math.min(20, Number(byId("cfg-espessura").value) || 4);
    if (toolSizes[toolName] !== undefined) byId("cfg-fonte").value = toolSizes[toolName];
    syncEditionFormatControlsFromMain();
    canvas.style.cursor = currentTool === "Mover" ? "default" : "crosshair";
    if (bgImage || workspaceMode === "edition") redraw();
    if (announce) setStatus(`${button?.title || currentTool} selecionado.`);
}

document.querySelectorAll(".tool-btn").forEach(button => {
    button.addEventListener("click", () => {
        if (button.dataset.tool !== currentTool) finishActiveCommand(true);
        selectTool(button.dataset.tool);
    });
});

function syncFormatControlsFromSelection(shape) {
    if (!shape) return;
    if (shape.color) byId("cfg-cor").value = shape.color;
    if (shape.thick) byId("cfg-espessura").value = shape.thick * (shape.type === "MarcaTexto" ? 4 : 1);
    if (shape.font) byId("cfg-fonte").value = shape.font;
    if (shape.type === "Balao") {
        if (byId("cfg-balao-fill")) byId("cfg-balao-fill").checked = shape.fillBalloon !== false;
        if (byId("cfg-balao-line")) byId("cfg-balao-line").checked = Boolean(shape.lineBalloon);
    }
    if (shape.type === "Revisao" && byId("cfg-revisao-fill")) byId("cfg-revisao-fill").checked = shape.fillReview === true;
    if (shape.type === "Nuvem" && byId("cfg-nuvem-livre")) byId("cfg-nuvem-livre").checked = isFreeCloud(shape);
    if (shape.type === "Texto" && byId("cfg-texto-auto")) byId("cfg-texto-auto").checked = shape.autoHeight !== false;
    byId("btn-bold").classList.toggle("active", Boolean(shape.bold));
    byId("btn-italic").classList.toggle("active", Boolean(shape.italic));
    byId("btn-underline").classList.toggle("active", Boolean(shape.underline));
    syncEditionFormatControlsFromMain();
}

function setOptionalValue(id, value) {
    const input = byId(id);
    if (input && value !== undefined && value !== null) input.value = value;
}

function setOptionalActive(id, value) {
    const button = byId(id);
    if (button) button.classList.toggle("active", Boolean(value));
}

function syncEditionFormatControlsFromMain() {
    setOptionalValue("ed-cfg-cor", byId("cfg-cor")?.value || "#107C41");
    setOptionalValue("ed-cfg-espessura", byId("cfg-espessura")?.value || 4);
    setOptionalValue("ed-cfg-fonte", byId("cfg-fonte")?.value || 28);
    setOptionalValue("ed-cfg-numero", byId("cfg-numero")?.value || 1);
    setOptionalActive("ed-btn-bold", byId("btn-bold")?.classList.contains("active"));
    setOptionalActive("ed-btn-italic", byId("btn-italic")?.classList.contains("active"));
    setOptionalActive("ed-btn-underline", byId("btn-underline")?.classList.contains("active"));
    refreshDrawingControls();
}

function syncMainFormatControlsFromEdition() {
    setOptionalValue("cfg-cor", byId("ed-cfg-cor")?.value || byId("cfg-cor")?.value);
    setOptionalValue("cfg-espessura", byId("ed-cfg-espessura")?.value || byId("cfg-espessura")?.value);
    setOptionalValue("cfg-fonte", byId("ed-cfg-fonte")?.value || byId("cfg-fonte")?.value);
    setOptionalValue("cfg-numero", byId("ed-cfg-numero")?.value || byId("cfg-numero")?.value);
    setOptionalActive("btn-bold", byId("ed-btn-bold")?.classList.contains("active"));
    setOptionalActive("btn-italic", byId("ed-btn-italic")?.classList.contains("active"));
    setOptionalActive("btn-underline", byId("ed-btn-underline")?.classList.contains("active"));
    handleFormatControlChanged();
}

function toggleEditionStyle(button, mainButtonId) {
    button.classList.toggle("active");
    const mainButton = byId(mainButtonId);
    if (mainButton) mainButton.classList.toggle("active", button.classList.contains("active"));
    handleFormatControlChanged();
}

function applyCurrentFormattingToSelection() {
    if (selectedIndex < 0 || !annotations[selectedIndex]) return false;
    const shape = annotations[selectedIndex];
    const options = getOptions();
    pushHistory();
    shape.color = options.color;
    shape.thick = options.thick;
    // O campo de tamanho da faixa vale para toda marcação que o usa — fonte,
    // ponta da seta e raio do festonado da nuvem. Antes só o texto respondia, e
    // a nuvem já desenhada ficava presa ao raio com que nasceu.
    if (toolSizes[shape.type] !== undefined) {
        shape.font = options.font;
        invalidateShapeBounds(shape);
    }
    if (isTextEditable(shape)) {
        shape.bold = options.bold;
        shape.italic = options.italic;
        shape.underline = options.underline;
        if (shape.type === "Balao") {
            shape.fillBalloon = options.fillBalloon;
            shape.lineBalloon = options.lineBalloon;
        }
        if (shape.type === "Revisao") shape.fillReview = options.fillReview;
        if (shape.type === "Texto") shape.autoHeight = options.autoHeight;
    }
    redraw();
    setStatus("Formatação aplicada à seleção.");
    return true;
}

function applyCurrentFormattingToActiveEditor() {
    if (!activeTextEditor) return false;
    const options = getOptions();
    const editor = activeTextEditor.editor;
    const target = activeTextEditor.options;
    Object.assign(target, {
        color: options.color, thick: options.thick, font: options.font,
        bold: options.bold, italic: options.italic, underline: options.underline,
        fillBalloon: options.fillBalloon, lineBalloon: options.lineBalloon,
        fillReview: options.fillReview
    });
    const scale = canvasScale();
    const editorFont = target.type === "Balao"
        ? balloonFontSize(target)
        : (target.type === "Revisao" ? reviewMarkerFontSize(target) : options.font);
    editor.style.color = options.color;
    editor.style.fontSize = `${Math.max(10, editorFont * scale.y)}px`;
    editor.style.fontWeight = options.bold ? "700" : "400";
    editor.style.fontStyle = options.italic ? "italic" : "normal";
    editor.style.textDecoration = options.underline ? "underline" : "none";
    editor.focus({preventScroll: true});
    return true;
}

function handleFormatControlChanged() {
    const tool = formattingTool();
    const maximum = tool === "MarcaTexto" ? 80 : 20;
    byId("cfg-espessura").value = Math.max(1, Math.min(maximum, Number(byId("cfg-espessura").value) || 4));
    if (strokeResizeTools.has(tool)) strokeWidths[tool] = Number(byId("cfg-espessura").value);
    if (toolSizes[tool] !== undefined) {
        const size = clampToolSize(tool, byId("cfg-fonte").value);
        toolSizes[tool] = size;
        byId("cfg-fonte").value = size;
    }
    if (byId("cfg-nuvem-livre")) cloudFreeMode = byId("cfg-nuvem-livre").checked;
    if (activeFormatPopover && activeFormatPopover.id === "tool-config-popover" && openToolConfig) {
        renderToolConfigMenu(activeFormatPopover, openToolConfig);
    }
    syncEditionFormatControlsFromMain();
    if (applyCurrentFormattingToActiveEditor()) {
        persistPreferences();
        return;
    }
    if (applyCurrentFormattingToSelection()) scheduleClipboardSync();
    persistPreferences();
}

document.querySelectorAll(".style-btn").forEach(button => {
    button.addEventListener("click", () => window.setTimeout(handleFormatControlChanged, 0));
});
[
    "cfg-cor", "cfg-espessura", "cfg-fonte", "cfg-numero", "cfg-balao-fill", "cfg-balao-line",
    "cfg-revisao-fill", "cfg-nuvem-livre", "cfg-texto-auto",
    "cfg-delay", "cfg-autocopy", "cfg-autosave", "cfg-video-format", "cfg-video-fps", "cfg-video-audio"
].forEach(id => {
    const element = byId(id);
    if (element) element.addEventListener("change", id.startsWith("cfg-") && ["cfg-cor", "cfg-espessura", "cfg-fonte", "cfg-balao-fill", "cfg-balao-line", "cfg-revisao-fill", "cfg-nuvem-livre", "cfg-texto-auto"].includes(id)
        ? handleFormatControlChanged
        : persistPreferences);
});

const titlebar = byId("app-titlebar");
titlebar.addEventListener("mousedown", event => {
    if (event.button === 0 && !event.target.closest("button") && pyBridge) pyBridge.startWindowDrag();
});
titlebar.addEventListener("dblclick", event => {
    if (!event.target.closest("button") && pyBridge) pyBridge.maximizeWindow();
});

document.querySelectorAll(".resize-grip").forEach(grip => {
    grip.addEventListener("mousedown", event => {
        if (event.button !== 0 || !pyBridge) return;
        event.preventDefault();
        event.stopPropagation();
        pyBridge.startWindowResize(grip.dataset.edge);
    });
});

function ensureImage() {
    if (workspaceMode === "edition") {
        ensureEditionCanvas();
        return true;
    }
    if (bgImage) return true;
    setStatus("Capture ou abra uma imagem primeiro.");
    return false;
}

function setWorkspaceMode(mode) {
    const nextMode = mode === "edition" ? "edition" : "home";
    if (workspaceMode === nextMode) {
        updateWorkspaceVisibility();
        return;
    }
    finishActiveCommand(true);
    if (workspaceMode === "home") {
        homeBgImage = bgImage;
        homeAnnotations = annotations;
    } else {
        editionAnnotations = annotations;
    }

    workspaceMode = nextMode;
    selectedIndex = -1;
    selectedEditionItemIndex = -1;
    interactionMode = null;
    isDrawing = false;
    preview = null;

    if (workspaceMode === "home") {
        bgImage = homeBgImage;
        annotations = homeAnnotations;
        if (bgImage) {
            docWidth = bgImage.naturalWidth || bgImage.width;
            docHeight = bgImage.naturalHeight || bgImage.height;
        }
    } else {
        bgImage = null;
        annotations = editionAnnotations;
        ensureEditionCanvas();
        selectTool("Mover", false);
    }
    updateWorkspaceVisibility();
    fitToWorkspace();
    redraw();
}

function updateWorkspaceVisibility() {
    const hasContent = workspaceMode === "edition"
        ? editionItems.length > 0 || editionAnnotations.length > 0
        : Boolean(bgImage);
    if (workspaceMode === "edition") {
        emptyState.style.display = hasContent ? "none" : "flex";
        emptyState.querySelector("p").textContent = "Cole ou adicione imagens para montar sua página.";
        const hint = emptyState.querySelector("p + p");
        if (hint) hint.textContent = "Use Add Imagem, Colar ou Ctrl+V. Depois arraste cada imagem livremente.";
        canvasContainer.style.display = "block";
        return;
    }
    emptyState.style.display = hasContent ? "none" : "flex";
    emptyState.querySelector("p").textContent = "Nenhuma imagem carregada.";
    const hint = emptyState.querySelector("p + p");
    if (hint) hint.textContent = "Use a captura de área ou abra uma imagem para começar.";
    canvasContainer.style.display = hasContent ? "block" : "none";
}

function ensureEditionCanvas() {
    const width = Math.max(800, Math.round(editionCanvasSize.width || 1600));
    const height = Math.max(600, Math.round(editionCanvasSize.height || 1000));
    if (docWidth !== width || docHeight !== height) {
        docWidth = width;
        docHeight = height;
        applyZoom();
    }
    canvasContainer.style.display = "block";
}

function runPostCaptureActions(autoCopy, autoSave) {
    if (!autoCopy && !autoSave) return;
    requestAnimationFrame(() => {
        setTimeout(() => {
            if (autoCopy) copyFinalImage(true);
            if (autoSave) savePng();
        }, 120);
    });
}

function loadImageData(dataUrl, autoCopy = false, autoSave = false) {
    if (pendingCaptureTarget === "edition") {
        pendingCaptureTarget = "home";
        addEditionImage(dataUrl, "Captura");
        runPostCaptureActions(autoCopy, autoSave);
        return;
    }
    const image = new Image();
    image.decoding = "async";
    image.onload = () => {
        finishActiveCommand(false);
        pushHistory();
        bgImage = image;
        homeBgImage = image;
        docWidth = image.naturalWidth;
        docHeight = image.naturalHeight;
        annotations = [];
        homeAnnotations = annotations;
        preview = null;
        selectedIndex = -1;
        emptyState.style.display = "none";
        canvasContainer.style.display = "block";
        fitToWorkspace();
        redraw();
        runPostCaptureActions(autoCopy, autoSave);
    };
    image.onerror = () => setStatus("A imagem capturada não pôde ser carregada.");
    image.src = dataUrl;
}

function triggerEditionImagePicker() {
    setWorkspaceMode("edition");
    byId("edition-image-input")?.click();
}

function addEditionImage(source, name = "Imagem") {
    setWorkspaceMode("edition");
    ensureEditionCanvas();
    const image = new Image();
    image.decoding = "async";
    image.onload = () => {
        const margin = 70;
        const offset = editionItems.length * 34;
        const firstImage = editionItems.length === 0;
        const item = {
            type: "Imagem",
            image,
            source,
            name,
            x: margin + offset,
            y: margin + offset,
            w: image.naturalWidth || image.width,
            h: image.naturalHeight || image.height
        };
        pushHistory();
        editionItems.push(item);
        selectedEditionItemIndex = editionItems.length - 1;
        selectedIndex = -1;
        expandEditionCanvasToFit(item);
        updateWorkspaceVisibility();
        if (firstImage) fitToWorkspace();
        else applyZoom();
        redraw();
        setStatus(`${name || "Imagem"} adicionada à edição.`);
        scheduleClipboardSync();
    };
    image.onerror = () => setStatus("Não foi possível adicionar a imagem.");
    image.src = source;
}

function expandEditionCanvasToFit(item) {
    const padding = 160;
    const needWidth = Math.ceil(item.x + item.w + padding);
    const needHeight = Math.ceil(item.y + item.h + padding);
    const newWidth = Math.max(editionCanvasSize.width, needWidth, 1600);
    const newHeight = Math.max(editionCanvasSize.height, needHeight, 1000);
    const changed = newWidth !== editionCanvasSize.width || newHeight !== editionCanvasSize.height;
    editionCanvasSize = {width: newWidth, height: newHeight};
    if (changed) ensureEditionCanvas();
    return changed;
}

function clearEdition() {
    finishActiveCommand(true);
    pushHistory();
    editionItems = [];
    editionAnnotations = [];
    if (workspaceMode === "edition") annotations = editionAnnotations;
    selectedIndex = -1;
    selectedEditionItemIndex = -1;
    editionCanvasSize = {width: 1600, height: 1000};
    ensureEditionCanvas();
    updateWorkspaceVisibility();
    fitToWorkspace();
    redraw();
    setStatus("Edição limpa.");
}

function findEditionItemAt(x, y) {
    for (let index = editionItems.length - 1; index >= 0; index--) {
        const item = editionItems[index];
        const handle = editionImageHandle(item);
        if (Math.abs(x - handle.x) <= 14 && Math.abs(y - handle.y) <= 14) {
            return {index, handle: "resize"};
        }
        if (x >= item.x && x <= item.x + item.w && y >= item.y && y <= item.y + item.h) {
            return {index, handle: "move"};
        }
    }
    return {index: -1, handle: null};
}

function editionImageHandle(item) {
    return {x: item.x + item.w, y: item.y + item.h};
}

function moveEditionItem(item, x, y) {
    item.x = x;
    item.y = y;
}

function resizeEditionItem(item, point) {
    const minSize = 40;
    const ratio = item.image && item.image.naturalWidth
        ? item.image.naturalHeight / Math.max(1, item.image.naturalWidth)
        : item.h / Math.max(1, item.w);
    const newWidth = Math.max(minSize, point.x - item.x);
    item.w = newWidth;
    item.h = Math.max(minSize, newWidth * ratio);
}

function finalizeEditionItemTransform(item) {
    if (!item) return;
    if (expandEditionCanvasToFit(item)) applyZoom();
}

function downscaleInSteps(image, width, height, target = null) {
    // Reduzir de uma vez só, com reamostragem simples, engrossa e serrilha o
    // que é fino. Em etapas de 2x cada passo é barato e o resultado fica bem
    // mais limpo - sem precisar da reamostragem "high", que aqui custa segundos.
    let source = image;
    let currentWidth = image.naturalWidth || image.width;
    let currentHeight = image.naturalHeight || image.height;
    while (currentWidth > width * 2 && currentHeight > height * 2) {
        const nextWidth = Math.max(width, Math.round(currentWidth / 2));
        const nextHeight = Math.max(height, Math.round(currentHeight / 2));
        const stepCanvas = document.createElement("canvas");
        stepCanvas.width = nextWidth;
        stepCanvas.height = nextHeight;
        const stepCtx = stepCanvas.getContext("2d");
        stepCtx.imageSmoothingEnabled = true;
        stepCtx.imageSmoothingQuality = "low";
        stepCtx.drawImage(source, 0, 0, currentWidth, currentHeight, 0, 0, nextWidth, nextHeight);
        source = stepCanvas;
        currentWidth = nextWidth;
        currentHeight = nextHeight;
    }
    const destino = target || document.createElement("canvas");
    destino.width = width;
    destino.height = height;
    const destinoCtx = destino.getContext("2d");
    destinoCtx.imageSmoothingEnabled = true;
    destinoCtx.imageSmoothingQuality = "low";
    destinoCtx.drawImage(source, 0, 0, currentWidth, currentHeight, 0, 0, width, height);
    return destino;
}

function backgroundRenderSource(scale) {
    // Com zoom bem reduzido o fundo encolhe mais da metade; aí vale guardar uma
    // cópia reduzida em etapas, senão a captura fica granulada.
    if (!bgImage) return null;
    if (scale > 0.55) return bgImage;
    const width = Math.max(1, Math.round(docWidth * scale));
    const height = Math.max(1, Math.round(docHeight * scale));
    const stale = bgProxySource !== bgImage
        || !bgProxyWidth
        || Math.abs(bgProxyWidth - width) > Math.max(3, width * 0.12);
    if (stale) {
        bgProxyCanvas = downscaleInSteps(bgImage, width, height, bgProxyCanvas);
        bgProxySource = bgImage;
        bgProxyWidth = width;
    }
    return bgProxyCanvas;
}

function buildEditionProxy(item, width, height) {
    item.proxy = downscaleInSteps(item.image, width, height, item.proxy);
    item.proxyWidth = width;
    item.proxyHeight = height;
}

function editionRenderSource(item) {
    // Guarda uma cópia da foto já reduzida ao tamanho em que ela aparece na
    // página. Assim cada quadro desenha a imagem praticamente 1:1, em vez de
    // reescalar vários megapixels toda vez - era isso que deixava o arraste
    // pesado. A cópia tem a resolução da página, então o que é salvo/copiado
    // continua com a mesma qualidade do que está na tela.
    if (!item.image) return null;
    const width = Math.max(1, Math.round(Math.abs(item.w)));
    const height = Math.max(1, Math.round(Math.abs(item.h)));
    const natural = item.image.naturalWidth || item.image.width || width;
    if (natural <= width * 1.15) return item.image;
    const stale = !item.proxyWidth || Math.abs(item.proxyWidth - width) > Math.max(4, width * 0.2);
    // Enquanto redimensiona, a cópia atual serve; só é refeita ao soltar.
    if (stale && (!isDrawing || !item.proxy)) buildEditionProxy(item, width, height);
    return item.proxy || item.image;
}

const editionImageInput = byId("edition-image-input");
if (editionImageInput) {
    editionImageInput.addEventListener("change", event => {
        Array.from(event.target.files || []).forEach(file => {
            if (!file.type.startsWith("image/")) return;
            const reader = new FileReader();
            reader.onload = () => addEditionImage(String(reader.result), file.name);
            reader.readAsDataURL(file);
        });
        event.target.value = "";
    });
}

window.addEventListener("paste", event => {
    if (workspaceMode !== "edition") return;
    const items = Array.from(event.clipboardData?.items || []);
    const imageItem = items.find(item => item.type.startsWith("image/"));
    if (!imageItem) return;
    const file = imageItem.getAsFile();
    if (!file) return;
    event.preventDefault();
    const reader = new FileReader();
    reader.onload = () => addEditionImage(String(reader.result), "Imagem colada");
    reader.readAsDataURL(file);
});

function formattingTool() {
    return annotations[selectedIndex]?.type || currentTool;
}

function clampToolSize(tool, value) {
    const size = Math.round(Number(value));
    if (!Number.isFinite(size)) return toolSizes[tool] ?? 20;
    if (tool === "Nuvem") return Math.max(3, Math.min(60, size));
    return Math.max(8, Math.min(200, size));
}

function isFreeCloud(shape) {
    return Boolean(shape) && shape.type === "Nuvem" && shape.free === true;
}

function drawingFreeCloud() {
    return currentTool === "Nuvem" && cloudFreeMode;
}

// Traco a mao livre, nuvem livre e linha ortogonal vivem em "points": mover,
// escalar e delimitar essas marcacoes passa pela lista de pontos, nao por
// x/y/w/h.
function isPointShape(shape) {
    return Boolean(shape) && (strokeResizeTools.has(shape.type) || shape.type === "LinhaOrto" || isFreeCloud(shape));
}

// Converte pixels de tela em unidades do documento. Alcas, tracejado da selecao
// e tolerancia do clique nao podem encolher quando o zoom ou o supersampling
// aumentam a escala do canvas.
function screenUnits(pixels) {
    return pixels / Math.max(0.05, canvasScale().x);
}

// O campo de tamanho e um so, mas o rotulo e os limites mudam com a ferramenta.
function updateSizeFieldLabel() {
    const tool = formattingTool();
    const label = sizeLabels[tool] || "Fonte";
    const cloud = tool === "Nuvem";
    for (const id of ["label-fonte", "ed-label-fonte"]) {
        const element = byId(id);
        if (element) element.textContent = `${label}/Nº`;
    }
    for (const id of ["cfg-fonte", "ed-cfg-fonte"]) {
        const input = byId(id);
        if (!input) continue;
        input.min = cloud ? 3 : 8;
        input.max = cloud ? 60 : 200;
        input.title = cloud ? "Raio do festonado da nuvem" : `${label}: tamanho em pixels da imagem`;
        input.setAttribute("aria-label", cloud ? "Raio do festonado" : `Tamanho: ${label}`);
    }
}

function refreshDrawingControls() {
    document.documentElement.style.setProperty("--drawing-color", byId("cfg-cor").value);
    const marker = formattingTool() === "MarcaTexto";
    for (const id of ["cfg-espessura", "ed-cfg-espessura"]) {
        byId(id).max = marker ? 80 : 20;
        byId(id).title = "Espessura em pixels da imagem";
        byId(id).setAttribute("aria-label", "Espessura em pixels");
    }
    updateSizeFieldLabel();
}

function closeFormatPopover(restoreFocus = false) {
    if (activeFormatPopover) activeFormatPopover.hidden = true;
    if (formatPopoverAnchor) {
        formatPopoverAnchor.setAttribute("aria-expanded", "false");
        if (restoreFocus) formatPopoverAnchor.focus({preventScroll: true});
    }
    activeFormatPopover = null;
    formatPopoverAnchor = null;
    openToolConfig = null;
}

function positionFormatPopover() {
    if (!activeFormatPopover || !formatPopoverAnchor) return;
    const anchor = formatPopoverAnchor.getBoundingClientRect();
    const popup = activeFormatPopover;
    popup.style.left = `${Math.max(12, Math.min(anchor.left, innerWidth - popup.offsetWidth - 12))}px`;
    popup.style.top = `${Math.max(12, Math.min(anchor.bottom + 8, innerHeight - popup.offsetHeight - 12))}px`;
}

function openFormatPopover(popup, anchor) {
    closeFormatPopover();
    activeFormatPopover = popup;
    formatPopoverAnchor = anchor;
    anchor.setAttribute("aria-expanded", "true");
    popup.hidden = false;
    positionFormatPopover();
    (popup.querySelector('button[aria-pressed="true"]') || popup.querySelector('button:not(.picker-close), input'))?.focus({preventScroll: true});
}

function setDrawingColor(color) {
    if (!/^#[0-9a-f]{6}$/i.test(color)) return false;
    color = color.toUpperCase();
    byId("cfg-cor").value = color;
    recentColors = [color, ...recentColors.filter(item => item.toUpperCase() !== color)].slice(0, 10);
    handleFormatControlChanged();
    closeFormatPopover(true);
    return true;
}

function initializeDrawingPickers() {
    const colors = document.createElement("section");
    colors.id = "drawing-color-popover";
    colors.className = "format-popover";
    colors.hidden = true;
    colors.setAttribute("role", "dialog");
    colors.setAttribute("aria-label", "Cores do desenho");
    colors.innerHTML = `<div class="picker-heading">Cores<button class="picker-close" aria-label="Fechar">×</button></div>
        <span class="picker-label">Cores do tema</span><div class="swatch-grid" data-palette="theme"></div>
        <span class="picker-label">Cores padrão</span><div class="swatch-grid" data-palette="standard"></div>
        <span class="picker-label" id="recent-color-label">Recentes</span><div class="swatch-grid" data-palette="recent"></div>
        <details class="picker-custom"><summary>Mais cores</summary>
            <div class="color-spectrum" id="color-spectrum" role="slider" tabindex="0" aria-label="Saturação e luminosidade: use as setas" aria-valuemin="0" aria-valuemax="100"><span class="spectrum-thumb"></span></div>
            <input class="hue-slider" id="color-hue" type="range" min="0" max="360" aria-label="Matiz">
            <div class="custom-color-row"><span class="color-chip" id="custom-color-preview"></span><input id="custom-color-hex" aria-label="Cor hexadecimal" maxlength="7" spellcheck="false" placeholder="#107C41"><button id="apply-custom-color">Aplicar</button></div>
            <p class="picker-error" id="custom-color-error" role="status"></p>
        </details>`;
    document.body.append(colors);
    const theme = ["#FFFFFF", "#242424", "#E7E6E6", "#44546A", "#107C41", "#4472C4", "#ED7D31", "#A5A5A5", "#FFC000", "#7030A0"];
    const standard = ["#C00000", "#FF0000", "#FFC000", "#FFFF00", "#92D050", "#00B050", "#00B0F0", "#0070C0", "#002060", "#7030A0"];
    const tint = (hex, fraction) => "#" + [1, 3, 5].map(offset => {
        const value = parseInt(hex.slice(offset, offset + 2), 16);
        const target = fraction < 0 ? 0 : 255;
        return Math.round(value + (target - value) * Math.abs(fraction)).toString(16).padStart(2, "0");
    }).join("");
    // Cada coluna desce do claro ao escuro. Branco recebe sombras de cinza,
    // pois misturar branco com branco produziria quatro células idênticas.
    const themePalette = [.8, .45, 0, -.3].flatMap((fraction, row) =>
        theme.map(color => tint(color, color === "#FFFFFF" ? [0, -.15, -.35, -.6][row] : fraction)));
    const fillPalette = (name, values) => {
        const grid = colors.querySelector(`[data-palette="${name}"]`);
        grid.replaceChildren();
        values.forEach(color => {
            const button = document.createElement("button");
            button.className = "color-swatch";
            button.style.setProperty("--swatch", color);
            button.title = color.toUpperCase();
            button.setAttribute("aria-label", `Cor ${color.toUpperCase()}`);
            button.setAttribute("aria-pressed", String(color.toUpperCase() === byId("cfg-cor").value.toUpperCase()));
            button.onclick = () => setDrawingColor(color);
            grid.append(button);
        });
    };
    let hue = 145, saturation = 0.85, value = 0.49;
    const spectrum = byId("color-spectrum");
    const hexInput = byId("custom-color-hex");
    const hsvColor = () => {
        const c = value * saturation, h = (hue % 360) / 60, x = c * (1 - Math.abs(h % 2 - 1));
        const channels = [[c,x,0],[x,c,0],[0,c,x],[0,x,c],[x,0,c],[c,0,x]][Math.floor(h)];
        return "#" + channels.map(channel => Math.round((channel + value - c) * 255).toString(16).padStart(2,"0")).join("").toUpperCase();
    };
    const updateCustom = () => {
        hexInput.value = hsvColor();
        spectrum.style.setProperty("--hue", hue);
        spectrum.firstElementChild.style.left = `${saturation * 100}%`;
        spectrum.firstElementChild.style.top = `${(1 - value) * 100}%`;
        spectrum.setAttribute("aria-valuenow", String(Math.round(saturation * 100)));
        spectrum.setAttribute("aria-valuetext", `Saturação ${Math.round(saturation * 100)}%, luminosidade ${Math.round(value * 100)}%`);
        byId("custom-color-preview").style.setProperty("--drawing-color", hexInput.value);
        byId("color-hue").value = hue;
        byId("custom-color-error").textContent = "";
    };
    const readCustom = hex => {
        const [r,g,b] = [1,3,5].map(offset => parseInt(hex.slice(offset,offset+2),16) / 255);
        const high = Math.max(r,g,b), low = Math.min(r,g,b), delta = high - low;
        hue = delta === 0 ? 0 : ((high === r ? (g-b)/delta : high === g ? (b-r)/delta+2 : (r-g)/delta+4) * 60 + 360) % 360;
        saturation = high === 0 ? 0 : delta/high;
        value = high;
        updateCustom();
    };
    const pickSpectrum = event => {
        const rect = spectrum.getBoundingClientRect();
        saturation = Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width));
        value = 1-Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height));
        updateCustom();
    };
    spectrum.onpointerdown = event => { if (event.button !== 0) return; spectrum.setPointerCapture(event.pointerId); pickSpectrum(event); };
    spectrum.onpointermove = event => { if (spectrum.hasPointerCapture(event.pointerId)) pickSpectrum(event); };
    spectrum.onkeydown = event => {
        if (!event.key.startsWith("Arrow")) return;
        event.preventDefault();
        saturation = Math.max(0, Math.min(1, saturation + (event.key === "ArrowRight" ? .02 : event.key === "ArrowLeft" ? -.02 : 0)));
        value = Math.max(0, Math.min(1, value + (event.key === "ArrowUp" ? .02 : event.key === "ArrowDown" ? -.02 : 0)));
        updateCustom();
    };
    byId("color-hue").oninput = event => { hue = Number(event.target.value); updateCustom(); };
    hexInput.oninput = () => { if (/^#[0-9a-f]{6}$/i.test(hexInput.value)) readCustom(hexInput.value); };
    const applyHex = () => {
        let color = hexInput.value.trim();
        if (!color.startsWith("#")) color = "#" + color;
        if (!setDrawingColor(color)) {
            byId("custom-color-error").textContent = "Use uma cor como #107C41.";
            hexInput.focus();
        }
    };
    byId("apply-custom-color").onclick = applyHex;
    hexInput.onkeydown = event => { if (event.key === "Enter") { event.preventDefault(); applyHex(); } };
    colors.querySelector("details").addEventListener("toggle", positionFormatPopover);
    colors.querySelector(".picker-close").onclick = () => closeFormatPopover(true);
    document.querySelectorAll("[data-color-picker]").forEach(button => {
        button.onclick = () => {
            if (activeFormatPopover === colors && formatPopoverAnchor === button) return closeFormatPopover();
            fillPalette("theme", themePalette);
            fillPalette("standard", standard);
            fillPalette("recent", recentColors);
            byId("recent-color-label").hidden = recentColors.length === 0;
            readCustom(byId("cfg-cor").value);
            openFormatPopover(colors, button);
        };
    });

    const thickness = document.createElement("section");
    thickness.id = "stroke-width-popover";
    thickness.className = "format-popover";
    thickness.hidden = true;
    thickness.setAttribute("role", "dialog");
    thickness.setAttribute("aria-label", "Espessura do traço");
    document.body.append(thickness);
    document.querySelectorAll('.tool-btn[data-tool="Caneta"],.tool-btn[data-tool="MarcaTexto"]').forEach(toolButton => {
        const wrapper = document.createElement("div");
        wrapper.className = "stroke-tool";
        toolButton.before(wrapper);
        wrapper.append(toolButton);
        const button = document.createElement("button");
        const tool = toolButton.dataset.tool;
        const marker = tool === "MarcaTexto";
        button.className = "stroke-menu-trigger";
        button.innerHTML = CARET_SVG;
        button.title = `Espessura ${marker ? "do marca-texto" : "da caneta"}`;
        button.setAttribute("aria-label", button.title);
        button.setAttribute("aria-expanded", "false");
        wrapper.append(button);
        button.onclick = () => {
            if (activeFormatPopover === thickness && formatPopoverAnchor === button) return closeFormatPopover();
            const editingSelection = annotations[selectedIndex]?.type === tool;
            if (!editingSelection) { finishActiveCommand(true); selectTool(tool); }
            thickness.innerHTML = `<div class="picker-heading">${marker ? "Marca-texto" : "Caneta"}<button class="picker-close" aria-label="Fechar">×</button></div><span class="picker-label">Espessura do traço</span><div class="stroke-choices"></div><span class="picker-label">Outros valores: campo Cor / Esp. na faixa.</span>`;
            thickness.querySelector(".picker-close").onclick = () => closeFormatPopover(true);
            (marker ? [8,12,16,24,32,48] : [1,2,3,4,6,8,12]).forEach(width => {
                const choice = document.createElement("button");
                choice.className = "stroke-choice";
                choice.dataset.marker = String(marker);
                choice.setAttribute("aria-label", `${width} pixels`);
                choice.setAttribute("aria-pressed", String(Number(byId("cfg-espessura").value) === width));
                choice.innerHTML = `<span class="stroke-sample" style="--stroke-size:${marker ? width / 2 : width}px"></span><span>${width} px</span>`;
                choice.onclick = () => { byId("cfg-espessura").value = width; handleFormatControlChanged(); closeFormatPopover(true); };
                thickness.querySelector(".stroke-choices").append(choice);
            });
            openFormatPopover(thickness, button);
        };
    });
    buildToolConfigMenus();

    document.addEventListener("mousedown", event => {
        if (activeFormatPopover && !activeFormatPopover.contains(event.target) && !formatPopoverAnchor.contains(event.target)) closeFormatPopover();
    });
    window.addEventListener("resize", () => closeFormatPopover());
    document.querySelectorAll(".ribbon-content").forEach(element => element.addEventListener("scroll", () => closeFormatPopover()));
    refreshDrawingControls();
}

function beginStroke(point) {
    currentPoints = [point];
    currentSmooth = [{x: point.x, y: point.y}];
}

function clearStroke() {
    currentPoints = [];
    currentSmooth = [];
}

// Vale para as próximas nuvens e, se houver uma selecionada, também para ela.
function applyCloudFreeMode(livre) {
    cloudFreeMode = livre;
    if (byId("cfg-nuvem-livre")) byId("cfg-nuvem-livre").checked = livre;
    const selecionada = annotations[selectedIndex];
    if (selecionada && selecionada.type === "Nuvem" && isFreeCloud(selecionada) !== livre) {
        // Só a nuvem desenhada à mão livre tem traço próprio; a retangular usa a
        // caixa. Trocar de tipo sem os pontos deixaria a marcação vazia.
        if (!livre) {
            pushHistory();
            const caixa = annotationBounds(selecionada);
            selecionada.free = undefined;
            selecionada.x = caixa.x;
            selecionada.y = caixa.y;
            selecionada.w = caixa.w;
            selecionada.h = caixa.h;
            invalidateShapeBounds(selecionada);
            redraw();
        } else if (Array.isArray(selecionada.points) && selecionada.points.length > 2) {
            pushHistory();
            selecionada.free = true;
            invalidateShapeBounds(selecionada);
            redraw();
        } else {
            setStatus("A nuvem retangular vira à mão livre apenas ao ser desenhada assim.");
        }
    }
    persistPreferences();
}

// ---------------------------------------------------------------------------
// Menu de opções por ferramenta
//
// Cada ferramenta com tamanho próprio ganha uma setinha ao lado do botão, no
// mesmo lugar em que a caneta, o marca-texto e a nuvem já tinham a delas. O
// menu reúne junto da ferramenta o que antes ficava solto na faixa — tamanho,
// preenchimento, número — e vale tanto para a próxima marcação quanto para a
// que estiver selecionada.
// ---------------------------------------------------------------------------

// O que cada menu mostra. "fill" e "text" só aparecem em quem tem essas opções.
const toolConfigMenus = {
    Seta: {title: "Seta", size: true},
    Chamada: {title: "Linha de chamada", size: true},
    CotaLivre: {title: "Cota livre", size: true},
    CotaAngulo: {title: "Cota de ângulo", size: true},
    Texto: {title: "Texto", size: true, check: {id: "cfg-texto-auto", rotulo: "Caixa acompanha o texto"}},
    Balao: {title: "Balão numerado", size: true, fill: "balao", text: "Balao",
            check: {id: "cfg-balao-line", rotulo: "Com linha de chamada"}},
    Revisao: {title: "Triângulo de revisão", size: true, fill: "revisao", text: "Revisao"},
    Nuvem: {title: "Nuvem de revisão", size: true, cloud: true}
};

// Cada ferramenta tem a sua faixa de valores; a nuvem é a única diferente.
const toolConfigLimits = {Nuvem: {min: 3, max: 60}};

function buildToolConfigMenus() {
    const popover = document.createElement("section");
    popover.id = "tool-config-popover";
    popover.className = "format-popover";
    popover.hidden = true;
    popover.setAttribute("role", "dialog");
    document.body.append(popover);

    Object.keys(toolConfigMenus).forEach(tool => {
        document.querySelectorAll('.tool-btn[data-tool="' + tool + '"]').forEach(toolButton => {
            const wrapper = document.createElement("div");
            wrapper.className = "stroke-tool";
            toolButton.before(wrapper);
            wrapper.append(toolButton);
            const trigger = document.createElement("button");
            trigger.className = "stroke-menu-trigger";
            trigger.innerHTML = CARET_SVG;
            trigger.title = "Opções: " + toolConfigMenus[tool].title;
            trigger.setAttribute("aria-label", trigger.title);
            trigger.setAttribute("aria-expanded", "false");
            wrapper.append(trigger);
            trigger.onclick = () => {
                if (activeFormatPopover === popover && formatPopoverAnchor === trigger) return closeFormatPopover();
                // Abrir o menu já escolhe a ferramenta, a não ser que a marcação
                // selecionada seja dela — aí o menu edita o que está selecionado.
                if (annotations[selectedIndex]?.type !== tool) { finishActiveCommand(true); selectTool(tool); }
                openToolConfig = tool;
                renderToolConfigMenu(popover, tool);
                openFormatPopover(popover, trigger);
            };
        });
    });
}

// O tamanho vem da marcação selecionada quando há uma; senão, do padrão da
// ferramenta. É o mesmo valor do campo da faixa, só que ao lado do botão.
function toolConfigSize(tool) {
    const selecionada = annotations[selectedIndex];
    if (selecionada && selecionada.type === tool && Number(selecionada.font) > 0) return Number(selecionada.font);
    return toolSizes[tool] ?? 20;
}

function applyToolConfigSize(tool, valor) {
    byId("cfg-fonte").value = clampToolSize(tool, valor);
    handleFormatControlChanged();
}

function toolConfigFilled(tool) {
    const selecionada = annotations[selectedIndex];
    if (tool === "Balao") {
        if (selecionada && selecionada.type === "Balao") return selecionada.fillBalloon !== false;
        return byId("cfg-balao-fill") ? byId("cfg-balao-fill").checked : true;
    }
    if (selecionada && selecionada.type === "Revisao") return selecionada.fillReview === true;
    return byId("cfg-revisao-fill") ? byId("cfg-revisao-fill").checked : false;
}

function toolConfigNextHint(chave, atual) {
    return autoSequence[chave] !== false
        ? "Próximo: " + atual + " · depois " + nextSequenceText(atual)
        : "Fixo em " + atual + ": não avança sozinho.";
}

function renderToolConfigMenu(popover, tool) {
    const config = toolConfigMenus[tool];
    const rotulo = sizeLabels[tool] || "Tamanho";
    const limites = toolConfigLimits[tool] || {min: 8, max: 200};
    popover.setAttribute("aria-label", config.title);

    let html = '<div class="picker-heading">' + config.title
        + '<button class="picker-close" aria-label="Fechar">&times;</button></div>';
    if (config.size) {
        html += '<span class="picker-label">' + rotulo + '</span>'
            + '<div class="config-size-row">'
            + '<input class="config-size" type="number" min="' + limites.min + '" max="'
            + limites.max + '" step="1" value="' + toolConfigSize(tool)
            + '" aria-label="' + rotulo + '">'
            + '<span class="config-stepper">'
            + '<button type="button" data-step="1" tabindex="-1" aria-label="Aumentar">&#9650;</button>'
            + '<button type="button" data-step="-1" tabindex="-1" aria-label="Diminuir">&#9660;</button>'
            + '</span><span class="config-hint">' + limites.min + ' a ' + limites.max
            + '</span></div>';
    }
    if (config.fill) {
        const cheio = toolConfigFilled(tool);
        html += '<span class="picker-label">Preenchimento</span>'
            + '<div class="option-choices" role="group" aria-label="Preenchimento">'
            + '<button class="option-choice" data-fill="solid" aria-pressed="' + cheio + '">'
            + '<span class="config-shape ' + config.fill + ' solid"></span><span>Sólido</span></button>'
            + '<button class="option-choice" data-fill="outline" aria-pressed="' + (!cheio) + '">'
            + '<span class="config-shape ' + config.fill + ' outline"></span><span>Vazado</span></button></div>';
    }
    if (config.cloud) {
        const livre = annotations[selectedIndex]?.type === "Nuvem"
            ? isFreeCloud(annotations[selectedIndex]) : cloudFreeMode;
        html += '<span class="picker-label">Traço</span>'
            + '<div class="option-choices" role="group" aria-label="Traço da nuvem">'
            + '<button class="option-choice" data-cloud="box" aria-pressed="' + (!livre) + '">'
            + '<span class="material-symbols-outlined">crop_square</span><span>Retangular</span></button>'
            + '<button class="option-choice" data-cloud="free" aria-pressed="' + livre + '">'
            + '<span class="material-symbols-outlined">gesture</span><span>À mão livre</span></button></div>'
            + '<div class="config-hint" style="margin-top:8px">À mão livre, termine o risco'
            + ' perto do início para fechar a nuvem.</div>';
    }
    if (config.check) {
        const marcado = byId(config.check.id) && byId(config.check.id).checked;
        html += '<label class="config-check" style="margin-top:12px">'
            + '<input type="checkbox" class="config-extra"' + (marcado ? " checked" : "") + ">"
            + "<span>" + config.check.rotulo + "</span></label>";
    }
    if (config.text) {
        const atual = String(byId("cfg-numero").value || "1");
        html += '<span class="picker-label">Texto</span>'
            + '<input class="config-text-input" type="text" maxlength="12" value="'
            + atual.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;")
            + '" placeholder="1, A, R1..." aria-label="Texto da marcação" autocomplete="off">'
            + '<label class="config-check"><input type="checkbox" class="config-seq"'
            + (autoSequence[config.text] !== false ? " checked" : "") + ">"
            + "<span>Sequência automática</span></label>"
            + '<div class="config-hint config-next">' + toolConfigNextHint(config.text, atual) + "</div>";
    }
    popover.innerHTML = html;
    popover.querySelector(".picker-close").onclick = () => closeFormatPopover(true);

    const campoTamanho = popover.querySelector(".config-size");
    if (campoTamanho) {
        campoTamanho.oninput = () => applyToolConfigSize(tool, campoTamanho.value);
        popover.querySelectorAll(".config-stepper button").forEach(passo => {
            passo.onclick = () => {
                const valor = clampToolSize(tool, Number(campoTamanho.value) + Number(passo.dataset.step));
                campoTamanho.value = valor;
                applyToolConfigSize(tool, valor);
            };
        });
    }
    popover.querySelectorAll("[data-cloud]").forEach(escolha => {
        escolha.onclick = () => {
            applyCloudFreeMode(escolha.dataset.cloud === "free");
            renderToolConfigMenu(popover, tool);
            positionFormatPopover();
        };
    });
    popover.querySelectorAll("[data-fill]").forEach(escolha => {
        escolha.onclick = () => {
            const alvo = byId(tool === "Balao" ? "cfg-balao-fill" : "cfg-revisao-fill");
            if (alvo) alvo.checked = escolha.dataset.fill === "solid";
            handleFormatControlChanged();
            renderToolConfigMenu(popover, tool);
            positionFormatPopover();
        };
    });
    const extra = popover.querySelector(".config-extra");
    if (extra) {
        extra.onchange = () => {
            const alvo = byId(config.check.id);
            if (alvo) alvo.checked = extra.checked;
            handleFormatControlChanged();
        };
    }
    const campoTexto = popover.querySelector(".config-text-input");
    if (campoTexto) {
        campoTexto.oninput = () => {
            byId("cfg-numero").value = campoTexto.value;
            handleFormatControlChanged();
            const dica = popover.querySelector(".config-next");
            if (dica) dica.textContent = toolConfigNextHint(config.text, campoTexto.value || "1");
        };
    }
    const interruptor = popover.querySelector(".config-seq");
    if (interruptor) {
        interruptor.onchange = () => {
            autoSequence[config.text] = interruptor.checked;
            persistPreferences();
            renderToolConfigMenu(popover, tool);
            positionFormatPopover();
        };
    }
}

function appendStrokePoint(point, final = false) {
    const previous = currentPoints[currentPoints.length - 1];
    const distance = previous ? Math.hypot(point.x-previous.x, point.y-previous.y) : Infinity;
    // Passo constante na tela: elimina o tremor subpixel e mantém o traço com a
    // mesma densidade de pontos em qualquer zoom.
    const threshold = Math.min(3, Math.max(.6, STROKE_MIN_DISTANCE / Math.max(.1, canvasScale().x)));
    if (!(distance > 0 && (final || distance >= threshold))) return;
    currentPoints.push(point);
    const last = currentPoints.length - 1;
    // Média ponderada 1-2-1 no ponto que deixou de ser a ponta. A ponta em si
    // fica crua, para o traço não ficar atrasado em relação ao cursor.
    if (last >= 2) {
        const before = currentPoints[last - 2];
        const middle = currentPoints[last - 1];
        currentSmooth[last - 1] = {
            x: (before.x + middle.x * 2 + point.x) / 4,
            y: (before.y + middle.y * 2 + point.y) / 4
        };
    }
    currentSmooth.push({x: point.x, y: point.y});
}

// Tira o "degrau" do traço antes de virar curva: descarta os pontos colados
// demais e passa uma média ponderada 1-2-1 pelos que sobraram. É o tratamento
// do Notas de Engenharia, e vale para o preview, a cópia e a exportação.
function smoothStrokePoints(points, passes = 1) {
    if (!Array.isArray(points) || points.length <= 2) return (points || []).map(point => ({x: point.x, y: point.y}));
    const filtered = [points[0]];
    for (let i = 1; i < points.length - 1; i++) {
        const previous = filtered[filtered.length - 1];
        if (Math.hypot(points[i].x - previous.x, points[i].y - previous.y) >= STROKE_MIN_DISTANCE) filtered.push(points[i]);
    }
    const last = points[points.length - 1];
    if (Math.hypot(last.x - filtered[filtered.length - 1].x, last.y - filtered[filtered.length - 1].y) > 0) filtered.push(last);
    let result = filtered.map(point => ({x: point.x, y: point.y}));
    for (let pass = 0; pass < passes && result.length > 2; pass++) {
        const source = result;
        result = source.map((point, index) => {
            if (index === 0 || index === source.length - 1) return point;
            const previous = source[index - 1];
            const next = source[index + 1];
            return {x: (previous.x + point.x * 2 + next.x) / 4, y: (previous.y + point.y * 2 + next.y) / 4};
        });
    }
    return result;
}

// Os pontos já chegam suavizados (appendStrokePoint durante o traço,
// smoothStrokePoints ao concluir): aqui só resta transformá-los em curva.
function drawSmoothStroke(context, points) {
    const smooth = points;
    if (!smooth || !smooth.length) return;
    context.beginPath();
    if (smooth.length === 1) {
        context.arc(smooth[0].x, smooth[0].y, context.lineWidth / 2, 0, Math.PI * 2);
        context.fill();
        return;
    }
    context.moveTo(smooth[0].x, smooth[0].y);
    // Curvas por pontos médios: tangentes contínuas e sem ultrapassar o traço.
    for (let i = 1; i < smooth.length - 1; i++) {
        const p = smooth[i], next = smooth[i+1];
        context.quadraticCurveTo(p.x, p.y, (p.x+next.x)/2, (p.y+next.y)/2);
    }
    const last = smooth[smooth.length-1];
    context.lineTo(last.x, last.y);
    context.stroke();
}

function getOptions() {
    return {
        color: byId("cfg-cor").value || "#107C41",
        thick: Math.max(1, Number(byId("cfg-espessura").value) || 4) / (formattingTool() === "MarcaTexto" ? 4 : 1),
        font: clampToolSize(formattingTool(), byId("cfg-fonte").value),
        bold: byId("btn-bold").classList.contains("active"),
        italic: byId("btn-italic").classList.contains("active"),
        underline: byId("btn-underline").classList.contains("active"),
        fillBalloon: byId("cfg-balao-fill") ? byId("cfg-balao-fill").checked : true,
        lineBalloon: byId("cfg-balao-line") ? byId("cfg-balao-line").checked : false,
        fillReview: byId("cfg-revisao-fill") ? byId("cfg-revisao-fill").checked : false,
        autoHeight: byId("cfg-texto-auto") ? byId("cfg-texto-auto").checked : true
    };
}

// Ler clientWidth forca o navegador a recalcular o layout. Como canvasScale e
// consultada dezenas de vezes por quadro (alcas, tolerancias, editor de texto),
// o valor e medido uma vez por quadro e reaproveitado.
let canvasScaleCache = {x: 1, y: 1};

function refreshCanvasScale() {
    canvasScaleCache = {
        x: canvas.clientWidth / Math.max(1, docWidth),
        y: canvas.clientHeight / Math.max(1, docHeight)
    };
    return canvasScaleCache;
}

function canvasScale() {
    return canvasScaleCache;
}

function finishActiveCommand(commit = true) {
    let handled = false;
    if (activeTextEditor) {
        finalizeTextEditor(commit, false);
        handled = true;
    }
    if (orthogonalPath) {
        finalizeOrthogonalPath(commit);
        handled = true;
    }
    if (isDrawing && currentTool !== "Mover") {
        isDrawing = false;
        startPoint = null;
        clearStroke();
        preview = null;
        handled = true;
        if (bgImage || workspaceMode === "edition") redraw();
    }
    return handled;
}

function interruptCommand() {
    const handled = finishActiveCommand(true);
    selectedIndex = -1;
    selectTool("Mover", false);
    if (handled) setStatus("Comando interrompido.");
}

function startTextEditor(point, options) {
    finishActiveCommand(true);
    createFloatingTextEditor({
        kind: "text",
        point,
        options,
        placeholder: "Digite o texto",
        status: "Digite o texto, ajuste a caixa se quiser e clique fora ou pressione ESC para concluir."
    });
}

function startShapeLabelEditor(shape, point) {
    createFloatingTextEditor({
        kind: "shapeLabel",
        point,
        options: shape,
        shape,
        placeholder: "Texto / cota",
        status: "Digite o texto da anotação e clique fora ou pressione ESC para concluir."
    });
}

function editAnnotationText(index) {
    const shape = annotations[index];
    if (!shape || !isTextEditable(shape)) return false;
    const kind = shape.type === "Texto" ? "editText" : "editShapeLabel";
    createFloatingTextEditor({
        kind,
        point: editorPointForAnnotation(shape),
        options: shape,
        shape,
        editIndex: index,
        initialText: String(shape.text || ""),
        placeholder: shape.type === "Balao" || shape.type === "Revisao" ? "Nº / letra" : "Texto / cota",
        status: "Edite o texto e clique fora ou pressione ESC para concluir."
    });
    return true;
}

function isTextEditable(shape) {
    return ["Texto", "CotaLivre", "CotaAngulo", "Chamada", "Balao", "Revisao"].includes(shape?.type);
}

function editorPointForAnnotation(shape) {
    if (shape.type === "Texto") return {x: shape.x, y: shape.y};
    if (shape.type === "Chamada") {
        const rect = calloutTextRect(shape);
        return {x: Math.max(0, rect.x), y: Math.max(0, rect.y)};
    }
    if (shape.type === "Balao") {
        const badge = balloonBadgePoint(shape);
        const font = balloonFontSize(shape);
        return {x: Math.max(0, badge.x - font * 1.2), y: Math.max(0, badge.y - font * 0.9)};
    }
    if (shape.type === "Revisao") {
        const size = reviewMarkerSize(shape);
        return {x: Math.max(0, shape.x - size * 0.45), y: Math.max(0, shape.y - size * 0.35)};
    }
    return labelPointForShape(shape);
}

function createFloatingTextEditor({kind, point, options, shape = null, editIndex = null, initialText = "", placeholder, status}) {
    const scale = canvasScale();
    const editor = document.createElement("textarea");
    editor.className = "canvas-text-editor";
    editor.placeholder = placeholder || "Digite o texto";
    editor.style.left = `${point.x * scale.x}px`;
    editor.style.top = `${point.y * scale.y}px`;
    const compact = kind === "shapeLabel" || kind === "editShapeLabel";
    // A chamada digita na mesma caixa em que o texto vai aparecer.
    const callout = options.type === "Chamada";
    const widthCanvas = callout
        ? calloutTextWidth(options)
        : (kind === "editText" && options.w ? options.w : Math.max(compact ? 120 : 180, options.font * (compact ? 4.8 : 7)));
    const heightCanvas = callout
        ? Math.max(options.font * 1.7, Number(options.textH) || 0)
        : (kind === "editText" && options.h ? options.h : Math.max(compact ? 34 : 70, options.font * (compact ? 1.7 : 2.6)));
    editor.style.width = `${widthCanvas * scale.x}px`;
    editor.style.height = `${heightCanvas * scale.y}px`;
    editor.style.color = options.color;
    const editorFont = options.type === "Balao"
        ? balloonFontSize(options)
        : (options.type === "Revisao" ? reviewMarkerFontSize(options) : options.font);
    editor.style.fontSize = `${Math.max(10, editorFont * scale.y)}px`;
    editor.style.fontWeight = options.bold ? "700" : "400";
    editor.style.fontStyle = options.italic ? "italic" : "normal";
    editor.style.textDecoration = options.underline ? "underline" : "none";
    editor.value = initialText;
    canvasContainer.appendChild(editor);
    activeTextEditor = {kind, editor, x: point.x, y: point.y, options, shape, editIndex};
    // stopPropagation apenas no mousedown: impede que o clique inicial feche o
    // editor (handler global), sem bloquear a seleção nativa por arraste.
    editor.addEventListener("mousedown", event => event.stopPropagation());
    // A caixa cresce em altura conforme o texto é digitado (largura continua
    // ajustável pela alça do textarea) — comportamento orgânico tipo PowerPoint.
    const autoGrowEditor = () => {
        editor.style.height = "auto";
        editor.style.height = `${editor.scrollHeight}px`;
    };
    editor.addEventListener("input", autoGrowEditor);
    editor.addEventListener("keydown", event => {
        if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            finalizeTextEditor(true, true);
        }
    });
    window.setTimeout(autoGrowEditor, 0);
    window.setTimeout(() => {
        if (activeTextEditor?.editor === editor) {
            editor.focus({preventScroll: true});
            editor.select();
        }
    }, 0);
    setStatus(status);
}

function finalizeTextEditor(commit = true, switchToMover = true) {
    if (!activeTextEditor) return;
    const {kind, editor, options, shape, editIndex} = activeTextEditor;
    const text = editor.value.trim();
    const canvasRect = canvas.getBoundingClientRect();
    const editorRect = editor.getBoundingClientRect();

    if (Number.isInteger(editIndex) && annotations[editIndex]) {
        const edited = annotations[editIndex];
        editor.remove();
        activeTextEditor = null;
        if (commit) {
            pushHistory();
            edited.text = text;
            if (edited.type === "Chamada") {
                edited.textW = Math.max(40, editorRect.width * docWidth / Math.max(1, canvasRect.width));
                if (calloutFixedHeight(edited)) {
                    edited.textH = Math.max(16, editorRect.height * docHeight / Math.max(1, canvasRect.height));
                }
            }
            if (edited.type === "Texto") {
                edited.x = (editorRect.left - canvasRect.left) * docWidth / Math.max(1, canvasRect.width);
                edited.y = (editorRect.top - canvasRect.top) * docHeight / Math.max(1, canvasRect.height);
                edited.w = editorRect.width * docWidth / Math.max(1, canvasRect.width);
                // Com o autoajuste ligado a caixa acompanha o texto digitado.
                // Desligado (a altura já foi definida à mão), o tamanho escolhido
                // manda e é o texto que encolhe para caber.
                const editorH = editorRect.height * docHeight / Math.max(1, canvasRect.height);
                edited.h = edited.autoHeight === false
                    ? Math.max(edited.h || 0, (edited.font || 18) * 1.2)
                    : Math.max(edited.h || 0, editorH);
            }
            selectedIndex = editIndex;
            setStatus("Texto atualizado.");
            scheduleClipboardSync();
        } else {
            setStatus("Edição cancelada.");
        }
        if (switchToMover) selectTool("Mover", false);
        redraw();
        return;
    }

    const annotation = kind === "shapeLabel" && shape
        ? (shape.type === "Chamada"
            ? {...shape, text, textW: Math.max(40, editorRect.width * docWidth / Math.max(1, canvasRect.width))}
            : {...shape, text})
        : {
            type: "Texto",
            x: (editorRect.left - canvasRect.left) * docWidth / Math.max(1, canvasRect.width),
            y: (editorRect.top - canvasRect.top) * docHeight / Math.max(1, canvasRect.height),
            w: editorRect.width * docWidth / Math.max(1, canvasRect.width),
            h: editorRect.height * docHeight / Math.max(1, canvasRect.height),
            text,
            ...options
        };
    editor.remove();
    activeTextEditor = null;
    if (commit && (kind === "shapeLabel" || text)) {
        pushHistory();
        annotations.push(annotation);
        selectedIndex = annotations.length - 1;
        setStatus(kind === "shapeLabel" ? "Anotação inserida." : "Texto inserido.");
        scheduleClipboardSync();
    } else {
        setStatus(kind === "shapeLabel" ? "Anotação cancelada." : "Texto cancelado.");
    }
    if (switchToMover) selectTool("Mover", false);
    redraw();
}

// Perto da horizontal ou da vertical, o traço encaixa nela. A tolerância cresce
// com o comprimento (8% dele, entre 6 e 24 px do documento): num traço curto o
// encaixe não atrapalha a mira, e num longo ele ainda pega. Passar da tolerância
// devolve o ângulo livre — não é uma trava, é um ímã fraco.
function applyAxisSnap(tool, origin, point) {
    if (!axisSnapTools.has(tool) || !origin || !point) return point;
    const dx = point.x - origin.x;
    const dy = point.y - origin.y;
    const comprimento = Math.hypot(dx, dy);
    if (comprimento < 8) return point;
    const tolerancia = Math.max(6, Math.min(24, comprimento * 0.08));
    if (Math.abs(dy) <= tolerancia) return {x: point.x, y: origin.y};
    if (Math.abs(dx) <= tolerancia) return {x: origin.x, y: point.y};
    return point;
}

function snapOrthogonalPoint(origin, point) {
    const dx = point.x - origin.x;
    const dy = point.y - origin.y;
    return Math.abs(dx) >= Math.abs(dy)
        ? {x: point.x, y: origin.y}
        : {x: origin.x, y: point.y};
}

function handleOrthogonalClick(point, options) {
    if (!orthogonalPath) {
        orthogonalPath = {type: "LinhaOrto", points: [point], ...options};
        preview = {...orthogonalPath, points: [point, point]};
        setStatus("Linha ortogonal iniciada. Clique para continuar; botão direito, Interromper ou ESC conclui.");
        redraw();
        return;
    }

    const lastPoint = orthogonalPath.points[orthogonalPath.points.length - 1];
    const snapped = snapOrthogonalPoint(lastPoint, point);
    if (Math.hypot(snapped.x - lastPoint.x, snapped.y - lastPoint.y) >= 2) {
        orthogonalPath.points.push(snapped);
    }
    const next = orthogonalPath.points[orthogonalPath.points.length - 1];
    preview = {...orthogonalPath, points: orthogonalPath.points.concat([{...next}])};
    redraw();
}

function finalizeOrthogonalPath(commit = true) {
    if (!orthogonalPath) return;
    if (commit && orthogonalPath.points.length > 1) {
        pushHistory();
        annotations.push({...orthogonalPath, points: orthogonalPath.points.map(point => ({...point}))});
        selectedIndex = annotations.length - 1;
        scheduleClipboardSync();
    }
    orthogonalPath = null;
    preview = null;
    redraw();
}

// O ponteiro dispara centenas de eventos por segundo; procurar a marcação sob o
// cursor a cada um deles é o que tirava a fluidez do Mover. Um por quadro basta
// para o cursor certo aparecer.
let hoverPending = false;
let hoverPoint = null;

function scheduleHoverCursor(point) {
    hoverPoint = point;
    if (hoverPending) return;
    hoverPending = true;
    requestAnimationFrame(() => {
        hoverPending = false;
        if (hoverPoint) updateHoverCursor(hoverPoint);
    });
}

function updateHoverCursor(point) {
    if (currentTool !== "Mover" || isDrawing) return;
    const hit = findAnnotationAt(point.x, point.y);
    if (hit.index >= 0) {
        if (hit.handle === "box-resize" || hit.handle === "line-resize" || hit.handle === "callout-text") {
            canvas.style.cursor = resizeHandleCursor(hit.corner);
        } else if (hit.handle === "marker-resize") {
            canvas.style.cursor = "nwse-resize";
        } else if (hit.handle === "dimension-grip") {
            canvas.style.cursor = dimensionGripCursor(annotations[hit.index]);
        } else if (hit.handle === "balloon-tip") {
            canvas.style.cursor = "crosshair";
        } else {
            canvas.style.cursor = "move";
        }
        return;
    }
    if (workspaceMode === "edition") {
        const imageHit = findEditionItemAt(point.x, point.y);
        canvas.style.cursor = imageHit.handle === "resize" ? "nwse-resize" : (imageHit.index >= 0 ? "move" : "default");
        return;
    }
    canvas.style.cursor = "default";
}

function getMousePos(event) {
    const rect = canvas.getBoundingClientRect();
    return {
        x: (event.clientX - rect.left) * docWidth / Math.max(1, rect.width),
        y: (event.clientY - rect.top) * docHeight / Math.max(1, rect.height)
    };
}

document.addEventListener("mousedown", event => {
    if (!activeTextEditor) return;
    if (activeTextEditor.editor.contains(event.target)) return;
    // Controles de formatação NÃO concluem a edição: aplicam-se ao texto aberto
    // (comportamento PowerPoint: selecionar texto e clicar em Negrito etc.).
    const formatControl = event.target.closest(
        '.ribbon-group[data-title="Formatação"], .format-popover');
    if (formatControl) {
        // Botões de estilo não roubam o foco, mantendo a seleção visível.
        if (event.target.closest(".style-btn")) event.preventDefault();
        return;
    }
    finalizeTextEditor(true, true);
}, true);

canvas.addEventListener("mousedown", event => {
    if (!ensureImage()) return;
    if (activeTextEditor) {
        finalizeTextEditor(true, true);
        event.preventDefault();
        return;
    }
    if (event.button !== 0) return;
    const point = getMousePos(event);
    const options = getOptions();

    if (currentTool === "Mover") {
        const hit = findAnnotationAt(point.x, point.y, true);
        selectedIndex = hit.index;
        if (selectedIndex >= 0) {
            selectedEditionItemIndex = -1;
            const annotation = annotations[selectedIndex];
            if (hit.handle === "box-resize" || hit.handle === "line-resize"
                || hit.handle === "marker-resize" || hit.handle === "callout-text") {
                interactionMode = hit.handle;
                resizeCorner = hit.corner;
            } else if (hit.handle === "dimension-grip") {
                interactionMode = "dimension-grip";
            } else if (hit.handle === "balloon-tip") {
                interactionMode = "balloon-tip";
            } else {
                interactionMode = "move";
            }
            const anchor = annotationAnchor(annotation);
            dragOffset = {x: point.x - anchor.x, y: point.y - anchor.y};
            beginHistoryTransaction();
            isDrawing = true;
            syncFormatControlsFromSelection(annotation);
        } else if (workspaceMode === "edition") {
            const imageHit = findEditionItemAt(point.x, point.y);
            selectedEditionItemIndex = imageHit.index;
            if (selectedEditionItemIndex >= 0) {
                selectedIndex = -1;
                interactionMode = imageHit.handle === "resize" ? "edition-image-resize" : "edition-image-move";
                const item = editionItems[selectedEditionItemIndex];
                dragOffset = {x: point.x - item.x, y: point.y - item.y};
                beginHistoryTransaction();
                isDrawing = true;
            }
        } else {
            selectedEditionItemIndex = -1;
        }
        redraw();
        return;
    }

    if (currentTool === "Revisao") {
        const reviewHit = findAnnotationAt(point.x, point.y);
        if (reviewHit.index >= 0 && annotations[reviewHit.index].type === "Revisao") {
            selectedIndex = reviewHit.index;
            editAnnotationText(reviewHit.index);
            return;
        }
        const numberInput = byId("cfg-numero");
        pushHistory();
        annotations.push({type: "Revisao", x: point.x, y: point.y, text: String(numberInput.value || "R"), ...options});
        selectedIndex = annotations.length - 1;
        if (autoSequence.Revisao) numberInput.value = nextSequenceText(numberInput.value || "R");
        persistPreferences();
        redraw();
        scheduleClipboardSync();
        return;
    }

    if (currentTool === "Balao") {
        const balloonHit = findAnnotationAt(point.x, point.y);
        if (balloonHit.index >= 0 && annotations[balloonHit.index].type === "Balao") {
            selectedIndex = balloonHit.index;
            editAnnotationText(balloonHit.index);
            return;
        }
        if (!options.lineBalloon) {
            const numberInput = byId("cfg-numero");
            pushHistory();
            annotations.push({type: "Balao", x: point.x, y: point.y, w: 0, h: 0, text: String(numberInput.value), ...options});
            if (autoSequence.Balao) numberInput.value = nextSequenceText(numberInput.value || "1");
            persistPreferences();
            redraw();
            scheduleClipboardSync();
            return;
        }
    }

    if (currentTool === "Texto") {
        event.preventDefault();
        event.stopPropagation();
        const textHit = findAnnotationAt(point.x, point.y);
        if (textHit.index >= 0 && annotations[textHit.index].type === "Texto") {
            selectedIndex = textHit.index;
            editAnnotationText(textHit.index);
        } else {
            startTextEditor(point, options);
        }
        return;
    }

    if (currentTool === "LinhaOrto") {
        handleOrthogonalClick(point, options);
        return;
    }

    startPoint = point;
    isDrawing = true;
    // A nuvem à mão livre é traçada como a caneta: o festonado nasce depois, em
    // cima da linha desenhada.
    if (strokeResizeTools.has(currentTool) || drawingFreeCloud()) beginStroke(point);
    else clearStroke();
    preview = createShape(currentTool, point, point, options);
});

canvas.addEventListener("pointermove", event => {
    if (workspaceMode !== "edition" && !bgImage) return;
    let point = getMousePos(event);
    if (orthogonalPath) {
        const lastPoint = orthogonalPath.points[orthogonalPath.points.length - 1];
        const snapped = snapOrthogonalPoint(lastPoint, point);
        preview = {...orthogonalPath, points: orthogonalPath.points.concat([snapped])};
        scheduleRedraw();
        return;
    }
    if (currentTool === "Mover" && !isDrawing) {
        scheduleHoverCursor(point);
    }
    if (!isDrawing) return;

    if (currentTool === "Mover" && workspaceMode === "edition" && selectedEditionItemIndex >= 0) {
        const item = editionItems[selectedEditionItemIndex];
        if (interactionMode === "edition-image-resize") {
            resizeEditionItem(item, point);
        } else {
            moveEditionItem(item, point.x - dragOffset.x, point.y - dragOffset.y);
        }
        scheduleRedraw();
        return;
    }

    if (currentTool === "Mover" && selectedIndex >= 0) {
        const annotation = annotations[selectedIndex];
        if (interactionMode === "box-resize") {
            if (isPointShape(annotation)) {
                resizeStrokeShape(annotation, resizeCorner, point);
            } else if (annotation.type === "Circulo" && resizeCorner && resizeCorner.length === 2) {
                resizeCircleCorner(annotation, resizeCorner, point);
            } else if (annotation.type === "Texto") {
                // Arrastar uma alça de cima ou de baixo desliga o autoajuste: a
                // partir daí a caixa manda e o texto encolhe para caber nela,
                // como no PowerPoint.
                if (/[ns]/.test(resizeCorner || "")) annotation.autoHeight = false;
                resizeBoxShape(annotation, resizeCorner, point, Math.max(12, (annotation.font || 18) * 0.35));
            } else {
                resizeBoxShape(annotation, resizeCorner, point);
            }
        } else if (interactionMode === "marker-resize") {
            resizeMarkerShape(annotation, point);
        } else if (interactionMode === "callout-text") {
            resizeCalloutText(annotation, resizeCorner, point);
        } else if (interactionMode === "line-resize") {
            resizeLineShape(annotation, resizeCorner, point);
        } else if (interactionMode === "dimension-grip" && annotation.type === "CotaLivre") {
            extendDimensionCallout(annotation, point);
        } else if (interactionMode === "balloon-tip" && annotation.type === "Balao") {
            moveBalloonTip(annotation, point);
        } else {
            moveAnnotation(annotation, point.x - dragOffset.x, point.y - dragOffset.y);
        }
        scheduleRedraw();
        return;
    }

    if (!startPoint) return;
    point = applyAxisSnap(currentTool, startPoint, point);
    if (strokeResizeTools.has(currentTool) || drawingFreeCloud()) {
        const samples = event.getCoalescedEvents?.() || [];
        for (const sample of samples) appendStrokePoint(getMousePos(sample));
        appendStrokePoint(point);
    }
    preview = createShape(currentTool, startPoint, point, getOptions());
    if (currentTool === "Balao") preview.text = String(byId("cfg-numero").value || "1");
    scheduleRedraw();
});

function finishDrawing(event) {
    if (!isDrawing) return;
    if (currentTool === "LinhaOrto") return;
    if (currentTool === "Mover") {
        if (workspaceMode === "edition" && selectedEditionItemIndex >= 0) {
            finalizeEditionItemTransform(editionItems[selectedEditionItemIndex]);
        }
        isDrawing = false;
        interactionMode = null;
        resizeCorner = null;
        commitHistoryTransaction();
        redraw();
        scheduleClipboardSync();
        return;
    }
    if (event && startPoint) {
        const point = applyAxisSnap(currentTool, startPoint, getMousePos(event));
        if (strokeResizeTools.has(currentTool) || drawingFreeCloud()) appendStrokePoint(point, true);
        preview = createShape(currentTool, startPoint, point, getOptions());
    }
    isDrawing = false;
    let committed = false;
    if (preview) freezeStrokePoints(preview);
    if (preview && shapeHasSize(preview)) {
        if (currentTool === "Cortar") {
            const cropShape = preview;
            preview = null;
            startPoint = null;
            clearStroke();
            cropToShape(cropShape);
            selectTool("Mover", false);
            return;
        } else if (currentTool === "Balao") {
            const numberInput = byId("cfg-numero");
            preview.text = String(numberInput.value || "1");
            pushHistory();
            annotations.push(preview);
            selectedIndex = annotations.length - 1;
            if (autoSequence.Balao) numberInput.value = nextSequenceText(numberInput.value || "1");
            persistPreferences();
            committed = true;
        } else if (labelTools.has(currentTool)) {
            const shape = preview;
            preview = null;
            startPoint = null;
            clearStroke();
            redraw();
            startShapeLabelEditor(shape, labelPointForShape(shape));
            return;
        } else {
            pushHistory();
            annotations.push(preview);
            committed = true;
        }
    }
    preview = null;
    startPoint = null;
    clearStroke();
    redraw();
    if (committed) scheduleClipboardSync();
}

canvas.addEventListener("mouseup", finishDrawing);
window.addEventListener("mouseup", finishDrawing);
canvas.addEventListener("mouseleave", event => {
    if (isDrawing && currentTool !== "Mover" && currentTool !== "LinhaOrto") finishDrawing(event);
});
canvas.addEventListener("contextmenu", event => {
    event.preventDefault();
    interruptCommand();
});
canvas.addEventListener("dblclick", event => {
    if (!ensureImage() || activeTextEditor) return;
    event.preventDefault();
    const point = getMousePos(event);
    const hit = findAnnotationAt(point.x, point.y);
    if (hit.index >= 0 && editAnnotationText(hit.index)) {
        currentTool = "Mover";
        document.querySelectorAll(".tool-btn").forEach(item => {
            item.classList.toggle("active", item.dataset.tool === "Mover");
        });
        selectedIndex = hit.index;
        redraw();
    }
});

function createShape(type, start, end, options) {
    let width = end.x - start.x;
    let height = end.y - start.y;
    if (type === "Circulo") {
        const side = Math.max(Math.abs(width), Math.abs(height));
        width = (width < 0 ? -1 : 1) * side;
        height = (height < 0 ? -1 : 1) * side;
    }
    const freehand = strokeResizeTools.has(type) || (type === "Nuvem" && cloudFreeMode);
    const shape = {
        type,
        x: start.x,
        y: start.y,
        w: width,
        h: height,
        // O preview aponta para a lista viva do traço; copiar ponto a ponto a
        // cada movimento do mouse era o que travava o risco longo. A cópia
        // própria é feita uma vez só, em freezeStrokePoints, ao concluir.
        points: freehand ? currentSmooth : [],
        ...options
    };
    if (type === "Nuvem" && cloudFreeMode) shape.free = true;
    if (type === "CotaLivre" && !Number.isFinite(Number(shape.extension))) shape.extension = DEFAULT_DIM_EXTENSION;
    return shape;
}

// Congela o traço no momento em que ele vira marcação: cópia própria dos pontos
// e, no marca-texto, um passe extra de suavização (a tarja é larga e o "bico"
// das curvas aparece mais nela).
function freezeStrokePoints(shape) {
    if (!shape || !Array.isArray(shape.points) || !shape.points.length) return shape;
    shape.points = shape.type === "MarcaTexto"
        ? smoothStrokePoints(shape.points, 1)
        : shape.points.map(point => ({x: point.x, y: point.y}));
    invalidateShapeBounds(shape);
    return shape;
}

function shapeHasSize(shape) {
    if (strokeResizeTools.has(shape.type)) return shape.points.length > 0;
    if (isFreeCloud(shape)) return Array.isArray(shape.points) && shape.points.length > 2;
    if (shape.type === "LinhaOrto" && Array.isArray(shape.points)) return shape.points.length > 1;
    return Math.abs(shape.w) > 2 || Math.abs(shape.h) > 2;
}

function renderScale() {
    return canvas.width / Math.max(1, docWidth);
}

function redraw() {
    redrawPending = false;
    refreshCanvasScale();
    // Tudo é desenhado em coordenadas do documento; esta escala leva o traço
    // para a resolução em que ele aparece na tela.
    const scale = renderScale();
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    if (workspaceMode === "edition") {
        drawEditionWorkspace();
        return;
    }
    if (!bgImage) return;
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "low";
    ctx.clearRect(0, 0, docWidth, docHeight);
    ctx.drawImage(backgroundRenderSource(scale), 0, 0, docWidth, docHeight);
    annotations.forEach((annotation, index) => drawShape(ctx, annotation, index === selectedIndex));
    if (preview) drawShape(ctx, preview, false, true);
}

function scheduleRedraw() {
    if (redrawPending) return;
    redrawPending = true;
    requestAnimationFrame(redraw);
}

function drawEditionWorkspace() {
    ctx.save();
    ctx.clearRect(0, 0, docWidth, docHeight);
    ctx.fillStyle = "#FFFFFF";
    ctx.fillRect(0, 0, docWidth, docHeight);
    // Reamostragem simples de propósito: a qualidade das imagens vem da cópia
    // preparada em editionRenderSource. Pedir "high"/"medium" aqui faria o
    // navegador reescalar as fotos inteiras a cada quadro - com três fotos
    // grandes isso media mais de um segundo por quadro nesta janela.
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "low";
    editionItems.forEach((item, index) => {
        const source = editionRenderSource(item);
        if (source) ctx.drawImage(source, item.x, item.y, item.w, item.h);
        if (index === selectedEditionItemIndex) drawEditionImageSelection(item);
    });
    annotations.forEach((annotation, index) => drawShape(ctx, annotation, index === selectedIndex));
    if (preview) drawShape(ctx, preview, false, true);
    ctx.restore();
}

function drawEditionImageSelection(item) {
    const handle = editionImageHandle(item);
    ctx.save();
    ctx.strokeStyle = "#F2A100";
    ctx.lineWidth = 2;
    ctx.setLineDash([7, 4]);
    ctx.strokeRect(item.x - 5, item.y - 5, item.w + 10, item.h + 10);
    ctx.setLineDash([]);
    ctx.fillStyle = "#F2A100";
    ctx.fillRect(handle.x - 5, handle.y - 5, 10, 10);
    ctx.restore();
}

function drawShape(context, shape, selected = false, temporary = false) {
    context.save();
    context.globalAlpha = temporary ? 0.75 : 1;
    context.strokeStyle = shape.color;
    context.fillStyle = shape.color;
    context.lineWidth = shape.thick;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.beginPath();

    if (shape.type === "Retangulo") {
        context.strokeRect(shape.x, shape.y, shape.w, shape.h);
    } else if (shape.type === "Circulo") {
        const rx = Math.abs(shape.w) / 2;
        const ry = Math.abs(shape.h) / 2;
        context.ellipse(shape.x + shape.w / 2, shape.y + shape.h / 2, rx, ry, 0, 0, Math.PI * 2);
        context.stroke();
    } else if (shape.type === "Linha") {
        context.moveTo(shape.x, shape.y);
        context.lineTo(shape.x + shape.w, shape.y + shape.h);
        context.stroke();
    } else if (shape.type === "Seta") {
        drawArrow(context, shape.x, shape.y, shape.x + shape.w, shape.y + shape.h, shape.thick, shape.font);
    } else if (shape.type === "CotaLivre") {
        drawFreeDimension(context, shape);
    } else if (shape.type === "CotaAngulo") {
        drawAngleDimension(context, shape);
    } else if (shape.type === "Chamada") {
        drawCallout(context, shape);
    } else if (shape.type === "LinhaOrto") {
        if (Array.isArray(shape.points) && shape.points.length) {
            context.moveTo(shape.points[0].x, shape.points[0].y);
            shape.points.slice(1).forEach(point => context.lineTo(point.x, point.y));
        } else {
            const middleX = shape.x + shape.w / 2;
            context.moveTo(shape.x, shape.y);
            context.lineTo(middleX, shape.y);
            context.lineTo(middleX, shape.y + shape.h);
            context.lineTo(shape.x + shape.w, shape.y + shape.h);
        }
        context.stroke();
    } else if (shape.type === "Nuvem") {
        if (isFreeCloud(shape)) drawFreeCloud(context, shape.points || [], cloudRadius(shape));
        else drawCloudBox(context, shape.x, shape.y, shape.w, shape.h, cloudRadius(shape));
    } else if (shape.type === "Caneta" || shape.type === "MarcaTexto") {
        if (shape.points.length) {
            if (shape.type === "MarcaTexto") {
                context.globalAlpha = temporary ? 0.3 : 0.38;
                context.lineWidth = shape.thick * 4;
            }
            drawSmoothStroke(context, shape.points);
        }
    } else if (shape.type === "Cobrir") {
        drawCoveredArea(context, shape);
    } else if (shape.type === "Cortar") {
        drawCropPreview(context, shape);
    } else if (shape.type === "Texto") {
        drawTextBox(context, shape);
    } else if (shape.type === "Balao") {
        drawBalloonBadge(context, shape);
    } else if (shape.type === "Revisao") {
        drawReviewMarker(context, shape);
    }

    context.restore();
    if (selected) drawSelection(shape);
}

function drawCropPreview(context, shape) {
    const rect = normalizedRect(shape);
    context.save();
    context.strokeStyle = shape.color || "#107C41";
    context.lineWidth = Math.max(2, shape.thick || 2);
    context.setLineDash([8, 5]);
    context.strokeRect(rect.x, rect.y, rect.w, rect.h);
    context.fillStyle = "rgba(16, 124, 65, 0.08)";
    context.fillRect(rect.x, rect.y, rect.w, rect.h);
    context.restore();
}

function drawArrow(context, x1, y1, x2, y2, thickness, markerSize = 0) {
    // A ponta acompanha o tamanho escolhido na faixa ("Ponta"); sem valor
    // gravado, cai no comportamento antigo, ligado só à espessura.
    const head = Number(markerSize) > 0
        ? Math.max(3, Number(markerSize) * 0.72 + thickness * 0.6)
        : 12 + thickness * 2;
    const halfWidth = Math.max(5, head * 0.42);
    const angle = Math.atan2(y2 - y1, x2 - x1);
    const baseX = x2 - head * Math.cos(angle);
    const baseY = y2 - head * Math.sin(angle);
    const perpX = Math.cos(angle + Math.PI / 2) * halfWidth;
    const perpY = Math.sin(angle + Math.PI / 2) * halfWidth;

    context.beginPath();
    context.moveTo(x1, y1);
    context.lineTo(baseX, baseY);
    context.stroke();

    context.beginPath();
    context.moveTo(x2, y2);
    context.lineTo(baseX + perpX, baseY + perpY);
    context.lineTo(baseX - perpX, baseY - perpY);
    context.closePath();
    context.fillStyle = context.strokeStyle;
    context.fill();
}

function annotationFont(shape) {
    return `${shape.italic ? "italic " : ""}${shape.bold ? "bold " : ""}${shape.font}px 'Segoe UI'`;
}

function labelPointForShape(shape) {
    if (shape.type === "CotaLivre") {
        return {x: shape.x + shape.w / 2, y: shape.y + shape.h / 2 - shape.font * 1.8};
    }
    if (shape.type === "CotaAngulo") {
        const endAngle = Math.atan2(shape.h, shape.w);
        const radius = Math.max(40, Math.hypot(shape.w, shape.h) * 0.62 + shape.font);
        return {
            x: shape.x + Math.cos(endAngle / 2) * radius,
            y: shape.y + Math.sin(endAngle / 2) * radius
        };
    }
    if (shape.type === "Chamada") {
        const rect = calloutTextRect(shape);
        return {x: rect.dir > 0 ? rect.x : rect.x + rect.w, y: rect.y};
    }
    return {x: shape.x + shape.w, y: shape.y + shape.h};
}

// Medidas repetidas da cota livre num lugar só: o desenho, as alças e os
// limites da seleção usam exatamente a mesma conta.
function dimensionInfo(shape) {
    const dx = shape.w || 0;
    const dy = shape.h || 0;
    const angle = Math.atan2(dy, dx);
    const perp = angle + Math.PI / 2;
    const value = Number(shape.extension);
    return {
        dx, dy, angle,
        endX: shape.x + dx,
        endY: shape.y + dy,
        midX: shape.x + dx / 2,
        midY: shape.y + dy / 2,
        perpX: Math.cos(perp),
        perpY: Math.sin(perp),
        extension: Number.isFinite(value) ? value : DEFAULT_DIM_EXTENSION
    };
}

function drawFreeDimension(context, shape) {
    const info = dimensionInfo(shape);
    const angle = info.angle;
    const endX = info.endX;
    const endY = info.endY;
    const midX = info.midX;
    const midY = info.midY;
    const tickLen = 10 + (shape.thick || 4);
    const perpX = info.perpX;
    const perpY = info.perpY;
    const extension = info.extension;

    context.beginPath();
    context.moveTo(shape.x, shape.y);
    context.lineTo(endX, endY);
    context.stroke();

    drawDimensionTriangle(context, shape.x, shape.y, angle, 1, shape.thick);
    drawDimensionTriangle(context, endX, endY, angle, -1, shape.thick);

    [0, 1].forEach(which => {
        const px = which ? endX : shape.x;
        const py = which ? endY : shape.y;
        context.beginPath();
        if (Math.abs(extension) > 1) {
            const direction = Math.sign(extension);
            context.moveTo(px - perpX * direction * tickLen / 2, py - perpY * direction * tickLen / 2);
            context.lineTo(px + perpX * extension, py + perpY * extension);
        } else {
            context.moveTo(px - perpX * tickLen / 2, py - perpY * tickLen / 2);
            context.lineTo(px + perpX * tickLen / 2, py + perpY * tickLen / 2);
        }
        context.stroke();
    });

    if (shape.text) {
        context.save();
        context.translate(midX, midY);
        let textAngle = angle;
        if (textAngle > Math.PI / 2 || textAngle < -Math.PI / 2) textAngle += Math.PI;
        context.rotate(textAngle);
        context.font = annotationFont(shape);
        context.textAlign = "center";
        context.textBaseline = "bottom";
        context.fillStyle = shape.color;
        context.fillText(shape.text, 0, -(shape.thick || 4) - 3);
        context.restore();
    }
}

function drawDimensionTriangle(context, x, y, angle, direction, thickness) {
    const length = 10 + Math.max(0, Number(thickness || 0)) * 1.4;
    const width = Math.max(7, length * 0.72);
    const tipX = x;
    const tipY = y;
    const baseX = x + Math.cos(angle) * direction * length;
    const baseY = y + Math.sin(angle) * direction * length;
    const perpX = Math.cos(angle + Math.PI / 2) * width / 2;
    const perpY = Math.sin(angle + Math.PI / 2) * width / 2;

    context.save();
    context.beginPath();
    context.moveTo(tipX, tipY);
    context.lineTo(baseX + perpX, baseY + perpY);
    context.lineTo(baseX - perpX, baseY - perpY);
    context.closePath();
    context.fillStyle = context.strokeStyle;
    context.fill();
    context.restore();
}

function drawAngleDimension(context, shape) {
    const dx = shape.w;
    const dy = shape.h;
    const radius = Math.hypot(dx, dy);
    if (radius < 8) return;
    const endAngle = Math.atan2(dy, dx);
    const arcRadius = radius * 0.6;

    context.beginPath();
    context.moveTo(shape.x, shape.y);
    context.lineTo(shape.x + radius, shape.y);
    context.moveTo(shape.x, shape.y);
    context.lineTo(shape.x + dx, shape.y + dy);
    context.stroke();

    context.beginPath();
    context.arc(shape.x, shape.y, arcRadius, 0, endAngle, endAngle < 0);
    context.stroke();

    if (shape.text) {
        const midAngle = endAngle / 2;
        const textRadius = arcRadius + shape.font / 2 + 8;
        context.font = annotationFont(shape);
        context.textAlign = "center";
        context.textBaseline = "middle";
        context.fillStyle = shape.color;
        context.fillText(
            shape.text,
            shape.x + Math.cos(midAngle) * textRadius,
            shape.y + Math.sin(midAngle) * textRadius
        );
    }
}

// O "pé" horizontal da chamada (onde o texto se apoia) cresce com a fonte,
// como no Notas de Engenharia: a marcação inteira escala junto.
function calloutLanding(shape) {
    return Math.max(16, (Number(shape.font) || 24) * 1.1);
}

// Contexto só para medir texto fora do desenho (limites e teste de clique).
let measureContext = null;

function measuringContext() {
    if (!measureContext) {
        const surface = document.createElement("canvas");
        surface.width = 1;
        surface.height = 1;
        measureContext = surface.getContext("2d");
    }
    return measureContext;
}

function calloutTextWidth(shape) {
    // Largura inicial larga o bastante para uma frase caber em poucas linhas;
    // a partir daí quem manda é a borda arrastada pelo usuário.
    return Math.max(40, Number(shape.textW) || Math.max(240, (Number(shape.font) || 24) * 9));
}

// A chamada só passa a encolher o texto depois que a altura dela foi fixada à
// mão (alça de cima ou de baixo). O autoajuste geral da ferramenta Texto não
// vale aqui: sem altura gravada não existe espaço para caber, e a fonte pedida
// acabava reduzida até o mínimo — a chamada saía com letra minúscula.
function calloutFixedHeight(shape) {
    return shape.autoHeight === false && Number(shape.textH) > 0;
}

// O texto da chamada usa a mesma máquina da ferramenta Texto: reflui na largura
// da caixa e, quando a altura é fixada à mão, diminui até caber nela.
function calloutTextLayout(context, shape) {
    return textBoxLayout(context, {
        text: shape.text || "",
        w: calloutTextWidth(shape),
        h: Number(shape.textH) || 0,
        font: shape.font,
        bold: shape.bold,
        italic: shape.italic,
        autoHeight: !calloutFixedHeight(shape)
    });
}

// A caixa fica encostada no fim do "pé", centrada nele na vertical.
function calloutTextRect(shape, layout = null) {
    const measured = layout || calloutTextLayout(measuringContext(), shape);
    const dir = shape.w >= 0 ? 1 : -1;
    const width = calloutTextWidth(shape);
    const height = calloutFixedHeight(shape)
        ? Math.max(measured.size * 1.4, Number(shape.textH) || 0)
        : measured.height;
    const endX = shape.x + (shape.w || 0);
    const endY = shape.y + (shape.h || 0);
    const offset = calloutLanding(shape) + 6;
    return {
        x: dir > 0 ? endX + offset : endX - offset - width,
        y: endY - height / 2,
        w: width,
        h: height,
        dir
    };
}

function drawCallout(context, shape) {
    const endX = shape.x + shape.w;
    const endY = shape.y + shape.h;
    const dir = shape.w >= 0 ? 1 : -1;
    const landing = calloutLanding(shape);

    drawArrow(context, endX, endY, shape.x, shape.y, shape.thick, shape.font);
    context.beginPath();
    context.moveTo(endX, endY);
    context.lineTo(endX + landing * dir, endY);
    context.stroke();

    if (!shape.text) return;
    const layout = calloutTextLayout(context, shape);
    const rect = calloutTextRect(shape, layout);
    context.save();
    context.textAlign = dir > 0 ? "left" : "right";
    context.textBaseline = "top";
    context.fillStyle = shape.color;
    context.beginPath();
    // Mesmo numa caixa apertada o texto não some: o recorte cresce se o conteúdo
    // ainda passar da altura depois de reduzido até o limite.
    context.rect(rect.x, rect.y, rect.w, Math.max(rect.h, layout.height));
    context.clip();
    const baseX = dir > 0 ? rect.x : rect.x + rect.w;
    layout.lines.forEach((line, index) => {
        const y = rect.y + 4 + index * layout.lineHeight;
        context.fillText(line, baseX, y);
        if (shape.underline) {
            const width = context.measureText(line).width;
            context.beginPath();
            context.lineWidth = Math.max(1, layout.size / 14);
            context.moveTo(dir > 0 ? baseX : baseX - width, y + layout.size * 1.05);
            context.lineTo(dir > 0 ? baseX + width : baseX, y + layout.size * 1.05);
            context.stroke();
        }
    });
    context.restore();
}

// Arrastar a borda da caixa: os lados refluem o texto, o topo e a base fixam a
// altura e passam a reduzir a fonte (igual à ferramenta Texto).
function resizeCalloutText(shape, corner, point) {
    const rect = calloutTextRect(shape);
    if (corner.includes("e") || corner.includes("w")) {
        const borda = rect.dir > 0 ? point.x - rect.x : rect.x + rect.w - point.x;
        shape.textW = Math.max(40, borda);
    }
    if (corner.includes("n") || corner.includes("s")) {
        shape.autoHeight = false;
        shape.textH = Math.max(16, Math.abs(point.y - (rect.y + rect.h / 2)) * 2);
    }
}

function rectHandlePoints(rect) {
    const midX = rect.x + rect.w / 2;
    const midY = rect.y + rect.h / 2;
    const right = rect.x + rect.w;
    const bottom = rect.y + rect.h;
    return [
        {code: "nw", x: rect.x, y: rect.y},
        {code: "n", x: midX, y: rect.y},
        {code: "ne", x: right, y: rect.y},
        {code: "e", x: right, y: midY},
        {code: "se", x: right, y: bottom},
        {code: "s", x: midX, y: bottom},
        {code: "sw", x: rect.x, y: bottom},
        {code: "w", x: rect.x, y: midY}
    ];
}

function cloudRadius(shape) {
    return Number(shape && shape.font) > 0 ? Number(shape.font) : CLOUD_DEFAULT_RADIUS;
}

function drawCloudBox(context, startX, startY, width, height, chosenRadius) {
    const x = Math.min(startX, startX + width);
    const y = Math.min(startY, startY + height);
    const w = Math.abs(width);
    const h = Math.abs(height);
    if (w < 10 || h < 10) {
        context.strokeRect(x, y, w, h);
        return;
    }
    // O raio vem do campo "Raio" da faixa, mas nunca passa da metade do lado
    // menor: senão o festonado engoliria a própria nuvem.
    const radius = Number(chosenRadius) > 0
        ? Math.max(3, Math.min(Number(chosenRadius), Math.min(w, h) / 2))
        : Math.max(6, Math.min(12, Math.min(w, h) / 4));
    const stepsX = Math.max(1, Math.ceil(w / (radius * 2)));
    const stepsY = Math.max(1, Math.ceil(h / (radius * 2)));
    const stepW = w / stepsX;
    const stepH = h / stepsY;
    context.beginPath();
    context.moveTo(x, y);
    for (let i = 0; i < stepsX; i++) context.quadraticCurveTo(x + i * stepW + stepW / 2, y - radius, x + (i + 1) * stepW, y);
    for (let i = 0; i < stepsY; i++) context.quadraticCurveTo(x + w + radius, y + i * stepH + stepH / 2, x + w, y + (i + 1) * stepH);
    for (let i = 0; i < stepsX; i++) context.quadraticCurveTo(x + w - i * stepW - stepW / 2, y + h + radius, x + w - (i + 1) * stepW, y + h);
    for (let i = 0; i < stepsY; i++) context.quadraticCurveTo(x - radius, y + h - i * stepH - stepH / 2, x, y + h - (i + 1) * stepH);
    context.stroke();
}

// Reamostra o traço livre em passos iguais: cada passo vira um festão. Se o
// traço fechar perto de onde começou, o primeiro ponto entra de novo no fim
// para o laço voltar ao começo.
function resamplePath(points, step, closed) {
    const path = points.slice();
    if (closed) {
        const first = path[0];
        const last = path[path.length - 1];
        if (first.x !== last.x || first.y !== last.y) path.push({x: first.x, y: first.y});
    }
    let total = 0;
    for (let i = 1; i < path.length; i++) total += Math.hypot(path[i].x - path[i-1].x, path[i].y - path[i-1].y);
    if (total <= 0) return [];
    const count = Math.max(closed ? 6 : 2, Math.round(total / step));
    const spacing = total / count;
    const out = [path[0]];
    let segment = 1;
    let walked = 0;
    for (let i = 1; i < count; i++) {
        let remaining = spacing;
        while (segment < path.length) {
            const a = path[segment - 1];
            const b = path[segment];
            const length = Math.hypot(b.x - a.x, b.y - a.y);
            if (walked + remaining <= length) {
                walked += remaining;
                const t = length ? walked / length : 0;
                out.push({x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t});
                remaining = 0;
                break;
            }
            remaining -= (length - walked);
            walked = 0;
            segment++;
        }
        if (remaining > 0) break;
    }
    if (!closed) out.push(path[path.length - 1]);
    return out;
}

// Terminou o traço perto de onde começou? Então a nuvem fecha. A tolerância sai
// do tamanho do próprio traço, não do raio, para o festonado não abrir ou fechar
// a figura quando o raio muda.
function freeCloudIsClosed(points) {
    if (points.length < 4) return false;
    const xs = points.map(point => point.x);
    const ys = points.map(point => point.y);
    const diagonal = Math.hypot(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
    const tolerance = Math.max(12, diagonal * 0.12);
    const last = points[points.length - 1];
    return Math.hypot(last.x - points[0].x, last.y - points[0].y) <= tolerance;
}

function drawFreeCloud(context, points, chosenRadius) {
    if (!Array.isArray(points) || points.length < 3) {
        drawSmoothStroke(context, points || []);
        return;
    }
    const radius = Math.max(3, chosenRadius || CLOUD_DEFAULT_RADIUS);
    const closed = freeCloudIsClosed(points);
    const nodes = resamplePath(points, radius * 2, closed);
    if (nodes.length < (closed ? 3 : 2)) {
        drawSmoothStroke(context, points);
        return;
    }
    // Contorno fechado: o sinal da área (fórmula do laço) diz onde é o "fora".
    // Traço aberto: todos os festões estufam para o mesmo lado do risco.
    let outward = 1;
    if (closed) {
        let area = 0;
        for (let i = 0; i < nodes.length; i++) {
            const a = nodes[i];
            const b = nodes[(i + 1) % nodes.length];
            area += a.x * b.y - b.x * a.y;
        }
        outward = area > 0 ? 1 : -1;
    }
    const arcs = closed ? nodes.length : nodes.length - 1;
    context.beginPath();
    context.moveTo(nodes[0].x, nodes[0].y);
    for (let i = 0; i < arcs; i++) {
        const a = nodes[i];
        const b = nodes[(i + 1) % nodes.length];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const length = Math.hypot(dx, dy) || 1;
        const bulge = radius * 1.35;
        context.quadraticCurveTo(
            (a.x + b.x) / 2 + (dy / length) * bulge * outward,
            (a.y + b.y) / 2 + (-dx / length) * bulge * outward,
            b.x, b.y
        );
    }
    if (closed) context.closePath();
    context.stroke();
}

function normalizedRect(shape) {
    return {
        x: Math.min(shape.x, shape.x + (shape.w || 0)),
        y: Math.min(shape.y, shape.y + (shape.h || 0)),
        w: Math.abs(shape.w || 0),
        h: Math.abs(shape.h || 0)
    };
}

function cropToShape(shape) {
    const rect = normalizedRect(shape);
    rect.x = Math.max(0, Math.floor(rect.x));
    rect.y = Math.max(0, Math.floor(rect.y));
    rect.w = Math.min(docWidth - rect.x, Math.floor(rect.w));
    rect.h = Math.min(docHeight - rect.y, Math.floor(rect.h));
    if (rect.w < 12 || rect.h < 12) {
        redraw();
        return setStatus("Área de corte muito pequena.");
    }
    pushHistory();
    if (workspaceMode === "edition") {
        cropEdition(rect);
    } else {
        cropHome(rect);
    }
}

function cropHome(rect) {
    if (!bgImage) return;
    const temp = document.createElement("canvas");
    temp.width = rect.w;
    temp.height = rect.h;
    const tempCtx = temp.getContext("2d");
    tempCtx.drawImage(bgImage, rect.x, rect.y, rect.w, rect.h, 0, 0, rect.w, rect.h);
    const image = new Image();
    image.onload = () => {
        bgImage = image;
        homeBgImage = image;
        docWidth = rect.w;
        docHeight = rect.h;
        annotations.forEach(annotation => shiftAnnotation(annotation, -rect.x, -rect.y));
        selectedIndex = -1;
        fitToWorkspace();
        redraw();
        setStatus("Imagem cortada.");
        scheduleClipboardSync();
    };
    image.src = temp.toDataURL("image/png");
}

function cropEdition(rect) {
    editionItems.forEach(item => {
        item.x -= rect.x;
        item.y -= rect.y;
    });
    annotations.forEach(annotation => shiftAnnotation(annotation, -rect.x, -rect.y));
    editionCanvasSize = {width: rect.w, height: rect.h};
    selectedEditionItemIndex = -1;
    selectedIndex = -1;
    ensureEditionCanvas();
    fitToWorkspace();
    redraw();
    setStatus("Edição cortada.");
    scheduleClipboardSync();
}

function shiftAnnotation(shape, dx, dy) {
    if (isPointShape(shape) && Array.isArray(shape.points)) {
        shape.points.forEach(point => {
            point.x += dx;
            point.y += dy;
        });
        invalidateShapeBounds(shape);
        return;
    }
    shape.x += dx;
    shape.y += dy;
}

let coverSnapshotCanvas = null;
let coverSnapshotCtx = null;
let coverSourceCanvas = null;
let coverSourceCtx = null;

function paintCoverSource(target, sx, sy, sw, sh, width, height) {
    // Redesenha, em miniatura, só o que existe embaixo da área coberta: a
    // imagem de fundo na aba principal, as imagens da guia Edição.
    target.save();
    target.setTransform(width / sw, 0, 0, height / sh, -sx * width / sw, -sy * height / sh);
    target.imageSmoothingEnabled = true;
    target.imageSmoothingQuality = "low";
    target.fillStyle = "#FFFFFF";
    target.fillRect(sx, sy, sw, sh);
    if (workspaceMode === "edition") {
        editionItems.forEach(item => {
            if (!item.image) return;
            if (item.x > sx + sw || item.x + item.w < sx) return;
            if (item.y > sy + sh || item.y + item.h < sy) return;
            target.drawImage(item.image, item.x, item.y, item.w, item.h);
        });
    } else if (bgImage) {
        target.drawImage(bgImage, sx, sy, sw, sh, sx, sy, sw, sh);
    }
    // O véu claro entra aqui, na miniatura (poucos milhares de pixels). Pintar
    // um retângulo translúcido direto no canvas grande custava ~19 ms por
    // quadro nesta janela, que faz toda a composição por software.
    target.fillStyle = "rgba(255,255,255,0.25)";
    target.fillRect(sx, sy, sw, sh);
    target.restore();
}

function drawCoveredArea(context, shape) {
    const rect = normalizedRect(shape);
    if (rect.w < 1 || rect.h < 1) return;
    // O desfoque sai de uma miniatura do conteúdo de baixo, ampliada de volta.
    // Foi assim que a lentidão desta região saiu (tudo medido nesta janela, que
    // compõe por software): a miniatura é montada a partir das imagens de
    // origem, a ampliação usa reamostragem simples ("high" custava ~70 ms por
    // quadro), o véu translúcido é pintado na miniatura (~19 ms por quadro se
    // pintado aqui) e o retângulo exato sai da própria miniatura, sem recorte.
    // O borrão gaussiano continua existindo, só que aplicado na miniatura, onde
    // custa quase nada.
    const factor = isDrawing ? 16 : 12;
    const padding = factor * 3;
    const sx = Math.max(0, Math.floor(rect.x - padding));
    const sy = Math.max(0, Math.floor(rect.y - padding));
    const sw = Math.min(docWidth - sx, Math.ceil(rect.w + padding * 2));
    const sh = Math.min(docHeight - sy, Math.ceil(rect.h + padding * 2));
    if (sw < 1 || sh < 1) return;
    if (!coverSnapshotCanvas) {
        coverSnapshotCanvas = document.createElement("canvas");
        coverSnapshotCtx = coverSnapshotCanvas.getContext("2d");
        coverSourceCanvas = document.createElement("canvas");
        coverSourceCtx = coverSourceCanvas.getContext("2d");
    }
    const width = Math.max(1, Math.round(sw / factor));
    const height = Math.max(1, Math.round(sh / factor));
    [coverSourceCanvas, coverSnapshotCanvas].forEach(target => {
        if (target.width !== width) target.width = width;
        if (target.height !== height) target.height = height;
    });
    coverSourceCtx.clearRect(0, 0, width, height);
    paintCoverSource(coverSourceCtx, sx, sy, sw, sh, width, height);
    coverSnapshotCtx.clearRect(0, 0, width, height);
    coverSnapshotCtx.filter = "blur(1.4px)";
    coverSnapshotCtx.drawImage(coverSourceCanvas, 0, 0);
    coverSnapshotCtx.filter = "none";

    const scaleX = width / sw;
    const scaleY = height / sh;
    context.save();
    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = "low";
    context.drawImage(
        coverSnapshotCanvas,
        (rect.x - sx) * scaleX, (rect.y - sy) * scaleY, rect.w * scaleX, rect.h * scaleY,
        rect.x, rect.y, rect.w, rect.h
    );
    context.restore();
}

// Caixa de texto no comportamento do PowerPoint: o texto sempre reflui na
// largura da caixa. Com o autoajuste ligado a caixa cresce em altura para caber
// o texto; depois de arrastar uma alça de cima ou de baixo o autoajuste desliga
// e passa a ser o texto que diminui até caber na altura escolhida.
function textBoxLayout(context, shape) {
    const nominal = Math.max(6, Number(shape.font) || 28);
    const width = Math.max(20, Math.abs(shape.w || 0) - 8);
    const style = `${shape.italic ? "italic " : ""}${shape.bold ? "bold " : ""}`;
    const measure = size => {
        context.font = `${style}${size}px 'Segoe UI'`;
        return wrapText(context, shape.text, width);
    };
    let size = nominal;
    let lines = measure(size);
    const room = Math.max(0, (Number(shape.h) || 0) - 8);
    // Sem altura útil gravada não há caixa para caber: reduzir aqui derrubaria o
    // texto até o piso, ignorando o tamanho pedido na faixa.
    if (shape.autoHeight === false && room > 0) {
        const floor = Math.max(6, nominal * 0.25);
        let guard = 0;
        while (size > floor && lines.length * size * 1.22 > room && guard++ < 160) {
            size = Math.max(floor, size - Math.max(0.5, size * 0.06));
            lines = measure(size);
        }
    }
    context.font = `${style}${size}px 'Segoe UI'`;
    return {size, lines, lineHeight: size * 1.22, height: lines.length * size * 1.22 + 8};
}

function drawTextBox(context, shape) {
    const layout = textBoxLayout(context, shape);
    context.textAlign = "left";
    context.textBaseline = "top";
    shape.h = shape.autoHeight === false
        ? Math.max(layout.size * 1.4, Number(shape.h) || 0)
        : Math.max(layout.height, layout.size * 1.4);
    context.save();
    context.beginPath();
    // Mesmo numa caixa apertada o texto não some: o recorte cresce se o conteúdo
    // ainda passar da altura depois de reduzido até o limite.
    context.rect(shape.x, shape.y, shape.w, Math.max(shape.h, layout.height));
    context.clip();
    layout.lines.forEach((line, index) => {
        const y = shape.y + 4 + index * layout.lineHeight;
        context.fillText(line, shape.x + 4, y);
        if (shape.underline) {
            context.beginPath();
            context.lineWidth = Math.max(1, layout.size / 14);
            context.moveTo(shape.x + 4, y + layout.size * 1.05);
            context.lineTo(shape.x + 4 + context.measureText(line).width, y + layout.size * 1.05);
            context.stroke();
        }
    });
    context.restore();
}

function wrapText(context, text, maxWidth) {
    const lines = [];
    String(text).split("\n").forEach(paragraph => {
        const words = paragraph.split(/\s+/).filter(Boolean);
        if (!words.length) return lines.push("");
        let line = words.shift();
        words.forEach(word => {
            const test = `${line} ${word}`;
            if (context.measureText(test).width <= maxWidth) line = test;
            else {
                lines.push(line);
                line = word;
            }
        });
        lines.push(line);
    });
    return lines;
}

function balloonFontSize(shape) {
    return Math.max(6, Math.round((Number(shape.font) || 28) * 0.72));
}

function balloonRadius(shape) {
    const fontSize = balloonFontSize(shape);
    const digits = Math.max(1, String(shape.text || "").length);
    // Piso proporcional à fonte: com um piso fixo não dava para fazer balões
    // pequenos, por menor que fosse o número escolhido na faixa.
    return Math.max(fontSize * 0.9, digits * fontSize * 0.38 + fontSize * 0.6);
}

// Sequência tipo planilha: A -> B, Z -> AA, az -> ba.
function nextAlphaText(text) {
    const upper = text === text.toUpperCase();
    const chars = text.toUpperCase().split("");
    let index = chars.length - 1;
    while (index >= 0) {
        if (chars[index] !== "Z") {
            chars[index] = String.fromCharCode(chars[index].charCodeAt(0) + 1);
            break;
        }
        chars[index] = "A";
        index -= 1;
    }
    if (index < 0) chars.unshift("A");
    const next = chars.join("");
    return upper ? next : next.toLowerCase();
}

// "1" -> "2", "09" -> "10", "A" -> "B", "R1" -> "R2", "Rev A" -> "Rev B".
function nextSequenceText(value) {
    const raw = String(value ?? "").trim();
    if (!raw) return "";
    const numeric = raw.match(/^(.*?)(\d+)$/);
    if (numeric) {
        const next = String(Number(numeric[2]) + 1);
        return numeric[1] + (next.length < numeric[2].length ? next.padStart(numeric[2].length, "0") : next);
    }
    const alpha = raw.match(/^(.*?)([A-Za-z]+)$/);
    if (alpha) return alpha[1] + nextAlphaText(alpha[2]);
    return raw;
}

function balloonBadgePoint(shape) {
    return {
        x: shape.lineBalloon ? shape.x + (shape.w || 0) : shape.x,
        y: shape.lineBalloon ? shape.y + (shape.h || 0) : shape.y
    };
}

function drawBalloonBadge(context, shape) {
    const radius = balloonRadius(shape);
    const fontSize = balloonFontSize(shape);
    const badge = balloonBadgePoint(shape);
    const badgeX = badge.x;
    const badgeY = badge.y;
    if (shape.lineBalloon && (Math.abs(shape.w || 0) > 1 || Math.abs(shape.h || 0) > 1)) {
        // A linha nasce na borda do círculo, não no centro dele: saindo do centro
        // ela atravessava o balão por dentro e encostava no número. Quando o alvo
        // cai dentro do próprio balão não sobra linha para desenhar.
        const rumo = Math.atan2(shape.y - badgeY, shape.x - badgeX);
        const distancia = Math.hypot(shape.x - badgeX, shape.y - badgeY);
        if (distancia > radius + 1) {
            drawArrow(context, badgeX + Math.cos(rumo) * radius, badgeY + Math.sin(rumo) * radius,
                      shape.x, shape.y, shape.thick, fontSize);
        }
    }

    context.beginPath();
    context.arc(badgeX, badgeY, radius, 0, Math.PI * 2);
    if (shape.fillBalloon !== false) {
        context.fillStyle = shape.color;
        context.fill();
        context.fillStyle = "#FFFFFF";
    } else {
        context.lineWidth = Math.max(1.2, shape.thick || 2);
        context.strokeStyle = shape.color;
        context.stroke();
        context.fillStyle = shape.color;
    }
    context.font = `bold ${fontSize}px 'Segoe UI'`;
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(shape.text, badgeX, badgeY + 1);
}

// Piso proporcional (antes fixo em 26): assim o triângulo acompanha de verdade
// o tamanho escolhido na faixa, inclusive nos valores pequenos.
function reviewMarkerSize(shape) {
    return Math.max(8, (Number(shape.font) || 28) * 1.3);
}

function reviewMarkerFontSize(shape) {
    return Math.max(6, Math.round((Number(shape.font) || 28) * 0.56));
}

function reviewMarkerGeometry(shape) {
    const size = reviewMarkerSize(shape);
    const height = size * 0.9;
    return {
        size,
        height,
        topY: shape.y - height * 0.58,
        bottomY: shape.y + height * 0.42,
        leftX: shape.x - size / 2,
        rightX: shape.x + size / 2
    };
}

function drawReviewMarker(context, shape) {
    const geometry = reviewMarkerGeometry(shape);
    const filled = shape.fillReview === true;

    context.save();
    context.beginPath();
    context.moveTo(shape.x, geometry.topY);
    context.lineTo(geometry.rightX, geometry.bottomY);
    context.lineTo(geometry.leftX, geometry.bottomY);
    context.closePath();
    if (filled) {
        context.fillStyle = shape.color;
        context.fill();
    }
    context.lineWidth = Math.max(1.2, shape.thick || 2);
    context.strokeStyle = shape.color;
    context.stroke();
    context.fillStyle = filled ? "#FFFFFF" : shape.color;
    context.font = `${shape.bold === false ? "" : "bold "}${reviewMarkerFontSize(shape)}px 'Segoe UI'`;
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(String(shape.text || "R"), shape.x, shape.y + geometry.height * 0.08);
    context.restore();
}

// Percorrer os pontos de um traço longo custa caro, e a caixa é pedida várias
// vezes por quadro (alças, âncora, teste de clique). O resultado fica guardado
// no próprio objeto; quem mexe nos pontos chama invalidateShapeBounds.
function pointsBounds(shape, pad) {
    const points = shape.points;
    const cache = shape.boundsCache;
    if (cache && cache.list === points && cache.count === points.length && cache.pad === pad) return cache.rect;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (let index = 0; index < points.length; index++) {
        const point = points[index];
        if (point.x < minX) minX = point.x;
        if (point.x > maxX) maxX = point.x;
        if (point.y < minY) minY = point.y;
        if (point.y > maxY) maxY = point.y;
    }
    const rect = {
        x: minX - pad,
        y: minY - pad,
        w: Math.max(1, maxX + pad - (minX - pad)),
        h: Math.max(1, maxY + pad - (minY - pad))
    };
    shape.boundsCache = {list: points, count: points.length, pad, rect};
    return rect;
}

function invalidateShapeBounds(shape) {
    if (shape) shape.boundsCache = null;
}

function annotationBounds(shape) {
    if (shape.type === "Revisao") {
        const geometry = reviewMarkerGeometry(shape);
        return {x: geometry.leftX, y: geometry.topY, w: geometry.size, h: geometry.height};
    }
    if (isFreeCloud(shape) && Array.isArray(shape.points) && shape.points.length) {
        // A nuvem livre estufa para fora do traço: a caixa cresce junto.
        return pointsBounds(shape, cloudRadius(shape) * 1.4);
    }
    if (shape.type === "Balao") {
        const radius = balloonRadius(shape);
        if (shape.lineBalloon) {
            const endX = shape.x + (shape.w || 0);
            const endY = shape.y + (shape.h || 0);
            const x = Math.min(shape.x, endX) - radius;
            const y = Math.min(shape.y, endY) - radius;
            return {x, y, w: Math.abs(endX - shape.x) + radius * 2.3, h: Math.abs(endY - shape.y) + radius * 2.1};
        }
        return {x: shape.x - radius, y: shape.y - radius, w: radius * 2.3, h: radius * 2.05};
    }
    if (shape.type === "Chamada") {
        const base = normalizedRect(shape);
        const rect = calloutTextRect(shape);
        const x1 = Math.min(base.x, rect.x);
        const y1 = Math.min(base.y, rect.y);
        const x2 = Math.max(base.x + base.w, rect.x + rect.w);
        const y2 = Math.max(base.y + base.h, rect.y + rect.h);
        return {x: x1, y: y1, w: Math.max(1, x2 - x1), h: Math.max(1, y2 - y1)};
    }
    if (labelTools.has(shape.type)) {
        let base = normalizedRect(shape);
        if (shape.type === "CotaLivre") {
            const info = dimensionInfo(shape);
            const extX = info.perpX * info.extension;
            const extY = info.perpY * info.extension;
            const xs = [shape.x, info.endX, shape.x + extX, info.endX + extX];
            const ys = [shape.y, info.endY, shape.y + extY, info.endY + extY];
            const x = Math.min(...xs);
            const y = Math.min(...ys);
            base = {x, y, w: Math.max(1, Math.max(...xs) - x), h: Math.max(1, Math.max(...ys) - y)};
        }
        const label = labelPointForShape(shape);
        const textWidth = Math.max(50, String(shape.text || "").length * (shape.font || 18) * 0.65);
        const textHeight = Math.max(20, (shape.font || 18) * 1.3);
        const labelRect = {x: label.x - textWidth / 2, y: label.y - textHeight / 2, w: textWidth, h: textHeight};
        const x1 = Math.min(base.x, labelRect.x);
        const y1 = Math.min(base.y, labelRect.y);
        const x2 = Math.max(base.x + base.w, labelRect.x + labelRect.w);
        const y2 = Math.max(base.y + base.h, labelRect.y + labelRect.h);
        return {x: x1, y: y1, w: Math.max(1, x2 - x1), h: Math.max(1, y2 - y1)};
    }
    if (isPointShape(shape) && Array.isArray(shape.points) && shape.points.length) {
        return pointsBounds(shape, 0);
    }
    return normalizedRect(shape);
}

function drawSelection(shape) {
    const bounds = annotationBounds(shape);
    // Tudo aqui é medido em pixels de tela: com o supersampling e o zoom, as
    // alças precisam manter o mesmo tamanho aparente para continuarem clicáveis.
    const inset = screenUnits(5);
    ctx.save();
    ctx.strokeStyle = "#F2A100";
    ctx.lineWidth = screenUnits(1.6);
    ctx.setLineDash([screenUnits(7), screenUnits(4)]);
    ctx.strokeRect(bounds.x - inset, bounds.y - inset, bounds.w + inset * 2, bounds.h + inset * 2);
    ctx.setLineDash([]);
    if (boxResizeTools.has(shape.type) || strokeResizeTools.has(shape.type) || markerResizeTools.has(shape.type)) {
        drawResizeHandles(boxHandlePoints(shape));
    }
    if (lineResizeTools.has(shape.type)) {
        drawLineHandles(lineEndpointPoints(shape));
    }
    if (shape.type === "Chamada" && shape.text) {
        const rect = calloutTextRect(shape);
        const inset = screenUnits(2);
        ctx.save();
        ctx.strokeStyle = "#F2A100";
        ctx.lineWidth = screenUnits(1);
        ctx.setLineDash([screenUnits(4), screenUnits(3)]);
        ctx.strokeRect(rect.x - inset, rect.y - inset, rect.w + inset * 2, rect.h + inset * 2);
        ctx.restore();
        drawResizeHandles(rectHandlePoints(rect));
    }
    if (shape.type === "CotaLivre") {
        drawDimensionGrips(shape);
    }
    if ((shape.type === "Balao") && shape.lineBalloon) {
        drawBalloonTipGrip(shape);
    }
    ctx.restore();
}

function balloonTipPoint(shape) {
    return {x: shape.x, y: shape.y};
}

function drawBalloonTipGrip(shape) {
    const point = balloonTipPoint(shape);
    ctx.fillStyle = "#F2A100";
    ctx.strokeStyle = "#FFFFFF";
    ctx.lineWidth = screenUnits(1.5);
    ctx.beginPath();
    ctx.arc(point.x, point.y, screenUnits(5.5), 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
}

function findBalloonTipGrip(shape, x, y) {
    if (!shape.lineBalloon || shape.type !== "Balao") return false;
    const point = balloonTipPoint(shape);
    return Math.hypot(x - point.x, y - point.y) <= screenUnits(13);
}

function moveBalloonTip(shape, point) {
    const badge = balloonBadgePoint(shape);
    shape.x = point.x;
    shape.y = point.y;
    shape.w = badge.x - point.x;
    shape.h = badge.y - point.y;
}

// As alças da extensão ficam na ponta das linhas de chamada da cota, longe das
// alças redondas das extremidades: uma muda o afastamento, a outra o tamanho.
function dimensionGripPoints(shape) {
    const info = dimensionInfo(shape);
    return [
        {x: shape.x + info.perpX * info.extension, y: shape.y + info.perpY * info.extension},
        {x: info.endX + info.perpX * info.extension, y: info.endY + info.perpY * info.extension}
    ];
}

function dimensionLabelBounds(shape) {
    const label = labelPointForShape(shape);
    const font = Number(shape.font) || 18;
    const text = String(shape.text || "000");
    const width = Math.max(42, text.length * font * 0.65);
    const height = Math.max(20, font * 1.35);
    return {x: label.x - width / 2, y: label.y - height / 2, w: width, h: height};
}

function drawDimensionGrips(shape) {
    const size = screenUnits(10);
    ctx.fillStyle = "#F2A100";
    ctx.strokeStyle = "#FFFFFF";
    ctx.lineWidth = screenUnits(1.5);
    dimensionGripPoints(shape).forEach(point => {
        ctx.beginPath();
        ctx.rect(point.x - size / 2, point.y - size / 2, size, size);
        ctx.fill();
        ctx.stroke();
    });
}

function findDimensionGrip(shape, x, y) {
    if (shape.type !== "CotaLivre") return -1;
    const tolerance = screenUnits(12);
    const index = dimensionGripPoints(shape).findIndex(point => Math.abs(x - point.x) <= tolerance && Math.abs(y - point.y) <= tolerance);
    if (index >= 0) return index;
    // Arrastar o próprio texto da cota também afasta ou aproxima as chamadas.
    return pointInRect(x, y, dimensionLabelBounds(shape), screenUnits(6)) ? 2 : -1;
}

function extendDimensionCallout(shape, point) {
    // Projeta o cursor na perpendicular da cota, medida a partir do meio: é a
    // distância que as linhas de extensão avançam para fora do risco.
    const info = dimensionInfo(shape);
    const projected = (point.x - info.midX) * info.perpX + (point.y - info.midY) * info.perpY;
    shape.extension = Math.abs(projected) < 2 ? 0 : projected;
}

function dimensionGripCursor(shape) {
    if (!shape) return "ew-resize";
    return Math.abs(shape.w) >= Math.abs(shape.h) ? "ns-resize" : "ew-resize";
}

// --- Alças de redimensionamento estilo PowerPoint -------------------------

function boxHandlePoints(shape) {
    const rect = annotationBounds(shape);
    const midX = rect.x + rect.w / 2;
    const midY = rect.y + rect.h / 2;
    const right = rect.x + rect.w;
    const bottom = rect.y + rect.h;
    return [
        {code: "nw", x: rect.x, y: rect.y},
        {code: "n", x: midX, y: rect.y},
        {code: "ne", x: right, y: rect.y},
        {code: "e", x: right, y: midY},
        {code: "se", x: right, y: bottom},
        {code: "s", x: midX, y: bottom},
        {code: "sw", x: rect.x, y: bottom},
        {code: "w", x: rect.x, y: midY}
    ];
}

function lineEndpointPoints(shape) {
    return [
        {code: "start", x: shape.x, y: shape.y},
        {code: "end", x: shape.x + shape.w, y: shape.y + shape.h}
    ];
}

function resizeBoxShape(shape, corner, point, minSize = 8) {
    const rect = normalizedRect(shape);
    let left = rect.x;
    let top = rect.y;
    let right = rect.x + rect.w;
    let bottom = rect.y + rect.h;
    if (corner.includes("w")) left = point.x;
    if (corner.includes("e")) right = point.x;
    if (corner.includes("n")) top = point.y;
    if (corner.includes("s")) bottom = point.y;
    shape.x = Math.min(left, right);
    shape.y = Math.min(top, bottom);
    shape.w = Math.max(minSize, Math.abs(right - left));
    shape.h = Math.max(minSize, Math.abs(bottom - top));
}

function resizeStrokeShape(shape, corner, point) {
    // Escala os pontos do traço (Caneta/MarcaTexto) a partir do lado oposto.
    if (!Array.isArray(shape.points) || !shape.points.length) return;
    const bounds = annotationBounds(shape);
    const affectX = corner.includes("e") || corner.includes("w");
    const affectY = corner.includes("n") || corner.includes("s");
    const anchorX = corner.includes("w") ? bounds.x + bounds.w : bounds.x;
    const anchorY = corner.includes("n") ? bounds.y + bounds.h : bounds.y;
    const handleX = corner.includes("w") ? bounds.x : bounds.x + bounds.w;
    const handleY = corner.includes("n") ? bounds.y : bounds.y + bounds.h;
    const minScale = 0.05;
    let sx = 1;
    let sy = 1;
    if (affectX && Math.abs(handleX - anchorX) > 0.001) {
        sx = (point.x - anchorX) / (handleX - anchorX);
        if (Math.abs(sx) < minScale) sx = sx < 0 ? -minScale : minScale;
    }
    if (affectY && Math.abs(handleY - anchorY) > 0.001) {
        sy = (point.y - anchorY) / (handleY - anchorY);
        if (Math.abs(sy) < minScale) sy = sy < 0 ? -minScale : minScale;
    }
    shape.points.forEach(p => {
        if (affectX) p.x = anchorX + (p.x - anchorX) * sx;
        if (affectY) p.y = anchorY + (p.y - anchorY) * sy;
    });
    invalidateShapeBounds(shape);
}

function resizeCircleCorner(shape, corner, point) {
    // Alças de canto mantêm o círculo (largura = altura), ancorando no canto oposto.
    const rect = normalizedRect(shape);
    const anchorX = corner.includes("w") ? rect.x + rect.w : rect.x;
    const anchorY = corner.includes("n") ? rect.y + rect.h : rect.y;
    const dx = point.x - anchorX;
    const dy = point.y - anchorY;
    const side = Math.max(8, Math.abs(dx), Math.abs(dy));
    const x2 = anchorX + (dx < 0 ? -1 : 1) * side;
    const y2 = anchorY + (dy < 0 ? -1 : 1) * side;
    shape.x = Math.min(anchorX, x2);
    shape.y = Math.min(anchorY, y2);
    shape.w = side;
    shape.h = side;
}

function resizeLineShape(shape, corner, point) {
    // A outra ponta é o ponto fixo: é dela que sai a horizontal e a vertical.
    point = corner === "start"
        ? applyAxisSnap(shape.type, {x: shape.x + (shape.w || 0), y: shape.y + (shape.h || 0)}, point)
        : applyAxisSnap(shape.type, {x: shape.x, y: shape.y}, point);
    if (corner === "start") {
        const endX = shape.x + shape.w;
        const endY = shape.y + shape.h;
        shape.x = point.x;
        shape.y = point.y;
        shape.w = endX - point.x;
        shape.h = endY - point.y;
    } else {
        shape.w = point.x - shape.x;
        shape.h = point.y - shape.y;
    }
}

function drawResizeHandles(points) {
    const size = screenUnits(9);
    ctx.fillStyle = "#FFFFFF";
    ctx.strokeStyle = "#F2A100";
    ctx.lineWidth = screenUnits(1.5);
    points.forEach(point => {
        ctx.beginPath();
        ctx.rect(point.x - size / 2, point.y - size / 2, size, size);
        ctx.fill();
        ctx.stroke();
    });
}

// Pontos redondos nas pontas de linhas/setas/chamadas (estilo PowerPoint),
// para arrastar cada extremidade e mudar o ângulo livremente.
function drawLineHandles(points) {
    ctx.fillStyle = "#FFFFFF";
    ctx.strokeStyle = "#F2A100";
    ctx.lineWidth = screenUnits(1.8);
    points.forEach(point => {
        ctx.beginPath();
        ctx.arc(point.x, point.y, screenUnits(5.5), 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
    });
}

// Escala o balão ou o triângulo de revisão a partir do centro: qualquer uma das
// oito alças serve, como num retângulo.
function resizeMarkerShape(shape, point) {
    if (!markerResizeTools.has(shape.type)) return;
    const center = shape.type === "Balao" ? balloonBadgePoint(shape) : {x: shape.x, y: shape.y};
    const reach = Math.max(Math.abs(point.x - center.x), Math.abs(point.y - center.y));
    const size = clampToolSize(shape.type, reach / (shape.type === "Balao" ? 0.65 : 0.68));
    shape.font = size;
    toolSizes[shape.type] = size;
    byId("cfg-fonte").value = size;
    syncEditionFormatControlsFromMain();
}

function findResizeHandle(shape, x, y) {
    if (boxResizeTools.has(shape.type) || strokeResizeTools.has(shape.type)) {
        const tolerance = screenUnits(9);
        const found = boxHandlePoints(shape).find(point => Math.abs(x - point.x) <= tolerance && Math.abs(y - point.y) <= tolerance);
        if (found) return {handle: "box-resize", corner: found.code};
    } else if (markerResizeTools.has(shape.type)) {
        const tolerance = screenUnits(11);
        const found = boxHandlePoints(shape).find(point => Math.abs(x - point.x) <= tolerance && Math.abs(y - point.y) <= tolerance);
        if (found) return {handle: "marker-resize", corner: found.code};
    }
    if (shape.type === "Chamada" && shape.text) {
        const tolerance = screenUnits(9);
        const found = rectHandlePoints(calloutTextRect(shape))
            .find(point => Math.abs(x - point.x) <= tolerance && Math.abs(y - point.y) <= tolerance);
        if (found) return {handle: "callout-text", corner: found.code};
    }
    if (lineResizeTools.has(shape.type)) {
        const tolerance = screenUnits(13);
        const found = lineEndpointPoints(shape).find(point => Math.abs(x - point.x) <= tolerance && Math.abs(y - point.y) <= tolerance);
        if (found) return {handle: "line-resize", corner: found.code};
    }
    return null;
}

function resizeHandleCursor(corner) {
    if (corner === "start" || corner === "end") return "crosshair";
    if (corner === "nw" || corner === "se") return "nwse-resize";
    if (corner === "ne" || corner === "sw") return "nesw-resize";
    if (corner === "n" || corner === "s") return "ns-resize";
    if (corner === "e" || corner === "w") return "ew-resize";
    return "crosshair";
}

// --- Seleção precisa de marcações sobrepostas -----------------------------
// A caixa que envolve uma seta é enorme e vazia; usá-la para selecionar fazia a
// seta "cobrir" o texto embaixo dela. Aqui o desenho real é testado primeiro
// (acerto exato) e a caixa envolvente só decide quando nada foi tocado.

function distanceToSegment(px, py, x1, y1, x2, y2) {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const lengthSq = dx * dx + dy * dy;
    if (lengthSq < 0.0001) return Math.hypot(px - x1, py - y1);
    let t = ((px - x1) * dx + (py - y1) * dy) / lengthSq;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}

function pointInRect(x, y, rect, padding = 0) {
    return x >= rect.x - padding && x <= rect.x + rect.w + padding
        && y >= rect.y - padding && y <= rect.y + rect.h + padding;
}

function pointNearRectBorder(x, y, rect, tolerance) {
    if (!pointInRect(x, y, rect, tolerance)) return false;
    const inside = x >= rect.x + tolerance && x <= rect.x + rect.w - tolerance
        && y >= rect.y + tolerance && y <= rect.y + rect.h - tolerance;
    return !inside;
}

function pointNearPolyline(points, x, y, tolerance) {
    if (!Array.isArray(points) || !points.length) return false;
    if (points.length === 1) return Math.hypot(x - points[0].x, y - points[0].y) <= tolerance;
    for (let index = 1; index < points.length; index++) {
        const a = points[index - 1];
        const b = points[index];
        if (distanceToSegment(x, y, a.x, a.y, b.x, b.y) <= tolerance) return true;
    }
    return false;
}

function pointNearTriangle(x, y, ax, ay, bx, by, cx, cy, tolerance) {
    const area = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay);
    if (Math.abs(area) > 0.0001) {
        const s = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / area;
        const t = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / area;
        if (s >= 0 && t >= 0 && s + t <= 1) return true;
    }
    return distanceToSegment(x, y, ax, ay, bx, by) <= tolerance
        || distanceToSegment(x, y, bx, by, cx, cy) <= tolerance
        || distanceToSegment(x, y, cx, cy, ax, ay) <= tolerance;
}

function hitTolerance(shape) {
    return Math.max(screenUnits(7), (Number(shape.thick) || 4) * 1.6);
}

function shapeLabelRect(shape) {
    if (!shape.text || !labelTools.has(shape.type)) return null;
    if (shape.type === "Chamada") return calloutTextRect(shape);
    const point = labelPointForShape(shape);
    const width = Math.max(26, String(shape.text).length * (shape.font || 18) * 0.62);
    const height = Math.max(18, (shape.font || 18) * 1.25);
    const left = shape.type === "Chamada" && shape.w >= 0 ? point.x : point.x - width / 2;
    return {x: left, y: point.y - height / 2, w: width, h: height};
}

function shapeHitsPoint(shape, x, y) {
    const tolerance = hitTolerance(shape);
    const label = shapeLabelRect(shape);
    if (label && pointInRect(x, y, label, 4)) return true;
    const endX = shape.x + (shape.w || 0);
    const endY = shape.y + (shape.h || 0);

    switch (shape.type) {
        case "Seta":
        case "Linha":
            return distanceToSegment(x, y, shape.x, shape.y, endX, endY) <= tolerance;
        case "Chamada": {
            const direction = shape.w >= 0 ? 1 : -1;
            const landing = calloutLanding(shape);
            return distanceToSegment(x, y, shape.x, shape.y, endX, endY) <= tolerance
                || distanceToSegment(x, y, endX, endY, endX + landing * direction, endY) <= tolerance;
        }
        case "CotaLivre": {
            if (distanceToSegment(x, y, shape.x, shape.y, endX, endY) <= tolerance) return true;
            const angle = Math.atan2(shape.h, shape.w) + Math.PI / 2;
            const perpX = Math.cos(angle);
            const perpY = Math.sin(angle);
            const reach = Math.max((10 + (shape.thick || 4)) / 2, Math.abs(Number(shape.extension) || 0));
            return [[shape.x, shape.y], [endX, endY]].some(([px, py]) => distanceToSegment(
                x, y, px - perpX * reach, py - perpY * reach, px + perpX * reach, py + perpY * reach
            ) <= tolerance);
        }
        case "CotaAngulo": {
            const radius = Math.hypot(shape.w, shape.h);
            if (distanceToSegment(x, y, shape.x, shape.y, shape.x + radius, shape.y) <= tolerance) return true;
            if (distanceToSegment(x, y, shape.x, shape.y, endX, endY) <= tolerance) return true;
            const arcRadius = radius * 0.6;
            if (Math.abs(Math.hypot(x - shape.x, y - shape.y) - arcRadius) > tolerance) return false;
            const endAngle = Math.atan2(shape.h, shape.w);
            const pointAngle = Math.atan2(y - shape.y, x - shape.x);
            return pointAngle >= Math.min(0, endAngle) - 0.06 && pointAngle <= Math.max(0, endAngle) + 0.06;
        }
        case "Retangulo":
            return pointNearRectBorder(x, y, normalizedRect(shape), tolerance);
        case "Nuvem":
            if (isFreeCloud(shape)) return pointNearPolyline(shape.points, x, y, tolerance + cloudRadius(shape) * 1.4);
            return pointNearRectBorder(x, y, normalizedRect(shape), tolerance + cloudRadius(shape) * 1.4);
        case "Circulo": {
            const rect = normalizedRect(shape);
            const rx = Math.max(1, rect.w / 2);
            const ry = Math.max(1, rect.h / 2);
            const nx = (x - (rect.x + rx)) / rx;
            const ny = (y - (rect.y + ry)) / ry;
            return Math.abs(Math.hypot(nx, ny) - 1) <= tolerance / Math.min(rx, ry);
        }
        case "Caneta":
        case "LinhaOrto":
            return pointNearPolyline(shape.points, x, y, tolerance);
        case "MarcaTexto":
            return pointNearPolyline(shape.points, x, y, Math.max(tolerance, (shape.thick || 4) * 2.4));
        case "Texto":
        case "Cobrir":
        case "Cortar":
            return pointInRect(x, y, normalizedRect(shape), 2);
        case "Balao": {
            const badge = balloonBadgePoint(shape);
            if (Math.hypot(x - badge.x, y - badge.y) <= balloonRadius(shape) + 4) return true;
            return Boolean(shape.lineBalloon)
                && distanceToSegment(x, y, shape.x, shape.y, badge.x, badge.y) <= tolerance;
        }
        case "Revisao": {
            const geometry = reviewMarkerGeometry(shape);
            return pointNearTriangle(
                x, y,
                shape.x, geometry.topY,
                geometry.rightX, geometry.bottomY,
                geometry.leftX, geometry.bottomY,
                tolerance
            );
        }
        default:
            return pointInRect(x, y, annotationBounds(shape), 4);
    }
}

// Folga máxima que algum teste usa nesta marcação. Serve para descartar de
// imediato os traços longe do cursor, sem percorrer ponto a ponto.
function hitPadding(shape) {
    const tolerance = hitTolerance(shape);
    if (shape.type === "MarcaTexto") return Math.max(tolerance, (shape.thick || 4) * 2.4);
    if (shape.type === "Nuvem") return tolerance + cloudRadius(shape) * 1.4;
    return Math.max(tolerance, 8, shape.thick || 4);
}

function collectAnnotationHits(x, y) {
    const exact = [];
    const loose = [];
    for (let index = annotations.length - 1; index >= 0; index--) {
        const shape = annotations[index];
        // Só o traço à mão livre é caro de testar (percorre todos os pontos).
        // Se o cursor está fora da caixa dele, nem vale entrar no teste exato.
        if (isPointShape(shape) && !pointInRect(x, y, annotationBounds(shape), hitPadding(shape))) continue;
        if (shapeHitsPoint(shape, x, y)) {
            exact.push(index);
        } else if (pointInRect(x, y, annotationBounds(shape), Math.max(8, shape.thick || 4))) {
            loose.push(index);
        }
    }
    return exact.concat(loose);
}

function findAnnotationAt(x, y, cycle = false) {
    // As alças da marcação já selecionada vêm sempre em primeiro lugar.
    if (selectedIndex >= 0 && annotations[selectedIndex]) {
        const shape = annotations[selectedIndex];
        if (findBalloonTipGrip(shape, x, y)) return {index: selectedIndex, handle: "balloon-tip"};
        // As alças das pontas vêm antes das alças de extensão: com a extensão
        // em zero as duas ficam no mesmo lugar, e mudar o tamanho é o gesto
        // mais provável.
        const resizeHit = findResizeHandle(shape, x, y);
        if (resizeHit) return {index: selectedIndex, handle: resizeHit.handle, corner: resizeHit.corner};
        const gripIndex = findDimensionGrip(shape, x, y);
        if (gripIndex >= 0) return {index: selectedIndex, handle: "dimension-grip", gripIndex};
    }

    const candidates = collectAnnotationHits(x, y);
    if (!candidates.length) {
        if (cycle) hitCycleState = {x: null, y: null, key: "", position: 0};
        return {index: -1, handle: null};
    }

    let position = 0;
    if (cycle) {
        // Clicar outra vez no mesmo ponto desce um nível: é assim que se alcança
        // o texto que está embaixo da seta, por exemplo.
        const key = candidates.join(",");
        const sameSpot = hitCycleState.x !== null
            && hitCycleState.key === key
            && Math.hypot(x - hitCycleState.x, y - hitCycleState.y) <= 6;
        position = sameSpot ? (hitCycleState.position + 1) % candidates.length : 0;
        hitCycleState = {x, y, key, position};
    }
    return {index: candidates[position], handle: null};
}

function annotationAnchor(shape) {
    if (isPointShape(shape)) {
        const bounds = annotationBounds(shape);
        return {x: bounds.x, y: bounds.y};
    }
    return {x: shape.x, y: shape.y};
}

function moveAnnotation(shape, newX, newY) {
    const anchor = annotationAnchor(shape);
    const dx = newX - anchor.x;
    const dy = newY - anchor.y;
    if (isPointShape(shape) && Array.isArray(shape.points)) {
        shape.points.forEach(point => { point.x += dx; point.y += dy; });
        invalidateShapeBounds(shape);
    } else {
        shape.x += dx;
        shape.y += dy;
    }
}

// --- Histórico de desfazer/refazer ----------------------------------------

function cloneAnnotations(list) {
    return (list || []).map(shape => {
        const copy = {...shape};
        if (Array.isArray(shape.points)) copy.points = shape.points.map(point => ({x: point.x, y: point.y}));
        return copy;
    });
}

function cloneEditionItem(item) {
    // A imagem em si é reaproveitada (mesmo objeto Image); o canvas de pré-visualização
    // usado no arraste não pode ser compartilhado entre cópias, então fica de fora.
    const {proxy, proxyWidth, proxyHeight, ...rest} = item;
    return {...rest};
}

function activeHomeAnnotations() {
    return workspaceMode === "home" ? annotations : homeAnnotations;
}

function activeEditionAnnotations() {
    return workspaceMode === "edition" ? annotations : editionAnnotations;
}

function snapshotState() {
    return {
        homeAnnotations: cloneAnnotations(activeHomeAnnotations()),
        editionAnnotations: cloneAnnotations(activeEditionAnnotations()),
        editionItems: editionItems.map(cloneEditionItem),
        editionCanvasSize: {width: editionCanvasSize.width, height: editionCanvasSize.height},
        bgImage: workspaceMode === "home" ? bgImage : homeBgImage
    };
}

function stateSignature() {
    const shapes = activeHomeAnnotations().concat(activeEditionAnnotations()).map(shape => [
        shape.type,
        Math.round(shape.x || 0), Math.round(shape.y || 0),
        Math.round(shape.w || 0), Math.round(shape.h || 0),
        shape.text || "", shape.color || "", shape.thick || 0, shape.font || 0,
        Math.round(Number(shape.extension) || 0),
        Array.isArray(shape.points)
            ? shape.points.map(point => `${Math.round(point.x)},${Math.round(point.y)}`).join(";")
            : ""
    ].join("|"));
    const items = editionItems.map(item => [
        item.name || "", Math.round(item.x), Math.round(item.y),
        Math.round(item.w), Math.round(item.h)
    ].join("|"));
    return `${shapes.join("\n")}##${items.join("\n")}`;
}

function pushHistory() {
    historyStack.push(snapshotState());
    if (historyStack.length > HISTORY_LIMIT) historyStack.shift();
    redoStack = [];
}

function beginHistoryTransaction() {
    // Guarda o estado antes de mover/redimensionar; só entra no histórico se
    // algo realmente mudou (um clique que apenas seleciona não vira "desfazer").
    pendingHistorySnapshot = snapshotState();
    pendingHistorySignature = stateSignature();
}

function commitHistoryTransaction() {
    if (!pendingHistorySnapshot) return;
    const snapshot = pendingHistorySnapshot;
    pendingHistorySnapshot = null;
    if (stateSignature() === pendingHistorySignature) return;
    hitCycleState = {x: null, y: null, key: "", position: 0};
    historyStack.push(snapshot);
    if (historyStack.length > HISTORY_LIMIT) historyStack.shift();
    redoStack = [];
}

function restoreState(state) {
    homeAnnotations = cloneAnnotations(state.homeAnnotations);
    editionAnnotations = cloneAnnotations(state.editionAnnotations);
    editionItems = state.editionItems.map(cloneEditionItem);
    editionCanvasSize = {width: state.editionCanvasSize.width, height: state.editionCanvasSize.height};
    homeBgImage = state.bgImage;
    selectedIndex = -1;
    selectedEditionItemIndex = -1;
    interactionMode = null;
    isDrawing = false;
    preview = null;
    startPoint = null;
    clearStroke();
    if (workspaceMode === "edition") {
        annotations = editionAnnotations;
        ensureEditionCanvas();
    } else {
        annotations = homeAnnotations;
        bgImage = homeBgImage;
        if (bgImage) {
            docWidth = bgImage.naturalWidth || bgImage.width;
            docHeight = bgImage.naturalHeight || bgImage.height;
        }
    }
    updateWorkspaceVisibility();
    applyZoom();
    redraw();
}

// --- Copiar e colar elementos (Ctrl+C / Ctrl+V) ---------------------------

function copySelectedElement() {
    if (selectedIndex >= 0 && annotations[selectedIndex]) {
        elementClipboard = {kind: "annotation", data: cloneAnnotations([annotations[selectedIndex]])[0]};
        setStatus("Marcação copiada. Use Ctrl+V para colar.");
        return true;
    }
    if (workspaceMode === "edition" && selectedEditionItemIndex >= 0 && editionItems[selectedEditionItemIndex]) {
        elementClipboard = {kind: "editionItem", data: cloneEditionItem(editionItems[selectedEditionItemIndex])};
        setStatus("Imagem copiada. Use Ctrl+V para colar.");
        return true;
    }
    return false;
}

function pasteCopiedElement() {
    if (!elementClipboard) return false;
    const offset = 24;
    if (elementClipboard.kind === "annotation") {
        if (!ensureImage()) return false;
        pushHistory();
        const copy = cloneAnnotations([elementClipboard.data])[0];
        shiftAnnotation(copy, offset, offset);
        annotations.push(copy);
        // selectTool limpa a seleção, então ele vem antes de marcar a cópia.
        selectTool("Mover", false);
        selectedIndex = annotations.length - 1;
        selectedEditionItemIndex = -1;
        // Colagens seguidas ficam em escada, como no PowerPoint.
        elementClipboard.data = cloneAnnotations([copy])[0];
        redraw();
        setStatus("Marcação colada.");
        scheduleClipboardSync();
        return true;
    }
    if (workspaceMode !== "edition") {
        setStatus("Abra a guia Edição para colar a imagem copiada.");
        return false;
    }
    pushHistory();
    ensureEditionCanvas();
    const source = elementClipboard.data;
    const copy = cloneEditionItem({...source, x: source.x + offset, y: source.y + offset});
    editionItems.push(copy);
    selectedEditionItemIndex = editionItems.length - 1;
    selectedIndex = -1;
    expandEditionCanvasToFit(copy);
    elementClipboard.data = cloneEditionItem(copy);
    updateWorkspaceVisibility();
    applyZoom();
    redraw();
    setStatus("Imagem colada.");
    scheduleClipboardSync();
    return true;
}

function undoAnnotation() {
    // Com o editor de texto aberto, Ctrl+Z desfaz a DIGITAÇÃO, não remove marcações.
    if (activeTextEditor) {
        activeTextEditor.editor.focus();
        document.execCommand("undo");
        return;
    }
    if (!historyStack.length) return setStatus("Não há mais nada para desfazer.");
    redoStack.push(snapshotState());
    if (redoStack.length > HISTORY_LIMIT) redoStack.shift();
    restoreState(historyStack.pop());
    setStatus("Ação desfeita.");
    scheduleClipboardSync();
}

function redoAnnotation() {
    if (activeTextEditor) {
        activeTextEditor.editor.focus();
        document.execCommand("redo");
        return;
    }
    if (!redoStack.length) return setStatus("Não há nada para refazer.");
    historyStack.push(snapshotState());
    if (historyStack.length > HISTORY_LIMIT) historyStack.shift();
    restoreState(redoStack.pop());
    setStatus("Ação refeita.");
    scheduleClipboardSync();
}

function clearAnnotations() {
    pushHistory();
    annotations = [];
    if (workspaceMode === "edition") editionAnnotations = annotations;
    else homeAnnotations = annotations;
    selectedIndex = -1;
    redraw();
    setStatus("Marcações limpas.");
    scheduleClipboardSync();
}

function exportDataUrl(type = "image/png") {
    if (!ensureImage()) return null;
    finishActiveCommand(true);
    // O que é salvo/copiado sai sempre na resolução do documento, num canvas
    // próprio - o canvas visível está no tamanho da tela, que muda com o zoom.
    if (!exportCanvas) {
        exportCanvas = document.createElement("canvas");
        exportCtx = exportCanvas.getContext("2d");
    }
    if (exportCanvas.width !== docWidth) exportCanvas.width = docWidth;
    if (exportCanvas.height !== docHeight) exportCanvas.height = docHeight;

    const oldSelection = selectedIndex;
    const oldEditionSelection = selectedEditionItemIndex;
    const oldContext = ctx;
    const oldPreview = preview;
    selectedIndex = -1;
    selectedEditionItemIndex = -1;
    preview = null;
    // As rotinas de desenho usam "ctx"; durante a exportação ele aponta para o
    // canvas de exportação, na escala 1:1.
    ctx = exportCtx;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    if (workspaceMode === "edition") drawEditionWorkspace();
    else if (bgImage) {
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = "low";
        ctx.clearRect(0, 0, docWidth, docHeight);
        ctx.drawImage(bgImage, 0, 0, docWidth, docHeight);
        annotations.forEach(annotation => drawShape(ctx, annotation, false));
    }
    ctx = oldContext;
    const data = exportCanvas.toDataURL(type, 0.95);
    selectedIndex = oldSelection;
    selectedEditionItemIndex = oldEditionSelection;
    preview = oldPreview;
    redraw();
    return data;
}

function savePng() {
    const data = exportDataUrl();
    if (data && pyBridge) pyBridge.saveImage(data, "png");
}

function saveAs() {
    const data = exportDataUrl();
    if (data && pyBridge) pyBridge.saveImageAs(data, "png");
}

function copyFinalImage(forceWholeImage = false) {
    // Com o editor de texto aberto, Ctrl+C deve copiar o TEXTO selecionado,
    // não fechar o editor para copiar a imagem.
    if (activeTextEditor) {
        const editor = activeTextEditor.editor;
        if (editor.selectionStart !== editor.selectionEnd) {
            editor.focus();
            document.execCommand("copy");
            setStatus("Texto selecionado copiado.");
        }
        return;
    }
    // Com uma marcação/imagem selecionada, Ctrl+C copia esse elemento (cole com
    // Ctrl+V). O botão "Copiar" da faixa continua copiando a imagem inteira.
    if (!forceWholeImage && copySelectedElement()) return;
    const data = exportDataUrl();
    if (data && pyBridge) pyBridge.copyImage(data);
}

function changeZoom(delta) {
    if (!ensureImage()) return;
    finishActiveCommand(true);
    zoomLevel = Math.max(0.1, Math.min(3, zoomLevel + delta));
    applyZoom();
}

function resetZoom() {
    finishActiveCommand(true);
    fitToWorkspace();
}

function fitToWorkspace() {
    if (workspaceMode === "edition") ensureEditionCanvas();
    else if (!bgImage) return;
    const maxWidth = Math.max(200, workspace.clientWidth - 60);
    const maxHeight = Math.max(200, workspace.clientHeight - 60);
    zoomLevel = Math.min(1, maxWidth / docWidth, maxHeight / docHeight);
    applyZoom();
}

function screenPixelRatio() {
    // Com a tela do Windows em 125%/150%, cada pixel do CSS vale mais de um
    // pixel de verdade; sem isto o desenho seria ampliado pelo sistema e o
    // traço voltaria a ficar serrilhado.
    // Acima disso o canvas ainda é rasterizado com sobra (RENDER_OVERSAMPLE) e
    // reduzido pelo navegador: é essa redução que apaga o serrilhado das bordas
    // da caneta, do marca-texto e de todas as marcações.
    const ratio = Number(window.devicePixelRatio) || 1;
    return Math.min(4, Math.max(RENDER_OVERSAMPLE, ratio));
}

function applyZoom() {
    const width = Math.max(1, Math.round(docWidth * zoomLevel));
    const height = Math.max(1, Math.round(docHeight * zoomLevel));
    // O canvas é criado no tamanho exibido (em pixels reais da tela), para o
    // traço nascer já do tamanho certo. Em imagens enormes com zoom alto o teto
    // de memória entra em ação e o bitmap volta a ser ampliado, como antes.
    const ratio = screenPixelRatio();
    const area = width * height * ratio * ratio;
    const limite = area > MAX_RENDER_PIXELS ? Math.sqrt(MAX_RENDER_PIXELS / area) : 1;
    const bufferWidth = Math.max(1, Math.round(width * ratio * limite));
    const bufferHeight = Math.max(1, Math.round(height * ratio * limite));
    if (canvas.width !== bufferWidth || canvas.height !== bufferHeight) {
        canvas.width = bufferWidth;
        canvas.height = bufferHeight;
    }
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    canvasContainer.style.width = `${width}px`;
    canvasContainer.style.height = `${height}px`;
    canvasContainer.style.transform = "none";
    byId("zoom-text").textContent = `${Math.round(zoomLevel * 100)}%`;
    redraw();
}

function handleCtrlWheelZoom(step, clientX = null, clientY = null) {
    if (workspaceMode !== "edition" && !bgImage) return;
    if (Number.isFinite(clientX) && Number.isFinite(clientY)) {
        const target = document.elementFromPoint(clientX, clientY);
        if (!target || !target.closest("#workspace") || target.closest(".floating-zoom")) return;
    }
    changeZoom(step);
}

window.addEventListener("resize", () => {
    if ((bgImage || workspaceMode === "edition") && zoomLevel <= 1) fitToWorkspace();
});

window.addEventListener("wheel", event => {
    if (!event.ctrlKey) return;
    event.preventDefault();
    event.stopPropagation();
    handleCtrlWheelZoom(event.deltaY < 0 ? 0.1 : -0.1, event.clientX, event.clientY);
}, {capture: true, passive: false});

window.addEventListener("keydown", event => {
    if (event.key === "Escape") {
        if (activeFormatPopover) {
            event.preventDefault();
            closeFormatPopover(true);
            return;
        }
        event.preventDefault();
        if (pyBridge && typeof pyBridge.cancelCapture === "function") pyBridge.cancelCapture();
        interruptCommand();
        return;
    }
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
    const key = event.key.toLowerCase();
    if (event.ctrlKey && key === "v") {
        // Elemento copiado com Ctrl+C tem prioridade sobre a imagem da área
        // de transferência do Windows.
        if (elementClipboard) {
            event.preventDefault();
            pasteCopiedElement();
            return;
        }
        if (workspaceMode === "edition") {
            event.preventDefault();
            pasteImageFromClipboard();
            return;
        }
    }
    // Refazer. O desfazer (Ctrl+Z) chega pelo atalho do próprio aplicativo, que
    // consome a tecla — tratá-lo aqui também desfaria duas vezes.
    if (event.ctrlKey && (key === "y" || (key === "z" && event.shiftKey))) {
        event.preventDefault();
        redoAnnotation();
        return;
    }
    if (workspaceMode === "edition" && event.key === "Delete" && selectedEditionItemIndex >= 0) {
        pushHistory();
        editionItems.splice(selectedEditionItemIndex, 1);
        selectedEditionItemIndex = -1;
        redraw();
        setStatus("Imagem removida da edição.");
        scheduleClipboardSync();
        return;
    }
    if (event.key === "Delete" && selectedIndex >= 0) {
        pushHistory();
        annotations.splice(selectedIndex, 1);
        selectedIndex = -1;
        redraw();
        setStatus("Marcação removida.");
        scheduleClipboardSync();
    }
});

initializeDrawingPickers();
initializeGreeting();
initializeBridge();
