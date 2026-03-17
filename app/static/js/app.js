/* DocAnalystAgent — main UI logic */
'use strict';

// ── State ──────────────────────────────────────────────
const state = {
  sessionId: null,
  filename: null,
  totalPages: null,
  hasAnalysis: false,
  hasTranslation: false,
  chatStreaming: false,
  suggestionsData: [],
  questionsData: [],
  currentFilter: { suggestions: 'all', questions: 'all' },
};

// ── DOM refs ────────────────────────────────────────────
const $ = id => document.getElementById(id);
const uploadZone = $('upload-zone');
const fileInput = $('file-input');
const docInfo = $('doc-info');
const btnAnalyze = $('btn-analyze');
const btnTranslate = $('btn-translate');
const btnClear = $('btn-clear');
const loadingOverlay = $('loading-overlay');
const loadingText = $('loading-text');
const loadingSub = $('loading-sub');

// ── Toast ───────────────────────────────────────────────
function toast(msg, type = 'info') {
  const c = $('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  c.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

// ── Loading ─────────────────────────────────────────────
function showLoading(text, sub = '') {
  loadingText.textContent = text;
  loadingSub.textContent = sub;
  loadingOverlay.classList.add('visible');
}
function hideLoading() { loadingOverlay.classList.remove('visible'); }

// ── Tab navigation ──────────────────────────────────────
document.querySelectorAll('.nav-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    const target = tab.dataset.panel;
    const panel = $(target + '-panel');
    if (panel) panel.classList.add('active');
  });
});

function switchTab(name) {
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  const tab = document.querySelector(`.nav-tab[data-panel="${name}"]`);
  if (tab) tab.classList.add('active');
  const panel = $(name + '-panel');
  if (panel) panel.classList.add('active');
}

// ── Upload ──────────────────────────────────────────────
uploadZone.addEventListener('click', () => fileInput.click());
uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('drag-over'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  uploadZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) uploadFile(file);
});
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) uploadFile(fileInput.files[0]);
});

async function uploadFile(file) {
  showLoading('Uploading document...', 'Extracting text content');
  const form = new FormData();
  form.append('file', file);
  try {
    const res = await fetch('/api/upload', { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Upload failed');
    }
    const data = await res.json();
    state.sessionId = data.session_id;
    state.filename = data.filename;
    state.totalPages = data.total_pages;
    state.hasAnalysis = false;
    state.hasTranslation = false;

    // Update UI
    docInfo.classList.add('visible');
    $('doc-name').textContent = data.filename;
    $('doc-pages').textContent = `${data.total_pages} page(s) extracted`;
    btnAnalyze.disabled = false;
    btnTranslate.disabled = false;
    btnClear.disabled = false;
    updateCounts(null, null);
    resetPanels();
    switchTab('welcome');
    toast(`"${data.filename}" uploaded successfully`, 'success');
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    hideLoading();
    fileInput.value = '';
  }
}

// ── Analyze ─────────────────────────────────────────────
btnAnalyze.addEventListener('click', async () => {
  if (!state.sessionId) return;
  showLoading('Analyzing document...', 'Running AI analysis (summary + suggestions + questions)');
  try {
    const res = await fetch(`/api/analyze/${state.sessionId}`, { method: 'POST' });
    if (!res.ok) throw new Error('Analysis failed');
    const data = await res.json();
    state.hasAnalysis = true;
    state.suggestionsData = data.suggestions || [];
    state.questionsData = data.questions || [];
    renderSummary(data.summary);
    renderSuggestions(data.suggestions);
    renderQuestions(data.questions);
    updateCounts(data.suggestions.length, data.questions.length);
    switchTab('summary');
    toast('Analysis complete', 'success');
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    hideLoading();
  }
});

// ── Translate ────────────────────────────────────────────
btnTranslate.addEventListener('click', async () => {
  if (!state.sessionId) return;
  showLoading('Translating to Chinese...', 'This may take a moment for long documents');
  try {
    const res = await fetch(`/api/translate/${state.sessionId}`, { method: 'POST' });
    if (!res.ok) throw new Error('Translation failed');
    const data = await res.json();
    state.hasTranslation = true;
    renderTranslation(data.translation);
    switchTab('translation');
    toast('Translation complete', 'success');
  } catch (e) {
    toast(e.message, 'error');
  } finally {
    hideLoading();
  }
});

// ── Clear ─────────────────────────────────────────────
btnClear.addEventListener('click', async () => {
  if (!state.sessionId) return;
  await fetch(`/api/session/${state.sessionId}`, { method: 'DELETE' });
  state.sessionId = null;
  state.filename = null;
  state.hasAnalysis = false;
  state.hasTranslation = false;
  docInfo.classList.remove('visible');
  btnAnalyze.disabled = true;
  btnTranslate.disabled = true;
  btnClear.disabled = true;
  resetPanels();
  updateCounts(null, null);
  switchTab('welcome');
  toast('Session cleared');
});

// ── Reset panels ─────────────────────────────────────────
function resetPanels() {
  $('summary-body').innerHTML = '<div class="empty-state"><div class="icon">📋</div><p>Run analysis to see summary</p></div>';
  $('suggestions-body').innerHTML = '<div class="empty-state"><div class="icon">💡</div><p>Run analysis to see suggestions</p></div>';
  $('questions-body').innerHTML = '<div class="empty-state"><div class="icon">❓</div><p>Run analysis to see questions</p></div>';
  $('translation-body').innerHTML = '<div class="empty-state"><div class="icon">🌐</div><p>Click "Translate to Chinese" to see translation</p></div>';
  $('chat-messages').innerHTML = '<div class="msg assistant"><div class="msg-avatar">🤖</div><div class="msg-bubble">Hello! Upload a document and I\'ll help you analyze it. Ask me anything about the document content, suggestions, or questions.</div></div>';
}

function updateCounts(suggestions, questions) {
  $('suggestions-count').textContent = suggestions !== null ? suggestions : '';
  $('questions-count').textContent = questions !== null ? questions : '';
}

// ── Render Summary ───────────────────────────────────────
function renderSummary(s) {
  if (!s) return;
  const html = `
    <div class="summary-card">
      <h3>Document Overview</h3>
      <div class="meta-grid">
        <div class="meta-item"><label>Title</label><span>${esc(s.title || 'Unknown')}</span></div>
        <div class="meta-item"><label>Type</label><span>${esc(s.document_type || '—')}</span></div>
        <div class="meta-item"><label>Language</label><span>${esc(s.language || '—')}</span></div>
        <div class="meta-item"><label>Pages</label><span>${s.total_pages || '—'}</span></div>
        <div class="meta-item"><label>Tone</label><span>${esc(s.tone || '—')}</span></div>
        <div class="meta-item"><label>Completeness</label><span>${esc(s.completeness || '—')}</span></div>
      </div>
    </div>
    <div class="summary-card">
      <h3>Executive Summary</h3>
      <div class="exec-summary">${esc(s.executive_summary || '')}</div>
      <div class="exec-summary-zh">${esc(s.executive_summary_zh || '')}</div>
    </div>
    <div class="summary-card">
      <h3>Key Points</h3>
      <ul class="key-points-list">
        ${(s.key_points || []).map(k => `
          <li class="key-point-item">
            <span class="kp-loc">P${k.page}</span>
            <span class="kp-text">${esc(k.point)}</span>
          </li>`).join('')}
      </ul>
    </div>
    <div class="summary-card">
      <h3>Main Topics</h3>
      <div class="topics">
        ${(s.main_topics || []).map(t => `<span class="topic-tag">${esc(t)}</span>`).join('')}
      </div>
    </div>
  `;
  $('summary-body').innerHTML = html;
}

// ── Render Suggestions ──────────────────────────────────
function renderSuggestions(items, filter = 'all') {
  const filterBar = `
    <div class="filter-bar">
      ${['all','high','medium','low'].map(f => `
        <button class="filter-btn ${filter === f ? 'active' : ''}" onclick="filterSuggestions('${f}')">${f === 'all' ? 'All' : f.charAt(0).toUpperCase()+f.slice(1)}</button>
      `).join('')}
      ${['clarity','accuracy','completeness','structure','logic','tone','evidence'].map(f => `
        <button class="filter-btn ${filter === f ? 'active' : ''}" onclick="filterSuggestions('${f}')">${f}</button>
      `).join('')}
    </div>`;

  const filtered = filter === 'all' ? items : items.filter(i =>
    i.severity === filter || i.type === filter
  );

  if (filtered.length === 0) {
    $('suggestions-body').innerHTML = filterBar + '<div class="empty-state"><div class="icon">✅</div><p>No suggestions match this filter</p></div>';
    return;
  }

  const cards = filtered.map((s, idx) => `
    <div class="item-card" id="sug-${s.id}">
      <div class="item-header" onclick="toggleCard('sug-${s.id}')">
        <span class="item-num">#${s.id}</span>
        <span class="item-badge badge-${s.severity}">${s.severity}</span>
        <span class="item-badge badge-type">${s.type}</span>
        <div class="item-loc">
          <span class="loc-chip" onclick="event.stopPropagation(); scrollToRef(${s.page}, '${esc(s.section)}')" title="Go to location">P${s.page} · ${esc(s.section || '').slice(0,20)}${(s.section||'').length>20?'…':''} · L${s.line||'?'}</span>
        </div>
        <span class="item-arrow">▶</span>
      </div>
      <div class="item-body">
        <div class="item-section">
          <label>Suggestion</label>
          <div class="content">${esc(s.suggestion)}</div>
          <div class="content zh">${esc(s.suggestion_zh)}</div>
        </div>
        ${s.original_text ? `<div class="item-section"><label>Original Text</label><div class="orig-text">${esc(s.original_text)}</div></div>` : ''}
        <div class="item-section">
          <label>Rationale</label>
          <div class="content">${esc(s.rationale)}</div>
        </div>
      </div>
    </div>`).join('');

  $('suggestions-body').innerHTML = filterBar + `<div class="item-list">${cards}</div>`;
}

// ── Render Questions ──────────────────────────────────────
function renderQuestions(items, filter = 'all') {
  const categories = ['assumption','evidence','completeness','consistency','feasibility','stakeholder','risk','methodology'];
  const filterBar = `
    <div class="filter-bar">
      ${['all','high','medium','low'].map(f => `
        <button class="filter-btn ${filter === f ? 'active' : ''}" onclick="filterQuestions('${f}')">${f === 'all' ? 'All' : f.charAt(0).toUpperCase()+f.slice(1)}</button>
      `).join('')}
      ${categories.map(f => `
        <button class="filter-btn ${filter === f ? 'active' : ''}" onclick="filterQuestions('${f}')">${f}</button>
      `).join('')}
    </div>`;

  const filtered = filter === 'all' ? items : items.filter(i =>
    i.importance === filter || i.category === filter
  );

  if (filtered.length === 0) {
    $('questions-body').innerHTML = filterBar + '<div class="empty-state"><div class="icon">💬</div><p>No questions match this filter</p></div>';
    return;
  }

  const cards = filtered.map(q => `
    <div class="item-card" id="que-${q.id}">
      <div class="item-header" onclick="toggleCard('que-${q.id}')">
        <span class="item-num">#${q.id}</span>
        <span class="item-badge badge-${q.importance}">${q.importance}</span>
        <span class="item-badge badge-cat">${q.category}</span>
        <div class="item-loc">
          <span class="loc-chip" onclick="event.stopPropagation(); scrollToRef(${q.page}, '${esc(q.section)}')" title="Go to location">P${q.page} · ${esc(q.section || '').slice(0,20)}${(q.section||'').length>20?'…':''} · L${q.line||'?'}</span>
        </div>
        <span class="item-arrow">▶</span>
      </div>
      <div class="item-body">
        <div class="item-section">
          <label>Question</label>
          <div class="content">${esc(q.question)}</div>
          <div class="content zh">${esc(q.question_zh)}</div>
        </div>
        <div class="item-section">
          <label>Why This Matters</label>
          <div class="content">${esc(q.context)}</div>
        </div>
        <div class="item-section">
          <button class="btn btn-outline" style="padding:6px 12px;font-size:12px" onclick="askInChat('${esc(q.question)}')">Ask in Chat ↗</button>
        </div>
      </div>
    </div>`).join('');

  $('questions-body').innerHTML = filterBar + `<div class="item-list">${cards}</div>`;
}

// ── Render Translation ───────────────────────────────────
function renderTranslation(text) {
  // Highlight page markers
  const html = text
    .split('\n')
    .map(line => {
      if (line.match(/^=== (PAGE|页|第) /i)) {
        return `<div class="page-marker">${esc(line)}</div>`;
      }
      return esc(line);
    })
    .join('\n');
  $('translation-body').innerHTML = `<div class="translation-content">${html}</div>`;
}

// ── Filter helpers ───────────────────────────────────────
window.filterSuggestions = (f) => {
  state.currentFilter.suggestions = f;
  renderSuggestions(state.suggestionsData, f);
};
window.filterQuestions = (f) => {
  state.currentFilter.questions = f;
  renderQuestions(state.questionsData, f);
};

// ── Card toggle ──────────────────────────────────────────
window.toggleCard = (id) => {
  const card = document.getElementById(id);
  if (card) card.classList.toggle('expanded');
};

// ── Scroll to reference (opens translation tab with scroll) ──
window.scrollToRef = (page, section) => {
  toast(`Navigating to Page ${page}${section ? ', Section: ' + section : ''}`);
  if (state.hasTranslation) {
    switchTab('translation');
    setTimeout(() => {
      const markers = document.querySelectorAll('.page-marker');
      markers.forEach(m => {
        if (m.textContent.includes(`PAGE ${page}`)) {
          m.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    }, 100);
  }
};

// ── Ask in chat ───────────────────────────────────────────
window.askInChat = (question) => {
  switchTab('chat');
  const input = $('chat-input');
  input.value = question;
  input.focus();
};

// ── Chat ──────────────────────────────────────────────────
const chatInput = $('chat-input');
const chatSend = $('chat-send');
const chatMessages = $('chat-messages');

chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendChat();
  }
});
chatSend.addEventListener('click', sendChat);
chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
});

async function sendChat() {
  const msg = chatInput.value.trim();
  if (!msg || state.chatStreaming) return;
  if (!state.sessionId) {
    toast('Please upload a document first', 'error');
    return;
  }

  appendMsg('user', msg);
  chatInput.value = '';
  chatInput.style.height = 'auto';

  const typingId = appendTyping();
  state.chatStreaming = true;
  chatSend.disabled = true;

  let assistantBubble = null;
  let fullText = '';

  try {
    const res = await fetch(`/api/chat/${state.sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const payload = line.slice(6).trim();
        if (payload === '[DONE]') break;
        try {
          const obj = JSON.parse(payload);
          if (obj.text) {
            fullText += obj.text;
            if (!assistantBubble) {
              removeTyping(typingId);
              assistantBubble = appendMsg('assistant', '');
            }
            assistantBubble.querySelector('.msg-bubble').innerHTML = renderMarkdown(fullText);
            chatMessages.scrollTop = chatMessages.scrollHeight;
          }
        } catch {}
      }
    }
  } catch (e) {
    removeTyping(typingId);
    appendMsg('assistant', 'Sorry, an error occurred. Please try again.');
    toast(e.message, 'error');
  } finally {
    state.chatStreaming = false;
    chatSend.disabled = false;
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
}

function appendMsg(role, text) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.innerHTML = `
    <div class="msg-avatar">${role === 'user' ? '👤' : '🤖'}</div>
    <div class="msg-bubble">${role === 'user' ? esc(text) : renderMarkdown(text)}</div>
  `;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return div;
}

function appendTyping() {
  const id = 'typing-' + Date.now();
  const div = document.createElement('div');
  div.className = 'msg assistant';
  div.id = id;
  div.innerHTML = `<div class="msg-avatar">🤖</div><div class="msg-bubble"><div class="typing-dots"><span></span><span></span><span></span></div></div>`;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return id;
}

function removeTyping(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

// ── Simple markdown renderer ─────────────────────────────
function renderMarkdown(text) {
  return esc(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');
}

// ── HTML escaping ─────────────────────────────────────────
function esc(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
