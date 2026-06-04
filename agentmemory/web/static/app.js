/**
 * AgentMemory Dashboard - Frontend Logic
 * 使用原生 JavaScript，无框架依赖
 */

(function() {
    'use strict';

    // API Base URL
    const API_BASE = '/api';

    // State
    const state = {
        currentTab: 'memories',
        memories: {
            items: [],
            page: 1,
            pageSize: 20,
            total: 0,
            pages: 1,
            search: ''
        },
        graph: {
            entities: [],
            relations: []
        },
        stats: null
    };

    // =========================================================================
    // API Helpers
    // =========================================================================

    async function apiGet(endpoint) {
        const response = await fetch(`${API_BASE}${endpoint}`);
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        return response.json();
    }

    async function apiDelete(endpoint) {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'DELETE'
        });
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        return response.json();
    }

    // =========================================================================
    // Tab Navigation
    // =========================================================================

    function initTabs() {
        const tabBtns = document.querySelectorAll('.tab-btn');
        const tabContents = document.querySelectorAll('.tab-content');

        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const tabId = btn.dataset.tab;

                // Update buttons
                tabBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                // Update content
                tabContents.forEach(c => c.classList.remove('active'));
                document.getElementById(`tab-${tabId}`).classList.add('active');

                state.currentTab = tabId;

                // Load data for tab
                if (tabId === 'memories') loadMemories();
                else if (tabId === 'graph') loadGraph();
                else if (tabId === 'stats') loadStats();
            });
        });
    }

    // =========================================================================
    // Memories Tab
    // =========================================================================

    async function loadMemories() {
        const tbody = document.getElementById('memories-tbody');
        tbody.innerHTML = '<tr><td colspan="6" class="loading">加载中...</td></tr>';

        try {
            const params = new URLSearchParams({
                page: state.memories.page,
                page_size: state.memories.pageSize
            });
            if (state.memories.search) {
                params.append('search', state.memories.search);
            }

            const data = await apiGet(`/memories?${params}`);

            state.memories.items = data.items;
            state.memories.total = data.total;
            state.memories.pages = data.pages;

            renderMemories();
            updatePagination();
        } catch (error) {
            tbody.innerHTML = `<tr><td colspan="6" class="empty-state">加载失败: ${error.message}</td></tr>`;
            showError(error.message);
        }
    }

    function renderMemories() {
        const tbody = document.getElementById('memories-tbody');

        if (state.memories.items.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="empty-state">
                        <div class="icon">📭</div>
                        <p>暂无记忆数据</p>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = state.memories.items.map(m => `
            <tr>
                <td class="id-cell" title="${m.id}">${truncate(m.id, 8)}</td>
                <td title="${escapeHtml(m.content)}">${escapeHtml(truncate(m.content, 50))}</td>
                <td>${renderImportance(m.importance)}</td>
                <td>${m.fact_type || '-'}</td>
                <td>${formatDate(m.created_at)}</td>
                <td>
                    <button class="btn btn-secondary" onclick="showMemoryDetail('${m.id}')">详情</button>
                    <button class="btn btn-danger" onclick="deleteMemory('${m.id}')">删除</button>
                </td>
            </tr>
        `).join('');
    }

    function renderImportance(value) {
        let badgeClass = 'importance-low';
        let text = '低';

        if (value >= 0.7) {
            badgeClass = 'importance-high';
            text = '高';
        } else if (value >= 0.4) {
            badgeClass = 'importance-medium';
            text = '中';
        }

        return `<span class="importance-badge ${badgeClass}">${text} ${(value * 100).toFixed(0)}%</span>`;
    }

    function updatePagination() {
        const pageInfo = document.getElementById('page-info');
        pageInfo.textContent = `第 ${state.memories.page} 页 / 共 ${state.memories.pages} 页 (共 ${state.memories.total} 条)`;

        document.getElementById('prev-page').disabled = state.memories.page <= 1;
        document.getElementById('next-page').disabled = state.memories.page >= state.memories.pages;
    }

    function initMemoriesHandlers() {
        // Search
        const searchInput = document.getElementById('search-input');
        const searchBtn = document.getElementById('search-btn');

        searchBtn.addEventListener('click', () => {
            state.memories.search = searchInput.value.trim();
            state.memories.page = 1;
            loadMemories();
        });

        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                state.memories.search = searchInput.value.trim();
                state.memories.page = 1;
                loadMemories();
            }
        });

        // Pagination
        document.getElementById('prev-page').addEventListener('click', () => {
            if (state.memories.page > 1) {
                state.memories.page--;
                loadMemories();
            }
        });

        document.getElementById('next-page').addEventListener('click', () => {
            if (state.memories.page < state.memories.pages) {
                state.memories.page++;
                loadMemories();
            }
        });

        // Close detail panel
        document.getElementById('close-detail').addEventListener('click', () => {
            document.getElementById('memory-detail').classList.add('hidden');
        });
    }

    // Global functions for inline handlers
    window.showMemoryDetail = async function(memoryId) {
        try {
            const memory = await apiGet(`/memories/${memoryId}`);
            const content = document.getElementById('memory-detail-content');

            content.innerHTML = `
                <div class="detail-item">
                    <div class="detail-label">ID</div>
                    <div class="detail-value">${memory.id}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">内容</div>
                    <div class="detail-value">${escapeHtml(memory.content)}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">重要性</div>
                    <div class="detail-value">${renderImportance(memory.importance)}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">类型</div>
                    <div class="detail-value">${memory.fact_type || '-'}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">标签</div>
                    <div class="detail-value">${(memory.tags || []).join(', ') || '-'}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">创建时间</div>
                    <div class="detail-value">${formatDate(memory.created_at)}</div>
                </div>
                ${memory.metadata ? `
                <div class="detail-item">
                    <div class="detail-label">元数据</div>
                    <div class="detail-value"><pre>${JSON.stringify(memory.metadata, null, 2)}</pre></div>
                </div>
                ` : ''}
            `;

            document.getElementById('memory-detail').classList.remove('hidden');
        } catch (error) {
            showError(error.message);
        }
    };

    window.deleteMemory = async function(memoryId) {
        if (!confirm(`确定要删除记忆 ${memoryId} 吗？`)) return;

        try {
            await apiDelete(`/memories/${memoryId}`);
            showError('记忆已删除');
            loadMemories();
        } catch (error) {
            showError(error.message);
        }
    };

    // =========================================================================
    // Graph Tab
    // =========================================================================

    async function loadGraph() {
        const entitiesContainer = document.getElementById('entities-container');
        const relationsContainer = document.getElementById('relations-container');

        entitiesContainer.innerHTML = '<div class="loading">加载中...</div>';
        relationsContainer.innerHTML = '<div class="loading">加载中...</div>';

        try {
            const [entitiesData, relationsData] = await Promise.all([
                apiGet('/graph/entities'),
                apiGet('/graph/relations')
            ]);

            state.graph.entities = entitiesData.items;
            state.graph.relations = relationsData.items;

            renderEntities(entitiesContainer, entitiesData);
            renderRelations(relationsContainer, relationsData);
        } catch (error) {
            entitiesContainer.innerHTML = `<div class="error">加载失败: ${error.message}</div>`;
            relationsContainer.innerHTML = `<div class="error">加载失败: ${error.message}</div>`;
            showError(error.message);
        }
    }

    function renderEntities(container, data) {
        if (data.items.length === 0) {
            container.innerHTML = '<div class="empty-state">暂无实体</div>';
            return;
        }

        container.innerHTML = data.items.map(e => `
            <div class="entity-tag">
                ${escapeHtml(e.name)}
                <span class="type">(${e.type})</span>
            </div>
        `).join('');
    }

    function renderRelations(container, data) {
        if (data.items.length === 0) {
            container.innerHTML = '<div class="empty-state">暂无关系</div>';
            return;
        }

        container.innerHTML = data.items.map(r => `
            <div class="relation-item">
                <span class="source">${truncate(r.source, 8)}</span>
                <span class="arrow">→</span>
                <span class="type">${r.type}</span>
                <span class="arrow">→</span>
                <span class="target">${truncate(r.target, 8)}</span>
            </div>
        `).join('');
    }

    // =========================================================================
    // Stats Tab
    // =========================================================================

    async function loadStats() {
        const container = document.getElementById('stats-container');
        container.innerHTML = '<div class="loading">加载中...</div>';

        try {
            const stats = await apiGet('/stats');
            state.stats = stats;
            renderStats(container, stats);
        } catch (error) {
            container.innerHTML = `<div class="error">加载失败: ${error.message}</div>`;
            showError(error.message);
        }
    }

    function renderStats(container, stats) {
        const layers = stats.layers || {};
        const graph = stats.graph || {};
        const vector = stats.vector || {};

        container.innerHTML = `
            <div class="stats-card">
                <h3>📦 存储层状态</h3>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-label">L1 压缩</div>
                        <div class="stat-value">${layers.l1_compress ? '✓' : '✗'}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">L2 图谱</div>
                        <div class="stat-value">${layers.l2_graph ? '✓' : '✗'}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">L3 向量</div>
                        <div class="stat-value">${layers.l3_vector ? '✓' : '✗'}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">L4 文件</div>
                        <div class="stat-value">${layers.l4_files ? '✓' : '✗'}</div>
                    </div>
                </div>
            </div>
            
            <div class="stats-card">
                <h3>🔷 实体统计</h3>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-label">实体数量</div>
                        <div class="stat-value">${graph.total || 0}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">关系数量</div>
                        <div class="stat-value">${graph.relations || 0}</div>
                    </div>
                </div>
            </div>
            
            <div class="stats-card">
                <h3>🔶 向量存储统计</h3>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-label">记忆总数</div>
                        <div class="stat-value">${vector.total || 0}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">向量维度</div>
                        <div class="stat-value">${vector.dimensions || '-'}</div>
                    </div>
                </div>
            </div>
            
            <div class="stats-card">
                <h3>⚙️ 系统配置</h3>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-label">遗忘引擎</div>
                        <div class="stat-value">${layers.decay ? '✓' : '✗'}</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">LLM Provider</div>
                        <div class="stat-value">${layers.llm_provider || '-'}</div>
                    </div>
                </div>
            </div>
        `;
    }

    // =========================================================================
    // Utilities
    // =========================================================================

    function truncate(str, maxLength) {
        if (!str) return '';
        return str.length > maxLength ? str.substring(0, maxLength) + '...' : str;
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatDate(dateStr) {
        if (!dateStr) return '-';
        try {
            const date = new Date(dateStr);
            return date.toLocaleString('zh-CN');
        } catch {
            return dateStr;
        }
    }

    function showError(message) {
        const toast = document.getElementById('error-toast');
        toast.textContent = message;
        toast.classList.remove('hidden');
        setTimeout(() => {
            toast.classList.add('hidden');
        }, 3000);
    }

    // =========================================================================
    // Initialize
    // =========================================================================

    function init() {
        initTabs();
        initMemoriesHandlers();
        loadMemories(); // Load initial tab
    }

    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
