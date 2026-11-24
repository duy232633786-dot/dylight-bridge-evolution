/* DYLIGHT Bridge / Lab — giao diện ưu tiên kỹ sư cầu (có nút gạt Lab / Dev).
   Chỉ gọi API cục bộ của scripts/serve_lab.py; mọi số kỹ thuật đến từ evaluate_candidate / design_loop / check_geometry / MAP-Elites. */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const nf = (v, d) => (v == null || !isFinite(v)) ? '–' : Number(v).toLocaleString('vi-VN', { minimumFractionDigits: d, maximumFractionDigits: d });
  const kv = (rows) => '<table class="kv">' + rows.filter(Boolean).map(([k, v]) => '<tr><td>' + k + '</td><td>' + v + '</td></tr>').join('') + '</table>';
  const pill = (text, cls) => '<span class="pill ' + cls + '">' + esc(text) + '</span>';
  const statusPill = (s) => pill(s, { PRESENT: 'pass', PARTIAL: 'warn', ABSENT: 'na', PASSED: 'pass', AVAILABLE: 'pass', BLOCKED: 'fail', ACCEPTED: 'pass', REVIEW: 'warn', ACTIVE: 'info', READY: 'na', BACKLOG: 'na', REJECTED: 'fail', APPROVE: 'pass', REVISE: 'warn', REJECT: 'fail', DRAFT: 'na', ENGINEER_APPROVED: 'pass', SCREENED: 'pass', IDEA: 'na', PASS: 'pass', FAIL: 'fail', NOT_EVALUATED: 'na', UNKNOWN: 'na', CONVERGED: 'pass', BUDGET_EXHAUSTED: 'warn', NO_IMPROVING_REPAIR: 'fail' }[s] || 'na');

  const VAR_LABELS = {
    girder_catalog_id: 'Tiết diện dầm',
    girder_count: 'Số lượng dầm chủ',
    girder_spacing_mm: 'Khoảng cách dầm (mm)',
    deck_slab_thickness_mm: 'Chiều dày bản mặt cầu (mm)',
    girder_concrete_id: 'Bê tông dầm',
    deck_concrete_id: 'Bê tông bản mặt cầu',
    diaphragm_layout_id: 'Hệ dầm ngang',
    prestress_layout_id: 'Bố trí cáp DƯL',
    girder_depth_mm: 'Chiều cao dầm H (mm)',
    top_flange_width_mm: 'Rộng cánh trên b_f (mm)',
    top_flange_thickness_mm: 'Dày cánh trên t_f (mm)',
    web_thickness_mm: 'Dày sườn t_w (mm)',
    bottom_bulb_width_mm: 'Rộng bầu b_b (mm)',
    bottom_bulb_height_mm: 'Cao bầu h_b (mm)',
    box_web_height_mm: 'Cao sườn hộp h_w (mm)',
    box_bottom_width_mm: 'Rộng bản đáy hộp b_bot (mm)',
    box_bottom_slab_mm: 'Dày bản đáy hộp t_bot (mm)',
    box_web_thickness_mm: 'Dày sườn hộp t_w (mm)',
    box_top_width_mm: 'Rộng bản mặt hộp (mm)',
    box_top_slab_mm: 'Dày bản mặt hộp (mm)',
  };
  const RULE_LABELS = {
    'STR-001': 'Uốn CĐ-I',
    'STR-002': 'Cắt CĐ-I',
    'SERV-001': 'Kéo thớ dưới SD-III',
    'SERV-002': 'Võng hoạt tải',
    'SERV-003': 'Tần số',
    'SERV-004': 'Nén thớ trên SD-I',
    'MODEL-001': 'Khối ứng suất trong bản',
    'GEOM-001': 'Cánh hẫng',
    'GEOM-002': 'Khe cánh dầm',
    'GEOM-003': 'Dày bản tối thiểu',
    'CONS-001': 'Dầm ngang',
    'CONS-002': 'Lưới thiết kế',
    'FAB-000': 'Tiết diện phi vật lý',
    'FAB-001': 'Sườn tối thiểu',
    'FAB-002': 'Cánh trên tối thiểu',
    'FAB-003': 'Chỗ xếp cáp',
    'FAB-004': 'Năng lực cẩu',
    'FAB-005': 'Tĩnh không vận chuyển',
    'FAB-006': 'Độ vát ván khuôn',
    'FAB-007': 'Tỷ lệ nhịp/chiều cao',
  };
  const LAB_ONLY_VIEWS = new Set(['overview', 'evidence', 'process', 'knowledge']);

  const state = {
    mode: localStorage.getItem('dylight_ui_mode') === 'lab' ? 'lab' : 'engineer',
    activeView: 'bench',
    overview: null,
    catalog: null,
    cards: [],
    knowledgeLoaded: false,
    obsidian: null,
    live: null,
    report: null,
    reportLabel: '',
    studioGene: null,
    creative: null,
    taskFilter: 'ALL',
    benchmarkRows: [],
    brief: {
      span_m: 38.2,
      deck_width_m: 12.0,
      concrete_grade: 'C50',
      family: 'super_t',
      concrete_vnd_m3: 3200000,
      tendon_vnd_t: 65000000,
    },
    presets: [],
    scenario: {
      id: 'V0_INLAND',
      name: 'V0 · Nội địa tiêu chuẩn',
      description: 'Điều kiện đồng bằng nội địa tiêu chuẩn TCVN 11823.',
      wind_vb_ms: 32,
      terrain_cat: 'II',
      bridge_height_m: 10,
      temp_min_c: 10,
      temp_max_c: 45,
      tg_t1_c: 22,
      tg_t2_c: 6,
      pga_g: 0.08,
      exposure_class: 'INLAND_MODERATE',
      ll_multiplier: 1.0,
      im_factor: 0.33,
    },
    benchPane: '3d',
    stressResult: null,
    stressLambda: 1.0,
    stressEnvMetric: 'M',
    stressPlayTimer: null,
    interchangeBundle: null,
    l2Result: null,
  };

  function toast(msg) {
    const t = $('toast');
    t.textContent = msg;
    t.classList.add('on');
    clearTimeout(toast._h);
    toast._h = setTimeout(() => t.classList.remove('on'), 3000);
  }
  async function api(path, body) {
    const res = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : undefined);
    const data = await res.json().catch(() => ({ error: 'phản hồi không phải JSON' }));
    if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
    return data;
  }

  // ---------------------------------------------------------------- chế độ Kỹ sư / Lab
  function updateHeaderForMode() {
    const isLab = state.mode === 'lab';
    document.body.classList.toggle('lab-mode', isLab);
    $('mode-eng').classList.toggle('on', !isLab);
    $('mode-lab').classList.toggle('on', isLab);
    $('brand-name').textContent = isLab ? 'DYLIGHT Lab' : 'DYLIGHT Bridge';
    $('brand-sub').textContent = isLab
      ? 'Hướng 1 · sáng tạo hình học và chất lượng cấu kiện cầu'
      : 'Thiết kế mặt cắt & Tối ưu dầm cầu';
    const ov = state.overview;
    if (isLab && ov) {
      $('claim-banner').innerHTML = pill(ov.claim_ceiling, ov.claim_ceiling === 'SCREENED' ? 'warn' : 'na') + '<span>' + esc(ov.claim_note) + '</span>';
    } else {
      $('claim-banner').innerHTML = pill('Sơ bộ L1 · TCVN 11823', 'warn') + '<span>Cần kiểm chứng MIDAS L2 trước khi phát hành</span>';
    }
  }
  function applyTheme(theme) {
    const t = theme === 'dark' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', t);
    localStorage.setItem('dylight_theme', t);
    const btn = $('btn-theme');
    if (btn) {
      btn.textContent = t === 'dark' ? '☀' : '☾';
      btn.title = t === 'dark' ? 'Chuyển sang giao diện Sáng' : 'Chuyển sang giao diện Tối';
    }
  }
  if ($('btn-theme')) {
    $('btn-theme').addEventListener('click', () => {
      const cur = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
      applyTheme(cur === 'dark' ? 'light' : 'dark');
    });
  }
  applyTheme(localStorage.getItem('dylight_theme') === 'dark' ? 'dark' : 'light');
  function setMode(mode) {
    state.mode = mode === 'lab' ? 'lab' : 'engineer';
    localStorage.setItem('dylight_ui_mode', state.mode);
    updateHeaderForMode();
    if (state.mode === 'engineer') {
      if (LAB_ONLY_VIEWS.has(state.activeView)) showView('bench');
      if ($('sec-arch').classList.contains('on')) activateSec('psc');
    }
  }
  $('mode-eng').addEventListener('click', () => setMode('engineer'));
  $('mode-lab').addEventListener('click', () => setMode('lab'));

  // ---------------------------------------------------------------- điều hướng
  document.querySelectorAll('.nav').forEach((b) => b.addEventListener('click', () => showView(b.dataset.view)));
  function showView(name) {
    state.activeView = name;
    document.querySelectorAll('.nav').forEach((b) => b.classList.toggle('on', b.dataset.view === name));
    document.querySelectorAll('.view').forEach((v) => v.classList.toggle('on', v.id === 'view-' + name));
    if (name === 'report') renderEngineerReport();
    if (name === 'evidence') renderEvidence();
    if (name === 'creative') ensureSecFrame();
    if (name === 'process' && !state.live) loadProcess();
    if (name === 'knowledge') { if (state.knowledgeLoaded) renderCards(state.cards); else loadKnowledge(); }
  }
  $('btn-go-report').addEventListener('click', () => showView('report'));
  $('btn-toggle-bench').addEventListener('click', () => $('bench-wrap').classList.add('collapsed'));
  $('btn-restore-bench').addEventListener('click', () => $('bench-wrap').classList.remove('collapsed'));

  // ---------------------------------------------------------------- bàn thiết kế mặt cắt
  function ensureSecFrame() {
    const f = $('midas-frame');
    if ($('sec-psc').classList.contains('on') && !f.getAttribute('src')) f.src = f.dataset.src;
  }
  function activateSec(sec) {
    document.querySelectorAll('#sec-tabs .btn').forEach((b) => b.classList.toggle('active', b.dataset.sec === sec));
    document.querySelectorAll('.sec-pane').forEach((pane) => pane.classList.toggle('on', pane.id === 'sec-' + sec));
    if (sec === 'psc') ensureSecFrame();
  }
  document.querySelectorAll('#sec-tabs .btn').forEach((b) => b.addEventListener('click', () => activateSec(b.dataset.sec)));

  // ---------------------------------------------------------------- tổng quan (Lab Mode)
  async function loadOverview() {
    try {
      const ov = await api('/api/lab/overview'); state.overview = ov;
      $('server-chip').innerHTML = '<span class="dot" style="background:var(--pass)"></span>server ' + esc(ov.lab_version) + ' · pkg ' + esc(ov.software_version);
      updateHeaderForMode();
      $('ov-gates').querySelector('.body').innerHTML = ov.gates.map((g) => '<div class="gate"><span class="g">' + g.gate + '</span><span>' + esc(g.label) + '<div class="d">' + esc(g.detail) + '</div></span>' + statusPill(g.status) + '</div>').join('');
      const caps = ov.capabilities.map((c) => '<span class="cap" title="' + esc(c.limit || c.title) + '"><span class="dot" style="background:var(--' + ({ PRESENT: 'pass', PARTIAL: 'warn', ABSENT: 'na' }[c.state] || 'na') + ')"></span>' + esc(c.id) + '</span>').join('');
      const counts = ov.capabilities.reduce((a, c) => { a[c.state] = (a[c.state] || 0) + 1; return a; }, {});
      $('ov-caps').querySelector('.body').innerHTML = '<div class="note">' + Object.entries(counts).map(([k, v]) => k + ' ' + v).join(' · ') + ' · rule runtime: ' + ov.rule_inventory.length + '</div><div class="caps">' + caps + '</div>';
      $('ov-basis').querySelector('.body').innerHTML = kv([
        ['Design basis', esc(ov.design_basis.project_id || '–')], ['Tiêu chuẩn', esc((ov.design_basis.standard || '') + ' ' + (ov.design_basis.standard_version || ''))],
        ['Tuổi thọ thiết kế', statusPill(ov.design_basis.design_life || 'UNKNOWN')], ['Cấp phơi nhiễm', statusPill(ov.design_basis.exposure_class || 'UNKNOWN')],
        ['Site profile', esc(ov.site.profile) + ' · ' + esc(ov.site.status || '')], ['G0', statusPill(ov.site.g0 || 'UNKNOWN')], ['Trường UNKNOWN', ov.site.unknown_fields.length],
      ]) + '<div class="note">Đây là lý do mọi số vẫn ở mức mô hình nghiên cứu: chưa có vị trí, gió, động đất, thủy văn, địa chất, ăn mòn thật.</div>';
      const ls = ov.lab_status || {};
      $('ov-lab').querySelector('.body').innerHTML = kv([
        ['Lab hợp lệ', ls.valid === true ? pill('valid', 'pass') : ls.valid === false ? pill('invalid', 'fail') : '–'],
        ['Task', ls.tasks ? Object.entries(ls.tasks).map(([k, v]) => k + ' ' + v).join(' · ') : '–'],
        ['CLI', ls.cli_available ? Object.entries(ls.cli_available).map(([k, v]) => k + (v ? ' ✓' : ' ✗')).join(' · ') : '–'],
        ['Tác tử', (ov.agents || []).map((a) => esc(a.agent_id)).join(', ')],
      ]) + '<div class="note">Đề tài mới đi qua lab orchestrate; mọi phát minh nộp handoff có hash; proposer không tự review.</div>';
      const o = ov.oracle_v1;
      $('ov-knowledge').querySelector('.body').innerHTML = kv([
        ['Thẻ tri thức', ov.knowledge.cards + ' · ' + Object.entries(ov.knowledge.by_status).map(([k, v]) => k + ' ' + v).join(', ')],
        ['Thẻ kỹ sư duyệt', (ov.knowledge.by_status.ENGINEER_APPROVED || 0)],
        o ? ['Oracle vét cạn v1', nf(o.domain_size, 0) + ' tổ hợp · ' + nf(o.l0_valid, 0) + ' L0 · ' + nf(o.feasible, 0) + ' khả thi'] : null,
        o && o.best_cost != null ? ['Chi phí tối ưu toàn cục v1', nf(o.best_cost, 2)] : null,
      ]) + '<div class="note">Mọi vòng lặp cục bộ phải đối chiếu với oracle này trước khi phát biểu "tốt".</div>';
      $('ov-honest').querySelector('.body').innerHTML = '<ul class="note" style="margin:0;padding-left:16px;color:var(--ink-2)">'
        + '<li>Được: sàng lọc L0/L1 tái lập được, lineage có hash, chẩn đoán vi phạm và nước sửa, danh mục hình thái F0.</li>'
        + '<li>Không được: kết luận đạt tiêu chuẩn, trích chi phí/carbon như dự toán, tối ưu cốt thép thường (chưa có biến), nói về gió/động đất/xói/độ bền.</li>'
        + '<li>Muốn nâng: G0 site thật → L2 qua midas-mcp → grammar cốt thép → L3 giai đoạn → kỹ sư duyệt.</li></ul>';
      renderEngineerReport();
    } catch (err) { $('server-chip').innerHTML = '<span class="dot" style="background:var(--fail)"></span>' + esc(err.message); }
  }

  // ---------------------------------------------------------------- tri thức nhúng cho kỹ sư
  async function ensureCards() {
    if (state.cards.length) return state.cards;
    try {
      const res = await api('/api/knowledge/cards');
      state.cards = res.cards || [];
    } catch (err) { /* bỏ qua */ }
    return state.cards;
  }

  function extractEngineeringHints(report) {
    if (!report) return [];
    const hints = [];
    const seen = new Set();
    const f = report.final || {};
    const failingRules = [];
    if (f.rule_utilizations) {
      for (const [k, u] of Object.entries(f.rule_utilizations)) {
        if (u > 1 + 1e-9) failingRules.push(k);
      }
    }
    for (const v of (f.violations || [])) {
      if (v.rule_id && !failingRules.includes(v.rule_id)) failingRules.push(v.rule_id);
    }
    // 1. Khớp rule đang trượt với thẻ tri thức
    for (const ruleId of failingRules) {
      const match = state.cards.find((c) => c.applies_to && (c.applies_to.rules || []).includes(ruleId));
      if (match && !seen.has(match.card_id)) {
        seen.add(match.card_id);
        hints.push({ tag: ruleId, title: match.title, detail: match.guidance || '' });
      }
    }
    // 2. Các nước sửa đã áp dụng thành công trong vòng lặp
    for (const it of (report.iterations || [])) {
      for (const p of (it.probes || [])) {
        if (p.outcome === 'ACCEPTED' && p.move && p.move.card_id && !seen.has(p.move.card_id)) {
          const card = state.cards.find((c) => c.card_id === p.move.card_id);
          if (card) {
            seen.add(card.card_id);
            hints.push({ tag: (card.applies_to && card.applies_to.rules && card.applies_to.rules[0]) || 'Gợi ý', title: card.title, detail: 'Đã áp dụng tự động trong quá trình tối ưu.' });
          }
        }
      }
    }
    return hints.slice(0, 4);
  }

  async function renderBenchHints() {
    const box = $('bench-hints');
    const body = $('bench-hints-body');
    if (!state.report) { box.style.display = 'none'; return; }
    await ensureCards();
    const hints = extractEngineeringHints(state.report);
    if (!hints.length) { box.style.display = 'none'; return; }
    body.innerHTML = hints.map((h) => '<div class="hint-item"><span class="hint-rule">' + esc(h.tag) + '</span><span>' + esc(h.title) + '</span></div>').join('');
    box.style.display = 'block';
  }

  // ---------------------------------------------------------------- Bước 1: Hồ sơ & Điều kiện tự nhiên Việt Nam
  const FALLBACK_PRESETS = [
    { id: 'V0_INLAND', name: 'V0 · Nội địa tiêu chuẩn', description: 'Đồng bằng nội địa, gió vùng II, hoạt tải HL-93 tiêu chuẩn.', wind_vb_ms: 32, terrain_cat: 'II', bridge_height_m: 10, temp_min_c: 10, temp_max_c: 45, tg_t1_c: 22, tg_t2_c: 6, pga_g: 0.08, exposure_class: 'INLAND_MODERATE', ll_multiplier: 1.0, im_factor: 0.33 },
    { id: 'V1_COASTAL_TYPHOON', name: 'V1 · Ven biển Miền Trung (Bão)', description: 'Gió bão mạnh V_B = 50 m/s, phơi nhiễm hơi muối ven biển.', wind_vb_ms: 50, terrain_cat: 'I', bridge_height_m: 14, temp_min_c: 14, temp_max_c: 48, tg_t1_c: 25, tg_t2_c: 7, pga_g: 0.08, exposure_class: 'COASTAL_HUMID', ll_multiplier: 1.05, im_factor: 0.33 },
    { id: 'V2_NORTHWEST_SEISMIC', name: 'V2 · Tây Bắc (Động đất cao)', description: 'Gia tốc nền PGA = 0.22g, biên độ nhiệt ngày đêm lớn.', wind_vb_ms: 34, terrain_cat: 'II', bridge_height_m: 18, temp_min_c: 5, temp_max_c: 44, tg_t1_c: 24, tg_t2_c: 6, pga_g: 0.22, exposure_class: 'INLAND_MODERATE', ll_multiplier: 1.0, im_factor: 0.33 },
    { id: 'V3_PORT_OVERLOAD', name: 'V3 · Trục cảng biển (Quá tải 1.35×)', description: 'Xe container nặng α = 1.35 × HL-93, xung kích cao IM = 0.38, môi trường biển.', wind_vb_ms: 42, terrain_cat: 'I', bridge_height_m: 12, temp_min_c: 15, temp_max_c: 47, tg_t1_c: 24, tg_t2_c: 6, pga_g: 0.10, exposure_class: 'MARINE_SEVERE', ll_multiplier: 1.35, im_factor: 0.38 },
    { id: 'V4_EXTREME_MULTIHAZARD', name: 'V4 · Đa thiên tai cực đoan', description: 'Tổ hợp cực đoan: bão 55 m/s + nhiệt 28°C + PGA 0.20g + biển khắc nghiệt + 1.3× HL-93.', wind_vb_ms: 55, terrain_cat: 'I', bridge_height_m: 16, temp_min_c: 10, temp_max_c: 50, tg_t1_c: 28, tg_t2_c: 7, pga_g: 0.20, exposure_class: 'MARINE_SEVERE', ll_multiplier: 1.30, im_factor: 0.40 },
  ];

  function estimateVndCost(objectives) {
    if (!objectives || objectives.material_mass_t == null) return null;
    const concVnd = Number(state.brief.concrete_vnd_m3) || 3200000;
    const tendVnd = Number(state.brief.tendon_vnd_t) || 65000000;
    const concVol = objectives.concrete_volume_m3 != null
      ? Number(objectives.concrete_volume_m3)
      : (Number(objectives.material_mass_t) * 0.955 / 2.45);
    const tendMass = objectives.tendon_mass_t != null
      ? Number(objectives.tendon_mass_t)
      : (Number(objectives.material_mass_t) * 0.045);
    return concVol * concVnd + tendMass * tendVnd;
  }

  function fmtVnd(amount) {
    if (amount == null || !isFinite(amount)) return '–';
    if (Math.abs(amount) >= 1e9) return nf(amount / 1e9, 2) + ' tỷ VNĐ';
    return nf(amount / 1e6, 1) + ' tr VNĐ';
  }

  function syncBriefSummary() {
    const sc = state.scenario;
    const b = state.brief;
    const label = sc.id ? (sc.id + (sc.name ? ' · ' + sc.name : '')) : 'Kịch bản tùy chỉnh';
    if ($('brief-preset-chip')) $('brief-preset-chip').textContent = 'Kịch bản: ' + (sc.id || 'CUSTOM');
    if ($('bench-scenario-chip')) $('bench-scenario-chip').textContent = 'Kịch bản: ' + (sc.id || 'CUSTOM') + ' · α=' + nf(sc.ll_multiplier, 2) + '×';
    if ($('brief-active-summary')) {
      $('brief-active-summary').innerHTML = ''
        + '<span><strong>Đề bài:</strong> L=' + nf(b.span_m, 1) + 'm · B=' + nf(b.deck_width_m, 1) + 'm · ' + esc(b.concrete_grade) + '</span>'
        + '<span><strong>Đơn giá tham chiếu:</strong> BT ' + nf(b.concrete_vnd_m3 / 1e6, 2) + ' tr/m³ · Cáp ' + nf(b.tendon_vnd_t / 1e6, 1) + ' tr/tấn</span>'
        + '<span><strong>Môi trường:</strong> ' + esc(label) + '</span>';
    }
  }

  function syncScenarioControlsFromState() {
    const sc = state.scenario;
    if ($('sc-wind-vb')) { $('sc-wind-vb').value = sc.wind_vb_ms; $('sc-wind-vb-val').textContent = sc.wind_vb_ms + ' m/s'; }
    if ($('sc-tg-t1')) { $('sc-tg-t1').value = sc.tg_t1_c; $('sc-tg-t1-val').textContent = sc.tg_t1_c + ' °C'; }
    if ($('sc-pga')) { $('sc-pga').value = sc.pga_g; $('sc-pga-val').textContent = nf(sc.pga_g, 2) + ' g'; }
    if ($('sc-ll-mult')) { $('sc-ll-mult').value = sc.ll_multiplier; $('sc-ll-mult-val').textContent = nf(sc.ll_multiplier, 2) + '×'; }
    if ($('sc-im')) { $('sc-im').value = sc.im_factor; $('sc-im-val').textContent = nf(sc.im_factor, 2); }
    if ($('sc-exposure')) $('sc-exposure').value = sc.exposure_class;
    syncBriefSummary();
  }

  const PRESET_ICONS = {
    V0_INLAND: '🌤',
    V1_COASTAL_TYPHOON: '🌊',
    V2_NORTHWEST_SEISMIC: '⛰',
    V3_PORT_OVERLOAD: '🚛',
    V4_EXTREME_MULTIHAZARD: '⚡',
  };

  function renderPresetCards() {
    const grid = $('brief-presets-grid');
    if (!grid) return;
    grid.innerHTML = '';
    for (const p of state.presets) {
      const icon = PRESET_ICONS[p.id] || '🧭';
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'preset-card' + (state.scenario.id === p.id ? ' on' : '');
      btn.innerHTML = '<div class="pc-head"><span>' + esc(p.id) + '</span><span>' + esc(p.exposure_class || '') + '</span></div>'
        + '<div class="pc-icon-row"><span class="pc-icon" aria-hidden="true">' + icon + '</span><span class="pc-title">' + esc(p.name) + '</span></div>'
        + '<div class="pc-desc">' + esc(p.description || '') + '</div>'
        + '<div class="pc-meta">'
        + '<span>V_B ' + nf(p.wind_vb_ms, 0) + ' m/s</span>'
        + '<span>T1 ' + nf(p.tg_t1_c, 0) + '°C</span>'
        + '<span>PGA ' + nf(p.pga_g, 2) + 'g</span>'
        + '<span>α=' + nf(p.ll_multiplier, 2) + '×</span>'
        + '</div>';
      btn.addEventListener('click', () => {
        state.scenario = Object.assign({}, p);
        syncScenarioControlsFromState();
        renderPresetCards();
        toast('Đã chọn kịch bản ' + p.name);
      });
      grid.appendChild(btn);
    }
  }

  async function loadSimPresets() {
    try {
      const res = await api('/api/sim/presets');
      state.presets = (res && Array.isArray(res.presets) && res.presets.length) ? res.presets : FALLBACK_PRESETS;
    } catch (err) {
      state.presets = FALLBACK_PRESETS;
    }
    if (state.presets.length) state.scenario = Object.assign({}, state.presets[0]);
    syncScenarioControlsFromState();
    renderPresetCards();
  }

  function bindBriefControls() {
    const bindNum = (id, key) => {
      const el = $(id);
      if (!el) return;
      el.addEventListener('input', () => { state.brief[key] = +el.value; syncBriefSummary(); if (state.activeView === 'report') renderEngineerReport(); });
    };
    bindNum('br-span', 'span_m');
    bindNum('br-width', 'deck_width_m');
    bindNum('br-price-concrete', 'concrete_vnd_m3');
    bindNum('br-price-tendon', 'tendon_vnd_t');
    if ($('br-fc')) $('br-fc').addEventListener('change', (e) => { state.brief.concrete_grade = e.target.value; syncBriefSummary(); });
    if ($('br-family')) $('br-family').addEventListener('change', (e) => { state.brief.family = e.target.value; syncBriefSummary(); });

    const bindSc = (id, key, fmt) => {
      const el = $(id);
      if (!el) return;
      el.addEventListener('input', () => {
        state.scenario[key] = el.tagName === 'SELECT' ? el.value : +el.value;
        state.scenario.id = 'CUSTOM';
        state.scenario.name = 'Kịch bản tùy chỉnh kỹ sư';
        if (fmt && $(id + '-val')) $(id + '-val').textContent = fmt(state.scenario[key]);
        renderPresetCards();
        syncBriefSummary();
      });
    };
    bindSc('sc-wind-vb', 'wind_vb_ms', (v) => v + ' m/s');
    bindSc('sc-tg-t1', 'tg_t1_c', (v) => v + ' °C');
    bindSc('sc-pga', 'pga_g', (v) => nf(v, 2) + ' g');
    bindSc('sc-ll-mult', 'll_multiplier', (v) => nf(v, 2) + '×');
    bindSc('sc-im', 'im_factor', (v) => nf(v, 2));
    if ($('sc-exposure')) {
      $('sc-exposure').addEventListener('change', (e) => {
        state.scenario.exposure_class = e.target.value;
        state.scenario.id = 'CUSTOM';
        state.scenario.name = 'Kịch bản tùy chỉnh kỹ sư';
        renderPresetCards();
        syncBriefSummary();
      });
    }

    if ($('btn-apply-brief')) {
      $('btn-apply-brief').addEventListener('click', () => {
        if (state.brief.family === 'box_girder') {
          const sel = $('seed-select');
          const boxOpt = [...sel.options].find((o) => o.value.includes('box_girder'));
          if (boxOpt) sel.value = boxOpt.value;
        }
        updateBoxL1Banner();
        showView('bench');
        toast('Đã áp dụng kịch bản ' + (state.scenario.id || 'CUSTOM') + ' — bấm Chạy tối ưu hoặc Thử tải λ');
      });
    }

    if ($('btn-demo-5min')) {
      $('btn-demo-5min').addEventListener('click', async () => {
        const btn = $('btn-demo-5min');
        btn.disabled = true;
        toast('Đang chạy Demo 5 phút: Áp dụng kịch bản → Tối ưu AI → Thử tải vật lý…');
        try {
          if (state.brief.family === 'box_girder') {
            const sel = $('seed-select');
            const boxOpt = [...sel.options].find((o) => o.value.includes('box_girder'));
            if (boxOpt) sel.value = boxOpt.value;
          }
          updateBoxL1Banner();
          showView('bench');
          const ok = await runDesignLoopAction();
          if (ok) {
            setBenchPane('stress');
            await runStressTest();
            toast('Hoàn tất Demo 5 phút! Xem Đấu trường Thử tải λ hoặc sang Bước 4 xuất BIM/MIDAS.');
          }
        } catch (err) {
          toast('Lỗi Demo: ' + err.message);
        }
        btn.disabled = false;
      });
    }
  }
  bindBriefControls();

  // ---------------------------------------------------------------- bàn cấu kiện (Bước 3: AI & Thử tải vật lý)
  const inspector = $('inspector');
  function sendInspector(msg) { try { inspector.contentWindow.postMessage(msg, '*'); } catch (err) { /* chưa sẵn sàng */ } }
  window.addEventListener('message', (e) => {
    const d = e.data; if (!d || typeof d !== 'object') return;
    if (d.type === 'dylight:loaded') {
      if (d.report) { state.report = d.report; state.reportLabel = d.label || ''; state.stressResult = null; }
      updateBoxL1Banner();
      renderBenchHints();
      renderEngineerReport();
      renderEvidence();
    }
  });

  function updateBoxL1Banner() {
    const banner = $('box-l1-banner');
    if (!banner) return;
    const selVal = ($('seed-select') && $('seed-select').value) || '';
    const repGram = (state.report && state.report.grammar_id) || '';
    const isBox = selVal.includes('box_girder') || repGram.includes('box_girder');
    banner.style.display = isBox ? 'block' : 'none';
  }

  async function loadCatalog() {
    const cat = await api('/api/catalog'); state.catalog = cat;
    const sel = $('seed-select'); sel.innerHTML = '';
    for (const gc of cat.gold_cases) {
      const o = document.createElement('option');
      o.value = 'gold:' + gc.file;
      o.textContent = gc.file.replace('.json', '') + ' — ' + (gc.description || '');
      sel.appendChild(o);
    }
    for (const [fam] of Object.entries(cat.anchor_genes || {})) {
      if (!cat.grammars[fam]) continue;
      const o = document.createElement('option');
      o.value = 'anchor:' + fam;
      o.textContent = fam === 'box_girder_parametric_v1'
        ? 'Hộp PSC 1 ô (box_girder_parametric_v1) — Mẫu chuẩn L1'
        : ('Mẫu chuẩn ' + fam);
      sel.appendChild(o);
    }
    const custom = document.createElement('option');
    custom.value = 'studio';
    custom.textContent = 'Mặt cắt từ Bước 2 (Super-T tham số)';
    sel.appendChild(custom);
    if (cat.gold_cases.find((g) => g.file.startsWith('GC-06'))) {
      sel.value = 'gold:' + cat.gold_cases.find((g) => g.file.startsWith('GC-06')).file;
    }
    sel.addEventListener('change', updateBoxL1Banner);
    updateBoxL1Banner();
    initStudio();
  }

  function seedPayload() {
    const v = $('seed-select').value;
    if (v.startsWith('gold:')) return { seed_file: v.slice(5) };
    if (v.startsWith('anchor:')) { const fam = v.slice(7); return { gene: state.catalog.anchor_genes[fam], grammar_id: fam }; }
    if (v === 'studio') { if (!state.studioGene) throw new Error('Chưa có mặt cắt từ Bước 2 (Thiết kế mặt cắt)'); return { gene: state.studioGene, grammar_id: 'super_t_parametric_v2' }; }
    throw new Error('Phương án gốc không hợp lệ');
  }

  async function runDesignLoopAction() {
    const btn = $('btn-run'); btn.disabled = true; $('run-status').textContent = 'Đang chạy tối ưu và kiểm toán L1…';
    let ok = false;
    try {
      const payload = Object.assign(seedPayload(), {
        budget: +$('in-budget').value,
        policy: { objective_key: $('in-objective').value, utilization_target: +$('in-target').value, move_policy: $('in-policy').value, trim_order: $('in-trim').value, trim_enabled: $('in-trim-on').value === '1' },
      });
      const res = await api('/api/design-loop', payload);
      state.report = res.report; state.reportLabel = res.saved_as; state.stressResult = null;
      sendInspector({ type: 'dylight:load', payload: res.report, label: res.saved_as });
      const f = res.report.final || {};
      const s = res.report.seed || {};
      const dMass = (f.objectives && s.objectives && f.objectives.material_mass_t != null && s.objectives.material_mass_t != null)
        ? (f.objectives.material_mass_t - s.objectives.material_mass_t) : null;
      $('run-status').innerHTML = (f.feasible ? pill('Đạt L1', 'pass') : pill('Chưa đạt', 'fail'))
        + ' · D/C max <strong>' + nf(f.max_utilization, 3) + '</strong>'
        + ' · chi phí ' + nf((f.objectives || {}).relative_cost, 1)
        + (dMass != null ? ' · khối lượng ' + (dMass <= 0 ? '<span class="delta-good">' : '<span class="delta-bad">+') + nf(dMass, 1) + ' t</span>' : '')
        + ' · ' + res.report.counters.evaluator.solver_calls + ' bước';
      updateBoxL1Banner();
      loadRuns(); renderBenchHints(); renderEngineerReport(); renderEvidence();
      ok = true;
    } catch (err) { $('run-status').innerHTML = '<span style="color:var(--fail)">' + esc(err.message) + '</span>'; }
    btn.disabled = false;
    return ok;
  }
  $('btn-run').addEventListener('click', runDesignLoopAction);

  // ---------------------------------------------------------------- Đấu trường Thử tải vật lý (Step 3)
  function setBenchPane(pane) {
    state.benchPane = pane === 'stress' ? 'stress' : '3d';
    if ($('tab-bench-3d')) $('tab-bench-3d').classList.toggle('active', state.benchPane === '3d');
    if ($('tab-bench-stress')) $('tab-bench-stress').classList.toggle('active', state.benchPane === 'stress');
    if ($('pane-3d')) $('pane-3d').classList.toggle('on', state.benchPane === '3d');
    if ($('pane-stress')) $('pane-stress').classList.toggle('on', state.benchPane === 'stress');
    if (state.benchPane === 'stress' && state.report && !state.stressResult) runStressTest();
  }
  if ($('tab-bench-3d')) $('tab-bench-3d').addEventListener('click', () => setBenchPane('3d'));
  if ($('tab-bench-stress')) $('tab-bench-stress').addEventListener('click', () => setBenchPane('stress'));
  if ($('btn-quick-stress')) $('btn-quick-stress').addEventListener('click', () => { setBenchPane('stress'); runStressTest(); });
  if ($('btn-st-run')) $('btn-st-run').addEventListener('click', () => runStressTest());

  function stopStressAnim() {
    if (state.stressPlayTimer) {
      clearInterval(state.stressPlayTimer);
      state.stressPlayTimer = null;
      if ($('btn-st-play')) $('btn-st-play').textContent = '▶ Chạy hoạt ảnh thử tải';
    }
  }
  if ($('st-lambda')) {
    $('st-lambda').addEventListener('input', (e) => {
      state.stressLambda = +e.target.value;
      if ($('st-lambda-val')) $('st-lambda-val').textContent = nf(state.stressLambda, 1) + '×';
      if (state.stressResult) renderStressTestViews();
    });
  }
  if ($('btn-st-play')) {
    $('btn-st-play').addEventListener('click', async () => {
      if (state.stressPlayTimer) { stopStressAnim(); return; }
      if (!state.stressResult) {
        const ok = await runStressTest();
        if (!ok) return;
      }
      state.stressLambda = 0.5;
      $('st-lambda').value = 0.5;
      $('st-lambda-val').textContent = '0.5×';
      renderStressTestViews();
      $('btn-st-play').textContent = '⏸ Dừng hoạt ảnh';
      state.stressPlayTimer = setInterval(() => {
        let next = Math.round((state.stressLambda + 0.1) * 10) / 10;
        if (next > 2.5) { stopStressAnim(); return; }
        state.stressLambda = next;
        $('st-lambda').value = next;
        $('st-lambda-val').textContent = nf(next, 1) + '×';
        renderStressTestViews();
      }, 220);
    });
  }
  document.querySelectorAll('#st-env-tabs .btn').forEach((b) => b.addEventListener('click', () => {
    state.stressEnvMetric = b.dataset.metric;
    document.querySelectorAll('#st-env-tabs .btn').forEach((x) => x.classList.toggle('active', x === b));
    if (state.stressResult) renderLongitudinalEnvSvg();
  }));

  async function runStressTest() {
    if (!state.report || !state.report.seed || !state.report.final) {
      toast('Hãy chạy tối ưu ở Bước 3 (hoặc chọn 1 phương án trong lịch sử) trước khi thử tải.');
      return false;
    }
    const btn = $('btn-st-run');
    if (btn) btn.disabled = true;
    try {
      const res = await api('/api/sim/stress-test', {
        baseline_state: state.report.seed,
        ai_state: state.report.final,
        scenario: state.scenario,
      });
      state.stressResult = res;
      renderStressTestViews();
      if (state.activeView === 'report') renderInsightsCard(state.report);
      if (btn) btn.disabled = false;
      return true;
    } catch (err) {
      if ($('st-reserve-wrap')) $('st-reserve-wrap').innerHTML = '<div class="note" style="color:var(--fail)">Lỗi thử tải: ' + esc(err.message) + '</div>';
      toast('Lỗi thử tải: ' + err.message);
      if (btn) btn.disabled = false;
      return false;
    }
  }

  function renderStressTestViews() {
    const res = state.stressResult;
    if (!res) return;
    const base = res.baseline || {};
    const ai = res.ai || {};
    const env = res.env_effects || {};
    const sweep = Array.isArray(res.sweep) ? res.sweep : [];
    const lam = state.stressLambda;

    if ($('st-honesty-note') && res.honesty_note) $('st-honesty-note').textContent = res.honesty_note;

    const envItems = [];
    const windPd = (env.wind && env.wind.P_D_kPa != null) ? env.wind.P_D_kPa : (env.wind_pd_kPa ?? env.P_D_kPa);
    const deltaL = (env.thermal && env.thermal.delta_L_mm != null) ? env.thermal.delta_L_mm : (env.thermal_delta_L_mm ?? env.delta_L_mm);
    const tgScope = (env.thermal && env.thermal.scope) || env.tg_scope || env.tg_note;
    const expCls = (env.exposure && env.exposure.exposure_class) || env.exposure_class;
    const nMin = (env.seismic_l1 && env.seismic_l1.N_min_mm != null) ? env.seismic_l1.N_min_mm : (env.seismic_n_min_mm ?? env.N_min_mm);
    const fKey = (env.seismic_l1 && env.seismic_l1.F_key_kN != null) ? env.seismic_l1.F_key_kN : (env.seismic_f_key_kN ?? env.F_key_kN);
    if (windPd != null) envItems.push('<span class="env-pill">Gió P_D: <strong>' + nf(windPd, 2) + ' kPa</strong></span>');
    if (deltaL != null) envItems.push('<span class="env-pill">Co giãn TU ΔL: <strong>' + nf(deltaL, 1) + ' mm</strong></span>');
    if (tgScope) envItems.push('<span class="env-pill">Nhiệt TG: <strong>' + esc(tgScope) + '</strong></span>');
    if (expCls) envItems.push('<span class="env-pill">Phơi nhiễm: <strong>' + esc(expCls) + '</strong></span>');
    if (nMin != null) envItems.push('<span class="env-pill">Động đất L1 · Gối đỡ N_min: <strong>' + nf(nMin, 0) + ' mm</strong></span>');
    if (fKey != null) envItems.push('<span class="env-pill">Chốt chống xô F_key: <strong>' + nf(fKey, 0) + ' kN</strong></span>');
    if ($('st-env-bar')) $('st-env-bar').innerHTML = envItems.join('');

    const curPt = sweep.reduce((best, p) => (!best || Math.abs((p.lam ?? p.lambda) - lam) < Math.abs((best.lam ?? best.lambda) - lam)) ? p : best, null);
    const rfBase = base.rating_factor ?? base.rf;
    const rfAi = ai.rating_factor ?? ai.rf;
    const sfBase = base.safety_factor ?? base.sf;
    const sfAi = ai.safety_factor ?? ai.sf;
    const lCrackBase = base.lambda_crack, lCrackAi = ai.lambda_crack;
    const lDeflBase = base.lambda_deflect, lDeflAi = ai.lambda_deflect;
    const lStrBase = base.lambda_str1, lStrAi = ai.lambda_str1;

    if ($('st-kpi-grid')) {
      const kClsGe1 = (v) => v == null ? '' : (Number(v) >= 1.0 ? ' kpi-pass' : ' kpi-fail');
      const kClsLe1 = (v) => v == null ? '' : (Number(v) <= 1.0 ? ' kpi-pass' : ' kpi-fail');
      $('st-kpi-grid').innerHTML = ''
        + '<div class="kpi' + kClsGe1(rfAi) + '"><div class="k-lbl">Rating Factor (RF)</div><div class="k-val">' + nf(rfAi, 2) + ' <span class="note">vs ' + nf(rfBase, 2) + '</span></div><div class="k-sub">' + fmtDelta(rfBase, rfAi, '', 2, false) + '</div></div>'
        + '<div class="kpi' + kClsGe1(sfAi) + '"><div class="k-lbl">Hệ số An toàn (SF)</div><div class="k-val">' + nf(sfAi, 2) + ' <span class="note">vs ' + nf(sfBase, 2) + '</span></div><div class="k-sub">' + fmtDelta(sfBase, sfAi, '', 2, false) + '</div></div>'
        + '<div class="kpi' + (curPt ? kClsLe1(curPt.dc_ai) : '') + '"><div class="k-lbl">D/C tại λ = ' + nf(lam, 1) + '×</div><div class="k-val">' + (curPt ? nf(curPt.dc_ai, 3) : '–') + ' <span class="note">vs ' + (curPt ? nf(curPt.dc_base, 3) : '–') + '</span></div><div class="k-sub">' + (curPt ? fmtDelta(curPt.dc_base, curPt.dc_ai, '', 3, true) : '–') + '</div></div>'
        + '<div class="kpi' + kClsGe1(lCrackAi) + '"><div class="k-lbl">Ngưỡng Nứt λ_crack</div><div class="k-val">' + nf(lCrackAi, 2) + '× <span class="note">vs ' + nf(lCrackBase, 2) + '×</span></div><div class="k-sub">' + fmtDelta(lCrackBase, lCrackAi, '×', 2, false) + '</div></div>'
        + '<div class="kpi' + kClsGe1(lDeflAi) + '"><div class="k-lbl">Ngưỡng Võng λ_deflect</div><div class="k-val">' + nf(lDeflAi, 2) + '× <span class="note">vs ' + nf(lDeflBase, 2) + '×</span></div><div class="k-sub">' + fmtDelta(lDeflBase, lDeflAi, '×', 2, false) + '</div></div>'
        + '<div class="kpi' + kClsGe1(lStrAi) + '"><div class="k-lbl">Ngưỡng CĐ-I λ_STR-I</div><div class="k-val">' + nf(lStrAi, 2) + '× <span class="note">vs ' + nf(lStrBase, 2) + '×</span></div><div class="k-sub">' + fmtDelta(lStrBase, lStrAi, '×', 2, false) + '</div></div>';
    }

    renderReserveCurveSvg();
    renderLongitudinalEnvSvg();
  }

  function renderReserveCurveSvg() {
    const wrap = $('st-reserve-wrap');
    const res = state.stressResult;
    const sweep = (res && Array.isArray(res.sweep)) ? res.sweep : [];
    if (!wrap) return;
    if (sweep.length < 2) {
      wrap.innerHTML = '<div class="note">Chưa có dữ liệu đường cong quét λ.</div>';
      return;
    }
    const W = 540, H = 250, pL = 50, pR = 20, pT = 26, pB = 34;
    const plotW = W - pL - pR, plotH = H - pT - pB;
    const lams = sweep.map((p) => Number(p.lam ?? p.lambda));
    const lMin = Math.min(...lams), lMax = Math.max(...lams);
    const dcs = sweep.flatMap((p) => [Number(p.dc_base || 0), Number(p.dc_ai || 0)]);
    const dMax = Math.max(1.4, Math.max(...dcs) * 1.1);
    const xOf = (v) => pL + ((v - lMin) / Math.max(1e-6, lMax - lMin)) * plotW;
    const yOf = (v) => pT + plotH - (v / dMax) * plotH;

    let grid = '';
    for (let i = 0; i <= 4; i++) {
      const y = pT + (i / 4) * plotH;
      const val = dMax * (1 - i / 4);
      grid += '<line x1="' + pL + '" x2="' + (W - pR) + '" y1="' + y.toFixed(1) + '" y2="' + y.toFixed(1) + '" stroke="#cbd5e1" stroke-opacity="0.45" stroke-dasharray="2 3"/>';
      grid += '<text x="' + (pL - 6) + '" y="' + (y + 3.5).toFixed(1) + '" text-anchor="end" font-size="10" fill="#64748b" font-family="IBM Plex Mono,monospace">' + val.toFixed(2) + '</text>';
    }
    for (let lv = 0.5; lv <= 2.51; lv += 0.5) {
      const x = xOf(lv);
      grid += '<text x="' + x.toFixed(1) + '" y="' + (H - 12) + '" text-anchor="middle" font-size="10" fill="#64748b" font-family="IBM Plex Mono,monospace">' + lv.toFixed(1) + '×</text>';
    }

    const basePath = sweep.map((p, i) => (i ? 'L' : 'M') + xOf(p.lam ?? p.lambda).toFixed(1) + ' ' + yOf(p.dc_base || 0).toFixed(1)).join(' ');
    const aiPath = sweep.map((p, i) => (i ? 'L' : 'M') + xOf(p.lam ?? p.lambda).toFixed(1) + ' ' + yOf(p.dc_ai || 0).toFixed(1)).join(' ');
    const limY = yOf(1.0);
    const curX = xOf(state.stressLambda);
    const curPt = sweep.reduce((best, p) => (!best || Math.abs((p.lam ?? p.lambda) - state.stressLambda) < Math.abs((best.lam ?? best.lambda) - state.stressLambda)) ? p : best, null);

    wrap.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + W + ' ' + H + '">'
      + grid
      + '<line x1="' + pL + '" x2="' + (W - pR) + '" y1="' + limY.toFixed(1) + '" y2="' + limY.toFixed(1) + '" stroke="#c8412f" stroke-width="1.2" stroke-dasharray="5 3"/>'
      + '<text x="' + (W - pR - 4) + '" y="' + (limY - 4).toFixed(1) + '" text-anchor="end" font-size="10" fill="#c8412f" font-family="IBM Plex Mono,monospace">Giới hạn D/C = 1.00</text>'
      + '<line x1="' + curX.toFixed(1) + '" x2="' + curX.toFixed(1) + '" y1="' + pT + '" y2="' + (H - pB) + '" stroke="#0f6bb5" stroke-opacity="0.45" stroke-width="1.5"/>'
      + '<path d="' + basePath + '" fill="none" stroke="#d98b1a" stroke-width="2" stroke-dasharray="6 3"/>'
      + '<path d="' + aiPath + '" fill="none" stroke="#2f8f5b" stroke-width="2.4"/>'
      + (curPt ? '<circle cx="' + curX.toFixed(1) + '" cy="' + yOf(curPt.dc_base || 0).toFixed(1) + '" r="4.5" fill="#d98b1a" stroke="#fff" stroke-width="1.2"/>'
        + '<circle cx="' + curX.toFixed(1) + '" cy="' + yOf(curPt.dc_ai || 0).toFixed(1) + '" r="4.5" fill="#2f8f5b" stroke="#fff" stroke-width="1.2"/>' : '')
      + '<text x="' + pL + '" y="16" font-size="10.5" font-weight="600" fill="#d98b1a" font-family="IBM Plex Sans,sans-serif">--- Human Baseline</text>'
      + '<text x="' + (pL + 135) + '" y="16" font-size="10.5" font-weight="600" fill="#2f8f5b" font-family="IBM Plex Sans,sans-serif">━━ AI-Optimized</text>'
      + '<text x="' + (W - pR) + '" y="16" text-anchor="end" font-size="10.5" fill="#0f6bb5" font-family="IBM Plex Mono,monospace">λ = ' + nf(state.stressLambda, 1) + '×</text>'
      + '<text x="' + (W / 2) + '" y="' + (H - 1) + '" text-anchor="middle" font-size="10" fill="#64748b" font-family="IBM Plex Sans,sans-serif">Hệ số nhân hoạt tải λ (0.5× → 2.5×)</text>'
      + '</svg>';
  }

  function renderLongitudinalEnvSvg() {
    const wrap = $('st-env-wrap');
    const res = state.stressResult;
    if (!wrap || !res) return;
    const baseSt = (res.baseline && (res.baseline.stations || res.baseline.envelopes)) || [];
    const aiSt = (res.ai && (res.ai.stations || res.ai.envelopes)) || [];
    if (baseSt.length < 2 || aiSt.length < 2) {
      wrap.innerHTML = '<div class="note">Chưa có dữ liệu 21 trạm dọc nhịp.</div>';
      return;
    }
    const metric = state.stressEnvMetric;
    const lam = state.stressLambda;
    const pick = (s) => {
      if (metric === 'M') return Number(s.M_kNm ?? s.m_kNm ?? 0) * (0.65 + 0.35 * lam);
      if (metric === 'defl') return Number(s.deflection_mm ?? s.defl_mm ?? 0) * lam;
      return Number(s.sigma_bot_MPa ?? s.sigma_MPa ?? 0) * (0.7 + 0.3 * lam);
    };
    const unit = metric === 'M' ? 'kN·m' : (metric === 'defl' ? 'mm' : 'MPa');
    const title = metric === 'M' ? 'Mô-men uốn M(x)' : (metric === 'defl' ? 'Độ võng hoạt tải δ(x)' : 'Ứng suất thớ dưới σ_bot(x)');

    const W = 540, H = 250, pL = 56, pR = 20, pT = 26, pB = 34;
    const plotW = W - pL - pR, plotH = H - pT - pB;
    const xs = baseSt.map((s) => Number(s.x_m ?? 0));
    const xMax = Math.max(1e-6, ...xs);
    const bVals = baseSt.map(pick);
    const aVals = aiSt.map(pick);
    const allV = bVals.concat(aVals, [0]);
    const vMin = Math.min(...allV);
    const vMax = Math.max(...allV);
    const spanV = Math.max(1e-6, (vMax - vMin) * 1.15);
    const lo = vMin - (spanV - (vMax - vMin)) * 0.3;
    const hi = lo + spanV;

    const xOf = (x) => pL + (x / xMax) * plotW;
    const yOf = (v) => pT + plotH - ((v - lo) / spanV) * plotH;

    let grid = '';
    for (let i = 0; i <= 4; i++) {
      const y = pT + (i / 4) * plotH;
      const val = hi - (i / 4) * spanV;
      grid += '<line x1="' + pL + '" x2="' + (W - pR) + '" y1="' + y.toFixed(1) + '" y2="' + y.toFixed(1) + '" stroke="#cbd5e1" stroke-opacity="0.45" stroke-dasharray="2 3"/>';
      grid += '<text x="' + (pL - 6) + '" y="' + (y + 3.5).toFixed(1) + '" text-anchor="end" font-size="10" fill="#64748b" font-family="IBM Plex Mono,monospace">' + val.toFixed(metric === 'M' ? 0 : 1) + '</text>';
    }
    for (let i = 0; i <= 4; i++) {
      const xv = (i / 4) * xMax;
      grid += '<text x="' + xOf(xv).toFixed(1) + '" y="' + (H - 12) + '" text-anchor="middle" font-size="10" fill="#64748b" font-family="IBM Plex Mono,monospace">' + xv.toFixed(1) + 'm</text>';
    }

    const bPath = baseSt.map((s, i) => (i ? 'L' : 'M') + xOf(s.x_m).toFixed(1) + ' ' + yOf(bVals[i]).toFixed(1)).join(' ');
    const aPath = aiSt.map((s, i) => (i ? 'L' : 'M') + xOf(s.x_m).toFixed(1) + ' ' + yOf(aVals[i]).toFixed(1)).join(' ');
    const midIdx = Math.floor(baseSt.length / 2);

    wrap.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + W + ' ' + H + '">'
      + grid
      + '<path d="' + bPath + '" fill="none" stroke="#d98b1a" stroke-width="2" stroke-dasharray="6 3"/>'
      + '<path d="' + aPath + '" fill="none" stroke="#0f6bb5" stroke-width="2.4"/>'
      + '<text x="' + pL + '" y="16" font-size="10.5" font-weight="600" fill="#d98b1a" font-family="IBM Plex Sans,sans-serif">--- Human (' + nf(bVals[midIdx], metric === 'M' ? 0 : 2) + ' ' + unit + ')</text>'
      + '<text x="' + (W - pR) + '" y="16" text-anchor="end" font-size="10.5" font-weight="600" fill="#0f6bb5" font-family="IBM Plex Sans,sans-serif">━━ AI (' + nf(aVals[midIdx], metric === 'M' ? 0 : 2) + ' ' + unit + ')</text>'
      + '<text x="' + (W / 2) + '" y="' + (H - 1) + '" text-anchor="middle" font-size="10" fill="#64748b" font-family="IBM Plex Sans,sans-serif">' + esc(title) + ' dọc nhịp L = ' + nf(xMax, 1) + ' m tại λ = ' + nf(lam, 1) + '×</text>'
      + '</svg>';
  }

  async function loadRuns() {
    try {
      const res = await api('/api/design-loop/runs'); const box = $('runs-list'); box.innerHTML = '';
      if (!res.runs.length) { box.innerHTML = '<div class="note">Chưa có phương án đã lưu.</div>'; return; }
      for (const r of res.runs.slice(0, 30)) {
        const d = document.createElement('div'); d.className = 'run';
        d.innerHTML = '<div class="t">' + esc(r.created_utc) + '</div><div>' + esc(r.seed_case_id) + ' → ' + esc(r.final_case_id || '–') + '</div><div class="m">' + (r.final_feasible ? pill('đạt', 'pass') : pill('chưa', 'fail')) + '<span>CP ' + nf(r.final_cost, 0) + '</span><span>D/C ' + nf(r.final_max_utilization, 3) + '</span></div>';
        d.addEventListener('click', async () => {
          try {
            const one = await api('/api/design-loop/runs/' + encodeURIComponent(r.name));
            state.report = one.report; state.reportLabel = r.name; state.stressResult = null;
            sendInspector({ type: 'dylight:load', payload: one.report, label: r.name });
            updateBoxL1Banner();
            renderBenchHints(); renderEngineerReport(); renderEvidence();
            toast('Đã nạp ' + r.name);
          } catch (err) { toast(err.message); }
        });
        box.appendChild(d);
      }
    } catch (err) { $('runs-list').innerHTML = '<div class="note">' + esc(err.message) + '</div>'; }
  }

  // ---------------------------------------------------------------- So sánh & Hồ sơ (Kỹ sư)
  function fmtDelta(a, b, unit, decimals, lowerIsBetter) {
    if (a == null || b == null || !isFinite(a) || !isFinite(b)) return '<span class="delta-neutral">–</span>';
    const diff = b - a;
    if (Math.abs(diff) < 1e-9) return '<span class="delta-neutral">0</span>';
    const pct = Math.abs(a) > 1e-9 ? (diff / a * 100) : null;
    const good = lowerIsBetter ? diff < 0 : diff > 0;
    const cls = good ? 'delta-good' : 'delta-bad';
    const sign = diff > 0 ? '+' : '';
    return '<span class="' + cls + '">' + sign + nf(diff, decimals) + (unit ? ' ' + unit : '') + (pct != null ? ' (' + sign + nf(pct, 1) + '%)' : '') + '</span>';
  }

  async function renderEngineerReport() {
    const r = state.report;
    const ov = state.overview;
    renderScopeCard(r, ov);
    if (!r) {
      $('rep-kpis').innerHTML = '';
      return;
    }
    const s = r.seed || {};
    const f = r.final || {};
    const so = s.objectives || {};
    const fo = f.objectives || {};
    $('rep-subtitle').textContent = 'Hồ sơ phương án: ' + (state.reportLabel || (f.case_id || 'mặc định')) + ' · ' + (r.grammar_id || '') + ' · Tiêu chuẩn TCVN 11823 (L1)';

    $('rep-kpis').innerHTML = ''
      + '<div class="kpi"><div class="k-lbl">Trạng thái kiểm toán L1</div><div class="k-val">' + (f.feasible ? pill('ĐẠT YÊU CẦU', 'pass') : pill('CHƯA ĐẠT', 'fail')) + '</div><div class="k-sub note">Phương án gốc: ' + (s.feasible ? 'Đạt' : 'Chưa đạt') + '</div></div>'
      + '<div class="kpi"><div class="k-lbl">Hệ số sử dụng D/C lớn nhất</div><div class="k-val">' + nf(f.max_utilization, 3) + '</div><div class="k-sub">' + fmtDelta(s.max_utilization, f.max_utilization, '', 3, true) + '</div></div>'
      + '<div class="kpi"><div class="k-lbl">Khối lượng vật liệu</div><div class="k-val">' + nf(fo.material_mass_t, 1) + ' t</div><div class="k-sub">' + fmtDelta(so.material_mass_t, fo.material_mass_t, 't', 1, true) + '</div></div>'
      + '<div class="kpi"><div class="k-lbl">Chi phí tương đối</div><div class="k-val">' + nf(fo.relative_cost, 1) + '</div><div class="k-sub">' + fmtDelta(so.relative_cost, fo.relative_cost, '', 1, true) + '</div></div>'
      + '<div class="kpi"><div class="k-lbl">Phát thải CO₂</div><div class="k-val">' + nf((fo.embodied_carbon_kgCO2e || 0) / 1000, 1) + ' tCO₂e</div><div class="k-sub">' + fmtDelta((so.embodied_carbon_kgCO2e || 0) / 1000, (fo.embodied_carbon_kgCO2e || 0) / 1000, 't', 1, true) + '</div></div>';

    const vndBase = estimateVndCost(so);
    const vndFinal = estimateVndCost(fo);
    $('rep-compare').querySelector('.body').innerHTML = '<table class="grid">'
      + '<thead><tr><th>Chỉ tiêu</th><th class="num">Phương án gốc</th><th class="num">Phương án tối ưu</th><th class="num">Chênh lệch</th></tr></thead><tbody>'
      + '<tr><td>Kiểm toán L1</td><td class="num">' + (s.feasible ? pill('Đạt', 'pass') : pill('Trượt', 'fail')) + '</td><td class="num">' + (f.feasible ? pill('Đạt', 'pass') : pill('Trượt', 'fail')) + '</td><td class="num">' + (!s.feasible && f.feasible ? '<span class="delta-good">Đã khắc phục</span>' : '–') + '</td></tr>'
      + '<tr><td>D/C lớn nhất</td><td class="num">' + nf(s.max_utilization, 3) + '</td><td class="num">' + nf(f.max_utilization, 3) + '</td><td class="num">' + fmtDelta(s.max_utilization, f.max_utilization, '', 3, true) + '</td></tr>'
      + '<tr><td>Chi phí tương đối</td><td class="num">' + nf(so.relative_cost, 2) + '</td><td class="num">' + nf(fo.relative_cost, 2) + '</td><td class="num">' + fmtDelta(so.relative_cost, fo.relative_cost, '', 2, true) + '</td></tr>'
      + (vndBase != null && vndFinal != null
        ? '<tr><td>Ước tính VNĐ <span class="note">(đơn giá kỹ sư)</span></td><td class="num">' + fmtVnd(vndBase) + '</td><td class="num">' + fmtVnd(vndFinal) + '</td><td class="num">' + fmtDelta(vndBase / 1e6, vndFinal / 1e6, 'tr', 1, true) + '</td></tr>'
        : '')
      + '<tr><td>Khối lượng (tấn)</td><td class="num">' + nf(so.material_mass_t, 1) + '</td><td class="num">' + nf(fo.material_mass_t, 1) + '</td><td class="num">' + fmtDelta(so.material_mass_t, fo.material_mass_t, 't', 1, true) + '</td></tr>'
      + '<tr><td>Phát thải (tCO₂e)</td><td class="num">' + nf((so.embodied_carbon_kgCO2e || 0) / 1000, 2) + '</td><td class="num">' + nf((fo.embodied_carbon_kgCO2e || 0) / 1000, 2) + '</td><td class="num">' + fmtDelta((so.embodied_carbon_kgCO2e || 0) / 1000, (fo.embodied_carbon_kgCO2e || 0) / 1000, 't', 2, true) + '</td></tr>'
      + '</tbody></table>'
      + '<div class="note">Chi phí tương đối dùng trọng số nội bộ; ước tính VNĐ dùng đơn giá tham chiếu do kỹ sư nhập ở Bước 1 (không thay thế dự toán).</div>';

    await ensureCards();
    const hints = extractEngineeringHints(r);
    const barsHtml = f.rule_utilizations
      ? Object.entries(f.rule_utilizations).map(([k, u]) => bar(esc(k) + ' <span class="note">' + esc(RULE_LABELS[k] || '') + '</span>', u)).join('')
      : '<div class="note">Chưa có kết quả D/C chi tiết.</div>';
    const hintsHtml = hints.length
      ? '<div class="eng-hints" style="margin-top:10px"><div class="eng-hints-title">Gợi ý khắc phục &amp; tối ưu áp dụng</div>' + hints.map((h) => '<div class="hint-item"><span class="hint-rule">' + esc(h.tag) + '</span><strong>' + esc(h.title) + '</strong><div class="note" style="margin:2px 0 0;color:var(--ink-2)">' + esc(h.detail) + '</div></div>').join('') + '</div>'
      : '';
    $('rep-dc').querySelector('.body').innerHTML = barsHtml + hintsHtml;

    const sg = s.gene || {};
    const fg = f.gene || {};
    const allKeys = [...new Set([...Object.keys(sg), ...Object.keys(fg)])];
    const diffRows = allKeys.map((k) => {
      const changed = String(sg[k]) !== String(fg[k]);
      return '<tr style="' + (changed ? 'background:var(--accent-soft)' : '') + '"><td>' + esc(VAR_LABELS[k] || k) + '</td><td class="num">' + esc(sg[k] ?? '–') + '</td><td class="num"><strong>' + esc(fg[k] ?? '–') + '</strong></td><td class="num">' + (changed ? pill('Đổi', 'info') : '<span class="note">Giữ nguyên</span>') + '</td></tr>';
    }).join('');
    $('rep-diff').querySelector('.body').innerHTML = '<table class="grid"><thead><tr><th>Thông số</th><th class="num">Gốc</th><th class="num">Tối ưu</th><th class="num">Trạng thái</th></tr></thead><tbody>' + diffRows + '</tbody></table>';
    renderInsightsCard(r);
    renderConvergenceChart(r, ov);
    renderCitationCard(r, ov);
  }

  function renderInsightsCard(r) {
    const body = $('rep-insights-body');
    if (!body) return;
    if (!r) {
      body.innerHTML = '<div class="note">Chạy tối ưu để hệ thống tự tổng hợp quy luật thiết kế và ước tính tiết kiệm VNĐ tham chiếu.</div>';
      return;
    }
    const s = r.seed || {}, f = r.final || {};
    const sg = s.gene || {}, fg = f.gene || {};
    const so = s.objectives || {}, fo = f.objectives || {};
    const bullets = [];

    // 1. Tóm tắt thay đổi thông số chính
    const changes = [];
    for (const k of new Set([...Object.keys(sg), ...Object.keys(fg)])) {
      if (String(sg[k]) !== String(fg[k])) {
        changes.push((VAR_LABELS[k] || k) + ': ' + sg[k] + ' → ' + fg[k]);
      }
    }
    if (changes.length) {
      bullets.push('<li><span class="ins-tag">[ĐIỀU CHỈNH HÌNH HỌC &amp; VẬT LIỆU]</span>AI đã thay đổi <strong>' + changes.length + ' thông số</strong> (' + esc(changes.slice(0, 5).join('; ')) + (changes.length > 5 ? '; …' : '') + ') để đưa hệ số sử dụng D/C từ <strong>' + nf(s.max_utilization, 3) + '</strong> về <strong>' + nf(f.max_utilization, 3) + '</strong>.</li>');
    } else {
      bullets.push('<li><span class="ins-tag">[HÌNH HỌC]</span>Phương án gốc đã đạt điểm cân bằng cục bộ trong không gian tìm kiếm hiện tại.</li>');
    }

    // 2. Thẻ tri thức đã kích hoạt
    const hints = extractEngineeringHints(r);
    if (hints.length) {
      bullets.push('<li><span class="ins-tag">[QUY LUẬT KỸ THUẬT KÍCH HOẠT]</span>' + hints.map((h) => '<strong>' + esc(h.tag) + '</strong>: ' + esc(h.title)).join(' · ') + '.</li>');
    }

    // 3. Ước tính tiết kiệm VNĐ theo đơn giá tham chiếu kỹ sư nhập
    const vndBase = estimateVndCost(so);
    const vndFinal = estimateVndCost(fo);
    if (vndBase != null && vndFinal != null) {
      const save = vndBase - vndFinal;
      const pct = vndBase > 0 ? (save / vndBase * 100) : 0;
      const verb = save >= 0 ? 'tiết kiệm ước tính' : 'tăng thêm ước tính (để khắc phục vi phạm chịu lực)';
      bullets.push('<li><span class="ins-tag">[KINH TẾ THAM CHIẾU]</span>Theo đơn giá kỹ sư nhập ở Bước 1 (BT ' + nf(state.brief.concrete_vnd_m3 / 1e6, 2) + ' tr/m³, Cáp ' + nf(state.brief.tendon_vnd_t / 1e6, 1) + ' tr/tấn), phương án tối ưu ' + verb + ' <strong>' + fmtVnd(Math.abs(save)) + '</strong> (' + (save >= 0 ? '-' : '+') + nf(Math.abs(pct), 1) + '%) và thay đổi phát thải <strong>' + nf(((fo.embodied_carbon_kgCO2e || 0) - (so.embodied_carbon_kgCO2e || 0)) / 1000, 2) + ' tCO₂e</strong>.</li>');
    }

    // 4. Dự trữ thử tải vật lý nếu đã chạy
    if (state.stressResult && state.stressResult.baseline && state.stressResult.ai) {
      const b = state.stressResult.baseline, a = state.stressResult.ai;
      const rfB = b.rating_factor ?? b.rf, rfA = a.rating_factor ?? a.rf;
      if (rfB != null && rfA != null) {
        bullets.push('<li><span class="ins-tag">[DỰ TRỮ THỬ TẢI λ]</span>Dưới kịch bản <strong>' + esc(state.scenario.id || 'CUSTOM') + '</strong>, Rating Factor (RF) thay đổi từ <strong>' + nf(rfB, 2) + '</strong> (Human) → <strong>' + nf(rfA, 2) + '</strong> (AI); ngưỡng CĐ-I đạt <strong>λ = ' + nf(a.lambda_str1, 2) + '×</strong>.</li>');
      }
    }

    if (String(r.grammar_id || '').includes('box_girder')) {
      bullets.push('<li><span class="ins-tag">[LƯU Ý DẦM HỘP L2]</span>Kết quả trên chỉ sàng lọc uốn/cắt 1D ở L1 — cần xuất gói <code>bridge_interchange_v1</code> sang MIDAS Civil để kiểm chứng xoắn St. Venant, vênh mặt cắt và hiệu ứng trễ cắt (Shear Lag).</li>');
    }

    body.innerHTML = '<ul class="insight-list">' + bullets.join('') + '</ul>';
  }

  // ---------------------------------------------------------------- Bước 4: Xuất gói đồng bộ Revit/MIDAS & Đối chứng L2
  if ($('btn-export-interchange')) {
    $('btn-export-interchange').addEventListener('click', async () => {
      if (!state.report) return toast('Chưa có phương án để xuất gói đồng bộ.');
      const btn = $('btn-export-interchange');
      btn.disabled = true;
      try {
        const res = await api('/api/export/interchange', {
          report: state.report,
          scenario: state.scenario,
          label: (state.reportLabel || (state.report.final && state.report.final.case_id) || 'dylight_bridge').replace(/\.json$/, ''),
        });
        state.interchangeBundle = res;
        const icObj = res.bridge_interchange_v1 || res.interchange || res.interchange_json || res;
        const sha = res.sha256 || (icObj && icObj.sha256) || 'local';
        if ($('ic-sha-chip')) $('ic-sha-chip').textContent = 'SHA-256: ' + String(sha).slice(0, 16) + '…';
        if ($('ic-summary')) {
          $('ic-summary').innerHTML = 'Đã tạo thành công gói đồng bộ chuẩn <code>bridge_interchange/1.0</code> kèm file tải trọng &amp; tổ hợp MIDAS (<code>*STLDCASE</code>, <code>*BEAMLOAD</code>, <code>*BSTEMP</code>, <code>*SPFC</code>, <code>*LOADCOMB</code>) và bảng trạm Revit/Dynamo cho kịch bản <strong>' + esc(state.scenario.id || 'CUSTOM') + '</strong>.';
        }
        if ($('interchange-panel')) $('interchange-panel').style.display = 'block';
        toast('Đã sinh gói đồng bộ Revit/MIDAS (bridge_interchange_v1)');
      } catch (err) {
        toast('Lỗi xuất gói đồng bộ: ' + err.message);
      }
      btn.disabled = false;
    });
  }

  if ($('btn-dl-ic-json')) {
    $('btn-dl-ic-json').addEventListener('click', () => {
      const b = state.interchangeBundle;
      if (!b) return toast('Hãy bấm Xuất gói đồng bộ trước.');
      const obj = b.bridge_interchange_v1 || b.interchange || b.interchange_json || b;
      downloadBlob('bridge_interchange_v1.json', JSON.stringify(obj, null, 2), 'application/json;charset=utf-8');
      toast('Đã tải bridge_interchange_v1.json');
    });
  }
  if ($('btn-dl-ic-mct')) {
    $('btn-dl-ic-mct').addEventListener('click', () => {
      const b = state.interchangeBundle;
      if (!b) return toast('Hãy bấm Xuất gói đồng bộ trước.');
      const mct = b.mct_text || b.midas_mct || b.mct || '';
      if (!mct) return toast('Gói không chứa nội dung .mct');
      downloadBlob('midas_full_loads.mct', mct, 'text/plain;charset=utf-8');
      toast('Đã tải midas_full_loads.mct');
    });
  }
  if ($('btn-dl-ic-csv')) {
    $('btn-dl-ic-csv').addEventListener('click', () => {
      const b = state.interchangeBundle;
      if (!b) return toast('Hãy bấm Xuất gói đồng bộ trước.');
      const csv = b.dynamo_csv || b.revit_csv || b.csv_text || '';
      if (!csv) return toast('Gói không chứa bảng trạm Dynamo CSV');
      downloadBlob('revit_dynamo_stations.csv', '\uFEFF' + csv, 'text/csv;charset=utf-8');
      toast('Đã tải revit_dynamo_stations.csv');
    });
  }

  function readOptNum(id) {
    const el = $(id);
    if (!el || el.value === '') return null;
    const n = Number(el.value);
    return isFinite(n) ? n : null;
  }

  function formatL2MetricLabel(row) {
    const k = String(row.key || row.metric || '').toLowerCase();
    const lbl = String(row.label || row.metric || row.key || '');
    if (k === 'm_max_knm' || lbl.includes('M_{\\max}')) return 'Mô-men M<sub>max</sub> (kN·m)';
    if (k === 'sigma_bot_mpa' || lbl.includes('\\sigma')) return 'Ứng suất σ<sub>bot</sub> (MPa)';
    if (k === 'deflection_mm' || lbl.includes('\\delta')) return 'Độ võng δ<sub>LL</sub> (mm)';
    if (k === 'volume_m3' || lbl.includes('V_c')) return 'Thể tích V<sub>c</sub> (m³)';
    if (k === 'max_dc' || lbl.includes('D/C')) return 'Tỷ số (D/C)<sub>max</sub>';
    return esc(lbl.replace(/\$/g, ''));
  }

  if ($('btn-l2-compare')) {
    $('btn-l2-compare').addEventListener('click', async () => {
      const btn = $('btn-l2-compare');
      btn.disabled = true;
      const r = state.report || {};
      const s = r.seed || {}, f = r.final || {};
      const stB = (state.stressResult && state.stressResult.baseline) || {};
      const stA = (state.stressResult && state.stressResult.ai) || {};
      const pickMid = (arr, key) => {
        if (!Array.isArray(arr) || !arr.length) return null;
        const m = arr[Math.floor(arr.length / 2)];
        return m && m[key] != null ? Number(m[key]) : null;
      };
      const l1_baseline = {
        m_max_kNm: pickMid(stB.stations || stB.envelopes, 'M_kNm'),
        sigma_bot_MPa: pickMid(stB.stations || stB.envelopes, 'sigma_bot_MPa'),
        deflection_mm: pickMid(stB.stations || stB.envelopes, 'deflection_mm'),
        volume_m3: s.objectives && s.objectives.material_mass_t != null ? +(Number(s.objectives.material_mass_t) * 0.955 / 2.45).toFixed(2) : null,
        max_dc: s.max_utilization != null ? Number(s.max_utilization) : null,
      };
      const l1_ai = {
        m_max_kNm: pickMid(stA.stations || stA.envelopes, 'M_kNm'),
        sigma_bot_MPa: pickMid(stA.stations || stA.envelopes, 'sigma_bot_MPa'),
        deflection_mm: pickMid(stA.stations || stA.envelopes, 'deflection_mm'),
        volume_m3: f.objectives && f.objectives.material_mass_t != null ? +(Number(f.objectives.material_mass_t) * 0.955 / 2.45).toFixed(2) : null,
        max_dc: f.max_utilization != null ? Number(f.max_utilization) : null,
      };
      const l2_baseline = {
        m_max_kNm: readOptNum('l2-base-m'),
        sigma_bot_MPa: readOptNum('l2-base-sigma'),
        deflection_mm: readOptNum('l2-base-defl'),
        volume_m3: readOptNum('l2-base-vol'),
        max_dc: readOptNum('l2-base-dc'),
      };
      const l2_ai = {
        m_max_kNm: readOptNum('l2-ai-m'),
        sigma_bot_MPa: readOptNum('l2-ai-sigma'),
        deflection_mm: readOptNum('l2-ai-defl'),
        volume_m3: readOptNum('l2-ai-vol'),
        max_dc: readOptNum('l2-ai-dc'),
      };
      try {
        const res = await api('/api/validation/l2-compare', { l1_baseline, l1_ai, l2_baseline, l2_ai });
        state.l2Result = res;
        const rows = Array.isArray(res.rows) ? res.rows : (Array.isArray(res.metrics) ? res.metrics : []);
        if (rows.length) {
          $('l2-result').innerHTML = '<table class="grid"><thead><tr><th>Đại lượng</th><th class="num">L1 Human</th><th class="num">L2 Human</th><th class="num">Sai số L1–L2 (H)</th><th class="num">L1 AI</th><th class="num">L2 AI</th><th class="num">Sai số L1–L2 (AI)</th><th class="num">Lợi thế AI (L2)</th></tr></thead><tbody>'
            + rows.map((row) => {
              const errBase = row.l1_vs_l2_err_baseline_pct ?? row.err_base_pct;
              const errAi = row.l1_vs_l2_err_ai_pct ?? row.err_ai_pct;
              const aiDelta = row.human_vs_ai_l2_delta_pct ?? row.ai_delta_pct;
              return '<tr><td>' + formatL2MetricLabel(row) + '</td>'
                + '<td class="num">' + nf(row.l1_baseline ?? row.l1_base, 2) + '</td>'
                + '<td class="num">' + nf(row.l2_baseline ?? row.l2_base, 2) + '</td>'
                + '<td class="num">' + (errBase != null ? nf(errBase, 1) + '%' : '–') + '</td>'
                + '<td class="num">' + nf(row.l1_ai, 2) + '</td>'
                + '<td class="num"><strong>' + nf(row.l2_ai, 2) + '</strong></td>'
                + '<td class="num">' + (errAi != null ? nf(errAi, 1) + '%' : '–') + '</td>'
                + '<td class="num">' + (aiDelta != null ? '<span class="' + (aiDelta <= 0 ? 'delta-good' : 'delta-bad') + '">' + (aiDelta > 0 ? '+' : '') + nf(aiDelta, 1) + '%</span>' : '–') + '</td></tr>';
            }).join('')
            + '</tbody></table>';
        } else {
          $('l2-result').innerHTML = '<pre class="note" style="white-space:pre-wrap;font-family:var(--font-mono)">' + esc(JSON.stringify(res.summary || res, null, 2)) + '</pre>';
        }
        $('btn-l2-tex').disabled = !(res.latex_table);
        $('btn-l2-csv').disabled = !(res.csv_text);
        toast('Đã hoàn tất đối chứng MIDAS Civil L2');
      } catch (err) {
        $('l2-result').innerHTML = '<div class="note" style="color:var(--fail)">Lỗi đối chứng L2: ' + esc(err.message) + '</div>';
      }
      btn.disabled = false;
    });
  }

  if ($('btn-l2-tex')) {
    $('btn-l2-tex').addEventListener('click', () => {
      if (!state.l2Result || !state.l2Result.latex_table) return toast('Chưa có bảng LaTeX đối chứng L2.');
      downloadBlob('dylight_l2_validation.tex', state.l2Result.latex_table, 'text/plain;charset=utf-8');
      toast('Đã tải bảng đối chứng L2 LaTeX (.tex)');
    });
  }
  if ($('btn-l2-csv')) {
    $('btn-l2-csv').addEventListener('click', () => {
      if (!state.l2Result || !state.l2Result.csv_text) return toast('Chưa có CSV đối chứng L2.');
      downloadBlob('dylight_l2_validation.csv', '\uFEFF' + state.l2Result.csv_text, 'text/csv;charset=utf-8');
      toast('Đã tải CSV đối chứng L2');
    });
  }

  function extractLineagePoints(r) {
    if (!r) return [];
    const views = [];
    if (r.seed) views.push(r.seed);
    for (const it of (r.iterations || [])) {
      const acc = (it.probes || []).find((p) => p.outcome === 'ACCEPTED');
      if (acc) views.push(acc);
    }
    if (r.final) {
      const last = views[views.length - 1];
      if (last && last.case_id === r.final.case_id) views[views.length - 1] = Object.assign({}, last, r.final);
      else if (!views.length || last.case_id !== r.final.case_id) views.push(r.final);
    }
    return views.map((rec, idx) => ({
      step: idx,
      case_id: rec.case_id || ('#' + idx),
      cost: rec.objectives && rec.objectives.relative_cost != null ? Number(rec.objectives.relative_cost) : null,
      dc: rec.max_utilization != null ? Number(rec.max_utilization) : null,
      feasible: !!rec.feasible,
    }));
  }

  function renderConvergenceChart(r, ov) {
    const wrap = $('rep-chart');
    const pts = extractLineagePoints(r);
    if (pts.length < 2) {
      wrap.innerHTML = '<div class="note">Phương án có ít hơn 2 bước lặp nên chưa cần vẽ đường hội tụ.</div>';
      return;
    }
    const W = 760, H = 260, pL = 62, pR = 58, pT = 28, pB = 38;
    const plotW = W - pL - pR, plotH = H - pT - pB;
    const oracleCost = (r.grammar_id === 'super_t_simple_v1' && ov && ov.oracle_v1 && ov.oracle_v1.best_cost != null)
      ? Number(ov.oracle_v1.best_cost) : null;
    const costs = pts.map((p) => p.cost).filter((v) => v != null);
    if (oracleCost != null) costs.push(oracleCost);
    const cMin = costs.length ? Math.min(...costs) * 0.96 : 0;
    const cMax = costs.length ? Math.max(...costs) * 1.04 : 1;
    const dcs = pts.map((p) => p.dc).filter((v) => v != null);
    const dMin = 0;
    const dMax = Math.max(1.2, dcs.length ? Math.max(...dcs) * 1.08 : 1.2);
    const xOf = (i) => pL + (pts.length === 1 ? plotW / 2 : (i / (pts.length - 1)) * plotW);
    const yCost = (v) => pT + plotH - ((v - cMin) / Math.max(1e-6, cMax - cMin)) * plotH;
    const yDc = (v) => pT + plotH - ((v - dMin) / Math.max(1e-6, dMax - dMin)) * plotH;

    let grid = '';
    for (let i = 0; i <= 4; i++) {
      const y = pT + (i / 4) * plotH;
      const cv = cMax - (i / 4) * (cMax - cMin);
      const dv = dMax - (i / 4) * (dMax - dMin);
      grid += '<line x1="' + pL + '" x2="' + (W - pR) + '" y1="' + y.toFixed(1) + '" y2="' + y.toFixed(1) + '" stroke="#cbd5e1" stroke-opacity="0.45" stroke-dasharray="2 3"/>';
      grid += '<text x="' + (pL - 8) + '" y="' + (y + 4).toFixed(1) + '" text-anchor="end" font-size="10.5" fill="#0f6bb5" font-family="IBM Plex Mono,monospace">' + cv.toFixed(0) + '</text>';
      grid += '<text x="' + (W - pR + 8) + '" y="' + (y + 4).toFixed(1) + '" text-anchor="start" font-size="10.5" fill="#d98b1a" font-family="IBM Plex Mono,monospace">' + dv.toFixed(2) + '</text>';
    }
    const costPath = pts.filter((p) => p.cost != null).map((p, idx) => (idx ? 'L' : 'M') + xOf(p.step).toFixed(1) + ' ' + yCost(p.cost).toFixed(1)).join(' ');
    const dcPath = pts.filter((p) => p.dc != null).map((p, idx) => (idx ? 'L' : 'M') + xOf(p.step).toFixed(1) + ' ' + yDc(p.dc).toFixed(1)).join(' ');
    const oracleLine = oracleCost != null
      ? '<line x1="' + pL + '" x2="' + (W - pR) + '" y1="' + yCost(oracleCost).toFixed(1) + '" y2="' + yCost(oracleCost).toFixed(1) + '" stroke="#2f8f5b" stroke-width="1.3" stroke-dasharray="6 4"/>'
        + '<text x="' + (pL + 6) + '" y="' + (yCost(oracleCost) - 5).toFixed(1) + '" font-size="10" fill="#2f8f5b" font-family="IBM Plex Mono,monospace">Oracle toàn cục = ' + oracleCost.toFixed(2) + '</text>'
      : '';
    const dcLimitY = yDc(1.0);
    const dcLimitLine = '<line x1="' + pL + '" x2="' + (W - pR) + '" y1="' + dcLimitY.toFixed(1) + '" y2="' + dcLimitY.toFixed(1) + '" stroke="#c8412f" stroke-width="1.1" stroke-dasharray="4 3"/>'
      + '<text x="' + (W - pR - 4) + '" y="' + (dcLimitY - 4).toFixed(1) + '" text-anchor="end" font-size="10" fill="#c8412f" font-family="IBM Plex Mono,monospace">D/C = 1.00</text>';
    const dots = pts.map((p) => {
      const cx = xOf(p.step).toFixed(1);
      const cDot = p.cost != null ? '<circle cx="' + cx + '" cy="' + yCost(p.cost).toFixed(1) + '" r="4" fill="' + (p.feasible ? '#2f8f5b' : '#c8412f') + '" stroke="#ffffff" stroke-width="1.2"><title>Bước ' + p.step + ': Chi phí ' + nf(p.cost, 2) + ', D/C ' + nf(p.dc, 3) + '</title></circle>' : '';
      const xLbl = (pts.length <= 16 || p.step === 0 || p.step === pts.length - 1 || p.step % 2 === 0)
        ? '<text x="' + cx + '" y="' + (H - 12) + '" text-anchor="middle" font-size="10.5" fill="#64748b" font-family="IBM Plex Mono,monospace">' + p.step + '</text>' : '';
      return cDot + xLbl;
    }).join('');

    wrap.innerHTML = '<svg id="convergence-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + W + ' ' + H + '">'
      + '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="transparent"/>'
      + grid + oracleLine + dcLimitLine
      + (costPath ? '<path d="' + costPath + '" fill="none" stroke="#0f6bb5" stroke-width="2.2"/>' : '')
      + (dcPath ? '<path d="' + dcPath + '" fill="none" stroke="#d98b1a" stroke-width="1.8" stroke-dasharray="5 3"/>' : '')
      + dots
      + '<text x="' + pL + '" y="16" font-size="11" font-weight="600" fill="#0f6bb5" font-family="IBM Plex Sans,sans-serif">● Chi phí tương đối (trục trái)</text>'
      + '<text x="' + (pL + 195) + '" y="16" font-size="11" font-weight="600" fill="#d98b1a" font-family="IBM Plex Sans,sans-serif">--- D/C max (trục phải)</text>'
      + '<text x="' + (W - pR) + '" y="16" text-anchor="end" font-size="10.5" fill="#64748b" font-family="IBM Plex Sans,sans-serif">● Xanh: Đạt L1 · ● Đỏ: Trượt L1</text>'
      + '<text x="' + (W / 2) + '" y="' + (H - 1) + '" text-anchor="middle" font-size="10.5" fill="#64748b" font-family="IBM Plex Sans,sans-serif">Bước chấp nhận (0 = Phương án gốc → ' + (pts.length - 1) + ' = Phương án cuối)</text>'
      + '</svg>';
  }

  function renderCitationCard(r, ov) {
    const body = $('rep-cite-body');
    if (!body) return;
    const sw = ov ? (ov.software_version || '0.8.0') : (r ? r.software_version : '0.8.0');
    const labv = ov ? (ov.lab_version || 'lab-ui/0.1.0') : 'lab-ui/0.1.0';
    const sha = r && r.report_sha256 ? r.report_sha256 : 'Chưa có báo cáo';
    const ruleset = r ? r.ruleset_version : 'TCVN 11823:2017 (L1)';
    const grammar = r ? (r.grammar_id + ' ' + r.grammar_version) : 'super_t_simple_v1 / v2';
    body.innerHTML = '<div class="cite-grid">'
      + '<div class="cite-item"><div class="c-k">Phiên bản công cụ</div><div class="c-v">DYLIGHT Bridge ' + esc(sw) + ' (' + esc(labv) + ')</div></div>'
      + '<div class="cite-item"><div class="c-k">Bộ kiểm toán &amp; Grammar</div><div class="c-v">' + esc(ruleset) + ' · ' + esc(grammar) + '</div></div>'
      + '<div class="cite-item"><div class="c-k">Mức công bố (Claim Ceiling)</div><div class="c-v">SCREENED (L0/L1 · Verifier độc lập)</div></div>'
      + '<div class="cite-item"><div class="c-k">Mã xác thực tái lập (SHA-256)</div><div class="c-v">' + esc(sha.slice(0, 32)) + (sha.length > 32 ? '…' : '') + '</div></div>'
      + '</div>';
  }

  $('btn-export-svg').addEventListener('click', () => {
    const svg = $('convergence-svg');
    if (!svg) return toast('Chưa có biểu đồ hội tụ để tải.');
    const clone = svg.cloneNode(true);
    const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    bg.setAttribute('width', '100%'); bg.setAttribute('height', '100%'); bg.setAttribute('fill', '#ffffff');
    clone.insertBefore(bg, clone.firstChild);
    const xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(clone);
    downloadBlob((state.reportLabel || 'hoi_tu_toi_uu').replace(/\.json$/, '') + '_convergence.svg', xml, 'image/svg+xml;charset=utf-8');
    toast('Đã tải hình vector SVG cho bài báo');
  });

  $('btn-copy-bibtex').addEventListener('click', async () => {
    const r = state.report, ov = state.overview;
    const sw = ov ? ov.software_version : '0.8.0';
    const sha = r && r.report_sha256 ? r.report_sha256.slice(0, 16) : 'local';
    const bib = '@software{dylight_bridge_2026,\n'
      + '  title     = {DYLIGHT Bridge: Verifier-Driven Parametric Bridge Girder Optimization and MIDAS PSC Section Workbench},\n'
      + '  version   = {' + sw + '},\n'
      + '  year      = {2026},\n'
      + '  note      = {TCVN 11823:2017 L0/L1 Screened Artifact; Report SHA-256 prefix: ' + sha + '}\n'
      + '}';
    try {
      await navigator.clipboard.writeText(bib);
      toast('Đã sao chép trích dẫn BibTeX vào clipboard');
    } catch (err) {
      downloadBlob('dylight_bridge_2026.bib', bib, 'text/plain;charset=utf-8');
      toast('Đã tải file trích dẫn .bib');
    }
  });

  // ---------------------------------------------------------------- thực nghiệm đối chứng (Ablation Benchmark)
  const BENCHMARK_POLICIES = [
    { id: 'Proposed (Tri thức + TRIM)', move_policy: 'knowledge_priority', trim_order: 'recent_reject_last', trim_enabled: true },
    { id: 'Ablation 1 (Không tri thức)', move_policy: 'cheapest_first', trim_order: 'cheapest_first', trim_enabled: true },
    { id: 'Ablation 2 (Tắt TRIM)', move_policy: 'knowledge_priority', trim_order: 'cheapest_first', trim_enabled: false },
  ];

  $('btn-run-benchmark').addEventListener('click', async () => {
    const btn = $('btn-run-benchmark');
    btn.disabled = true;
    const scope = $('bm-scope').value;
    const budget = +$('in-budget').value || 40;
    const target = +$('in-target').value || 1.0;
    const objective = $('in-objective').value || 'relative_cost';
    const oracleCost = (state.overview && state.overview.oracle_v1 && state.overview.oracle_v1.best_cost != null)
      ? Number(state.overview.oracle_v1.best_cost) : null;

    let cases = [];
    if (scope === 'all' && state.catalog && state.catalog.gold_cases) {
      cases = state.catalog.gold_cases.map((g) => ({ label: g.file.replace('.json', ''), payload: { seed_file: g.file } }));
    } else {
      try {
        const sel = $('seed-select');
        const lbl = sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].textContent.split(' — ')[0] : 'Current';
        cases = [{ label: lbl, payload: seedPayload() }];
      } catch (err) {
        $('bm-status').innerHTML = '<span style="color:var(--fail)">' + esc(err.message) + '</span>';
        btn.disabled = false;
        return;
      }
    }

    const total = cases.length * BENCHMARK_POLICIES.length;
    const rows = [];
    let done = 0;
    for (const c of cases) {
      for (const pol of BENCHMARK_POLICIES) {
        done += 1;
        $('bm-status').textContent = 'Đang chạy thực nghiệm ' + done + '/' + total + ': ' + c.label + ' · ' + pol.id + '…';
        try {
          const req = Object.assign({}, c.payload, {
            budget,
            policy: { objective_key: objective, utilization_target: target, move_policy: pol.move_policy, trim_order: pol.trim_order, trim_enabled: pol.trim_enabled },
          });
          const res = await api('/api/design-loop', req);
          const rep = res.report, f = rep.final || {}, fo = f.objectives || {};
          const cost = fo.relative_cost != null ? Number(fo.relative_cost) : null;
          const gap = (oracleCost != null && cost != null && rep.grammar_id === 'super_t_simple_v1' && f.feasible)
            ? ((cost - oracleCost) / oracleCost * 100) : null;
          rows.push({
            case_label: c.label,
            strategy: pol.id,
            feasible: !!f.feasible,
            solver_calls: rep.counters.evaluator.solver_calls,
            dc: f.max_utilization,
            cost,
            oracle_gap_pct: gap,
            mass_t: fo.material_mass_t,
            termination: rep.termination.reason,
          });
        } catch (err) {
          rows.push({ case_label: c.label, strategy: pol.id, feasible: false, solver_calls: 0, dc: null, cost: null, oracle_gap_pct: null, mass_t: null, termination: 'ERROR: ' + err.message });
        }
      }
    }
    state.benchmarkRows = rows;
    $('bm-status').innerHTML = 'Hoàn tất <strong>' + rows.length + ' lượt thực nghiệm</strong> (Ngân sách ' + budget + ' lần solver · D/C ≤ ' + target + (oracleCost != null ? ' · Oracle v1 = ' + nf(oracleCost, 2) : '') + '). Có thể xuất ngay bảng LaTeX (.tex) hoặc CSV cho bài báo.';
    $('bm-table').innerHTML = '<table class="grid"><thead><tr><th>Ca thử</th><th>Chiến lược</th><th>Đạt L1</th><th class="num">Solver</th><th class="num">D/C max</th><th class="num">Chi phí</th><th class="num">Lệch Oracle</th><th class="num">Khối lượng (t)</th></tr></thead><tbody>'
      + rows.map((r) => '<tr><td>' + esc(r.case_label) + '</td><td>' + esc(r.strategy) + '</td><td>' + (r.feasible ? pill('Đạt', 'pass') : pill('Chưa', 'fail')) + '</td><td class="num">' + r.solver_calls + '</td><td class="num">' + nf(r.dc, 3) + '</td><td class="num">' + nf(r.cost, 2) + '</td><td class="num">' + (r.oracle_gap_pct != null ? '+' + nf(r.oracle_gap_pct, 2) + '%' : '–') + '</td><td class="num">' + nf(r.mass_t, 1) + '</td></tr>').join('')
      + '</tbody></table>';
    $('btn-export-tex').disabled = !rows.length;
    $('btn-export-bm-csv').disabled = !rows.length;
    btn.disabled = false;
    loadRuns();
  });

  $('btn-export-tex').addEventListener('click', () => {
    const rows = state.benchmarkRows;
    if (!rows.length) return toast('Hãy chạy thực nghiệm đối chứng trước.');
    const texEsc = (s) => String(s ?? '').replace(/([_%&#])/g, '\\$1');
    const lines = [
      '% Generated by DYLIGHT Bridge — Ablation Benchmark Table (requires \\usepackage{booktabs})',
      '\\begin{table}[htbp]',
      '  \\centering',
      '  \\caption{So s\\\'anh hi\\d{e}u n\\u{a}ng c\\\'ac chi\\\'\\^e{}n l\\u{u}\\d{o}c t\\\'\\^o{}i \\u{u}u h\\\'oa d\\`\\^a{}m c\\`\\^a{}u (TCVN 11823:2017 L1)}',
      '  \\label{tab:ablation_benchmark}',
      '  \\begin{tabular}{llccrrrr}',
      '    \\toprule',
      '    Case & Strategy & Feasible & Solver Calls & $D/C_{\\max}$ & Rel. Cost & Oracle Gap (\\%) & Mass (t) \\\\',
      '    \\midrule',
    ];
    for (const r of rows) {
      lines.push('    ' + texEsc(r.case_label) + ' & ' + texEsc(r.strategy) + ' & ' + (r.feasible ? 'Yes' : 'No')
        + ' & ' + r.solver_calls
        + ' & ' + (r.dc != null ? Number(r.dc).toFixed(3) : '--')
        + ' & ' + (r.cost != null ? Number(r.cost).toFixed(2) : '--')
        + ' & ' + (r.oracle_gap_pct != null ? Number(r.oracle_gap_pct).toFixed(2) : '--')
        + ' & ' + (r.mass_t != null ? Number(r.mass_t).toFixed(1) : '--') + ' \\\\');
    }
    lines.push('    \\bottomrule', '  \\end{tabular}', '\\end{table}');
    downloadBlob('dylight_ablation_benchmark.tex', lines.join('\n'), 'text/plain;charset=utf-8');
    toast('Đã tải bảng LaTeX (.tex) cho bài báo');
  });

  $('btn-export-bm-csv').addEventListener('click', () => {
    const rows = state.benchmarkRows;
    if (!rows.length) return toast('Hãy chạy thực nghiệm đối chứng trước.');
    const csvRows = [['Ca thử', 'Chiến lược', 'Đạt L1', 'Số lần gọi Solver', 'D/C max', 'Chi phí tương đối', 'Lệch Oracle (%)', 'Khối lượng (tấn)', 'Trạng thái kết thúc']];
    for (const r of rows) {
      csvRows.push([r.case_label, r.strategy, r.feasible ? 'Đạt' : 'Chưa đạt', r.solver_calls, r.dc ?? '', r.cost ?? '', r.oracle_gap_pct != null ? r.oracle_gap_pct.toFixed(2) : '', r.mass_t ?? '', r.termination]);
    }
    const csv = '\uFEFF' + csvRows.map((row) => row.map((v) => '"' + String(v).replace(/"/g, '""') + '"').join(',')).join('\r\n');
    downloadBlob('dylight_ablation_benchmark.csv', csv, 'text/csv;charset=utf-8');
    toast('Đã tải CSV thực nghiệm đối chứng');
  });

  function renderScopeCard(r, ov) {
    const f = r ? (r.final || {}) : null;
    const l0Ok = f && f.status === 'SUCCESS';
    const l1Ok = f && f.solver_status === 'CONVERGED';
    const unknownCount = ov && ov.site ? ov.site.unknown_fields.length : 31;
    $('rep-scope').querySelector('.body').innerHTML = '<div class="scope-list">'
      + '<div class="scope-item ' + (l0Ok ? 'ok' : 'todo') + '"><div><strong>' + (l0Ok ? '✓' : '!') + ' Hình học &amp; Cấu tạo (L0)</strong><span>Kiểm tra cánh hẫng, khe cánh dầm, chiều dày bản tối thiểu, quy tắc chế tạo.</span></div></div>'
      + '<div class="scope-item ' + (l1Ok ? 'ok' : 'todo') + '"><div><strong>' + (l1Ok ? '✓' : '!') + ' Kiểm toán dầm đơn TCVN 11823 (L1)</strong><span>Uốn CĐ-I, Cắt CĐ-I, Ứng suất kéo thớ dưới SD-III, Võng hoạt tải.</span></div></div>'
      + '<div class="scope-item todo"><div><strong>○ Kiểm chứng FEM 3D / MIDAS Civil (L2)</strong><span>Cần xuất mặt cắt sang MIDAS để kiểm tra phân bố ngang, xoắn, ứng suất cục bộ.</span></div></div>'
      + '<div class="scope-item todo"><div><strong>○ Giai đoạn thi công, Mỏi, Ổn định &amp; Điều kiện địa điểm</strong><span>Còn ' + unknownCount + ' thông số địa điểm (gió, động đất, cấp phơi nhiễm) chưa nhập và cần kỹ sư chủ trì ký duyệt.</span></div></div>'
      + '</div>';
  }

  function downloadBlob(filename, content, mime) {
    const blob = new Blob([content], { type: mime });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  $('btn-export-print').addEventListener('click', () => {
    if (!state.report) return toast('Chưa có phương án để in.');
    window.print();
  });
  $('btn-export-csv').addEventListener('click', () => {
    const r = state.report;
    if (!r) return toast('Chưa có phương án để xuất CSV.');
    const s = r.seed || {}, f = r.final || {}, so = s.objectives || {}, fo = f.objectives || {};
    const rows = [
      ['Hạng mục', 'Phương án gốc', 'Phương án tối ưu'],
      ['Mã phương án', s.case_id || '', f.case_id || ''],
      ['Trạng thái L1', s.feasible ? 'Đạt' : 'Chưa đạt', f.feasible ? 'Đạt' : 'Chưa đạt'],
      ['D/C lớn nhất', s.max_utilization ?? '', f.max_utilization ?? ''],
      ['Chi phí tương đối', so.relative_cost ?? '', fo.relative_cost ?? ''],
      ['Khối lượng (tấn)', so.material_mass_t ?? '', fo.material_mass_t ?? ''],
      ['Phát thải CO2 (kgCO2e)', so.embodied_carbon_kgCO2e ?? '', fo.embodied_carbon_kgCO2e ?? ''],
    ];
    const sg = s.gene || {}, fg = f.gene || {};
    for (const k of new Set([...Object.keys(sg), ...Object.keys(fg)])) {
      rows.push([VAR_LABELS[k] || k, sg[k] ?? '', fg[k] ?? '']);
    }
    if (f.rule_utilizations) {
      for (const [k, u] of Object.entries(f.rule_utilizations)) {
        rows.push(['D/C ' + k + ' (' + (RULE_LABELS[k] || '') + ')', (s.rule_utilizations || {})[k] ?? '', u]);
      }
    }
    const csv = '\uFEFF' + rows.map((row) => row.map((v) => '"' + String(v).replace(/"/g, '""') + '"').join(',')).join('\r\n');
    downloadBlob((state.reportLabel || 'phuong_an_cau').replace(/\.json$/, '') + '_so_sanh.csv', csv, 'text/csv;charset=utf-8');
    toast('Đã tải file CSV cho Excel');
  });
  $('btn-export-json').addEventListener('click', () => {
    if (!state.report) return toast('Chưa có dữ liệu để tải.');
    downloadBlob(state.reportLabel || 'dylight_report.json', JSON.stringify(state.report, null, 2), 'application/json');
    toast('Đã tải báo cáo JSON');
  });

  // ---------------------------------------------------------------- studio tiết diện Super-T v2
  const STUDIO_KEYS = ['girder_depth_mm', 'top_flange_width_mm', 'top_flange_thickness_mm', 'web_thickness_mm', 'bottom_bulb_width_mm', 'bottom_bulb_height_mm', 'girder_count', 'girder_spacing_mm', 'deck_slab_thickness_mm', 'prestress_layout_id', 'girder_concrete_id', 'deck_concrete_id', 'diaphragm_layout_id'];
  function initStudio() {
    const g = state.catalog.grammars.super_t_parametric_v2; if (!g) return;
    state.studioGene = Object.assign({}, state.catalog.anchor_genes.super_t_parametric_v2);
    const box = $('studio-sliders'); box.innerHTML = '';
    for (const key of STUDIO_KEYS) {
      const dom = g.domains[key]; const lab = document.createElement('label');
      const numeric = typeof dom[0] === 'number';
      if (numeric) lab.innerHTML = '<span>' + esc(VAR_LABELS[key] || key) + '</span><input type="range" min="0" max="' + (dom.length - 1) + '" step="1" data-key="' + key + '" value="' + dom.indexOf(state.studioGene[key]) + '"><input type="number" class="val-in" id="sv-' + key + '" data-key="' + key + '" value="' + state.studioGene[key] + '" min="' + dom[0] + '" max="' + dom[dom.length - 1] + '" step="' + (dom.length > 1 ? dom[1] - dom[0] : 1) + '" title="nhập số, tự bắt vào bước lưới">';
      else lab.innerHTML = '<span>' + esc(VAR_LABELS[key] || key) + '</span><select data-key="' + key + '">' + dom.map((v) => '<option value="' + esc(v) + '"' + (v === state.studioGene[key] ? ' selected' : '') + '>' + esc(v) + '</option>').join('') + '</select><span class="val"></span>';
      box.appendChild(lab);
    }
    box.querySelectorAll('input[type=range]').forEach((r) => r.addEventListener('input', () => { const key = r.dataset.key; state.studioGene[key] = g.domains[key][+r.value]; $('sv-' + key).value = state.studioGene[key]; scheduleStudio(); }));
    box.querySelectorAll('input.val-in').forEach((n) => n.addEventListener('change', () => { const key = n.dataset.key; const dom = g.domains[key]; const v = +n.value; let best = dom[0]; for (const c of dom) if (Math.abs(c - v) < Math.abs(best - v)) best = c; state.studioGene[key] = best; n.value = best; const r = box.querySelector('input[type=range][data-key="' + key + '"]'); if (r) r.value = dom.indexOf(best); if (best !== v) toast(esc(VAR_LABELS[key] || key) + ' bắt vào bước lưới: ' + best); scheduleStudio(); }));
    box.querySelectorAll('select').forEach((s) => s.addEventListener('change', () => { state.studioGene[s.dataset.key] = s.value; scheduleStudio(); }));
    scheduleStudio();
  }
  let studioTimer = null;
  function scheduleStudio() { clearTimeout(studioTimer); studioTimer = setTimeout(runStudio, 120); }
  async function runStudio() {
    try {
      const res = await api('/api/section', { grammar_id: 'super_t_parametric_v2', gene: state.studioGene });
      drawSection(res); const s = res.section, o = res.objectives, geo = res.geometry || {};
      $('studio-props').innerHTML = s ? 'A ' + nf(s.area_m2, 4) + ' m² · I ' + nf(s.I_m4, 4) + ' m⁴ · y_b ' + nf(s.y_bottom_m * 1000, 0) + ' mm · S_b ' + nf(s.I_m4 / s.y_bottom_m, 4) + ' m³ · cánh hẫng ' + nf(geo.overhang_m * 1000, 0) + ' mm · khe cánh ' + nf(geo.flange_gap_m * 1000, 0) + ' mm' + (o ? ' · chi phí ' + nf(o.relative_cost, 2) + ' · ' + nf(o.material_mass_t, 1) + ' t' : ' · <span style="color:var(--fail)">Vi phạm hình học L0</span>') : 'Không dựng được tiết diện.';
      const hard = res.violations.filter((v) => v.severity === 'HARD'), soft = res.violations.filter((v) => v.severity !== 'HARD');
      $('studio-violations').innerHTML = (res.schema_errors.length ? res.schema_errors.map((e) => '<div class="viol">' + esc(e) + '</div>').join('') : '')
        + hard.map((v) => '<div class="viol"><span class="rid">' + esc(v.rule_id) + '</span> ' + esc(RULE_LABELS[v.rule_id] || '') + ' · ' + esc(v.message) + '</div>').join('')
        + soft.map((v) => '<div class="viol soft"><span class="rid">' + esc(v.rule_id) + '</span> ' + esc(v.message) + '</div>').join('')
        + (!hard.length && !res.schema_errors.length ? '<div class="note">Hình học &amp; cấu tạo L0 đạt. Chuyển sang tab <strong>Tối ưu &amp; Kiểm tra</strong> để kiểm toán chịu lực.</div>' : '');
    } catch (err) { $('studio-props').textContent = err.message; }
  }
  function drawSection(res) {
    const svg = $('studio-svg'); const ring = res.polygon; if (!ring || !ring.length) { svg.innerHTML = '<text x="10" y="20" fill="currentColor" font-size="12">' + esc(res.polygon_error || 'không có biên') + '</text>'; return; }
    const xs = ring.map((p) => p[0]), ys = ring.map((p) => p[1]); const bf = Math.max(...xs) - Math.min(...xs), H = Math.max(...ys);
    const W = 420, Hh = 340, pad = 30; const sc = Math.min((W - 2 * pad) / bf, (Hh - 2 * pad - 20) / H);
    const X = (x) => W / 2 + x * sc, Y = (y) => Hh - pad - y * sc;
    const path = ring.map((p, i) => (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ' ' + Y(p[1]).toFixed(1)).join(' ') + ' Z';
    const s = res.section || {}; const yb = s.y_bottom_m;
    svg.innerHTML = '<path d="' + path + '" fill="rgba(128,128,128,.22)" stroke="currentColor" stroke-width="1.2"/>'
      + (yb != null ? '<line x1="' + X(-bf / 2) + '" x2="' + X(bf / 2) + '" y1="' + Y(yb) + '" y2="' + Y(yb) + '" stroke="var(--accent)" stroke-dasharray="4 3"/>' : '')
      + '<text x="' + (X(-bf / 2) - 4) + '" y="' + (Y(H / 2)) + '" font-size="11" fill="var(--accent)" text-anchor="end" font-family="IBM Plex Mono">H ' + Math.round(H * 1000) + '</text>'
      + '<text x="' + X(0) + '" y="' + (Y(H) - 8) + '" font-size="11" fill="var(--accent)" text-anchor="middle" font-family="IBM Plex Mono">b_f ' + Math.round(bf * 1000) + '</text>'
      + '<text x="10" y="16" font-size="11" fill="var(--muted)">Super-T tham số · ' + esc(res.geometry ? res.geometry.section_source : '') + '</text>';
  }
  $('btn-studio-anchor').addEventListener('click', initStudio);
  $('btn-studio-seed').addEventListener('click', () => { $('seed-select').value = 'studio'; showView('bench'); toast('Đã chọn mặt cắt Super-T làm phương án gốc — bấm Chạy tối ưu'); });

  // Bắt tay với iframe MIDAS: gene chỉ gửi khi iframe đã báo 'dylight:midas-ready' (tránh mất message trước khi listener cài xong).
  state.midasReady = false; state.midasQueue = [];
  function midasSend(msg) { const f = $('midas-frame'); if (state.midasReady) { try { f.contentWindow.postMessage(msg, '*'); } catch (err) { toast(err.message); } } else { state.midasQueue.push(msg); if (!f.getAttribute('src')) f.src = f.dataset.src; } }
  window.addEventListener('message', (e) => {
    const d = e.data; if (!d || typeof d !== 'object') return;
    if (d.type === 'dylight:midas-ready') { state.midasReady = true; const q = state.midasQueue.splice(0); q.forEach(midasSend); }
    if (d.type === 'dylight:supert-ack') toast('MIDAS đã nhận mặt cắt: ' + (d.vertices || '?') + ' đỉnh');
  });
  $('btn-studio-midas').addEventListener('click', () => {
    showView('creative'); activateSec('psc');
    midasSend({ type: 'dylight:supert-gene', gene: state.studioGene, grammar_id: 'super_t_parametric_v2' });
    toast('Đang xuất mặt cắt Super-T sang PSC-Value MIDAS');
  });

  // ---------------------------------------------------------------- danh mục hình thái (Lab Mode)
  $('btn-creative').addEventListener('click', async () => {
    const btn = $('btn-creative'); btn.disabled = true; $('cs-status').textContent = 'Đang chạy MAP-Elites…';
    try {
      const res = await api('/api/creative-search', { seed: +$('cs-seed').value, iterations: +$('cs-iter').value }); state.creative = res;
      $('cs-status').innerHTML = res.archive_size + ' hình thái trong archive · ' + res.rejected + ' bị loại · ' + res.unknown + ' chưa xác định · claim ' + pill(res.claim_level, 'na') + '<div class="note">Profile: ' + esc(res.profile.source_ref) + ' sha ' + esc(res.profile.sha256.slice(0, 12)) + ' — ' + esc(res.profile.note) + '</div>';
      const grid = $('cs-grid'); grid.innerHTML = '';
      res.candidates.forEach((c) => {
        const d = document.createElement('div'); d.className = 'cs-card';
        d.innerHTML = graphSvg(c.graph, c.axis_points) + '<div class="t"><span>' + esc((c.genome.topology || '').replace('_ARCH', '')) + ' ' + nf(c.genome.span_m, 0) + 'm</span><span>' + (c.all_known_pass ? pill(c.screening_status, 'pass') : pill(c.screening_status, 'warn')) + '</span></div>';
        d.addEventListener('click', () => { grid.querySelectorAll('.cs-card').forEach((x) => x.classList.remove('on')); d.classList.add('on'); renderCreativeDetail(c); });
        grid.appendChild(d);
      });
    } catch (err) { $('cs-status').innerHTML = '<span style="color:var(--fail)">' + esc(err.message) + '</span>'; }
    btn.disabled = false;
  });
  function graphSvg(graph, axis) {
    const nodes = graph.nodes || []; if (!nodes.length) return '<svg viewBox="0 0 100 40"></svg>';
    const xs = nodes.map((n) => n.x_m), ys = nodes.map((n) => n.y_m); const minx = Math.min(...xs), maxx = Math.max(...xs), miny = Math.min(...ys), maxy = Math.max(...ys);
    const W = 200, H = 90, pad = 6; const sc = Math.min((W - 2 * pad) / Math.max(1e-6, maxx - minx), (H - 2 * pad) / Math.max(1e-6, maxy - miny));
    const X = (x) => pad + (x - minx) * sc, Y = (y) => H - pad - (y - miny) * sc; const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
    const col = { ARCH_RIB: 'var(--accent)', DECK: 'var(--ink)', SPANDREL: 'var(--muted)', HANGER: 'var(--muted)', NETWORK_HANGER: 'var(--muted)', END_POST: 'var(--warn)' };
    const lines = (graph.edges || []).map((e) => { const a = byId[e.from], b = byId[e.to]; if (!a || !b) return ''; return '<line x1="' + X(a.x_m).toFixed(1) + '" y1="' + Y(a.y_m).toFixed(1) + '" x2="' + X(b.x_m).toFixed(1) + '" y2="' + Y(b.y_m).toFixed(1) + '" stroke="' + (col[e.kind] || 'var(--muted)') + '" stroke-width="' + (e.kind === 'ARCH_RIB' ? 2 : e.kind === 'DECK' ? 1.6 : 0.8) + '"/>'; }).join('');
    const axisPath = axis && axis.length ? '<path d="' + axis.map((p, i) => (i ? 'L' : 'M') + X(p.x_m).toFixed(1) + ' ' + Y(p.y_m).toFixed(1)).join(' ') + '" fill="none" stroke="var(--select)" stroke-width="0.8" stroke-dasharray="2 2"/>' : '';
    return '<svg viewBox="0 0 ' + W + ' ' + H + '">' + axisPath + lines + '</svg>';
  }
  function renderCreativeDetail(c) {
    const g = c.genome, d = c.descriptors || {};
    $('cs-detail').innerHTML = '<h3 style="margin-top:10px">' + esc(c.candidate_id) + ' · ' + pill(c.claim_level, 'na') + '</h3>' + graphSvg(c.graph, c.axis_points).replace('<svg', '<svg style="width:100%;height:160px;background:var(--panel-2);border:1px solid var(--line);border-radius:4px"')
      + kv([['Topology', esc(g.topology)], ['Nhịp', nf(g.span_m, 1) + ' m'], ['Tỷ số vồng f/L', nf(g.rise_ratio, 3)], ['Số khoang', g.panel_count], ['Số sườn vòm', g.rib_count], ['Chiều cao sườn', nf(g.rib_depth_m, 2) + ' m'], ['Tĩnh không mặt cầu', nf(g.deck_clearance_m, 2) + ' m'], ['Hệ số hình dạng', (g.shape_coefficients || []).map((v) => nf(v, 3)).join(', ')]]
        .concat(Object.entries(d).filter(([, v]) => typeof v === 'number').map(([k, v]) => [esc(k), nf(v, 4)])))
      + '<h3 style="margin-top:10px">Kiểm F0</h3>' + '<table class="grid"><thead><tr><th>check</th><th>mô hình</th><th>trạng thái</th></tr></thead><tbody>' + c.checks.map((k) => '<tr><td>' + esc(k.check_id) + '</td><td class="note">' + esc(k.model_kind || k.clause_id || '') + '</td><td>' + statusPill(k.status) + '</td></tr>').join('') + '</tbody></table>'
      + (c.limitations && c.limitations.length ? '<div class="note">Giới hạn: ' + c.limitations.map(esc).join('; ') + '</div>' : '')
      + '<div class="note">Bước kế tiếp theo repo: creative_frame_adapter → frame F1 → arch action → funicular reference (creative_portfolio). Vẫn là IDEA cho tới khi có profile có nguồn.</div>';
  }

  // ---------------------------------------------------------------- bằng chứng (Lab Mode)
  const CHECK_LABELS = { FLEXURE_STRENGTH: 'Sức kháng uốn', SHEAR_TORSION: 'Cắt – xoắn', SERVICE_STRESS: 'Ứng suất sử dụng', DEFLECTION: 'Võng', FATIGUE: 'Mỏi', STABILITY: 'Ổn định', DURABILITY: 'Độ bền lâu', SHEAR_PUNCHING: 'Chọc thủng', SERVICE_CRACKING: 'Nứt', JACKING_STRESS: 'Ứng suất kích', TRANSFER_STRESS: 'Ứng suất truyền lực', LOSSES: 'Mất mát DƯL', ULTIMATE_STRENGTH: 'Cường độ cực hạn', ANCHORAGE_ZONE: 'Vùng neo', GROUTING_DURABILITY: 'Bơm vữa' };
  function bar(label, u) { const pct = Math.min(100, u * 100 / 1.25); const cls = u > 1 + 1e-9 ? 'fail' : u > 0.9 ? 'warn' : ''; return '<div class="bar"><span>' + label + '</span><div class="track"><div class="fill ' + cls + '" style="width:' + pct.toFixed(1) + '%"></div><div class="lim" style="left:80%"></div></div><span class="v">' + nf(u, 3) + '</span></div>'; }
  async function renderEvidence() {
    const r = state.report; if (!r) return;
    const f = r.final || {};
    $('ev-current').querySelector('.body').innerHTML = kv([['Report', esc(state.reportLabel)], ['Seed → cuối', esc(r.seed.case_id) + ' → ' + esc(f.case_id || '–')], ['Claim', statusPill(r.claim_level) + ' (trần ' + esc(r.claim_ceiling) + ')'], ['Verdict authority', esc(r.design_verdict_authority) + ' · loop ' + esc(r.loop_authority)], ['Kết thúc', esc(r.termination.reason)], ['Khả thi (verifier L1)', f.feasible ? pill('FEASIBLE', 'pass') : pill('INFEASIBLE', 'fail')], ['Đạt mục tiêu D/C', f.meets_target ? pill('đạt', 'pass') : pill('chưa', 'warn')], ['Ngân sách', r.counters.evaluator.solver_calls + ' / ' + r.budget_solver_calls + ' solver']])
      + (f.rule_utilizations ? '<h3 style="margin-top:10px">D/C theo rule · fidelity L1</h3>' + Object.entries(f.rule_utilizations).map(([k, u]) => bar(esc(k) + ' <span class="note">' + esc(RULE_LABELS[k] || '') + '</span>', u)).join('') : '');
    const ov = state.overview; const gates = ov ? ov.gates.map((g) => Object.assign({}, g)) : [];
    for (const g of gates) {
      if (g.gate === 'G1') { g.status = f.status === 'SUCCESS' ? 'PASSED' : 'BLOCKED'; g.detail = 'Phương án cuối ' + (f.status === 'SUCCESS' ? 'qua L0 (bố trí + chế tạo)' : 'chưa qua L0: ' + f.status); }
      if (g.gate === 'G2') { g.status = f.solver_status === 'CONVERGED' ? 'PASSED' : 'BLOCKED'; g.detail = 'Solver ' + esc(f.solver_status || '–') + ' · ' + esc(r.solver_version) + ' · verifier ' + esc(r.ruleset_version); }
    }
    $('ev-gates').querySelector('.body').innerHTML = gates.map((g) => '<div class="gate"><span class="g">' + g.gate + '</span><span>' + esc(g.label) + '<div class="d">' + esc(g.detail) + '</div></span>' + statusPill(g.status) + '</div>').join('') + '<div class="note">G1, G2 là của phương án này; G0 và G3–G7 là của toàn dự án và đang chặn.</div>';
    const a = r.component_audit;
    $('ev-audit').querySelector('.body').innerHTML = a ? '<div class="note">Trạng thái ' + statusPill(a.status) + ' · không đổi verdict evaluator</div>' + a.components.map((c) => '<div style="font-weight:600;margin-top:6px">' + esc(c.component_id) + ' · ' + esc(c.kind) + '</div><table class="grid">' + c.checks.map((k) => '<tr><td>' + esc(CHECK_LABELS[k.check_id] || k.check_id) + '</td><td class="num">' + (k.utilization != null ? nf(k.utilization, 3) : '') + '</td><td>' + statusPill(k.status) + (k.evidence ? ' <span class="note">' + esc(k.evidence.fidelity) + '</span>' : '') + '</td></tr>').join('') + '</table>').join('') + '<div class="note">' + a.proposals.length + ' đề xuất EVIDENCE_REQUEST — việc còn lại trước khi gọi là thiết kế.</div>' : '<div class="note">Phương án cuối chưa qua solver nên không có audit.</div>';
    const used = new Map();
    for (const it of r.iterations || []) for (const p of it.probes || []) if (p.outcome === 'ACCEPTED' && p.move && p.move.card_id) used.set(p.move.card_id, (used.get(p.move.card_id) || 0) + 1);
    await ensureCards();
    $('ev-cards').querySelector('.body').innerHTML = used.size ? [...used.entries()].map(([id, n]) => { const c = state.cards.find((x) => x.card_id === id); return '<div class="hand"><div class="h"><span>' + esc(id) + ' × ' + n + '</span>' + (c ? statusPill(c.status) : '') + '</div><div class="s">' + esc(c ? c.title : '') + '</div></div>'; }).join('') + '<div class="note">Thẻ chỉ gợi ý thứ tự nước sửa; PASS/FAIL luôn của verifier. Thẻ DRAFT chưa được kỹ sư duyệt.</div>' : '<div class="note">Không có nước sửa nào gắn thẻ tri thức trong report này.</div>';
    $('ev-prov').querySelector('.body').innerHTML = kv([['report_sha256', '<span style="font-size:11px">' + esc(r.report_sha256) + '</span>'], ['basis', esc(r.basis.basis_id) + ' · ' + esc(r.basis.sha256.slice(0, 16))], ['nguồn', r.source_digests.map((s) => esc(s.path) + ' ' + esc(s.sha256.slice(0, 12))).join('<br>')], ['catalog / grammar', esc(r.catalogs_version) + ' / ' + esc(r.grammar_id) + ' ' + esc(r.grammar_version)], ['solver / ruleset', esc(r.solver_version) + ' / ' + esc(r.ruleset_version)], ['policy', esc(JSON.stringify(r.policy))]]);
  }

  // ---------------------------------------------------------------- quy trình lab (Lab Mode)
  async function loadProcess() {
    try {
      const [live, status] = await Promise.all([api('/api/live-data'), api('/api/lab-status')]); state.live = live;
      $('lab-valid').innerHTML = (status.valid ? '<span class="dot" style="background:var(--pass)"></span>lab valid' : '<span class="dot" style="background:var(--fail)"></span>lab invalid') + ' · trần ' + esc(status.current_project_claim_ceiling || '');
      const filters = ['ALL', 'BRD', 'RND']; $('task-filters').innerHTML = filters.map((f) => '<button class="btn' + (f === state.taskFilter ? ' active' : '') + '" data-f="' + f + '">' + f + '</button>').join('');
      $('task-filters').querySelectorAll('button').forEach((b) => b.addEventListener('click', () => { state.taskFilter = b.dataset.f; loadProcess(); }));
      renderBoard();
      const hb = $('pr-handoffs').querySelector('.body'); hb.innerHTML = live.handoffs.slice(-25).reverse().map((h) => '<div class="hand"><div class="h"><span>' + esc(h.task_id) + ' · ' + esc(h.agent_id) + ' · ' + esc(h.role) + '</span><span>' + statusPill(h.claim_level) + ' ' + esc((h.gates_completed || []).join(' ')) + '</span></div><div class="s">' + esc(String(h.summary || '').slice(0, 260)) + (String(h.summary || '').length > 260 ? '…' : '') + '</div><div class="h"><span>' + (h.artifacts || []).length + ' artifact có SHA-256</span><span>' + esc(h.filename) + '</span></div></div>').join('');
      const rb = $('pr-reviews').querySelector('.body'); rb.innerHTML = live.reviews.slice(-25).reverse().map((v) => '<div class="hand"><div class="h"><span>' + esc(v.task_id) + ' · ' + esc(v.reviewer_id) + '</span><span>' + statusPill(v.decision) + '</span></div><div class="s">' + (v.gate_findings || []).map((g) => esc(g.gate) + ' ' + esc(g.status)).join(' · ') + '</div><div class="s note">' + esc(String(v.notes || '').slice(0, 220)) + '</div></div>').join('');
    } catch (err) { $('board').innerHTML = '<div class="note">' + esc(err.message) + '</div>'; }
  }
  function renderBoard() {
    const q = ($('task-search').value || '').toLowerCase(); const cols = ['READY', 'ACTIVE', 'REVIEW', 'ACCEPTED', 'BLOCKED', 'REJECTED', 'BACKLOG'];
    const tasks = Object.values(state.live.tasks).filter((t) => (state.taskFilter === 'ALL' || t.task_id.startsWith(state.taskFilter)) && (!q || JSON.stringify(t).toLowerCase().includes(q)));
    $('board').innerHTML = cols.map((c) => { const items = tasks.filter((t) => t.status === c); return '<div class="col"><h4><span>' + c + '</span><span>' + items.length + '</span></h4>' + items.map((t) => '<div class="task ' + esc(t.priority) + '" data-id="' + esc(t.task_id) + '"><div class="id"><span>' + esc(t.task_id) + '</span><span>' + esc(t.owner || '') + '</span></div><div class="ttl">' + esc(t.title) + '</div></div>').join('') + '</div>'; }).join('');
    $('board').querySelectorAll('.task').forEach((d) => d.addEventListener('click', () => showTask(state.live.tasks[d.dataset.id])));
  }
  $('task-search').addEventListener('input', () => { if (state.live) renderBoard(); });
  function showTask(t) {
    $('task-modal-body').innerHTML = '<h3>' + esc(t.task_id) + ' · ' + statusPill(t.status) + '</h3><div style="font-weight:600;margin:6px 0">' + esc(t.title) + '</div><div class="note">' + esc(t.research_question) + '</div>'
      + kv([['Owner / reviewer', esc(t.owner || '–') + ' / ' + esc(t.reviewer || '–')], ['Claim ceiling', esc(t.claim_ceiling)], ['Gates', esc((t.required_gates || []).join(', '))], ['Runtime scope', t.runtime_scope ? esc(t.runtime_scope.runtime_domain) + ' · ' + esc((t.runtime_scope.structural_families || []).join(', ')) : '–'], ['Write scope', (t.write_scope || []).map(esc).join('<br>')]])
      + '<h3 style="margin-top:10px">Tiêu chí nghiệm thu</h3><ul class="note" style="color:var(--ink-2)">' + (t.acceptance_criteria || []).map((x) => '<li>' + esc(x) + '</li>').join('') + '</ul>'
      + '<h3>An toàn</h3><ul class="note" style="color:var(--ink-2)">' + (t.safety_notes || []).map((x) => '<li>' + esc(x) + '</li>').join('') + '</ul>'
      + (t.review_notes && t.review_notes.length ? '<h3>Review</h3>' + t.review_notes.map((x) => '<div class="note" style="color:var(--ink-2)">' + esc(x) + '</div>').join('') : '')
      + '<div class="row-btns"><button class="btn primary" id="task-close">Đóng</button></div>';
    $('task-modal').classList.add('on'); $('task-close').addEventListener('click', () => $('task-modal').classList.remove('on'));
  }
  $('task-modal').addEventListener('click', (e) => { if (e.target === $('task-modal')) $('task-modal').classList.remove('on'); });

  // ---------------------------------------------------------------- não 2 (Lab Mode)
  async function loadKnowledge() {
    try {
      const [cards, ob] = await Promise.all([api('/api/knowledge/cards'), api('/api/obsidian')]); state.cards = cards.cards; state.obsidian = ob; state.knowledgeLoaded = true;
      $('obsidian-chip').innerHTML = ob.available ? '<span class="dot" style="background:var(--pass)"></span>Obsidian: ' + esc(ob.vault_name) : '<span class="dot" style="background:var(--na)"></span>Obsidian chưa cấu hình';
      renderCards(state.cards);
    } catch (err) { $('kc-list').innerHTML = '<div class="note">' + esc(err.message) + '</div>'; }
  }
  function renderCards(cards) {
    const list = $('kc-list'); list.innerHTML = '';
    for (const c of cards) {
      const d = document.createElement('div'); d.className = 'kc';
      d.innerHTML = '<div class="id"><span>' + esc(c.card_id) + ' · ' + esc(c.type) + '</span>' + statusPill(c.status) + '</div><div>' + esc(c.title) + '</div><div class="note">' + esc((c.applies_to.rules || []).join(', ')) + ' · ' + esc((c.applies_to.variables || []).join(', ')) + '</div>';
      d.addEventListener('click', () => { list.querySelectorAll('.kc').forEach((x) => x.classList.remove('on')); d.classList.add('on'); renderCard(c); });
      list.appendChild(d);
    }
  }
  function renderCard(c) {
    const ob = state.obsidian; const link = ob && ob.available ? '<a href="obsidian://open?vault=' + encodeURIComponent(ob.vault_name) + '&file=' + encodeURIComponent(ob.managed_folder + '/Cards/' + c.card_id) + '">mở trong Obsidian</a>' : '';
    $('kc-detail').innerHTML = '<h3>' + esc(c.card_id) + ' · ' + statusPill(c.status) + '</h3><div style="font-weight:600;margin:6px 0">' + esc(c.title) + '</div>' + kv([['Loại', esc(c.type)], ['Họ', esc(c.applies_to.family || '')], ['Rule', esc((c.applies_to.rules || []).join(', '))], ['Biến', esc((c.applies_to.variables || []).join(', '))], ['Nguồn', esc(c.source ? (c.source.kind || '') + ' ' + (c.source.ref || c.source.reference || '') : '')], link ? ['Obsidian', link] : null])
      + '<h3 style="margin-top:10px">Hướng dẫn</h3><div class="note" style="color:var(--ink-2)">' + esc(c.guidance) + '</div><h3>Bằng chứng</h3><div class="note" style="color:var(--ink-2)">' + esc(c.evidence || '') + '</div><div class="note">Thẻ chỉ gợi ý; muốn thành rule phải dẫn điều khoản, thêm test và kỹ sư duyệt.</div>';
  }
  let kcTimer = null;
  $('kc-search').addEventListener('input', () => { clearTimeout(kcTimer); kcTimer = setTimeout(async () => { const q = $('kc-search').value.trim(); if (!q) return renderCards(state.cards); const rules = q.match(/[A-Z]{3,6}-[0-9]{3}/g) || []; try { const res = await api('/api/knowledge/query?rules=' + encodeURIComponent(rules.join(',')) + '&text=' + encodeURIComponent(q)); renderCards(res.hits.map((h) => h.card)); } catch (err) { toast(err.message); } }, 200); });

  // ---------------------------------------------------------------- khởi động
  updateHeaderForMode();
  loadOverview();
  loadSimPresets();
  loadCatalog().then(loadRuns).catch((err) => toast(err.message));
})();
