// DYLIGHT Bridge Research Lab — Visual Dashboard Core Application

(function() {
  'use strict';

  let labData = window.LAB_INITIAL_DATA || { tasks: {}, handoffs: [], reviews: [], runs: {}, providers: {} };
  let activeFilter = 'ALL';
  let searchQuery = '';

  // Parametric Bridge Section State
  const girderParams = {
    type: 'v2', // 'v1', 'v2', 'michell'
    H: 1750,      // Total height (mm)
    B_top: 2150,  // Top flange width (mm)
    t_top: 100,   // Top flange thickness (mm)
    t_web: 120,   // Web thickness (mm)
    B_bot: 750,   // Bottom flange width (mm)
    H_bulb: 280,  // Bulb / bottom flange height (mm)
    t_deck: 200,  // Slab thickness (mm)
    strands: 34,  // Number of prestressing strands
    fc: 60,       // Concrete strength (MPa)
  };

  // Michell Bridge State
  const michellParams = {
    span: 480,       // meters
    h_pier: 28,      // meters
    h_mid: 9,        // meters
    theta: 45,       // degrees
    cfrp_stress: 1400 // MPa
  };

  // Initialize App
  function init() {
    setupNavigation();
    renderStats();
    renderAgentStatus();
    renderTaskBoard();
    renderAuditStream();
    renderClaimsRegister();
    renderParetoChart();
    initParametricViewer();
    setupEventListeners();
    fetchLiveData();
  }

  // Fetch live API if server is running
  async function fetchLiveData() {
    try {
      const res = await fetch('/api/live-data');
      if (res.ok) {
        labData = await res.json();
        renderStats();
        renderAgentStatus();
        renderTaskBoard();
        renderAuditStream();
        renderClaimsRegister();
      }
    } catch (e) {
      // Offline fallback: uses LAB_INITIAL_DATA
      console.log('Using static embedded lab data');
    }
  }

  // Setup Navigation Tabs
  function setupNavigation() {
    const tabs = document.querySelectorAll('.nav-tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        
        tab.classList.add('active');
        const targetId = tab.getAttribute('data-tab');
        const targetPanel = document.getElementById(targetId);
        if (targetPanel) {
          targetPanel.classList.add('active');
          if (targetId === 'tab-geometry') {
            drawCrossSection();
          } else if (targetId === 'tab-pareto') {
            drawParetoCanvas();
          }
        }
      });
    });
  }

  // Render Stats
  function renderStats() {
    const tasks = Object.values(labData.tasks || {});
    const total = tasks.length;
    const accepted = tasks.filter(t => t.status === 'ACCEPTED').length;
    const inReview = tasks.filter(t => t.status === 'REVIEW').length;
    const active = tasks.filter(t => t.status === 'ACTIVE').length;
    const ready = tasks.filter(t => t.status === 'READY').length;

    document.getElementById('stat-total-tasks').textContent = total;
    document.getElementById('stat-review-tasks').textContent = inReview;
    document.getElementById('stat-accepted-tasks').textContent = accepted;
    document.getElementById('stat-active-ready').textContent = `${active} / ${ready}`;
  }

  // Render Agent Status
  function renderAgentStatus() {
    const container = document.getElementById('agent-ribbon');
    if (!container) return;
    const providers = labData.providers || {
      codex: { status: 'ONLINE', role: 'Reviewer' },
      claude: { status: 'ONLINE', role: 'Proposer' },
      antigravity: { status: 'ACTIVE', role: 'Orchestrator' },
      opencode: { status: 'STANDBY', role: 'Reproducer' }
    };

    container.innerHTML = Object.entries(providers).map(([name, info]) => {
      let dotClass = 'online';
      if (info.status === 'REVIEWING') dotClass = 'reviewing';
      if (info.status === 'ACTIVE') dotClass = 'active';
      if (info.status === 'STANDBY') dotClass = 'standby';

      return `
        <div class="agent-badge" title="${info.role} (${info.version || ''})">
          <div class="agent-dot ${dotClass}"></div>
          <span style="font-weight:600; text-transform:capitalize;">${name}</span>
          <span style="font-size:0.7rem; color:var(--text-dim);">${info.status}</span>
        </div>
      `;
    }).join('');
  }

  // Render Tasks
  function renderTaskBoard() {
    const container = document.getElementById('tasks-container');
    if (!container) return;

    let tasks = Object.values(labData.tasks || {});
    
    // Apply status filter
    if (activeFilter !== 'ALL') {
      tasks = tasks.filter(t => t.status === activeFilter);
    }

    // Apply search filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      tasks = tasks.filter(t => 
        t.task_id.toLowerCase().includes(q) ||
        t.title.toLowerCase().includes(q) ||
        (t.research_question && t.research_question.toLowerCase().includes(q)) ||
        (t.owner && t.owner.toLowerCase().includes(q))
      );
    }

    if (tasks.length === 0) {
      container.innerHTML = `<div style="grid-column: 1/-1; text-align:center; padding:3rem; color:var(--text-dim);">Không có task nào phù hợp bộ lọc.</div>`;
      return;
    }

    container.innerHTML = tasks.map(task => {
      const gates = (task.required_gates || []).map(g => `<span class="gate-pill">${g}</span>`).join('');
      const owner = task.owner ? `<span class="role-tag" style="color:#38bdf8;">👤 ${task.owner}</span>` : `<span class="role-tag">Unclaimed</span>`;
      const reviewer = task.reviewer || task.review_provider ? `<span class="role-tag" style="color:#fbbf24;">🔍 ${task.reviewer || task.review_provider}</span>` : '';

      return `
        <div class="task-item" onclick="window.showTaskModal('${task.task_id}')">
          <div>
            <div class="task-top">
              <span class="task-id">${task.task_id}</span>
              <span class="status-badge status-${task.status}">${task.status}</span>
            </div>
            <div class="task-title">${task.title}</div>
            <div class="task-question">${task.research_question || ''}</div>
          </div>
          <div class="task-footer">
            <div class="task-roles">
              ${owner}
              ${reviewer}
            </div>
            <div class="gates-list">
              ${gates}
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  // Render Audit Log Stream
  function renderAuditStream() {
    const container = document.getElementById('audit-stream');
    if (!container) return;

    const handoffs = labData.handoffs || [];
    const reviews = labData.reviews || [];

    // Combine and sort by date/id
    const feed = [];

    handoffs.forEach(h => {
      feed.push({
        type: 'HANDOFF',
        task_id: h.task_id,
        agent: h.agent_id,
        role: h.role,
        summary: h.summary,
        hash: (h.artifacts && h.artifacts[0]) ? h.artifacts[0].sha256 : 'N/A',
        gates: h.gates_completed || [],
        claim: h.claim_level,
        raw: h
      });
    });

    reviews.forEach(r => {
      feed.push({
        type: 'REVIEW',
        task_id: r.task_id,
        agent: r.reviewer_id,
        decision: r.decision,
        summary: r.notes,
        hash: r.handoff_sha256 || 'N/A',
        findings: r.gate_findings || [],
        raw: r
      });
    });

    if (feed.length === 0) {
      container.innerHTML = `<div style="color:var(--text-dim); text-align:center; padding:2rem;">Chưa có bản ghi audit nào.</div>`;
      return;
    }

    container.innerHTML = feed.map(item => {
      if (item.type === 'HANDOFF') {
        return `
          <div class="audit-entry">
            <div class="audit-header">
              <div style="display:flex; align-items:center; gap:0.6rem;">
                <span class="audit-badge HANDOFF">HANDOFF SUBMITTED</span>
                <strong style="color:#fff;">${item.task_id}</strong>
                <span style="font-size:0.75rem; color:var(--text-dim);">bởi <strong>${item.agent}</strong> (${item.role})</span>
              </div>
              <span class="audit-hash" title="Artifact SHA-256 (Click to view)" onclick="navigator.clipboard.writeText('${item.hash}'); alert('Copied SHA-256: ${item.hash}')">
                🔑 ${item.hash.substring(0, 12)}...
              </span>
            </div>
            <div class="audit-summary">${item.summary}</div>
            <div style="margin-top:0.5rem; display:flex; gap:0.5rem;">
              <span class="role-tag">Claim: ${item.claim}</span>
              ${item.gates.map(g => `<span class="gate-pill">${g}</span>`).join('')}
            </div>
          </div>
        `;
      } else {
        const badgeClass = item.decision === 'APPROVE' ? 'APPROVE' : 'REVISE';
        const findingsHtml = (item.findings || []).map(f => `
          <div style="margin-top:0.25rem;">
            <strong style="color:${f.status === 'PASS' ? '#34d399' : '#f87171'}">${f.gate} ${f.status}:</strong> 
            <span style="color:var(--text-muted);">${f.evidence}</span>
          </div>
        `).join('');

        return `
          <div class="audit-entry" style="border-left: 3px solid ${item.decision === 'APPROVE' ? 'var(--success)' : 'var(--danger)'};">
            <div class="audit-header">
              <div style="display:flex; align-items:center; gap:0.6rem;">
                <span class="audit-badge ${badgeClass}">${item.decision}</span>
                <strong style="color:#fff;">${item.task_id}</strong>
                <span style="font-size:0.75rem; color:var(--text-dim);">thẩm định bởi <strong>${item.agent}</strong></span>
              </div>
              <span class="audit-hash" title="Target Handoff SHA-256">
                🔑 ${item.hash.substring(0, 12)}...
              </span>
            </div>
            <div class="audit-summary"><strong>Reviewer Notes:</strong> ${item.summary}</div>
            ${findingsHtml ? `<div class="audit-findings">${findingsHtml}</div>` : ''}
          </div>
        `;
      }
    }).join('');
  }

  // Render Claims Register (BRD-005)
  function renderClaimsRegister() {
    const container = document.getElementById('claims-register-container');
    if (!container) return;
    const text = labData.claims_register_md || '';
    if (!text) {
      container.innerHTML = `<div style="color:var(--text-dim);">Đang cập nhật sổ đăng ký claim...</div>`;
      return;
    }
    // Simple markdown to html rendering
    let html = text
      .replace(/^# (.*$)/gim, '<h2 style="color:#fff; margin-bottom:0.75rem; font-size:1.3rem;">$1</h2>')
      .replace(/^## (.*$)/gim, '<h3 style="color:var(--primary); margin:1.25rem 0 0.5rem; font-size:1.05rem;">$1</h3>')
      .replace(/\*\*(.*?)\*\*/gim, '<strong style="color:#fff;">$1</strong>')
      .replace(/`([^`]+)`/gim, '<code style="background:rgba(255,255,255,0.08); padding:0.1rem 0.4rem; border-radius:4px; font-family:var(--font-mono); font-size:0.8rem;">$1</code>')
      .replace(/\n\n/gim, '<p style="margin-bottom:0.75rem; line-height:1.6; color:var(--text-muted); font-size:0.88rem;"></p>');

    container.innerHTML = `<div style="background:var(--bg-card); padding:1.5rem; border-radius:var(--radius-lg); border:1px solid var(--border-subtle);">${html}</div>`;
  }

  // Setup Event Listeners
  function setupEventListeners() {
    // Filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeFilter = btn.getAttribute('data-status');
        renderTaskBoard();
      });
    });

    // Search input
    const searchInput = document.getElementById('taskSearch');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        searchQuery = e.target.value;
        renderTaskBoard();
      });
    }

    // Modal Close
    const closeBtn = document.getElementById('modalClose');
    const modal = document.getElementById('taskModal');
    if (closeBtn && modal) {
      closeBtn.addEventListener('click', () => modal.classList.remove('open'));
      modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('open');
      });
    }

    // Parametric Sliders
    ['H', 'B_top', 't_web', 'B_bot', 'H_bulb', 'strands'].forEach(param => {
      const el = document.getElementById(`slider-${param}`);
      if (el) {
        el.addEventListener('input', (e) => {
          girderParams[param] = parseFloat(e.target.value);
          const valEl = document.getElementById(`val-${param}`);
          if (valEl) valEl.textContent = e.target.value;
          updateCalculations();
          drawCrossSection();
        });
      }
    });

    // Girder Type Selector
    document.querySelectorAll('.girder-type-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.girder-type-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        girderParams.type = btn.getAttribute('data-type');
        
        if (girderParams.type === 'v1') {
          girderParams.H = 1750;
          girderParams.B_top = 2100;
          girderParams.t_web = 100;
          girderParams.B_bot = 700;
          girderParams.H_bulb = 250;
          girderParams.strands = 42;
        } else if (girderParams.type === 'v2') {
          girderParams.H = 2000;
          girderParams.B_top = 2200;
          girderParams.t_web = 120;
          girderParams.B_bot = 800;
          girderParams.H_bulb = 300;
          girderParams.strands = 34;
        }
        syncSliders();
        updateCalculations();
        drawCrossSection();
      });
    });
  }

  function syncSliders() {
    ['H', 'B_top', 't_web', 'B_bot', 'H_bulb', 'strands'].forEach(param => {
      const el = document.getElementById(`slider-${param}`);
      const valEl = document.getElementById(`val-${param}`);
      if (el) el.value = girderParams[param];
      if (valEl) valEl.textContent = girderParams[param];
    });
  }

  // Show Task Details Modal
  window.showTaskModal = function(taskId) {
    const task = labData.tasks[taskId];
    if (!task) return;

    const modal = document.getElementById('taskModal');
    const modalTitle = document.getElementById('modalTaskTitle');
    const modalBody = document.getElementById('modalTaskBody');

    modalTitle.textContent = `[${task.task_id}] ${task.title}`;
    
    modalBody.innerHTML = `
      <div style="display:flex; gap:0.5rem; margin-bottom:1rem;">
        <span class="status-badge status-${task.status}">${task.status}</span>
        <span class="role-tag">Workstream: ${task.workstream || 'General'}</span>
        <span class="role-tag">Claim Ceiling: ${task.claim_ceiling || 'IDEA'}</span>
      </div>

      <div style="margin-bottom:1.25rem;">
        <strong style="color:var(--primary); display:block; margin-bottom:0.3rem;">Câu hỏi nghiên cứu:</strong>
        <p style="color:#e2e8f0; line-height:1.5;">${task.research_question || 'N/A'}</p>
      </div>

      <div style="margin-bottom:1.25rem;">
        <strong style="color:#fff; display:block; margin-bottom:0.3rem;">Tiêu chí chấp nhận (Acceptance Criteria):</strong>
        <ul style="padding-left:1.25rem; color:var(--text-muted); line-height:1.6;">
          ${(task.acceptance_criteria || []).map(c => `<li>${c}</li>`).join('')}
        </ul>
      </div>

      <div style="margin-bottom:1.25rem;">
        <strong style="color:#fff; display:block; margin-bottom:0.3rem;">Ghi chú an toàn (Safety Notes):</strong>
        <ul style="padding-left:1.25rem; color:#f87171; line-height:1.6;">
          ${(task.safety_notes || []).map(s => `<li>${s}</li>`).join('')}
        </ul>
      </div>

      <div>
        <strong style="color:#fff; display:block; margin-bottom:0.3rem;">JSON Definition (Canonical):</strong>
        <pre>${JSON.stringify(task, null, 2)}</pre>
      </div>
    `;

    modal.classList.add('open');
  };

  // Parametric Geometry Calculations
  function updateCalculations() {
    const H = girderParams.H;
    const B_top = girderParams.B_top;
    const t_top = girderParams.t_top;
    const t_web = girderParams.t_web;
    const B_bot = girderParams.B_bot;
    const H_bulb = girderParams.H_bulb;
    const strands = girderParams.strands;

    // Approximate section area (mm2)
    const A_top = B_top * t_top;
    const H_web = H - t_top - H_bulb;
    const A_web = (H_web > 0 ? H_web : 0) * t_web;
    const A_bot = B_bot * H_bulb;
    const A_total = A_top + A_web + A_bot; // mm2

    // Neutral axis from bottom (y_bar)
    const y_bot_flange = H_bulb / 2;
    const y_web = H_bulb + H_web / 2;
    const y_top_flange = H - t_top / 2;
    const y_bar = (A_bot * y_bot_flange + A_web * y_web + A_top * y_top_flange) / (A_total || 1);

    // Moment of inertia (Ix in mm4 * 10^9)
    const I_bot = (B_bot * Math.pow(H_bulb, 3)) / 12 + A_bot * Math.pow(y_bot_flange - y_bar, 2);
    const I_web = (t_web * Math.pow(H_web, 3)) / 12 + A_web * Math.pow(y_web - y_bar, 2);
    const I_top = (B_top * Math.pow(t_top, 3)) / 12 + A_top * Math.pow(y_top_flange - y_bar, 2);
    const I_x = (I_bot + I_web + I_top) / 1e9; // m4 * 10^3 or mm4 / 1e9

    // Mass per meter length (kg/m, rho = 2500 kg/m3)
    const mass_per_m = (A_total / 1e6) * 2500;
    // Estimated girder 38.3m weight (tons)
    const total_weight = (mass_per_m * 38.3) / 1000;
    // Estimated Cost Index
    const cost_index = (total_weight * 18.5) + (strands * 8.2);
    // Carbon Footprint Index (kgCO2e/girder)
    const carbon_index = (A_total / 1e6 * 38.3) * 320 + (strands * 15.4);

    document.getElementById('metric-area').textContent = `${(A_total / 1e6).toFixed(3)} m²`;
    document.getElementById('metric-ix').textContent = `${I_x.toFixed(2)} ×10⁹ mm⁴`;
    document.getElementById('metric-ybar').textContent = `${y_bar.toFixed(0)} mm`;
    document.getElementById('metric-weight').textContent = `${total_weight.toFixed(1)} tấn`;
    document.getElementById('metric-cost').textContent = `$${cost_index.toFixed(0)}`;
    document.getElementById('metric-carbon').textContent = `${carbon_index.toFixed(0)} kg`;
  }

  // Draw Cross Section Canvas
  function initParametricViewer() {
    updateCalculations();
    drawCrossSection();
  }

  function drawCrossSection() {
    const canvas = document.getElementById('bridgeCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.parentElement.clientWidth || 600;
    const height = canvas.parentElement.clientHeight || 480;
    canvas.width = width;
    canvas.height = height;

    ctx.clearRect(0, 0, width, height);

    if (girderParams.type === 'michell') {
      drawMichellBridge(ctx, width, height);
      return;
    }

    // Draw Grid Background
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
    ctx.lineWidth = 1;
    const gridSize = 30;
    for (let x = 0; x < width; x += gridSize) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke();
    }
    for (let y = 0; y < height; y += gridSize) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke();
    }

    // Girder coordinates scale & center
    const scale = Math.min((width - 120) / 2400, (height - 100) / 2200);
    const cx = width / 2;
    const cy = height / 2 + 20;

    const H = girderParams.H * scale;
    const B_top = girderParams.B_top * scale;
    const t_top = girderParams.t_top * scale;
    const t_web = girderParams.t_web * scale;
    const B_bot = girderParams.B_bot * scale;
    const H_bulb = girderParams.H_bulb * scale;

    const top_y = cy - H / 2;
    const bot_y = cy + H / 2;

    // Draw Girder Contour (Super-T parametric)
    ctx.beginPath();
    // Top flange
    ctx.moveTo(cx - B_top / 2, top_y);
    ctx.lineTo(cx + B_top / 2, top_y);
    ctx.lineTo(cx + B_top / 2, top_y + t_top);
    // Taper to web
    ctx.lineTo(cx + t_web / 2 + 15 * scale, top_y + t_top + 20 * scale);
    ctx.lineTo(cx + t_web / 2, top_y + t_top + 40 * scale);
    // Down web
    ctx.lineTo(cx + t_web / 2, bot_y - H_bulb);
    // Bottom bulb taper
    ctx.lineTo(cx + B_bot / 2, bot_y - H_bulb / 2);
    ctx.lineTo(cx + B_bot / 2, bot_y);
    // Bottom
    ctx.lineTo(cx - B_bot / 2, bot_y);
    ctx.lineTo(cx - B_bot / 2, bot_y - H_bulb / 2);
    ctx.lineTo(cx - t_web / 2, bot_y - H_bulb);
    // Up web
    ctx.lineTo(cx - t_web / 2, top_y + t_top + 40 * scale);
    ctx.lineTo(cx - t_web / 2 - 15 * scale, top_y + t_top + 20 * scale);
    ctx.lineTo(cx - B_top / 2, top_y + t_top);
    ctx.closePath();

    // Fill concrete with gradient
    const grad = ctx.createLinearGradient(cx - B_top / 2, top_y, cx + B_top / 2, bot_y);
    grad.addColorStop(0, 'rgba(6, 182, 212, 0.25)');
    grad.addColorStop(1, 'rgba(139, 92, 246, 0.2)');
    ctx.fillStyle = grad;
    ctx.fill();

    // Outline glow
    ctx.strokeStyle = '#06b6d4';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Draw Strands Pattern in Bottom Flange
    const numStrands = girderParams.strands;
    const strandCols = 8;
    const strandRows = Math.ceil(numStrands / strandCols);
    ctx.fillStyle = '#f59e0b';

    let count = 0;
    for (let r = 0; r < strandRows; r++) {
      for (let c = 0; c < strandCols; c++) {
        if (count >= numStrands) break;
        const sx = cx - (B_bot * 0.7) / 2 + (c * (B_bot * 0.7) / (strandCols - 1));
        const sy = bot_y - 12 * scale - (r * 14 * scale);
        ctx.beginPath();
        ctx.arc(sx, sy, 3 * scale, 0, Math.PI * 2);
        ctx.fill();
        count++;
      }
    }

    // Draw Neutral Axis (NA)
    const A_top = girderParams.B_top * girderParams.t_top;
    const H_web_val = girderParams.H - girderParams.t_top - girderParams.H_bulb;
    const A_web = H_web_val * girderParams.t_web;
    const A_bot = girderParams.B_bot * girderParams.H_bulb;
    const y_bar = (A_bot * (girderParams.H_bulb / 2) + A_web * (girderParams.H_bulb + H_web_val / 2) + A_top * (girderParams.H - girderParams.t_top / 2)) / (A_top + A_web + A_bot);
    const na_y = bot_y - y_bar * scale;

    ctx.strokeStyle = '#ec4899';
    ctx.setLineDash([6, 6]);
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(cx - B_top / 2 - 30, na_y);
    ctx.lineTo(cx + B_top / 2 + 30, na_y);
    ctx.stroke();
    ctx.setLineDash([]);

    // NA Label
    ctx.fillStyle = '#ec4899';
    ctx.font = '11px "JetBrains Mono"';
    ctx.fillText(`Trục trung hòa (NA) y = ${y_bar.toFixed(0)} mm`, cx + B_top / 2 + 35, na_y + 4);

    // Dimension lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
    ctx.font = '10px "JetBrains Mono"';

    // Height H
    ctx.beginPath();
    ctx.moveTo(cx - B_top / 2 - 40, top_y);
    ctx.lineTo(cx - B_top / 2 - 40, bot_y);
    ctx.stroke();
    ctx.fillText(`H = ${girderParams.H} mm`, cx - B_top / 2 - 120, cy);
  }

  // Draw 480m Michell Continuous Truss Bridge
  function drawMichellBridge(ctx, width, height) {
    ctx.fillStyle = '#080d1a';
    ctx.fillRect(0, 0, width, height);

    ctx.fillStyle = '#fff';
    ctx.font = '14px Outfit';
    ctx.fillText('Mô phỏng Dầm Liên Tục 480m có Bản Bụng Giàn Michell & Cáp CFRP (RUN-b471879e)', 20, 30);

    const marginX = 50;
    const baseY = height - 120;
    const spanWidth = width - marginX * 2;
    const scaleX = spanWidth / 480;

    // Draw Piers (Trụ cầu)
    const pier1X = marginX + 120 * scaleX;
    const pier2X = marginX + 360 * scaleX;

    ctx.fillStyle = '#334155';
    // Pier 1
    ctx.fillRect(pier1X - 8, baseY - 70, 16, 120);
    // Pier 2
    ctx.fillRect(pier2X - 8, baseY - 70, 16, 120);

    // Deck Line
    ctx.strokeStyle = '#06b6d4';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(marginX, baseY - 70);
    ctx.lineTo(width - marginX, baseY - 70);
    ctx.stroke();

    // Michell Variable Bottom Soffit Curve
    ctx.strokeStyle = '#8b5cf6';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(marginX, baseY - 60);

    for (let x = 0; x <= 480; x += 10) {
      const px = marginX + x * scaleX;
      // Parabolic variation at piers
      let h = 9; // mid span
      if (x < 120) {
        h = 9 + 19 * Math.pow(x / 120, 2);
      } else if (x <= 360) {
        const midDist = Math.abs(x - 240);
        h = 9 + 19 * Math.pow((120 - midDist) / 120, 2);
      } else {
        h = 9 + 19 * Math.pow((480 - x) / 120, 2);
      }
      const py = baseY - 70 + h * 2.2;
      if (x === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.stroke();

    // Draw Michell Diagonal Truss Web
    ctx.strokeStyle = 'rgba(6, 182, 212, 0.4)';
    ctx.lineWidth = 1;
    for (let x = 20; x < 460; x += 20) {
      const px = marginX + x * scaleX;
      const py_top = baseY - 70;
      let h = 9;
      if (x <= 240) h = 9 + 19 * Math.pow((x < 120 ? x : 240 - x) / 120, 2);
      else h = 9 + 19 * Math.pow((x > 360 ? 480 - x : x - 240) / 120, 2);
      const py_bot = baseY - 70 + h * 2.2;

      ctx.beginPath();
      ctx.moveTo(px, py_top);
      ctx.lineTo(px + 15 * scaleX, py_bot);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(px + 15 * scaleX, py_top);
      ctx.lineTo(px, py_bot);
      ctx.stroke();
    }

    // Legend
    ctx.fillStyle = 'var(--text-muted)';
    ctx.font = '11px "JetBrains Mono"';
    ctx.fillText('Nhịp biên: 120m | Nhịp chính: 240m | Nhịp biên: 120m (Tổng L = 480m)', marginX, baseY + 80);
    ctx.fillText('Chiều cao dầm: h_pier = 28m (tại trụ) -> h_mid = 9m (tại giữa nhịp)', marginX, baseY + 98);
  }

  // Draw Pareto Frontier Chart
  function renderParetoChart() {
    const canvas = document.getElementById('paretoCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.parentElement.clientWidth || 600;
    const height = canvas.parentElement.clientHeight || 400;
    canvas.width = width;
    canvas.height = height;

    ctx.clearRect(0, 0, width, height);

    // Axis margins
    const pad = 50;
    const plotW = width - pad * 2;
    const plotH = height - pad * 2;

    // Grid
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const y = pad + (plotH / 5) * i;
      ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(width - pad, y); ctx.stroke();
      const x = pad + (plotW / 5) * i;
      ctx.beginPath(); ctx.moveTo(x, pad); ctx.lineTo(x, height - pad); ctx.stroke();
    }

    // Axis Labels
    ctx.fillStyle = 'var(--text-dim)';
    ctx.font = '11px "JetBrains Mono"';
    ctx.fillText('Chi phí cấu kiện ($)', width / 2 - 40, height - 15);
    ctx.save();
    ctx.translate(15, height / 2 + 30);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Phát thải Carbon (kgCO2e)', 0, 0);
    ctx.restore();

    // Sample Pareto points (Grammar v1 vs Grammar v2)
    // Arm 1 (Grammar v1 Standard)
    const v1Points = [
      { cost: 2150, carbon: 9800, name: 'Super-T v1 (42 strands)' },
      { cost: 2072, carbon: 9600, name: 'Oracle Optimum v1 (38.3m)' },
      { cost: 2200, carbon: 10100, name: 'v1 Sub-opt' }
    ];

    // Arm 2 (Grammar v2 AI Custom Shape)
    const v2Points = [
      { cost: 2025, carbon: 8900, name: 'v2 AI Optimum (-2.4% Cost)' },
      { cost: 1980, carbon: 8750, name: 'v2 Boundary Design' },
      { cost: 2050, carbon: 9100, name: 'v2 Mid Range' }
    ];

    // Map function
    const minC = 1900, maxC = 2300;
    const minCarb = 8500, maxCarb = 10500;
    const mapX = (c) => pad + ((c - minC) / (maxC - minC)) * plotW;
    const mapY = (carb) => height - pad - ((carb - minCarb) / (maxCarb - minCarb)) * plotH;

    // Draw v1 points (Blue)
    ctx.fillStyle = '#38bdf8';
    v1Points.forEach(p => {
      ctx.beginPath();
      ctx.arc(mapX(p.cost), mapY(p.carbon), 6, 0, Math.PI * 2);
      ctx.fill();
    });

    // Draw v2 points (Neon Violet)
    ctx.fillStyle = '#a855f7';
    v2Points.forEach(p => {
      ctx.beginPath();
      ctx.arc(mapX(p.cost), mapY(p.carbon), 7, 0, Math.PI * 2);
      ctx.fill();
    });

    // Connect v2 Pareto Frontier
    ctx.strokeStyle = '#a855f7';
    ctx.lineWidth = 2;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    v2Points.sort((a,b) => a.cost - b.cost).forEach((p, i) => {
      if (i === 0) ctx.moveTo(mapX(p.cost), mapY(p.carbon));
      else ctx.lineTo(mapX(p.cost), mapY(p.carbon));
    });
    ctx.stroke();
    ctx.setLineDash([]);

    // Legend
    ctx.fillStyle = '#38bdf8';
    ctx.fillRect(width - 180, pad + 10, 10, 10);
    ctx.fillStyle = '#fff';
    ctx.fillText('Grammar v1 (Định hình)', width - 160, pad + 19);

    ctx.fillStyle = '#a855f7';
    ctx.fillRect(width - 180, pad + 30, 10, 10);
    ctx.fillStyle = '#fff';
    ctx.fillText('Grammar v2 (AI Custom)', width - 160, pad + 39);
  }

  // Run on load
  window.addEventListener('DOMContentLoaded', init);
})();
