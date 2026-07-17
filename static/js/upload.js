// 翻译工具 - JavaScript逻辑
// 注意：languages 变量由 HTML 中的 inline script 提供（服务器端渲染）
/* global languages */

let selectedLanguages = new Set();
let aiModels = [];  // 存储 AI 模型列表（OpenRouter 提供）

// 工具函数：从 redirect_url 中提取 ZIP 文件路径
function extractZipPath(redirectUrl) {
    // redirectUrl 格式: /success?zip_path=/output/xxx.zip
    try {
        const url = new URL(redirectUrl, window.location.origin);
        return url.searchParams.get('zip_path');
    } catch (e) {
        console.error('解析 redirect_url 失败:', e);
        return null;
    }
}

// 工具函数：触发文件下载（不跳转）
function triggerDownload(filePath) {
    const link = document.createElement('a');
    link.href = filePath;
    link.download = ''; // 使用服务器提供的文件名
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// 工具函数：HTML 转义 —— 所有拼进 innerHTML 的不可控字符串（文件名、后端错误、
// ZIP 成员名回传的 warnings）必须先过这里，否则恶意 ZIP 条目名如
// `<img src=x onerror=...>.json` 会在队列 UI 里执行脚本（XSS）。
function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, ch => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[ch]));
}

// Socket.IO 连接
const socket = io.connect("http://" + document.domain + ":" + location.port + "/test", {
    reconnection: true,
    reconnectionAttempts: 10,
    reconnectionDelay: 2000,
});

socket.on("connect", function () {
    console.log("Connected to server");
});

        socket.on("progress", function (data) {
      const progressFill = document.getElementById("progressFill");
      const progressText = document.getElementById("progressText");
      const progressSection = document.getElementById("progressSection");

      progressSection.style.display = "block";
      progressFill.style.width = data.progress + "%";

      // 显示进度百分比和消息
      let displayText = Math.round(data.progress) + "%";
      if (data.message) {
          displayText += " - " + data.message;
      }
      if (data.error) {
          displayText = "❌ " + data.error;
          progressFill.style.background = "linear-gradient(90deg, #ff6b6b, #ee5a52)";
      }

      progressText.innerText = displayText;

      // 新契约：socket progress 事件只更新进度条/状态文本，不再据此判定完成或自动下载。
      // 完成/失败一律以 /translate 的 fetch 响应 JSON 为准（见 translateFile）；
      // 单文件自动下载改由 fetch 结果驱动（见表单提交完成处）。
      // 说明：原先的 `!isProcessing` 分支恒假（表单提交总会先置 isProcessing=true），属死代码，已删除。
  });

// 文件上传处理
const fileUpload = document.querySelector('.file-upload');
const fileInput = document.getElementById('fileInput');
const fileInfo = document.getElementById('fileInfo');

// 拖拽功能
fileUpload.addEventListener('dragover', (e) => {
    e.preventDefault();
    fileUpload.classList.add('dragover');
});

fileUpload.addEventListener('dragleave', () => {
    fileUpload.classList.remove('dragover');
});

fileUpload.addEventListener('drop', async (e) => {
    e.preventDefault();
    fileUpload.classList.remove('dragover');

    // 检查是否有 DataTransferItemList（支持文件夹拖拽）
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
        // 检查是否包含文件夹
        let hasDirectory = false;
        for (const item of e.dataTransfer.items) {
            const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
            if (entry && entry.isDirectory) {
                hasDirectory = true;
                break;
            }
        }

        if (hasDirectory) {
            // 使用异步处理文件夹
            await handleDropItems(e.dataTransfer.items);
        } else {
            // 普通文件，使用原有逻辑
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFileSelection(files);
            }
        }
    } else {
        // 回退到传统方式
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelection(files);
        }
    }
});

// 文件队列管理
let fileQueue = [];
let currentFileIndex = 0;
let isProcessing = false;
let isPaused = false;

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileSelection(e.target.files);
    }
});

// 生成文件唯一标识（基于文件名、大小、修改时间）
function getFileId(file) {
    return `${file.name}_${file.size}_${file.lastModified}`;
}

function handleFileSelection(files) {
    const validTypes = ['.js', '.json', '.zip'];
    const newFiles = [];

    Array.from(files).forEach(file => {
        const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
        if (validTypes.includes(fileExtension)) {
            // 检查是否已存在相同文件（基于文件名、大小、修改时间）
            if (!fileQueue.find(item => getFileId(item.file) === getFileId(file))) {
                newFiles.push({
                    id: Date.now() + Math.random(),
                    file: file,
                    status: 'waiting',  // waiting, processing, completed, failed
                    progress: 0,
                    error: null,
                    result: null,
                    warnings: null,  // 部分语言失败时的警告列表（仍算成功）
                    isZip: fileExtension === '.zip'  // 标记 ZIP 文件
                });
            } else {
                console.log(`文件 "${file.name}" 已在队列中，跳过`);
            }
        } else {
            alert(`文件 "${file.name}" 不是有效的 .js、.json 或 .zip 文件`);
        }
    });

    if (newFiles.length > 0) {
        fileQueue.push(...newFiles);
        updateFileQueueUI();
        updateSubmitButton();
    }
}

function updateFileQueueUI() {
    const queueSection = document.getElementById('fileQueueSection');
    const queueList = document.getElementById('fileQueueList');
    const queueCount = document.getElementById('queueCount');

    if (fileQueue.length === 0) {
        queueSection.style.display = 'none';
        fileInfo.style.display = 'none';
        return;
    }

    queueSection.style.display = 'block';
    queueCount.textContent = `(${fileQueue.length})`;

    // 更新文件列表
    queueList.innerHTML = fileQueue.map((item, index) => {
        const statusClass = `status-${item.status}`;
        const statusText = {
            'waiting': '⏳ 等待中',
            'processing': '⚙️ 翻译中',
            'completed': '✓ 已完成',
            'failed': '✗ 失败'
        }[item.status];

        const icon = {
            'waiting': '<i class="fas fa-clock" style="color: #ffc107;"></i>',
            'processing': '<i class="fas fa-spinner fa-spin" style="color: #007bff;"></i>',
            'completed': '<i class="fas fa-check-circle" style="color: #28a745;"></i>',
            'failed': '<i class="fas fa-times-circle" style="color: #dc3545;"></i>'
        }[item.status];

        // ZIP 文件特殊标记
        const fileTypeIcon = item.isZip
            ? '<i class="fas fa-file-archive" style="color: #6c5ce7; margin-right: 5px;"></i>'
            : '<i class="fas fa-file-code" style="color: #74b9ff; margin-right: 5px;"></i>';
        const fileTypeLabel = item.isZip ? ' <span style="color: #6c5ce7; font-size: 0.8em;">[压缩包]</span>' : '';

        return `
            <div class="queue-item" data-id="${item.id}">
                <div class="queue-item-icon">${icon}</div>
                <div class="queue-item-info">
                    <div class="queue-item-name">${fileTypeIcon}${escapeHtml(item.file.name)}${fileTypeLabel}</div>
                    <div class="queue-item-details">
                        ${(item.file.size / 1024).toFixed(1)} KB
                        ${item.error ? ` • <span style="color: #dc3545;">${escapeHtml(item.error)}</span>` : ''}
                        ${item.result ? ` • <span style="color: #28a745;">翻译完成</span>` : ''}
                        ${item.warnings && item.warnings.length ? ` • <span style="color: #f39c12;">部分语言失败: ${item.warnings.map(escapeHtml).join('；')}</span>` : ''}
                    </div>
                    ${item.status === 'processing' ? `
                        <div class="queue-item-progress">
                            <div class="queue-item-progress-bar" style="width: ${item.progress}%"></div>
                        </div>
                    ` : ''}
                </div>
                <div class="queue-item-status ${statusClass}">${statusText}</div>
                <div class="queue-item-actions">
                    ${item.status === 'completed' && item.result ? `
                        <button class="queue-item-btn btn-download" onclick="downloadFile(${index})">
                            <i class="fas fa-download"></i> 下载
                        </button>
                    ` : ''}
                    ${item.status === 'failed' ? `
                        <button class="queue-item-btn btn-retry" onclick="retryFile(${index})">
                            <i class="fas fa-redo"></i> 重试
                        </button>
                    ` : ''}
                    ${item.status !== 'processing' ? `
                        <button class="queue-item-btn btn-remove" onclick="removeFile(${index})">
                            <i class="fas fa-times"></i>
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');

    // 更新统计信息
    updateQueueStats();

    // 更新简单的文件信息显示
    if (fileQueue.length === 1) {
        fileInfo.innerHTML = `
            <i class="fas fa-file-code"></i>
            <strong>${escapeHtml(fileQueue[0].file.name)}</strong> (${(fileQueue[0].file.size / 1024).toFixed(1)} KB)
        `;
        fileInfo.style.display = 'block';
    } else {
        fileInfo.innerHTML = `
            <i class="fas fa-files"></i>
            已选择 <strong>${fileQueue.length}</strong> 个文件
        `;
        fileInfo.style.display = 'block';
    }
}

function updateQueueStats() {
    const waitingCount = fileQueue.filter(f => f.status === 'waiting').length;
    const processingCount = fileQueue.filter(f => f.status === 'processing').length;
    const completedCount = fileQueue.filter(f => f.status === 'completed').length;
    const failedCount = fileQueue.filter(f => f.status === 'failed').length;

    document.getElementById('waitingCount').textContent = waitingCount;
    document.getElementById('processingCount').textContent = processingCount;
    document.getElementById('completedCount').textContent = completedCount;
    document.getElementById('failedCount').textContent = failedCount;

    // 更新总体进度
    const totalProgress = fileQueue.length > 0
        ? (completedCount / fileQueue.length) * 100
        : 0;
    document.getElementById('queueProgressBar').style.width = totalProgress + '%';
    document.getElementById('queueProgressText').textContent = Math.round(totalProgress) + '%';

    // 更新"下载全部"按钮状态
    const downloadAllBtn = document.getElementById('downloadAllBtn');
    const completedWithResults = fileQueue.filter(f => f.status === 'completed' && f.result).length;
    downloadAllBtn.disabled = completedWithResults === 0;
    if (completedWithResults > 0) {
        downloadAllBtn.title = `下载 ${completedWithResults} 个已完成的文件`;
    }
}

function removeFile(index) {
    fileQueue.splice(index, 1);
    updateFileQueueUI();
    updateSubmitButton();
}

function retryFile(index) {
    fileQueue[index].status = 'waiting';
    fileQueue[index].error = null;
    fileQueue[index].result = null;
    fileQueue[index].warnings = null;
    fileQueue[index].progress = 0;
    updateFileQueueUI();
}

function clearQueue() {
    if (isProcessing) {
        if (!confirm('队列正在处理中，确定要清空吗？')) {
            return;
        }
        isPaused = true;
    }
    fileQueue = [];
    currentFileIndex = 0;
    isProcessing = false;
    updateFileQueueUI();
    updateSubmitButton();
}

// 下载单个文件
function downloadFile(index) {
    const fileItem = fileQueue[index];
    if (fileItem && fileItem.result) {
        // 提取 ZIP 文件路径并直接下载
        const zipPath = extractZipPath(fileItem.result);
        if (zipPath) {
            triggerDownload(zipPath);
        }
    }
}

// 下载所有已完成的文件
function downloadAll() {
    const completedFiles = fileQueue.filter(f => f.status === 'completed' && f.result);

    if (completedFiles.length === 0) {
        alert('没有可下载的文件');
        return;
    }

    // 逐个触发下载，间隔500ms避免浏览器阻止
    completedFiles.forEach((file, index) => {
        setTimeout(() => {
            const zipPath = extractZipPath(file.result);
            if (zipPath) {
                triggerDownload(zipPath);
            }
        }, index * 500);
    });

    // 提示用户
    alert(`开始下载 ${completedFiles.length} 个文件\n\n如果浏览器阻止了下载，请在弹出窗口中允许下载。`);
}

// 清空队列按钮
document.getElementById('clearQueueBtn').addEventListener('click', clearQueue);

// 下载全部按钮
document.getElementById('downloadAllBtn').addEventListener('click', downloadAll);

// 语言搜索功能
const searchInput = document.getElementById('languageSearch');
const dropdown = document.getElementById('languageDropdown');

searchInput.addEventListener('input', (e) => {
    const query = e.target.value.toLowerCase().trim();

    if (query.length < 1) {
        dropdown.style.display = 'none';
        return;
    }

    const filtered = languages.filter(lang =>
        lang.name.toLowerCase().includes(query) ||
        lang.code.toLowerCase().includes(query) ||
        getChineseName(lang.code).includes(query)
    );

    showDropdown(filtered);
});

function getChineseName(code) {
    const chineseNames = {
        'zh': '中文',
        'zh-TW': '繁体中文',
        'en': '英语',
        'ja': '日语',
        'ko': '韩语',
        'fr': '法语',
        'de': '德语',
        'es': '西班牙语',
        'ru': '俄语',
        'ar': '阿拉伯语',
        'pt': '葡萄牙语',
        'it': '意大利语',
        'th': '泰语',
        'vi': '越南语',
        'hi': '印地语'
    };
    return chineseNames[code] || '';
}

function showDropdown(filteredLanguages) {
    dropdown.innerHTML = '';

    if (filteredLanguages.length === 0) {
        dropdown.innerHTML = '<div class="language-option">未找到匹配的语言</div>';
    } else {
        filteredLanguages.slice(0, 10).forEach(lang => {
            const option = document.createElement('div');
            option.className = 'language-option';
            option.innerHTML = `${lang.name} - ${lang.code}`;
            option.addEventListener('click', () => selectLanguage(lang.code, lang.name));
            dropdown.appendChild(option);
        });
    }

    dropdown.style.display = 'block';
}

// 点击其他地方关闭下拉框
document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-container')) {
        dropdown.style.display = 'none';
    }
});

// 常用语言标签点击
document.getElementById('popularLanguages').addEventListener('click', (e) => {
    if (e.target.classList.contains('language-tag')) {
        const code = e.target.dataset.code;
        const name = e.target.dataset.name;

        if (selectedLanguages.has(code)) {
            removeLanguage(code);
        } else {
            selectLanguage(code, name);
        }
    }
});

function selectLanguage(code, name) {
    if (!selectedLanguages.has(code)) {
        selectedLanguages.add(code);
        updateSelectedDisplay();
        updatePopularTags();
        updateSubmitButton();
    }

    searchInput.value = '';
    dropdown.style.display = 'none';
}

function removeLanguage(code) {
    selectedLanguages.delete(code);
    updateSelectedDisplay();
    updatePopularTags();
    updateSubmitButton();
}

function updateSelectedDisplay() {
    const selectedList = document.getElementById('selectedList');
    const selectedCount = document.getElementById('selectedCount');

    selectedCount.textContent = selectedLanguages.size;

    if (selectedLanguages.size === 0) {
        selectedList.innerHTML = '<div class="empty-state">请选择要翻译的目标语言</div>';
    } else {
        selectedList.innerHTML = '';
        selectedLanguages.forEach(code => {
            const lang = languages.find(l => l.code === code);
            if (lang) {
                const item = document.createElement('div');
                item.className = 'selected-item';
                item.innerHTML = `
                    ${lang.name} (${lang.code})
                    <span class="remove" onclick="removeLanguage('${code}')">&times;</span>
                `;
                selectedList.appendChild(item);
            }
        });
    }
}

function updatePopularTags() {
    const tags = document.querySelectorAll('.language-tag');
    tags.forEach(tag => {
        const code = tag.dataset.code;
        if (selectedLanguages.has(code)) {
            tag.classList.add('selected');
        } else {
            tag.classList.remove('selected');
        }
    });
}

function updateSubmitButton() {
    const submitBtn = document.getElementById('submitBtn');
    const estimateBtn = document.getElementById('estimateBtn');
    const hasFile = fileQueue.length > 0;
    const hasLanguages = selectedLanguages.size > 0;

    submitBtn.disabled = !(hasFile && hasLanguages) || isProcessing;

    // 更新按钮文字
    if (isProcessing) {
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 处理队列中...';
    } else if (fileQueue.length > 1) {
        submitBtn.innerHTML = `<i class="fas fa-magic"></i> 开始批量翻译 (${fileQueue.length} 个文件)`;
    } else {
        submitBtn.innerHTML = '<i class="fas fa-magic"></i> 开始翻译';
    }

    // 显示/隐藏费用预估按钮
    const selectedEngine = document.querySelector('input[name="translation_engine"]:checked')?.value;
    if (hasFile && hasLanguages && selectedEngine === 'openrouter') {
        estimateBtn.style.display = 'inline-block';
    } else {
        estimateBtn.style.display = 'none';
        document.getElementById('costEstimation').style.display = 'none';
    }
}

// 表单提交处理 - 支持队列
document.getElementById('translateForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    if (selectedLanguages.size === 0) {
        alert('请至少选择一种目标语言');
        return;
    }

    if (fileQueue.length === 0) {
        alert('请至少选择一个文件');
        return;
    }

    // 开始处理队列
    isProcessing = true;
    isPaused = false;
    currentFileIndex = 0;
    updateSubmitButton();

    await processQueue();

    // 全部完成
    isProcessing = false;
    updateSubmitButton();

    const completedCount = fileQueue.filter(f => f.status === 'completed').length;
    const failedCount = fileQueue.filter(f => f.status === 'failed').length;

    // 单文件（非批量）成功时自动下载：原 socket 自动下载分支恒假，已删除，改由 fetch 结果驱动。
    if (fileQueue.length === 1 && fileQueue[0].status === 'completed' && fileQueue[0].result) {
        const zipPath = extractZipPath(fileQueue[0].result);
        if (zipPath) {
            triggerDownload(zipPath);
        }
    }

    if (failedCount === 0) {
        alert(`🎉 批量翻译完成！\n成功: ${completedCount} 个文件`);
    } else {
        alert(`翻译完成\n成功: ${completedCount} 个文件\n失败: ${failedCount} 个文件\n\n请查看队列中的失败项并重试。`);
    }
});

// 队列处理核心函数
async function processQueue() {
    for (let i = 0; i < fileQueue.length; i++) {
        if (isPaused) {
            console.log('队列已暂停');
            break;
        }

        const fileItem = fileQueue[i];

        // 跳过已完成的文件
        if (fileItem.status === 'completed') {
            continue;
        }

        // 标记为处理中
        fileItem.status = 'processing';
        fileItem.progress = 0;
        currentFileIndex = i;
        updateFileQueueUI();

        try {
            await translateFile(fileItem);
            fileItem.status = 'completed';
            fileItem.progress = 100;
        } catch (error) {
            console.error(`文件 ${fileItem.file.name} 翻译失败:`, error);
            fileItem.status = 'failed';
            fileItem.error = error.message || '翻译失败';
            fileItem.progress = 0;
        }

        updateFileQueueUI();

        // 短暂延迟，避免请求过快
        if (i < fileQueue.length - 1) {
            await new Promise(resolve => setTimeout(resolve, 500));
        }
    }
}

// 翻译单个文件
// 新契约：完成/失败一律以 /translate 的 fetch 响应 JSON 为准；socket progress 只更新进度条。
async function translateFile(fileItem) {
    return new Promise((resolve, reject) => {
        const formData = new FormData();
        formData.append('file', fileItem.file);

        // 添加选中的语言
        selectedLanguages.forEach(code => {
            formData.append('languages', code);
        });

        // 添加翻译引擎选择
        const selectedEngine = document.querySelector('input[name="translation_engine"]:checked').value;
        formData.append('translation_engine', selectedEngine);

        // 如果选择了 OpenRouter AI，添加模型选择
        if (selectedEngine === 'openrouter') {
            const aiModel = document.getElementById('aiModel').value;
            formData.append('ai_model', aiModel);
        }

        // 新契约：带上当前 socket sid，后端据此定向 emit 进度（sid 缺失时后端退回全局广播）
        formData.append('socket_sid', socket.id || '');

        let timeoutTimer = null;

        // 进度事件只更新进度条/状态文本，不再写 fileItem.result，也不作为完成依据
        // （消除多客户端进度串台对本文件完成判定的影响）
        const progressHandler = (data) => {
            fileItem.progress = data.progress || 0;
            updateFileQueueUI();
        };

        socket.on('progress', progressHandler);

        // 统一清理：解绑进度监听 + 清除超时兜底计时器。所有完成/失败路径都必须调用。
        const cleanup = () => {
            socket.off('progress', progressHandler);
            if (timeoutTimer) {
                clearTimeout(timeoutTimer);
                timeoutTimer = null;
            }
        };

        // 超时兜底 (10分钟)：作为最后防线，任何正常路径都会先经 cleanup 清除它
        timeoutTimer = setTimeout(() => {
            cleanup();
            reject(new Error('翻译超时'));
        }, 600000);

        // 使用 AJAX 提交，以响应 JSON 判定成功/失败
        fetch('/translate', {
            method: 'POST',
            body: formData
        })
        .then(async (response) => {
            let data = null;
            try {
                data = await response.json();
            } catch (parseErr) {
                // JSON 解析失败：给通用错误
                cleanup();
                reject(new Error('服务器返回了无法解析的响应'));
                return;
            }

            if (response.ok && data && data.success) {
                // 成功：用响应里的 redirect_url / zip_path 填充结果，供下载按钮 / 单文件自动下载使用
                fileItem.result = data.redirect_url
                    || (data.zip_path ? `/success?zip_path=${data.zip_path}` : null);
                fileItem.progress = 100;
                // 部分语言失败仍算成功，保存警告用于展示
                fileItem.warnings = (Array.isArray(data.errors) && data.errors.length > 0)
                    ? data.errors
                    : null;
                cleanup();
                resolve();
            } else {
                // 失败：优先展示后端返回的中文错误消息
                const message = (data && data.error) ? data.error : '翻译失败';
                cleanup();
                reject(new Error(message));
            }
        })
        .catch((error) => {
            // 网络错误等
            cleanup();
            reject(error);
        });
    });
}

// 翻译引擎选择函数
function selectEngine(element, engine) {
    // 移除所有选中状态
    document.querySelectorAll('.engine-option').forEach(opt => {
        opt.classList.remove('selected');
    });
    
    // 添加选中状态
    element.classList.add('selected');
    
    // 选中对应的radio
    document.getElementById('engine_' + engine).checked = true;
    
    // 显示或隐藏模型选择器
    const modelSelector = document.getElementById('modelSelector');
    if (engine === 'openrouter') {
        modelSelector.classList.add('visible');
    } else {
        modelSelector.classList.remove('visible');
    }
    
    // 更新按钮状态
    updateSubmitButton();
}

// 费用预估函数
// 数据源为文件队列 fileQueue；后端仅支持 JSON 文件预估，多个 JSON 时串行汇总总价。
async function estimateCost() {
    const estimateBtn = document.getElementById('estimateBtn');
    const costEstimation = document.getElementById('costEstimation');
    const estimationContent = document.getElementById('estimationContent');

    // 检查语言
    if (selectedLanguages.size === 0) {
        alert('请先选择目标语言');
        return;
    }

    costEstimation.style.display = 'block';

    // 后端费用预估仅支持 .json 文件（.js / .zip 无法估算），从队列筛出可估文件
    const jsonItems = fileQueue.filter(item => {
        const ext = '.' + item.file.name.split('.').pop().toLowerCase();
        return ext === '.json';
    });

    if (jsonItems.length === 0) {
        // 队列里没有可估算的 JSON 文件，给出明确提示（不发请求）
        estimationContent.textContent =
            '⚠️ 费用预估仅支持 .json 文件，当前队列中没有可估算的 JSON 文件（.js / .zip 暂不支持预估）。';
        return;
    }

    const aiModel = document.getElementById('aiModel').value;

    // 显示加载状态
    const loadingSpinner = document.createElement('div');
    loadingSpinner.className = 'loading-spinner';
    loadingSpinner.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 计算中...';
    estimationContent.replaceChildren(loadingSpinner);
    estimateBtn.disabled = true;

    try {
        const perFileSummaries = [];
        const failures = [];
        let totalCostUsd = 0;
        let totalCostCny = 0;
        let totalInputTokens = 0;
        let totalOutputTokens = 0;
        let successCount = 0;

        // 逐个 JSON 文件请求并汇总（串行即可）
        for (const item of jsonItems) {
            const formData = new FormData();
            formData.append('file', item.file);
            selectedLanguages.forEach(code => formData.append('languages', code));
            formData.append('translation_engine', 'openrouter');
            formData.append('ai_model', aiModel);

            let data = null;
            try {
                const response = await fetch('/api/estimate-cost', {
                    method: 'POST',
                    body: formData
                });
                data = await response.json();
            } catch (e) {
                failures.push(`${item.file.name}: 请求失败`);
                continue;
            }

            if (data && data.success) {
                successCount++;
                const est = data.estimation || {};
                totalCostUsd += Number(est.total_cost_usd) || 0;
                totalCostCny += Number(est.total_cost_cny) || 0;
                totalInputTokens += Number(est.estimated_input_tokens) || 0;
                totalOutputTokens += Number(est.estimated_output_tokens) || 0;
                perFileSummaries.push(`【${item.file.name}】\n${data.formatted_summary || ''}`);
            } else {
                failures.push(`${item.file.name}: ${(data && data.error) || '预估失败'}`);
            }
        }

        // 组装展示文本（.estimation-content 为 white-space: pre-wrap，可直接渲染换行）
        const parts = [];
        if (successCount > 1) {
            parts.push(
                `📦 汇总（${successCount} 个 JSON 文件）\n` +
                `━━━━━━━━━━━━━━━━━━━━━━\n` +
                `📈 总 Token: 输入 ${totalInputTokens.toLocaleString()} / 输出 ${totalOutputTokens.toLocaleString()}\n` +
                `💰 总费用: $${totalCostUsd.toFixed(4)} (≈ ¥${totalCostCny.toFixed(4)})`
            );
        }
        if (perFileSummaries.length > 0) {
            parts.push(perFileSummaries.join('\n'));
        }
        if (failures.length > 0) {
            parts.push(`⚠️ 以下文件预估失败:\n${failures.join('\n')}`);
        }

        estimationContent.textContent = parts.length > 0 ? parts.join('\n') : '无法获取预估信息';
    } catch (error) {
        console.error('预估失败:', error);
        estimationContent.textContent = '❌ 预估失败，请重试';
    } finally {
        estimateBtn.disabled = false;
    }
}

// 更新模型描述
function updateModelDescription() {
    const select = document.getElementById('aiModel');
    const description = document.getElementById('modelDescription');

    const selectedModel = aiModels.find(model => model.id === select.value);
    if (selectedModel) {
        description.textContent = selectedModel.description;
    } else {
        description.textContent = '';
    }
}

// 加载 AI 模型列表（OpenRouter 3 档）
async function loadAiModels() {
    try {
        const response = await fetch('/api/llm-models');
        const data = await response.json();

        if (data.success && data.models) {
            aiModels = data.models;
            renderAiModelOptions(data.models);
        } else {
            loadDefaultModels();
        }
    } catch (error) {
        console.error('加载模型列表失败:', error);
        loadDefaultModels();
    }
}

// 渲染模型下拉选项
function renderAiModelOptions(models) {
    const select = document.getElementById('aiModel');
    const description = document.getElementById('modelDescription');

    select.replaceChildren();
    let defaultIndex = 0;
    models.forEach((model, index) => {
        const option = document.createElement('option');
        option.value = model.id;
        option.textContent = model.name;
        if (model.default) {
            defaultIndex = index;
        }
        select.appendChild(option);
    });
    select.selectedIndex = defaultIndex;

    if (models.length > 0) {
        description.textContent = models[defaultIndex].description;
    }
}

// 默认模型列表（后端 /api/llm-models 不可用时兜底）
function loadDefaultModels() {
    const defaultModels = [
        { id: 'anthropic/claude-sonnet-5', name: 'Claude Sonnet 5 ⭐', description: '质量档 — 编码/agentic 接近 Opus 级，推荐生产默认', default: true },
        { id: 'openai/gpt-5.4', name: 'GPT-5.4 ✨', description: '备选档 — 同价位替代方案，推理强' },
        { id: 'google/gemini-3.1-flash-lite-preview', name: 'Gemini 3.1 Flash Lite 💰', description: '经济档 — 比 Sonnet 便宜 12x，适合大批量' }
    ];
    aiModels = defaultModels;
    renderAiModelOptions(defaultModels);
}

// ========== 文件夹上传支持 ==========

// 文件夹选择处理
function handleFolderSelection() {
    const folderInput = document.getElementById('folderInput');
    if (folderInput) {
        folderInput.click();
    }
}

// 文件夹 input change 事件处理
function setupFolderInput() {
    const folderInput = document.getElementById('folderInput');
    if (folderInput) {
        folderInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                // 过滤出有效的 .js 和 .json 文件
                const validFiles = Array.from(e.target.files).filter(file => {
                    const ext = '.' + file.name.split('.').pop().toLowerCase();
                    return ['.js', '.json'].includes(ext);
                });

                if (validFiles.length > 0) {
                    handleFileSelection(validFiles);
                } else {
                    alert('文件夹中没有找到有效的 .js 或 .json 文件');
                }

                // 重置 input 以允许再次选择同一文件夹
                e.target.value = '';
            }
        });
    }
}

// 递归遍历目录（用于拖拽）
async function traverseDirectory(entry, path = '') {
    const files = [];

    if (entry.isFile) {
        try {
            const file = await new Promise((resolve, reject) => {
                entry.file(resolve, reject);
            });
            // 添加相对路径信息
            Object.defineProperty(file, 'relativePath', {
                value: path + file.name,
                writable: false
            });
            files.push(file);
        } catch (e) {
            console.error('读取文件失败:', e);
        }
    } else if (entry.isDirectory) {
        const reader = entry.createReader();
        // Chrome 的 readEntries 每批最多返回 100 条，必须在同一个 reader 上循环调用，
        // 直到返回空数组才算读完，否则文件数 > 100 的目录会被截断。
        const readBatch = () => new Promise((resolve, reject) => {
            reader.readEntries(resolve, reject);
        });

        let batch = await readBatch();
        while (batch.length > 0) {
            for (const e of batch) {
                const subFiles = await traverseDirectory(e, path + entry.name + '/');
                files.push(...subFiles);
            }
            batch = await readBatch();
        }
    }

    return files;
}

// 处理拖拽的文件/文件夹
async function handleDropItems(items) {
    const allFiles = [];

    for (const item of items) {
        if (item.kind === 'file') {
            const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;

            if (entry) {
                if (entry.isDirectory) {
                    // 递归获取文件夹中的文件
                    const dirFiles = await traverseDirectory(entry);
                    allFiles.push(...dirFiles);
                } else {
                    // 普通文件
                    allFiles.push(item.getAsFile());
                }
            } else {
                // 回退到普通文件获取
                allFiles.push(item.getAsFile());
            }
        }
    }

    if (allFiles.length > 0) {
        handleFileSelection(allFiles);
    }
}

// 初始化
updateSubmitButton();

// 页面加载时的初始化
window.addEventListener('load', () => {
    const progressSection = document.getElementById('progressSection');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');

    // 确保进度条隐藏
    progressSection.style.display = 'none';
    progressFill.style.width = '0%';
    progressText.innerText = '0%';

    // 重置进度条颜色
    progressFill.style.background = 'linear-gradient(90deg, #4facfe, #00f2fe)';

    // 加载 AI 模型列表
    loadAiModels();

    // 设置文件夹 input
    setupFolderInput();
});
