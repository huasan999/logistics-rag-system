// 物流RAG系统聊天界面 - 完整修复版（保留原有逻辑，修复消息计数问题）
// 修复重点：移除前端消息计数逻辑，完全依赖后端返回的数据

document.addEventListener('DOMContentLoaded', function() {
    // DOM元素
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const chatMessages = document.getElementById('chat-messages');
    const clearChatBtn = document.getElementById('clear-chat');
    const newChatBtn = document.getElementById('new-chat');
    const exampleButtons = document.querySelectorAll('.example-btn');
    const streamToggle = document.getElementById('stream-toggle');
    const functionCallToggle = document.getElementById('function-call-toggle');
    const typingIndicator = document.getElementById('typing-indicator');
    const modelInfoEl = document.getElementById('model-info');
    const modeInfoEl = document.getElementById('mode-info');
    const statusEl = document.getElementById('status');
    const docCountEl = document.getElementById('doc-count');
    const refreshInfoBtn = document.getElementById('refresh-info');
    const summaryBtn = document.getElementById('summary-btn');
    const viewConversationBtn = document.getElementById('view-conversation-btn');
    const showSourcesBtn = document.getElementById('show-sources-btn');
    const summaryPreview = document.getElementById('summary-preview');
    const summaryPreviewText = document.getElementById('summary-preview-text');
    const summaryText = document.getElementById('summary-text');
    const summaryTime = document.getElementById('summary-time');
    const copySummaryBtn = document.getElementById('copy-summary-btn');

    // 状态变量
    let sessionId = generateSessionId();
    let isStreaming = streamToggle.checked;
    let isFunctionCallEnabled = functionCallToggle.checked;
    let isProcessing = false;
    let wsConnection = null;
    let currentStreamingMessage = null;
    let currentSources = [];
    let conversationStats = {
        messageCount: 0,
        hasSummary: false,
        summaryVersion: 0,
        summary: '',
        lastSummaryTime: null
    };

    // 摘要自动生成阈值
    const SUMMARY_THRESHOLD = 8;
    const SUMMARY_REGEN_INTERVAL = 5;

    // 初始化
    init();

    function init() {
        // 加载系统信息
        loadSystemInfo();

        // 设置事件监听器
        setupEventListeners();

        // 调整输入框高度
        adjustTextareaHeight(messageInput);

        // 连接WebSocket
        connectWebSocket();

        // 更新当前时间
        updateCurrentTime();
        setInterval(updateCurrentTime, 60000);

        // 初始滚动到底部
        setTimeout(scrollToBottom, 100);

        // 加载对话信息
        setTimeout(() => getConversationInfo(), 1000);
    }

    function setupEventListeners() {
        // 发送消息
        sendButton.addEventListener('click', sendMessage);

        // 回车发送
        messageInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // 输入框自动调整高度
        messageInput.addEventListener('input', function() {
            adjustTextareaHeight(this);
        });

        // 示例问题
        exampleButtons.forEach(btn => {
            btn.addEventListener('click', function() {
                const question = this.getAttribute('data-question');
                messageInput.value = question;
                adjustTextareaHeight(messageInput);
                sendMessage();
            });
        });

        // 清空对话
        clearChatBtn.addEventListener('click', clearChat);

        // 新对话
        newChatBtn.addEventListener('click', startNewChat);

        // 流式响应切换
        streamToggle.addEventListener('change', function() {
            isStreaming = this.checked;
            showNotification(`流式响应已${isStreaming ? '开启' : '关闭'}`, 'info');
        });

        // 函数调用切换
        functionCallToggle.addEventListener('change', function() {
            isFunctionCallEnabled = this.checked;
            showNotification(`函数调用已${isFunctionCallEnabled ? '开启' : '关闭'}`, 'info');
        });

        // 刷新信息
        refreshInfoBtn.addEventListener('click', function() {
            loadSystemInfo();
            getConversationInfo();
            showNotification('系统信息已刷新', 'info');
        });

        // 生成摘要
        if (summaryBtn) {
            summaryBtn.addEventListener('click', generateConversationSummary);
        }

        // 查看对话信息
        if (viewConversationBtn) {
            viewConversationBtn.addEventListener('click', showConversationInfo);
        }

        // 查看参考来源
        if (showSourcesBtn) {
            showSourcesBtn.addEventListener('click', function() {
                if (currentSources && currentSources.length > 0) {
                    showSourcesModal(currentSources);
                } else {
                    showNotification('本次回答没有参考来源', 'info');
                }
            });
        }

        // 复制摘要按钮
        if (copySummaryBtn) {
            copySummaryBtn.addEventListener('click', copySummaryToClipboard);
        }

        // 模态框关闭按钮
        document.querySelectorAll('.close-modal').forEach(btn => {
            btn.addEventListener('click', function() {
                const modal = this.closest('.modal');
                modal.style.display = 'none';
            });
        });

        // 点击模态框外部关闭
        window.addEventListener('click', function(event) {
            if (event.target.classList.contains('modal')) {
                event.target.style.display = 'none';
            }
        });
    }

    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/ws`;

        try {
            wsConnection = new WebSocket(wsUrl);

            wsConnection.onopen = function() {
                console.log('WebSocket连接已建立');
                updateStatus('已连接', 'ready');

                // 发送获取系统信息的请求
                setTimeout(() => {
                    if (wsConnection.readyState === WebSocket.OPEN) {
                        wsConnection.send(JSON.stringify({
                            type: "get_system_info"
                        }));

                        // 获取对话信息
                        getConversationInfo();
                    }
                }, 500);
            };

            wsConnection.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    console.log('收到WebSocket消息:', data.type);
                    handleWebSocketMessage(data);
                } catch (e) {
                    console.error('WebSocket消息解析失败:', e);
                }
            };

            wsConnection.onclose = function() {
                console.log('WebSocket连接已关闭');
                updateStatus('连接断开', 'error');

                // 3秒后重连
                setTimeout(connectWebSocket, 3000);
            };

            wsConnection.onerror = function(error) {
                console.error('WebSocket错误:', error);
                updateStatus('连接错误', 'error');
            };
        } catch (error) {
            console.error('WebSocket连接失败:', error);
            updateStatus('连接失败', 'error');
        }
    }

    function handleWebSocketMessage(data) {
        console.log('收到 WebSocket 消息:', data.type, data);

        switch(data.type) {
            case 'system_info':
                updateSystemInfo(data);
                break;

            case 'conversation_info':
                updateConversationInfo(data);
                break;

            case 'conversation_stats':
                // 新增：处理实时对话统计更新
                updateConversationInfo(data);
                break;

            case 'summary_generated':
                handleSummaryGenerated(data);
                break;

            case 'conversation_cleared':
                showNotification('对话历史已清空', 'info');
                resetConversationStats();
                updateConversationUI();
                break;

            case 'stream_start':
                hideTypingIndicator();
                createNewStreamMessage(data.question);
                break;

            case 'stream_chunk':
                appendToStreamMessage(data.chunk);
                break;

            case 'stream_end':
                console.log('流式结束，来源信息:', data.sources);
                finalizeStreamMessage(data);

                // 流式结束后获取最新对话统计
                setTimeout(() => getConversationInfo(), 500);
                break;

            case 'result':
                console.log('查询结果，来源信息:', data.sources);
                handleQueryResult(data);
                break;

            case 'tools_list':
                console.log('可用工具列表:', data.tools);
                break;

            case 'error':
                handleErrorMessage(data);
                break;

            default:
                console.warn('未知的WebSocket消息类型:', data.type);
        }
    }

    function updateSystemInfo(data) {
        if (data.llm_model) {
            modelInfoEl.textContent = data.model_provider ? `${data.llm_model} (${data.model_provider})` : data.llm_model;
        }
        if (data.mode) {
            modeInfoEl.textContent = data.mode === 'enhanced' ? '增强版' : '基础版';
        }
        if (data.function_call_enabled !== undefined) {
            functionCallToggle.checked = data.function_call_enabled;
            isFunctionCallEnabled = data.function_call_enabled;
        }
        if (data.document_count !== undefined) {
            docCountEl.textContent = data.document_count;
        }
        if (data.status) {
            updateStatus(data.status, 'ready');
        }
    }

    function updateStatus(text, type) {
        statusEl.textContent = text;
        statusEl.className = type === 'ready' ? 'status-ready' : 'status-error';
    }

    function createNewStreamMessage(question) {
        const messageId = Date.now();
        const timestamp = getCurrentTime();

        const messageHtml = `
            <div class="message assistant-message" id="stream-message-${messageId}">
                <div class="message-avatar">
                    <i class="fas fa-robot"></i>
                </div>
                <div class="message-content">
                    <div class="message-header">
                        <strong>助手</strong>
                        <span class="message-time">${timestamp}</span>
                    </div>
                    <div class="message-text" id="stream-content-${messageId}">
                        <span class="streaming-text"></span>
                        <span class="typing-cursor">█</span>
                    </div>
                </div>
            </div>
        `;

        chatMessages.insertAdjacentHTML('beforeend', messageHtml);
        currentStreamingMessage = {
            id: messageId,
            content: '',
            element: document.getElementById(`stream-content-${messageId}`),
            textElement: document.querySelector(`#stream-content-${messageId} .streaming-text`)
        };

        scrollToBottom();
    }

    function appendToStreamMessage(chunk) {
        if (!currentStreamingMessage) return;

        currentStreamingMessage.content += chunk;
        if (currentStreamingMessage.textElement) {
            currentStreamingMessage.textElement.textContent = currentStreamingMessage.content;
        }

        scrollToBottom();
    }

    function finalizeStreamMessage(data) {
        if (!currentStreamingMessage) return;

        // 移除光标
        const cursor = currentStreamingMessage.element.querySelector('.typing-cursor');
        if (cursor) {
            cursor.remove();
        }

        // 更新完整内容
        if (currentStreamingMessage.textElement) {
            currentStreamingMessage.textElement.textContent = currentStreamingMessage.content;
        }

        // 处理来源信息
        const sources = data.sources || data.rag_sources || [];
        updateSourcesDisplay(sources);

        // 不在这里更新对话统计，等待后端推送
        // 检查是否需要自动生成摘要
        checkAutoSummary();

        currentStreamingMessage = null;
        isProcessing = false;
    }

    function handleQueryResult(data) {
        hideTypingIndicator();

        if (data.answer) {
            addMessage('助手', data.answer, 'assistant', data.timestamp);

            // 显示函数调用信息
            if (data.function_call) {
                addToolCallMessage(data.function_call);
            }

            // 处理来源信息 - 兼容多种字段名
            let sources = [];
            if (data.sources && Array.isArray(data.sources)) {
                sources = data.sources;
            } else if (data.rag_sources && Array.isArray(data.rag_sources)) {
                sources = data.rag_sources;
            }

            updateSourcesDisplay(sources);

            // 更新对话统计
            if (data.conversation_stats) {
                updateConversationInfo(data.conversation_stats);
            } else {
                // 如果没有统计信息，主动获取
                setTimeout(() => getConversationInfo(), 500);
            }

            // 检查是否需要自动生成摘要
            checkAutoSummary();
        }

        isProcessing = false;
    }

    function handleErrorMessage(data) {
        hideTypingIndicator();
        addMessage('错误', data.message || '处理失败', 'error');
        isProcessing = false;
    }

    function handleSummaryGenerated(data) {
        // 更新对话统计
        updateConversationInfo({
            has_summary: true,
            summary_version: data.summary_version || (conversationStats.summaryVersion + 1),
            summary: data.summary || '',
            last_summary_time: data.timestamp || new Date().toISOString(),
            message_count: data.message_count || conversationStats.messageCount
        });

        // 显示通知
        if (data.summary) {
            showNotification('对话摘要已生成，点击侧边栏查看详情', 'info');
            showSummaryModal(data.summary, data.timestamp || new Date().toISOString());
        } else {
            showNotification('摘要生成失败或未满足条件', 'warning');
        }
    }

    function updateSourcesDisplay(sources) {
        if (!sources || sources.length === 0) {
            // 没有来源时隐藏按钮
            if (showSourcesBtn) {
                showSourcesBtn.style.display = 'none';
            }
            currentSources = [];
            return;
        }

        // 确保 sources 是数组
        if (!Array.isArray(sources)) {
            sources = [sources];
        }

        // 保存当前来源
        currentSources = sources;

        // 显示来源按钮
        if (showSourcesBtn) {
            showSourcesBtn.style.display = 'flex';
            showSourcesBtn.innerHTML = `<i class="fas fa-book"></i> 参考来源 (${sources.length})`;
        }

        // 为最新一条助手消息添加来源提示
        const lastAssistantMessage = document.querySelector('#chat-messages .assistant-message:last-child');
        if (lastAssistantMessage) {
            addSourcesHint(lastAssistantMessage.querySelector('.message-text'), sources);
        }
    }

    function sendMessage() {
        const message = messageInput.value.trim();

        if (!message || isProcessing) {
            return;
        }

        // 添加用户消息
        addMessage('您', message, 'user');

        // 清空输入框
        messageInput.value = '';
        adjustTextareaHeight(messageInput);

        // 显示正在输入
        showTypingIndicator();

        // 设置处理状态
        isProcessing = true;

        // 隐藏来源按钮（新的查询会生成新的来源）
        if (showSourcesBtn) {
            showSourcesBtn.style.display = 'none';
        }
        currentSources = [];

        // 发送请求
        if (isStreaming && wsConnection && wsConnection.readyState === WebSocket.OPEN) {
            sendWebSocketMessage(message);
        } else {
            sendHttpRequest(message);
        }

        // 不在这里更新消息计数，等待后端响应
    }

    function sendWebSocketMessage(message) {
        if (!wsConnection || wsConnection.readyState !== WebSocket.OPEN) {
            console.warn('WebSocket未连接，使用HTTP请求');
            sendHttpRequest(message);
            return;
        }

        wsConnection.send(JSON.stringify({
            type: "query",
            question: message,
            session_id: sessionId,
            stream: isStreaming
        }));
    }

    function sendHttpRequest(message) {
        const endpoint = isStreaming ? '/api/query/stream' : '/api/query';

        fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question: message,
                session_id: sessionId,
                stream: isStreaming
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP错误! 状态: ${response.status}`);
            }

            if (isStreaming) {
                // 创建新的流式消息
                createNewStreamMessage(message);

                // 处理流式响应
                return processStreamResponse(response, message);
            } else {
                return response.json().then(data => {
                    hideTypingIndicator();

                    if (data.status === 'success') {
                        addMessage('助手', data.answer, 'assistant', data.timestamp);

                        // 显示函数调用信息
                        if (data.function_call) {
                            addToolCallMessage(data.function_call);
                        }

                        // 处理来源信息
                        const sources = data.sources || data.rag_sources || [];
                        updateSourcesDisplay(sources);

                        // 更新对话统计
                        if (data.conversation_stats) {
                            updateConversationInfo(data.conversation_stats);
                        } else {
                            // 如果没有统计信息，主动获取
                            setTimeout(() => getConversationInfo(), 500);
                        }

                        // 检查是否需要自动生成摘要
                        checkAutoSummary();
                    } else {
                        addMessage('错误', data.answer || '处理失败', 'error');
                    }

                    isProcessing = false;
                });
            }
        })
        .catch(error => {
            hideTypingIndicator();
            addMessage('错误', `请求失败：${error.message}`, 'error');
            isProcessing = false;
            console.error('Error:', error);
        });
    }

    async function processStreamResponse(response, question) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        let fullAnswer = '';

        try {
            while (true) {
                const { done, value } = await reader.read();

                if (done) {
                    // 流式结束
                    if (currentStreamingMessage) {
                        finalizeStreamMessage({
                            sources: currentSources,
                            answer: fullAnswer
                        });
                    }
                    break;
                }

                // 解码数据
                buffer += decoder.decode(value, { stream: true });

                // 处理 EventSource 格式：以 "data: " 开头，以两个换行符结束
                const lines = buffer.split('\n\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.substring(6);

                        // 检查是否是结束标记
                        if (dataStr.trim() === '[DONE]') {
                            // 流式结束
                            if (currentStreamingMessage) {
                                finalizeStreamMessage({
                                    sources: currentSources,
                                    answer: fullAnswer
                                });
                            }
                            continue;
                        }

                        // 尝试解析JSON（处理来源信息和对话统计）
                        if (dataStr.trim().startsWith('{') && dataStr.trim().endsWith('}')) {
                            try {
                                const data = JSON.parse(dataStr);
                                if (data.type === 'sources' && data.sources) {
                                    // 处理来源信息
                                    updateSourcesDisplay(data.sources);
                                    continue;
                                } else if (data.type === 'conversation_stats') {
                                    // 处理对话统计信息
                                    updateConversationInfo(data);
                                    continue;
                                }
                            } catch (e) {
                                // 不是JSON，当作纯文本处理
                                console.log('解析JSON失败，当作纯文本处理:', e);
                            }
                        }

                        // 纯文本内容，直接追加
                        if (dataStr.trim()) {
                            fullAnswer += dataStr;
                            appendToStreamMessage(dataStr);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('流式处理错误:', error);
            hideTypingIndicator();
            addMessage('错误', `流式处理失败：${error.message}`, 'error');
            isProcessing = false;
        }
    }

    function addMessage(sender, text, type, timestamp = null) {
        const messageId = Date.now();
        const time = timestamp ? formatTime(timestamp) : getCurrentTime();

        const messageHtml = `
            <div class="message ${type}-message" id="message-${messageId}">
                <div class="message-avatar">
                    <i class="fas ${getAvatarIcon(type)}"></i>
                </div>
                <div class="message-content">
                    <div class="message-header">
                        <strong>${sender}</strong>
                        <span class="message-time">${time}</span>
                    </div>
                    <div class="message-text">
                        ${escapeHtml(text).replace(/\n/g, '<br>')}
                    </div>
                </div>
            </div>
        `;

        chatMessages.insertAdjacentHTML('beforeend', messageHtml);
        scrollToBottom();
    }

    function addToolCallMessage(functionCall) {
        const toolName = functionCall.name || '未知工具';
        const toolArgs = JSON.stringify(functionCall.arguments || {}, null, 2);

        const messageHtml = `
            <div class="message tool-message">
                <div class="message-avatar">
                    <i class="fas fa-cogs"></i>
                </div>
                <div class="message-content">
                    <div class="message-header">
                        <strong>工具调用</strong>
                        <span class="message-time">${getCurrentTime()}</span>
                    </div>
                    <div class="message-text">
                        <strong>${toolName}</strong>
                        <pre>${escapeHtml(toolArgs)}</pre>
                    </div>
                </div>
            </div>
        `;

        chatMessages.insertAdjacentHTML('beforeend', messageHtml);
        scrollToBottom();
    }

    function addSourcesHint(messageElement, sources) {
        if (!messageElement || !sources || sources.length === 0) return;

        // 移除旧的来源提示
        const oldHint = messageElement.querySelector('.sources-hint');
        if (oldHint) oldHint.remove();

        const hintHtml = `
            <div class="sources-hint">
                <i class="fas fa-info-circle"></i> 参考了 ${sources.length} 个知识库文档
                <button class="view-sources-btn" onclick="window.showSourcesModal(${JSON.stringify(sources).replace(/"/g, '&quot;')})">
                    查看详情
                </button>
            </div>
        `;

        messageElement.insertAdjacentHTML('beforeend', hintHtml);
    }

    function showSourcesModal(sources) {
        const modal = document.getElementById('sources-modal');
        const sourcesInfo = document.getElementById('sources-info');
        const sourcesList = document.getElementById('sources-list');

        if (!sources || sources.length === 0) {
            sourcesInfo.innerHTML = `
                <div style="text-align: center; padding: 20px;">
                    <i class="fas fa-book-open" style="font-size: 48px; color: #ccc; margin-bottom: 15px;"></i>
                    <p style="margin: 0; color: #666; font-size: 14px;">本次回答没有参考知识库文档。</p>
                </div>
            `;
            sourcesList.innerHTML = '';
        } else {
            sourcesInfo.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <p style="margin: 0; color: #666;">
                        本次回答参考了 <strong style="color: #667eea;">${sources.length}</strong> 个知识库文档
                    </p>
                    <span style="font-size: 12px; color: #888;">
                        总字数: ${calculateSourcesWords(sources)}
                    </span>
                </div>
            `;

            let sourcesHtml = '';
            sources.forEach((source, index) => {
                const sourceName = source.source || '未知来源';
                const chunkId = source.chunk_id || 'N/A';
                const content = source.content ?
                    source.content.substring(0, 400) + (source.content.length > 400 ? '...' : '') :
                    '无内容';
                const similarity = source.similarity ? `相关度: ${(source.similarity * 100).toFixed(1)}%` : '';
                const wordCount = source.content ? `字数: ${source.content.length}` : '';

                sourcesHtml += `
                    <div class="source-item" style="cursor: pointer;" onclick="toggleSourceDetail(${index})">
                        <div class="source-header">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span style="background: #667eea; color: white; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold;">
                                    ${index + 1}
                                </span>
                                <strong style="font-size: 14px; color: #333; flex: 1;">${sourceName}</strong>
                            </div>
                            <div style="display: flex; gap: 8px; align-items: center;">
                                ${similarity ? `<span class="source-id" style="background: #10b981;">${similarity}</span>` : ''}
                                <span class="source-id">#${chunkId}</span>
                            </div>
                        </div>
                        <div class="source-content" style="margin-top: 10px; font-size: 13px; color: #555; line-height: 1.6;">
                            ${escapeHtml(content)}
                        </div>
                        <div class="source-footer" style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #e5e7eb; display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size: 11px; color: #888;">
                                ${wordCount}
                            </span>
                            <button class="copy-source-btn" onclick="event.stopPropagation(); copySourceContent(${index})" style="background: none; border: none; color: #667eea; cursor: pointer; font-size: 11px; display: flex; align-items: center; gap: 4px;">
                                <i class="fas fa-copy"></i> 复制
                            </button>
                        </div>
                    </div>
                `;
            });

            sourcesList.innerHTML = sourcesHtml;
        }

        modal.style.display = 'block';
    }

    function calculateSourcesWords(sources) {
        if (!sources) return '0';
        let totalWords = 0;
        sources.forEach(source => {
            if (source.content) {
                totalWords += source.content.length;
            }
        });
        return totalWords + ' 字';
    }

    function getConversationInfo() {
        if (!sessionId) return;

        try {
            if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
                wsConnection.send(JSON.stringify({
                    type: "get_conversation_info",
                    session_id: sessionId
                }));
            } else {
                // 使用HTTP请求
                fetch(`/api/conversation/${encodeURIComponent(sessionId)}`)
                .then(response => {
                    if (response.ok) {
                        return response.json();
                    }
                    throw new Error('获取对话信息失败');
                })
                .then(data => {
                    updateConversationInfo(data);
                })
                .catch(error => {
                    console.error('获取对话信息失败:', error);
                });
            }
        } catch (error) {
            console.error('获取对话信息失败:', error);
        }
    }

    function updateConversationInfo(data) {
        // 完全使用后端返回的数据，不进行任何前端计算
        conversationStats = {
            messageCount: data.message_count || 0, // 完全信任后端
            hasSummary: data.has_summary || false,
            summaryVersion: data.summary_version || 0,
            summary: data.summary || '',
            lastSummaryTime: data.last_summary_time || null
        };

        // 更新UI显示
        updateConversationUI();
    }

    function updateConversationUI() {
        // 更新对话统计显示
        const statsElement = document.getElementById('conversation-stats');
        if (statsElement) {
            const summaryStatus = conversationStats.hasSummary ?
                `<span style="color: #10b981; cursor: pointer;" onclick="window.viewSummaryDetail()" title="点击查看摘要">已生成</span>` :
                `<span style="color: #ef4444">未生成</span>`;

            statsElement.innerHTML = `
                <p>消息: <span id="message-count">${conversationStats.messageCount}</span> | 
                摘要: ${summaryStatus}</p>
            `;
        }

        // 更新摘要按钮状态
        if (summaryBtn) {
            if (conversationStats.hasSummary) {
                summaryBtn.innerHTML = '<i class="fas fa-sync-alt"></i> 重新生成摘要';
                summaryBtn.setAttribute('title', '重新生成对话摘要');
            } else {
                summaryBtn.innerHTML = '<i class="fas fa-file-alt"></i> 生成摘要';
                summaryBtn.setAttribute('title', '生成对话摘要');
            }

            // 启用/禁用按钮
            summaryBtn.disabled = conversationStats.messageCount < 3;
        }

        // 显示/隐藏摘要预览
        if (summaryPreview) {
            if (conversationStats.hasSummary && conversationStats.summary) {
                summaryPreview.style.display = 'block';
                const previewText = conversationStats.summary.length > 100 ?
                    conversationStats.summary.substring(0, 100) + '...' :
                    conversationStats.summary;
                summaryPreviewText.textContent = previewText;
            } else {
                summaryPreview.style.display = 'none';
            }
        }

        // 根据消息数量显示提示
        if (conversationStats.messageCount >= SUMMARY_THRESHOLD && !conversationStats.hasSummary) {
            // 显示非阻塞式提示
            setTimeout(() => {
                if (!conversationStats.hasSummary && conversationStats.messageCount >= SUMMARY_THRESHOLD) {
                    showNotification('对话已较长，建议生成摘要以优化后续对话质量', 'info');
                }
            }, 2000);
        }
    }

    // 不再需要 syncMessageCountWithServer 函数，因为现在完全依赖后端数据
    // 但保留函数以兼容原有代码
    function syncMessageCountWithServer() {
        // 空函数，不再需要同步
        console.log('消息计数同步已禁用，完全依赖后端数据');
    }

    function checkAutoSummary() {
        // 检查是否满足自动生成摘要的条件
        if (!conversationStats.hasSummary && conversationStats.messageCount >= SUMMARY_THRESHOLD) {
            // 延迟执行，避免干扰用户体验
            setTimeout(() => {
                if (!conversationStats.hasSummary && conversationStats.messageCount >= SUMMARY_THRESHOLD) {
                    if (confirm(`对话已有${conversationStats.messageCount}条消息，是否生成摘要以优化后续对话？`)) {
                        generateConversationSummary();
                    }
                }
            }, 1500);
        }
    }

    function generateConversationSummary() {
        if (!sessionId) {
            showNotification('请先开始对话', 'warning');
            return;
        }

        // 检查是否有足够消息生成摘要
        if (conversationStats.messageCount < 3) {
            showNotification(`当前对话只有${conversationStats.messageCount}条消息，建议达到5条以上再生成摘要`, 'warning');
            return;
        }

        // 检查是否刚生成过摘要
        if (conversationStats.hasSummary && conversationStats.messageCount < conversationStats.summaryVersion * SUMMARY_REGEN_INTERVAL + SUMMARY_THRESHOLD) {
            if (!confirm(`摘要版本 ${conversationStats.summaryVersion} 仍然有效，确定要重新生成吗？`)) {
                return;
            }
        }

        showNotification('正在生成对话摘要...', 'info');

        // 禁用按钮避免重复点击
        if (summaryBtn) {
            summaryBtn.disabled = true;
            summaryBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 生成中...';
        }

        // 使用HTTP请求（更稳定）
        fetch(`/api/conversation/${encodeURIComponent(sessionId)}/summary`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            // 检查响应状态
            if (!response.ok) {
                // 尝试解析错误响应
                return response.json().then(errorData => {
                    throw new Error(errorData.message || `服务器错误 (${response.status})`);
                }).catch(() => {
                    throw new Error(`服务器响应错误，状态码: ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            console.log('摘要生成响应:', data);

            // 检查响应状态
            if (data.status === 'success' && data.summary) {
                // 更新对话信息
                updateConversationInfo({
                    has_summary: true,
                    summary_version: conversationStats.summaryVersion + 1,
                    summary: data.summary,
                    last_summary_time: data.timestamp || new Date().toISOString(),
                    message_count: conversationStats.messageCount
                });

                // 显示摘要模态框
                setTimeout(() => {
                    showSummaryModal(data.summary, data.timestamp || new Date().toISOString());
                }, 500);

                showNotification('摘要生成成功！', 'info');
            } else if (data.status === 'failed') {
                // 服务器返回了失败状态
                showNotification(`摘要生成失败: ${data.message || '未知错误'}`, 'error');
            } else {
                // 未知响应格式
                showNotification('摘要生成失败: 响应格式错误', 'error');
            }
        })
        .catch(error => {
            console.error('生成摘要失败:', error);

            // 检查错误类型
            let errorMessage = error.message;
            if (errorMessage.includes('Failed to fetch')) {
                errorMessage = '无法连接到服务器，请检查服务器是否运行';
            } else if (errorMessage.includes('NetworkError')) {
                errorMessage = '网络错误，请检查网络连接';
            }

            showNotification(`生成摘要失败: ${errorMessage}`, 'error');
        })
        .finally(() => {
            // 重新启用按钮
            if (summaryBtn) {
                setTimeout(() => {
                    summaryBtn.disabled = false;
                    summaryBtn.innerHTML = conversationStats.hasSummary ?
                        '<i class="fas fa-sync-alt"></i> 重新生成摘要' :
                        '<i class="fas fa-file-alt"></i> 生成摘要';
                }, 1000);
            }
        });
    }

    function showSummaryModal(summary, timestamp) {
        const modal = document.getElementById('summary-modal');
        if (!modal) return;

        // 更新摘要内容
        if (summaryText) {
            summaryText.innerHTML = escapeHtml(summary).replace(/\n/g, '<br>');
        }

        // 更新时间
        if (summaryTime) {
            const formattedTime = timestamp ? formatTime(timestamp) : getCurrentTime();
            summaryTime.textContent = `生成时间: ${formattedTime}`;
        }

        // 绑定复制功能
        if (copySummaryBtn) {
            copySummaryBtn.onclick = function() {
                copyToClipboard(summary);
            };
        }

        modal.style.display = 'block';
    }

    function copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            showNotification('已复制到剪贴板', 'info');
        }).catch(err => {
            console.error('复制失败:', err);
            showNotification('复制失败，请手动复制', 'error');
        });
    }

    function copySummaryToClipboard() {
        if (conversationStats.summary) {
            copyToClipboard(conversationStats.summary);
        } else {
            showNotification('没有可复制的摘要内容', 'warning');
        }
    }

    function viewSummaryDetail() {
        if (conversationStats.hasSummary && conversationStats.summary) {
            showSummaryModal(conversationStats.summary, conversationStats.lastSummaryTime);
        } else {
            showNotification('当前对话没有摘要，请先生成摘要', 'warning');
        }
    }

    function copySourceContent(index) {
        const sourceContent = currentSources[index]?.content;
        if (sourceContent) {
            copyToClipboard(sourceContent);
        } else {
            showNotification('没有可复制的内容', 'warning');
        }
    }

    function toggleSourceDetail(index) {
        const sourceItems = document.querySelectorAll('.source-item');
        if (sourceItems[index]) {
            const contentElement = sourceItems[index].querySelector('.source-content');
            const currentContent = contentElement.textContent;
            const fullContent = currentSources[index]?.content || currentContent;

            if (contentElement.getAttribute('data-expanded') === 'true') {
                // 收起
                const shortContent = fullContent.substring(0, 400) + (fullContent.length > 400 ? '...' : '');
                contentElement.innerHTML = escapeHtml(shortContent);
                contentElement.setAttribute('data-expanded', 'false');
            } else {
                // 展开
                contentElement.innerHTML = escapeHtml(fullContent);
                contentElement.setAttribute('data-expanded', 'true');
            }
        }
    }

    function showConversationInfo() {
        const modal = document.getElementById('conversation-modal');
        if (!modal) return;

        // 填充对话信息
        const summaryAction = conversationStats.hasSummary ?
            `<button class="btn-primary" onclick="window.viewSummaryDetail()">
                <i class="fas fa-file-alt"></i> 查看摘要
            </button>` :
            `<button class="btn-primary" onclick="window.generateConversationSummary()">
                <i class="fas fa-file-alt"></i> 生成摘要
            </button>`;

        const content = `
            <div class="conversation-info">
                <h4>对话信息</h4>
                <div class="info-grid">
                    <div class="info-item">
                        <label>会话ID:</label>
                        <span>${sessionId}</span>
                    </div>
                    <div class="info-item">
                        <label>消息数量:</label>
                        <span>${conversationStats.messageCount}</span>
                    </div>
                    <div class="info-item">
                        <label>摘要状态:</label>
                        <span>${conversationStats.hasSummary ? '已生成' : '未生成'}</span>
                    </div>
                    <div class="info-item">
                        <label>摘要版本:</label>
                        <span>${conversationStats.summaryVersion}</span>
                    </div>
                    ${conversationStats.lastSummaryTime ? `
                    <div class="info-item">
                        <label>最后生成时间:</label>
                        <span>${formatTime(conversationStats.lastSummaryTime)}</span>
                    </div>
                    ` : ''}
                </div>
                
                <div class="action-buttons">
                    ${summaryAction}
                    <button class="btn-secondary" onclick="window.startNewChat()">
                        <i class="fas fa-plus"></i> 新对话
                    </button>
                    <button class="btn-secondary" onclick="window.clearChat()">
                        <i class="fas fa-trash"></i> 清空历史
                    </button>
                </div>
                
                <div class="conversation-tips">
                    <p><i class="fas fa-info-circle"></i> 提示：</p>
                    <ul>
                        <li>当对话超过${SUMMARY_THRESHOLD}条消息时，系统会提示生成摘要</li>
                        <li>摘要会作为上下文帮助系统理解之前的对话</li>
                        <li>每${SUMMARY_REGEN_INTERVAL}条新消息后建议重新生成摘要</li>
                        <li>定期清理对话可以避免达到长度限制</li>
                    </ul>
                </div>
            </div>
        `;

        modal.querySelector('.modal-body').innerHTML = content;
        modal.style.display = 'block';
    }

    function loadSystemInfo() {
        // 尝试从WebSocket获取信息
        if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
            wsConnection.send(JSON.stringify({
                type: "get_system_info"
            }));
        } else {
            // 回退到HTTP请求
            fetch('/api/info')
            .then(response => response.json())
            .then(data => {
                modelInfoEl.textContent = data.llm_model ? (data.model_provider ? `${data.llm_model} (${data.model_provider})` : data.llm_model) : '未知';
                modeInfoEl.textContent = data.function_call_enabled ? '增强版' : '基础版';
                functionCallToggle.checked = data.function_call_enabled;
                isFunctionCallEnabled = data.function_call_enabled;

                if (data.document_count) {
                    docCountEl.textContent = data.document_count;
                }

                updateStatus('已连接', 'ready');
            })
            .catch(error => {
                console.error('加载系统信息失败:', error);
                updateStatus('连接失败', 'error');
            });
        }
    }

    function getAvatarIcon(type) {
        const icons = {
            'user': 'fa-user',
            'assistant': 'fa-robot',
            'error': 'fa-exclamation-triangle',
            'system': 'fa-info-circle',
            'tool': 'fa-cogs'
        };
        return icons[type] || 'fa-user';
    }

    function clearChat() {
        if (!confirm('确定要清空当前对话吗？这将删除所有对话历史，但保留会话ID。')) {
            return;
        }

        // 清空对话历史
        if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
            wsConnection.send(JSON.stringify({
                type: "clear_conversation",
                session_id: sessionId
            }));
        } else {
            // 使用HTTP请求
            fetch(`/api/conversation/${encodeURIComponent(sessionId)}/clear`, {
                method: 'POST'
            })
            .then(response => {
                if (response.ok) {
                    showNotification('对话历史已清空', 'info');
                    resetConversationStats();
                    updateConversationUI();
                }
            })
            .catch(error => {
                console.error('清空对话失败:', error);
            });
        }

        // 清空聊天消息（保留欢迎消息）
        const welcomeMessage = chatMessages.querySelector('.system-message');
        chatMessages.innerHTML = '';

        if (welcomeMessage) {
            chatMessages.appendChild(welcomeMessage);
        }

        currentStreamingMessage = null;
        currentSources = [];

        // 隐藏来源按钮
        if (showSourcesBtn) {
            showSourcesBtn.style.display = 'none';
        }

        showNotification('对话历史已清空，可以继续对话', 'info');
    }

    function resetConversationStats() {
        conversationStats = {
            messageCount: 0,
            hasSummary: false,
            summaryVersion: 0,
            summary: '',
            lastSummaryTime: null
        };
    }

    function startNewChat() {
        // 生成新会话ID
        const oldSessionId = sessionId;
        sessionId = generateSessionId();

        showNotification(`新对话已开始 (会话ID: ${sessionId.substring(0, 10)}...)`, 'info');

        // 清空聊天界面
        clearChat();

        // 更新对话信息
        setTimeout(() => getConversationInfo(), 500);
    }

    function showNotification(message, type = 'info') {
        // 移除现有通知
        const existingNotifications = document.querySelectorAll('.notification');
        existingNotifications.forEach(notif => notif.remove());

        // 创建新通知
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${type === 'error' ? '#ef4444' : type === 'warning' ? '#f59e0b' : type === 'info' ? '#3b82f6' : '#10b981'};
            color: white;
            padding: 12px 18px;
            border-radius: 8px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            z-index: 1001;
            font-size: 14px;
            animation: slideInRight 0.3s ease;
            display: flex;
            align-items: center;
            gap: 10px;
            max-width: 300px;
        `;

        // 添加图标
        const icon = document.createElement('i');
        icon.className = `fas ${type === 'error' ? 'fa-exclamation-circle' : type === 'warning' ? 'fa-exclamation-triangle' : 'fa-info-circle'}`;
        notification.appendChild(icon);

        // 添加文本
        const text = document.createElement('span');
        text.textContent = message;
        notification.appendChild(text);

        document.body.appendChild(notification);

        // 3秒后移除
        setTimeout(() => {
            notification.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 3000);

        // 添加动画样式（如果不存在）
        if (!document.querySelector('#notification-styles')) {
            const style = document.createElement('style');
            style.id = 'notification-styles';
            style.textContent = `
                @keyframes slideInRight {
                    from { transform: translateX(100%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
                @keyframes slideOutRight {
                    from { transform: translateX(0); opacity: 1; }
                    to { transform: translateX(100%); opacity: 0; }
                }
            `;
            document.head.appendChild(style);
        }
    }

    function showTypingIndicator() {
        typingIndicator.style.display = 'flex';
        scrollToBottom();
    }

    function hideTypingIndicator() {
        typingIndicator.style.display = 'none';
    }

    function scrollToBottom() {
        requestAnimationFrame(() => {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    }

    function adjustTextareaHeight(textarea) {
        textarea.style.height = 'auto';
        const newHeight = Math.min(textarea.scrollHeight, 120);
        textarea.style.height = newHeight + 'px';

        // 调整聊天容器高度
        if (chatMessages) {
            chatMessages.style.height = `calc(100% - ${textarea.scrollHeight + 80}px)`;
        }
    }

    function generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    function getCurrentTime() {
        return new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    }

    function formatTime(timestamp) {
        try {
            const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
            if (isNaN(date.getTime())) {
                return getCurrentTime();
            }
            return date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        } catch (e) {
            console.warn('时间格式化失败:', e);
            return getCurrentTime();
        }
    }

    function updateCurrentTime() {
        const now = new Date();
        const timeString = now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        const dateString = now.toLocaleDateString('zh-CN', {year: 'numeric', month: 'long', day: 'numeric'});

        const currentTimeEl = document.getElementById('current-time');
        if (currentTimeEl) {
            currentTimeEl.textContent = `${dateString} ${timeString}`;
        }
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 将函数暴露给全局，供内联事件使用
    window.showSourcesModal = showSourcesModal;
    window.generateConversationSummary = generateConversationSummary;
    window.startNewChat = startNewChat;
    window.clearChat = clearChat;
    window.viewSummaryDetail = viewSummaryDetail;
    window.copySourceContent = copySourceContent;
    window.toggleSourceDetail = toggleSourceDetail;
});