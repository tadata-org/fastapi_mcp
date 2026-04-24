"""
Console API Router for FastAPI-MCP.

Provides API endpoints for the web management console and serves the frontend page.
"""

import json
from typing import Any, Callable, Dict, List, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException, Request, params
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from fastapi_mcp.console.logs import LogStore, get_global_log_store
from fastapi_mcp.types import AuthConfig


class ConsoleConfig(BaseModel):
    """Configuration for the MCP Console."""

    enabled: bool = True
    mount_path: str = "/mcp-console"
    log_max_size: int = 1000
    dependencies: Optional[Sequence[params.Depends]] = None


class ToolExecuteRequest(BaseModel):
    """Request model for executing a tool."""

    arguments: Dict[str, Any] = {}


CONSOLE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MCP Console - FastAPI-MCP</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --success: #10b981;
            --error: #ef4444;
            --warning: #f59e0b;
            --bg-dark: #0f172a;
            --bg-card: #1e293b;
            --bg-hover: #334155;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --border: #475569;
            --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            min-height: 100vh;
            line-height: 1.5;
        }
        
        /* Header */
        .header {
            background: var(--bg-card);
            border-bottom: 1px solid var(--border);
            padding: 1rem 2rem;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        
        .header-content {
            max-width: 1600px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        
        .logo-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 1.25rem;
        }
        
        .logo-text h1 { font-size: 1.25rem; font-weight: 600; }
        .logo-text p { font-size: 0.75rem; color: var(--text-secondary); }
        
        .nav-tabs {
            display: flex;
            gap: 0.5rem;
        }
        
        .nav-tab {
            padding: 0.5rem 1.25rem;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.2s;
            border: none;
            background: transparent;
            color: var(--text-secondary);
        }
        
        .nav-tab:hover { background: var(--bg-hover); color: var(--text-primary); }
        .nav-tab.active { background: var(--primary); color: white; }
        
        /* Stats Bar */
        .stats-bar {
            max-width: 1600px;
            margin: 1.5rem auto;
            padding: 0 2rem;
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1rem;
        }
        
        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 1.25rem;
        }
        
        .stat-value {
            font-size: 1.75rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }
        
        .stat-label {
            font-size: 0.85rem;
            color: var(--text-secondary);
        }
        
        .stat-value.success { color: var(--success); }
        .stat-value.error { color: var(--error); }
        .stat-value.primary { color: var(--primary); }
        
        /* Main Content */
        .main-container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 0 2rem 2rem;
        }
        
        .content-section {
            display: none;
        }
        
        .content-section.active {
            display: block;
        }
        
        /* Tools Section */
        .tools-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        
        .tools-title {
            font-size: 1.1rem;
            font-weight: 600;
        }
        
        .search-box {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.6rem 1rem;
            color: var(--text-primary);
            width: 300px;
            font-size: 0.9rem;
        }
        
        .search-box:focus {
            outline: none;
            border-color: var(--primary);
        }
        
        .tool-list {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }
        
        .tool-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 10px;
            overflow: hidden;
            transition: all 0.2s;
        }
        
        .tool-card:hover {
            border-color: var(--primary);
            box-shadow: var(--shadow);
        }
        
        .tool-header {
            padding: 1rem 1.25rem;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .tool-header-left {
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        .tool-badge {
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .method-get { background: rgba(16, 185, 129, 0.2); color: var(--success); }
        .method-post { background: rgba(99, 102, 241, 0.2); color: var(--primary); }
        .method-put { background: rgba(245, 158, 11, 0.2); color: var(--warning); }
        .method-delete { background: rgba(239, 68, 68, 0.2); color: var(--error); }
        .method-patch { background: rgba(236, 72, 153, 0.2); color: #ec4899; }
        
        .tool-name {
            font-weight: 600;
            font-size: 1rem;
        }
        
        .tool-path {
            color: var(--text-secondary);
            font-size: 0.85rem;
            font-family: 'Monaco', 'Menlo', monospace;
        }
        
        .tool-summary {
            color: var(--text-secondary);
            font-size: 0.9rem;
            max-width: 400px;
        }
        
        .expand-icon {
            color: var(--text-secondary);
            transition: transform 0.2s;
        }
        
        .tool-card.expanded .expand-icon {
            transform: rotate(180deg);
        }
        
        .tool-body {
            display: none;
            border-top: 1px solid var(--border);
        }
        
        .tool-card.expanded .tool-body {
            display: block;
        }
        
        .tool-content {
            padding: 1.25rem;
        }
        
        .tool-section {
            margin-bottom: 1.25rem;
        }
        
        .tool-section:last-child {
            margin-bottom: 0;
        }
        
        .tool-section-title {
            font-size: 0.85rem;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-bottom: 0.75rem;
        }
        
        .tool-desc {
            color: var(--text-primary);
            font-size: 0.9rem;
            line-height: 1.6;
            white-space: pre-line;
        }
        
        .params-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 0.75rem;
        }
        
        .param-card {
            background: var(--bg-dark);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 0.75rem;
        }
        
        .param-header {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.25rem;
        }
        
        .param-name {
            font-weight: 600;
            font-size: 0.9rem;
        }
        
        .param-type {
            font-size: 0.75rem;
            color: var(--text-secondary);
            font-family: monospace;
        }
        
        .param-required {
            font-size: 0.7rem;
            color: var(--error);
            font-weight: 600;
        }
        
        .param-desc {
            font-size: 0.8rem;
            color: var(--text-secondary);
        }
        
        .execute-section {
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border);
        }
        
        .execute-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
        }
        
        .btn {
            padding: 0.6rem 1.25rem;
            border-radius: 6px;
            font-size: 0.9rem;
            font-weight: 500;
            cursor: pointer;
            border: none;
            transition: all 0.2s;
        }
        
        .btn-primary {
            background: var(--primary);
            color: white;
        }
        
        .btn-primary:hover { background: var(--primary-dark); }
        
        .btn-secondary {
            background: var(--bg-hover);
            color: var(--text-primary);
        }
        
        .btn-secondary:hover { background: var(--border); }
        
        .btn-danger {
            background: var(--error);
            color: white;
        }
        
        .btn-danger:hover { background: #dc2626; }
        
        .params-input-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 0.75rem;
            margin-bottom: 0.75rem;
        }
        
        .param-input-group {
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }
        
        .param-input-label {
            font-size: 0.8rem;
            color: var(--text-secondary);
            display: flex;
            gap: 0.25rem;
        }
        
        .param-input-label .required { color: var(--error); }
        
        .param-input {
            background: var(--bg-dark);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 0.5rem 0.75rem;
            color: var(--text-primary);
            font-size: 0.9rem;
        }
        
        .param-input:focus {
            outline: none;
            border-color: var(--primary);
        }
        
        .raw-json-section {
            margin-top: 0.75rem;
        }
        
        .raw-json-label {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.25rem;
        }
        
        .raw-json-label span {
            font-size: 0.8rem;
            color: var(--text-secondary);
        }
        
        .json-editor {
            width: 100%;
            min-height: 120px;
            background: var(--bg-dark);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 0.75rem;
            color: var(--text-primary);
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.85rem;
            resize: vertical;
        }
        
        .json-editor:focus {
            outline: none;
            border-color: var(--primary);
        }
        
        .execute-actions {
            display: flex;
            gap: 0.5rem;
            margin-top: 0.75rem;
        }
        
        .result-section {
            margin-top: 1rem;
        }
        
        .result-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }
        
        .result-status {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.85rem;
        }
        
        .result-status.success { color: var(--success); }
        .result-status.error { color: var(--error); }
        
        .result-duration {
            color: var(--text-secondary);
            font-size: 0.8rem;
        }
        
        .result-content {
            background: var(--bg-dark);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 1rem;
            max-height: 400px;
            overflow: auto;
        }
        
        .result-content pre {
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.85rem;
            white-space: pre-wrap;
            word-break: break-all;
        }
        
        .result-content.success { border-color: var(--success); }
        .result-content.error { border-color: var(--error); }
        
        /* Logs Section */
        .logs-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        
        .logs-actions {
            display: flex;
            gap: 0.5rem;
        }
        
        .log-list {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }
        
        .log-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 8px;
            overflow: hidden;
        }
        
        .log-header {
            padding: 0.85rem 1rem;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .log-left {
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        .log-status-badge {
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }
        
        .log-status-badge.success { background: var(--success); }
        .log-status-badge.error { background: var(--error); }
        .log-status-badge.pending { background: var(--warning); }
        
        .log-tool-name {
            font-weight: 600;
            font-size: 0.95rem;
        }
        
        .log-meta {
            display: flex;
            align-items: center;
            gap: 1rem;
            font-size: 0.8rem;
            color: var(--text-secondary);
        }
        
        .log-duration {
            background: var(--bg-dark);
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
        }
        
        .log-body {
            display: none;
            border-top: 1px solid var(--border);
        }
        
        .log-card.expanded .log-body {
            display: block;
        }
        
        .log-content {
            padding: 1rem;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }
        
        .log-section {
            background: var(--bg-dark);
            border-radius: 6px;
            padding: 0.75rem;
        }
        
        .log-section-title {
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }
        
        .log-json {
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.8rem;
            white-space: pre-wrap;
            word-break: break-all;
            max-height: 200px;
            overflow: auto;
        }
        
        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 4rem 2rem;
            color: var(--text-secondary);
        }
        
        .empty-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
        }
        
        .empty-text {
            font-size: 1rem;
            margin-bottom: 0.5rem;
        }
        
        .empty-hint {
            font-size: 0.85rem;
            color: var(--text-secondary);
        }
        
        /* Loading */
        .loading {
            display: inline-block;
            width: 14px;
            height: 14px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        /* Responsive */
        @media (max-width: 1024px) {
            .stats-bar { grid-template-columns: repeat(2, 1fr); }
            .log-content { grid-template-columns: 1fr; }
        }
        
        @media (max-width: 640px) {
            .header-content { flex-direction: column; gap: 1rem; }
            .nav-tabs { width: 100%; }
            .nav-tab { flex: 1; text-align: center; }
            .stats-bar { grid-template-columns: 1fr; }
            .tools-header { flex-direction: column; gap: 0.75rem; align-items: stretch; }
            .search-box { width: 100%; }
            .tool-header { flex-direction: column; gap: 0.5rem; align-items: flex-start; }
            .tool-header-left { flex-wrap: wrap; }
            .tool-summary { max-width: 100%; }
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="header-content">
            <div class="logo">
                <div class="logo-icon">MCP</div>
                <div class="logo-text">
                    <h1>FastAPI-MCP Console</h1>
                    <p>MCP 工具管理与调试面板</p>
                </div>
            </div>
            <div class="nav-tabs">
                <button class="nav-tab active" data-tab="tools">📋 工具列表</button>
                <button class="nav-tab" data-tab="logs">📝 调用日志</button>
            </div>
        </div>
    </header>
    
    <div class="stats-bar">
        <div class="stat-card">
            <div class="stat-value primary" id="stat-tools">0</div>
            <div class="stat-label">已注册工具</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="stat-total">0</div>
            <div class="stat-label">总调用次数</div>
        </div>
        <div class="stat-card">
            <div class="stat-value success" id="stat-success">0</div>
            <div class="stat-label">成功调用</div>
        </div>
        <div class="stat-card">
            <div class="stat-value error" id="stat-error">0</div>
            <div class="stat-label">失败调用</div>
        </div>
    </div>
    
    <main class="main-container">
        <!-- Tools Section -->
        <section id="tools-section" class="content-section active">
            <div class="tools-header">
                <span class="tools-title">已注册的 MCP 工具</span>
                <input type="text" class="search-box" id="tool-search" placeholder="搜索工具名称、路径或描述...">
            </div>
            <div class="tool-list" id="tool-list"></div>
        </section>
        
        <!-- Logs Section -->
        <section id="logs-section" class="content-section">
            <div class="logs-header">
                <span class="tools-title">工具调用日志</span>
                <div class="logs-actions">
                    <button class="btn btn-secondary" id="refresh-logs">🔄 刷新</button>
                    <button class="btn btn-danger" id="clear-logs">🗑️ 清空日志</button>
                </div>
            </div>
            <div class="log-list" id="log-list"></div>
        </section>
    </main>
    
    <script>
        const API_BASE = window.location.pathname.replace(/\\/$/, '');
        
        let tools = [];
        let operationMap = {};
        let logs = [];
        
        // Tab switching
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                
                document.querySelectorAll('.content-section').forEach(s => s.classList.remove('active'));
                document.getElementById(tab.dataset.tab + '-section').classList.add('active');
                
                if (tab.dataset.tab === 'logs') {
                    loadLogs();
                }
            });
        });
        
        // Search
        document.getElementById('tool-search').addEventListener('input', (e) => {
            filterTools(e.target.value.toLowerCase());
        });
        
        // Log actions
        document.getElementById('refresh-logs').addEventListener('click', loadLogs);
        document.getElementById('clear-logs').addEventListener('click', clearLogs);
        
        // Load initial data
        Promise.all([loadTools(), loadStats()]);
        
        async function fetchAPI(endpoint, options = {}) {
            const url = API_BASE + endpoint;
            const response = await fetch(url, {
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                }
            });
            
            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || `HTTP ${response.status}`);
            }
            
            return response.json();
        }
        
        async function loadTools() {
            try {
                const data = await fetchAPI('/api/tools');
                tools = data.tools || [];
                operationMap = data.operation_map || {};
                renderTools();
                document.getElementById('stat-tools').textContent = tools.length;
            } catch (err) {
                console.error('Failed to load tools:', err);
                showError('加载工具列表失败: ' + err.message);
            }
        }
        
        async function loadStats() {
            try {
                const stats = await fetchAPI('/api/stats');
                document.getElementById('stat-total').textContent = stats.total;
                document.getElementById('stat-success').textContent = stats.success;
                document.getElementById('stat-error').textContent = stats.error;
            } catch (err) {
                console.error('Failed to load stats:', err);
            }
        }
        
        async function loadLogs() {
            try {
                const data = await fetchAPI('/api/logs');
                logs = data.logs || [];
                renderLogs();
                loadStats();
            } catch (err) {
                console.error('Failed to load logs:', err);
            }
        }
        
        async function clearLogs() {
            if (!confirm('确定要清空所有日志吗？')) return;
            
            try {
                await fetchAPI('/api/logs', { method: 'DELETE' });
                loadLogs();
            } catch (err) {
                console.error('Failed to clear logs:', err);
                alert('清空日志失败: ' + err.message);
            }
        }
        
        function renderTools() {
            const container = document.getElementById('tool-list');
            
            if (tools.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">📦</div>
                        <div class="empty-text">暂无已注册的 MCP 工具</div>
                        <div class="empty-hint">请确保 FastAPI 应用已正确配置 MCP</div>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = tools.map(tool => {
                const op = operationMap[tool.name] || {};
                const method = op.method || 'GET';
                const path = op.path || '';
                const description = tool.description || method.toUpperCase() + ' ' + path;
                const summary = description.split('\\n')[0].substring(0, 80);
                
                return `
                    <div class="tool-card" data-tool="${escapeHtml(tool.name)}" data-method="${method.toLowerCase()}">
                        <div class="tool-header" onclick="toggleTool('${escapeHtml(tool.name)}')">
                            <div class="tool-header-left">
                                <span class="tool-badge method-${method.toLowerCase()}">${method.toUpperCase()}</span>
                                <div>
                                    <div class="tool-name">${escapeHtml(tool.name)}</div>
                                    <div class="tool-path">${escapeHtml(path)}</div>
                                </div>
                            </div>
                            <div style="display: flex; align-items: center; gap: 1rem;">
                                <div class="tool-summary">${escapeHtml(summary)}${summary.length >= 80 ? '...' : ''}</div>
                                <span class="expand-icon">▼</span>
                            </div>
                        </div>
                        <div class="tool-body">
                            <div class="tool-content">
                                ${renderToolDetails(tool, op)}
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        function renderToolDetails(tool, op) {
            const inputSchema = tool.inputSchema || {};
            const properties = inputSchema.properties || {};
            const required = inputSchema.required || [];
            
            let html = `
                <div class="tool-section">
                    <div class="tool-section-title">描述</div>
                    <div class="tool-desc">${escapeHtml(tool.description || '无描述')}</div>
                </div>
            `;
            
            if (Object.keys(properties).length > 0) {
                html += `
                    <div class="tool-section">
                        <div class="tool-section-title">参数</div>
                        <div class="params-grid">
                            ${Object.entries(properties).map(([name, schema]) => {
                                const isRequired = required.includes(name);
                                const type = schema.type || 'object';
                                const desc = schema.description || '';
                                return `
                                    <div class="param-card">
                                        <div class="param-header">
                                            <span class="param-name">${escapeHtml(name)}</span>
                                            <span class="param-type">${escapeHtml(type)}</span>
                                            ${isRequired ? '<span class="param-required">必填</span>' : ''}
                                        </div>
                                        <div class="param-desc">${escapeHtml(desc)}</div>
                                    </div>
                                `;
                            }).join('')}
                        </div>
                    </div>
                `;
            }
            
            html += `
                <div class="execute-section">
                    <div class="execute-header">
                        <div class="tool-section-title">在线调试</div>
                    </div>
                    ${renderExecuteForm(tool, op)}
                </div>
            `;
            
            return html;
        }
        
        function renderExecuteForm(tool, op) {
            const inputSchema = tool.inputSchema || {};
            const properties = inputSchema.properties || {};
            const required = inputSchema.required || [];
            
            if (Object.keys(properties).length === 0) {
                return `
                    <div class="raw-json-section">
                        <div class="raw-json-label">
                            <span>该工具无需参数</span>
                        </div>
                    </div>
                    <div class="execute-actions">
                        <button class="btn btn-primary" onclick="executeTool('${escapeHtml(tool.name)}', {})">
                            ▶️ 执行调用
                        </button>
                    </div>
                    <div id="result-${escapeHtml(tool.name)}" class="result-section" style="display: none;"></div>
                `;
            }
            
            return `
                <div class="params-input-grid">
                    ${Object.entries(properties).map(([name, schema]) => {
                        const isRequired = required.includes(name);
                        const type = schema.type || 'string';
                        const placeholder = schema.description || name;
                        const defaultVal = schema.default !== undefined ? schema.default : '';
                        
                        return `
                            <div class="param-input-group">
                                <label class="param-input-label">
                                    ${escapeHtml(name)}
                                    ${isRequired ? '<span class="required">*</span>' : ''}
                                    <span style="color: var(--text-secondary);">(${type})</span>
                                </label>
                                <input type="text" 
                                       class="param-input" 
                                       id="param-${escapeHtml(tool.name)}-${escapeHtml(name)}"
                                       placeholder="${escapeHtml(placeholder)}"
                                       value="${escapeHtml(String(defaultVal))}">
                            </div>
                        `;
                    }).join('')}
                </div>
                <div class="raw-json-section">
                    <div class="raw-json-label">
                        <span>原始 JSON（可选，覆盖表单输入）</span>
                    </div>
                    <textarea class="json-editor" id="json-${escapeHtml(tool.name)}" placeholder="{}"></textarea>
                </div>
                <div class="execute-actions">
                    <button class="btn btn-secondary" onclick="resetForm('${escapeHtml(tool.name)}')">🔄 重置</button>
                    <button class="btn btn-primary" onclick="executeToolFromForm('${escapeHtml(tool.name)}')">▶️ 执行调用</button>
                </div>
                <div id="result-${escapeHtml(tool.name)}" class="result-section" style="display: none;"></div>
            `;
        }
        
        function renderLogs() {
            const container = document.getElementById('log-list');
            
            if (logs.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">📝</div>
                        <div class="empty-text">暂无调用日志</div>
                        <div class="empty-hint">在"工具列表"中执行工具调用后，日志将显示在这里</div>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = logs.map(log => {
                const status = log.status || 'pending';
                const duration = log.duration_ms ? `${log.duration_ms.toFixed(2)}ms` : '-';
                
                return `
                    <div class="log-card" data-log="${escapeHtml(log.id)}">
                        <div class="log-header" onclick="toggleLog('${escapeHtml(log.id)}')">
                            <div class="log-left">
                                <span class="log-status-badge ${status}"></span>
                                <span class="log-tool-name">${escapeHtml(log.tool_name)}</span>
                            </div>
                            <div class="log-meta">
                                <span>${escapeHtml(log.start_datetime || '')}</span>
                                <span class="log-duration">${duration}</span>
                                <span class="expand-icon">▼</span>
                            </div>
                        </div>
                        <div class="log-body">
                            <div class="log-content">
                                <div class="log-section">
                                    <div class="log-section-title">请求参数</div>
                                    <pre class="log-json">${escapeHtml(JSON.stringify(log.arguments, null, 2))}</pre>
                                </div>
                                ${log.result ? `
                                    <div class="log-section">
                                        <div class="log-section-title">响应结果</div>
                                        <pre class="log-json">${escapeHtml(log.result)}</pre>
                                    </div>
                                ` : ''}
                                ${log.error ? `
                                    <div class="log-section">
                                        <div class="log-section-title">错误信息</div>
                                        <pre class="log-json" style="color: var(--error);">${escapeHtml(log.error)}</pre>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        function toggleTool(toolName) {
            const card = document.querySelector(`[data-tool="${escapeSelector(toolName)}"]`);
            if (card) {
                card.classList.toggle('expanded');
            }
        }
        
        function toggleLog(logId) {
            const card = document.querySelector(`[data-log="${escapeSelector(logId)}"]`);
            if (card) {
                card.classList.toggle('expanded');
            }
        }
        
        function filterTools(query) {
            document.querySelectorAll('.tool-card').forEach(card => {
                const name = card.dataset.tool.toLowerCase();
                const method = card.dataset.method.toLowerCase();
                const content = card.textContent.toLowerCase();
                
                const matches = !query || 
                    name.includes(query) || 
                    method.includes(query) ||
                    content.includes(query);
                
                card.style.display = matches ? '' : 'none';
            });
        }
        
        function resetForm(toolName) {
            const tool = tools.find(t => t.name === toolName);
            if (!tool) return;
            
            const properties = (tool.inputSchema || {}).properties || {};
            
            Object.keys(properties).forEach(name => {
                const input = document.getElementById(`param-${escapeHtml(toolName)}-${escapeHtml(name)}`);
                if (input) {
                    const defaultVal = properties[name].default !== undefined ? String(properties[name].default) : '';
                    input.value = defaultVal;
                }
            });
            
            const jsonEditor = document.getElementById(`json-${escapeHtml(toolName)}`);
            if (jsonEditor) {
                jsonEditor.value = '';
            }
            
            const resultDiv = document.getElementById(`result-${escapeHtml(toolName)}`);
            if (resultDiv) {
                resultDiv.style.display = 'none';
            }
        }
        
        function executeToolFromForm(toolName) {
            const tool = tools.find(t => t.name === toolName);
            if (!tool) {
                alert('工具未找到');
                return;
            }
            
            const properties = (tool.inputSchema || {}).properties || {};
            const required = (tool.inputSchema || {}).required || [];
            
            let args = {};
            
            const jsonEditor = document.getElementById(`json-${escapeHtml(toolName)}`);
            if (jsonEditor && jsonEditor.value.trim()) {
                try {
                    args = JSON.parse(jsonEditor.value);
                } catch (err) {
                    alert('JSON 格式错误: ' + err.message);
                    return;
                }
            } else {
                Object.entries(properties).forEach(([name, schema]) => {
                    const input = document.getElementById(`param-${escapeHtml(toolName)}-${escapeHtml(name)}`);
                    if (input && input.value.trim() !== '') {
                        const type = schema.type || 'string';
                        args[name] = parseValue(input.value, type);
                    }
                });
            }
            
            for (const req of required) {
                if (!(req in args)) {
                    alert(`缺少必填参数: ${req}`);
                    return;
                }
            }
            
            executeTool(toolName, args);
        }
        
        function parseValue(value, type) {
            if (type === 'integer') return parseInt(value, 10);
            if (type === 'number') return parseFloat(value);
            if (type === 'boolean') return value.toLowerCase() === 'true';
            if (type === 'array' || type === 'object') {
                try {
                    return JSON.parse(value);
                } catch {
                    return value;
                }
            }
            return value;
        }
        
        async function executeTool(toolName, args) {
            const resultDiv = document.getElementById(`result-${escapeHtml(toolName)}`);
            const executeBtns = document.querySelectorAll(`[onclick*="executeTool"][onclick*="${escapeSelector(toolName)}"]`);
            
            executeBtns.forEach(btn => {
                btn.disabled = true;
                btn.innerHTML = '<span class="loading"></span> 执行中...';
            });
            
            const startTime = performance.now();
            
            try {
                const result = await fetchAPI(`/api/tools/${encodeURIComponent(toolName)}/execute`, {
                    method: 'POST',
                    body: JSON.stringify({ arguments: args })
                });
                
                const duration = performance.now() - startTime;
                
                resultDiv.style.display = 'block';
                resultDiv.innerHTML = `
                    <div class="result-header">
                        <span class="result-status success">✅ 执行成功</span>
                        <span class="result-duration">耗时: ${duration.toFixed(2)}ms</span>
                    </div>
                    <div class="result-content success">
                        <pre>${escapeHtml(JSON.stringify(result, null, 2))}</pre>
                    </div>
                `;
                
                loadLogs();
                
            } catch (err) {
                const duration = performance.now() - startTime;
                
                resultDiv.style.display = 'block';
                resultDiv.innerHTML = `
                    <div class="result-header">
                        <span class="result-status error">❌ 执行失败</span>
                        <span class="result-duration">耗时: ${duration.toFixed(2)}ms</span>
                    </div>
                    <div class="result-content error">
                        <pre style="color: var(--error);">${escapeHtml(err.message)}</pre>
                    </div>
                `;
                
                loadLogs();
                
            } finally {
                executeBtns.forEach(btn => {
                    btn.disabled = false;
                    if (btn.onclick && btn.onclick.toString().includes('executeToolFromForm')) {
                        btn.innerHTML = '▶️ 执行调用';
                    } else {
                        btn.innerHTML = '▶️ 执行调用';
                    }
                });
            }
        }
        
        function escapeHtml(str) {
            if (str === null || str === undefined) return '';
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }
        
        function escapeSelector(str) {
            return str.replace(/[!"#$%&'()*+,.\\/\\\\:;<=>?@\\[\\]^`{|}~]/g, '\\\\$&');
        }
        
        function showError(message) {
            const toolsSection = document.getElementById('tools-section');
            const existing = toolsSection.querySelector('.error-banner');
            if (existing) existing.remove();
            
            const banner = document.createElement('div');
            banner.className = 'error-banner';
            banner.style.cssText = `
                background: rgba(239, 68, 68, 0.1);
                border: 1px solid var(--error);
                border-radius: 8px;
                padding: 1rem;
                margin-bottom: 1rem;
                color: var(--error);
            `;
            banner.textContent = message;
            toolsSection.insertBefore(banner, toolsSection.firstChild);
        }
    </script>
</body>
</html>
"""


def get_console_router(
    log_store: LogStore,
    tools_getter: Callable[[], List[Any]],
    operation_map_getter: Callable[[], Dict[str, Any]],
    execute_tool_callback: Callable[[str, Dict[str, Any]], Any],
    config: ConsoleConfig,
) -> APIRouter:
    """Create the console API router.

    Args:
        log_store: The log store instance
        tools_getter: Function that returns the list of tools
        operation_map_getter: Function that returns the operation map
        execute_tool_callback: Callback to execute a tool
        config: Console configuration

    Returns:
        Configured APIRouter
    """
    router = APIRouter()
    dependencies = config.dependencies or []

    @router.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def get_console_page() -> HTMLResponse:
        """Serve the console HTML page."""
        return HTMLResponse(content=CONSOLE_HTML)

    @router.get("/api/tools", include_in_schema=False, dependencies=dependencies)
    async def get_tools() -> Dict[str, Any]:
        """Get all registered MCP tools.

        Returns:
            Dictionary with tools and operation_map
        """
        tools = tools_getter()
        operation_map = operation_map_getter()

        serializable_tools = []
        for tool in tools:
            if hasattr(tool, "model_dump"):
                serializable_tools.append(tool.model_dump())
            elif hasattr(tool, "__dict__"):
                serializable_tools.append(tool.__dict__)
            else:
                serializable_tools.append(dict(tool))

        return {"tools": serializable_tools, "operation_map": operation_map}

    @router.get("/api/tools/{tool_name}", include_in_schema=False, dependencies=dependencies)
    async def get_tool(tool_name: str) -> Dict[str, Any]:
        """Get a specific tool by name.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool information
        """
        tools = tools_getter()
        operation_map = operation_map_getter()

        tool = next((t for t in tools if t.name == tool_name), None)
        if tool is None:
            raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

        tool_dict = tool.model_dump() if hasattr(tool, "model_dump") else dict(tool)
        op_info = operation_map.get(tool_name, {})

        return {"tool": tool_dict, "operation": op_info}

    @router.post("/api/tools/{tool_name}/execute", include_in_schema=False, dependencies=dependencies)
    async def execute_tool(tool_name: str, request: Request, body: ToolExecuteRequest) -> Any:
        """Execute an MCP tool.

        Args:
            tool_name: Name of the tool to execute
            request: FastAPI request object
            body: Request body containing arguments

        Returns:
            Tool execution result
        """
        tools = tools_getter()
        operation_map = operation_map_getter()

        tool = next((t for t in tools if t.name == tool_name), None)
        if tool is None:
            raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")

        op_info = operation_map.get(tool_name, {})

        log_entry = log_store.create_entry(
            tool_name=tool_name,
            arguments=body.arguments,
            method=op_info.get("method"),
            path=op_info.get("path"),
        )

        try:
            result = await execute_tool_callback(tool_name, body.arguments)
            log_entry.complete(result=result)
            return result
        except Exception as e:
            log_entry.complete(result=None, error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/api/logs", include_in_schema=False, dependencies=dependencies)
    async def get_logs(limit: Optional[int] = 100) -> Dict[str, Any]:
        """Get tool call logs.

        Args:
            limit: Maximum number of logs to return

        Returns:
            List of log entries
        """
        entries = log_store.get_all(limit=limit)
        return {"logs": [entry.to_dict() for entry in entries]}

    @router.get("/api/logs/{log_id}", include_in_schema=False, dependencies=dependencies)
    async def get_log(log_id: str) -> Dict[str, Any]:
        """Get a specific log entry by ID.

        Args:
            log_id: The log entry ID

        Returns:
            Log entry
        """
        entry = log_store.get_by_id(log_id)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"Log not found: {log_id}")
        return entry.to_dict()

    @router.delete("/api/logs", include_in_schema=False, dependencies=dependencies)
    async def clear_logs() -> Dict[str, Any]:
        """Clear all log entries.

        Returns:
            Count of cleared entries
        """
        count = log_store.clear()
        return {"cleared": count}

    @router.get("/api/stats", include_in_schema=False, dependencies=dependencies)
    async def get_stats() -> Dict[str, Any]:
        """Get statistics about tool calls.

        Returns:
            Statistics dictionary
        """
        return log_store.get_stats()

    return router
