/* ============================================================
   Character · 特殊化 UI 逻辑
   代码组织（关注点分离，防屎山）：
     1) 配置 / 状态   —— 常量、localStorage 键、单一数据源 tasks
     2) 工具          —— creds / nowTime
     3) API 层        —— callProcess：唯一取数入口，契约稳定独立
     4) 状态变更      —— snOn 开关 / addTask / archive（按权限分流）
     5) 渲染层        —— buildCard / renderTaskbar / renderWorkspace（组件化）
     6) 视图 / 输入   —— newCapture / 自动滚底
     7) 设置          —— 主题 / 语言 / 字号 / 权限（四行全部真生效）
     8) 初始化
   API 契约：POST /api/process {text, project, mode, jev_key, openai_key,
            llm_base, llm_model, threshold}
      full        → {route, summary, extra_fields, md, raw_md,
                     raw_md_path, summary_md_path, title}
      archive_only→ {mode, title, raw_md, raw_md_path}
   ============================================================ */

import { prepare, layout } from './vendor/pretext/layout.js';  // 文本测量引擎（本地自托管）

const $ = (id) => document.getElementById(id);

/* ---------- 1) 配置 / 状态 ---------- */
const LS_KEYS  = ['jev_key', 'openai_key', 'llm_base', 'llm_model', 'threshold'];
const LS_TASKS = 'character_tasks';
const LS_SPACES = 'character_ws_spaces';   // 展开着的「空间」名（侧栏归类状态）
const LS_CUSTOM_SPACES = 'character_spaces';   // 用户自建空间 [{key,name}]

// 设置项（四行都真生效）：外观 / 语言 / 字号 / 权限
const SETTINGS = {
  theme: { key: 'char_theme', def: 'light' },   // light | dark | system
  lang:  { key: 'char_lang',  def: 'zh' },      // zh | en
  size:  { key: 'char_size',  def: 22 },        // 记录内容字号（px），范围见 SIZE_MIN/MAX
  perm:  { key: 'char_perm',  def: 'full' },    // full | ask | readonly
  calli: { key: 'char_calli', def: 'xingshu' }, // lishu | kaishu | caoshu | xingshu（中文书法体）
};
const SIZE_MIN = 10, SIZE_MAX = 30;             // 任务栏是窄栏，上限不宜太大
const clampSize = (n) => Math.min(SIZE_MAX, Math.max(SIZE_MIN, n));

/* 一次性迁移（v5）：默认字号 18 → 22px（用户反馈还要再大四号），上限同步 26 → 30。
   把浏览器里遗留的旧值清掉，回到新默认（用户在设置里仍可自行调）。只跑一次。 */
if (localStorage.getItem('char_size_v5') !== '1') {
  localStorage.removeItem('char_size');
  localStorage.setItem('char_size_v5', '1');
}

function getSet(name) {
  const raw = localStorage.getItem(SETTINGS[name].key);
  if (raw === null) return SETTINGS[name].def;
  return name === 'size' ? (parseInt(raw, 10) || SETTINGS[name].def) : raw;
}
function setSet(name, v) { localStorage.setItem(SETTINGS[name].key, String(v)); }

// 单一数据源：所有视图都从这里渲染
let tasks = loadTasks();
let expandedSpaces = new Set(loadSpaces());   // 侧栏「空间」分区里展开着的文件夹
let curLang = getSet('lang');

function loadSpaces() {
  try { return JSON.parse(localStorage.getItem(LS_SPACES) || '[]'); }
  catch { return []; }
}
function saveSpaces() { localStorage.setItem(LS_SPACES, JSON.stringify([...expandedSpaces])); }

/* 用户自建空间（JEV 固定类别之外的空间）：没任务也显示，可把任务移进来 */
let customSpaces = loadCustomSpaces();          // [{key, name}]，按创建序
let addingSpace = false;                        // 空间分区里「新建空间」输入框是否开着
function loadCustomSpaces() {
  try { return JSON.parse(localStorage.getItem(LS_CUSTOM_SPACES) || '[]'); }
  catch { return []; }
}
function saveCustomSpaces() { localStorage.setItem(LS_CUSTOM_SPACES, JSON.stringify(customSpaces)); }

function loadTasks() {
  try { return JSON.parse(localStorage.getItem(LS_TASKS) || '[]'); }
  catch { return []; }
}
function saveTasks() { localStorage.setItem(LS_TASKS, JSON.stringify(tasks.slice(0, 200))); }

/* ---------- 2) 工具 ---------- */
function creds() {
  const c = {};
  LS_KEYS.forEach(k => c[k] = localStorage.getItem(k) || '');
  return c;
}
function nowTime() {                        // 卡片右上时间：年份月日（本地时区）
  const d = new Date();
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}

/* ---------- 3) API 层（唯一取数入口） ---------- */
async function callProcess(text, project, mode) {
  const c = creds();
  const res = await fetch('/api/process', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text, project, mode,
      jev_key: c.jev_key, openai_key: c.openai_key,
      llm_base: c.llm_base, llm_model: c.llm_model,
      threshold: c.threshold || 0.7,
    }),
  });
  const data = await res.json();
  if (!res.ok) throw Object.assign(new Error(data.error || '请求失败'), { data });
  return data;
}

/* 只分类、不落盘：给历史记录补算「归类比例」（/api/classify） */
async function callClassify(text) {
  const c = creds();
  const res = await fetch('/api/classify', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, jev_key: c.jev_key, threshold: c.threshold || 0.7 }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || '分类失败');
  return data;
}

/* ---------- 4) 状态变更 ---------- */
let snOn = false;   // simple note 开关：开=纯记录(archive_only)，关=走权限判断

function toggleCreate() {
  snOn = !snOn;
  const sw = $('snSwitch');
  sw.classList.toggle('on', snOn);
  sw.setAttribute('aria-checked', String(snOn));
}

/* —— 权限询问条（权限 =「每次询问」时出现）—— */
function showPermAsk() { $('permAsk').classList.add('show'); }
function hidePermAsk() { $('permAsk').classList.remove('show'); }

/* 权限决定「存档」按钮走哪条路：
     simple note 开 → 纯记录（用户显式表态，优先级最高）
     只读           → 纯记录，绝不调外部服务
     每次询问       → 先问一次，再按用户点的那颗按钮走
     完全权限       → 直接调 AI 处理
   modeOverride 由询问条上的按钮传入（'full' / 'archive_only'）。 */
function resolveMode() {
  if (snOn) return 'archive_only';
  const perm = getSet('perm');
  if (perm === 'readonly') return 'archive_only';
  if (perm === 'ask') return 'ask';
  return 'full';
}

function addTask(t, quiet) {
  tasks.push(t);
  saveTasks();
  renderWorkspace();
}

async function archive(modeOverride) {
  const el = $('input'), text = el.value.trim();
  const project = '';                    // 「项目（可选）」输入框已删，固定不带项目
  if (!text) return;

  const mode = modeOverride || resolveMode();
  if (mode === 'ask') { showPermAsk(); return; }   // 先问一句，不动原文

  hidePermAsk();
  const btn = $('archiveBtn'); btn.disabled = true;
  try {
    const d = await callProcess(text, project, mode);
    if (mode === 'archive_only') {
      // simple note / 纯记录：原样入工作区，不分类、不总结，也不去弹任务栏打扰
      addTask({
        ts: Date.now(), time: nowTime(), title: d.title || text.slice(0, 40),
        category: 'raw', project, raw_path: d.raw_md_path,
        status: '已记录', raw_md: d.raw_md,
      }, true);
    } else {
      addTask({
        ts: Date.now(), time: nowTime(), title: d.title,
        category: d.route.final_skill, project,
        raw_path: d.raw_md_path, summary_path: d.summary_md_path,
        status: '已总结', summary: d.summary, md: d.md, raw_md: d.raw_md,
        conf: d.route.skill_confidence, probs: d.route.skill_probabilities,
        probsSource: d.mode && d.mode.jev, llmMode: d.mode && d.mode.llm,
      });
      toast('✅ ' + tr('jevJudged'));   // 内容已送 JEV 分类，给一句可见反馈
    }
    /* 存档后书写框内容保留（用户要求）：接着写、改了再存就是新记录，原文不丢 */
  } catch (e) {
    const d = e.data || {};
    addTask({
      ts: Date.now(), time: nowTime(), title: (d.title || text.slice(0, 40)),
      category: 'raw', project, raw_path: d.raw_md_path,
      status: '处理失败', error: e.message,
    });
  } finally { btn.disabled = false; }
}

/* —— 底部操作栏新增：总结 / 复制（蓝色存档钮左边）——
   总结 = 直接走 AI 全量处理（与权限询问条里的「AI 处理」同一条路，会分类+总结+存档）；
   复制 = 把书写框当前内容复制到剪贴板（纯本地，不碰任何服务）。 */
async function summarize() {
  const el = $('input'), text = el.value.trim();
  if (!text) return;
  const btn = $('summarizeBtn'); btn.disabled = true;
  try {
    const d = await callSummarize(text);
    showSummaryPanel(d, text);
  } catch (e) {
    toast('总结失败：' + e.message);
  } finally { btn.disabled = false; }
}

async function copyInput() {
  const el = $('input'), text = el.value.trim();
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const ta = document.createElement('textarea');   // 非 https / 旧浏览器兜底
    ta.value = text; ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0;';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); } finally { document.body.removeChild(ta); }
  }
  toast(tr('copied'));
}

/* —— 总结按钮：调 /api/summarize 出摘要，弹面板展示 + 一键交给 Agent —— */
async function callSummarize(text) {
  const c = creds();
  const res = await fetch('/api/summarize', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, jev_key: c.jev_key, openai_key: c.openai_key, threshold: c.threshold || 0.7 }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || '总结失败');
  return data;
}

let _summaryText = '';
let _handoffLead = '';   // 「交给 Agent」复制时带的指令前缀（按面板口径变）
function showSummaryPanel(d, originalText) {
  _summaryText = (d.summary && d.summary.trim()) ? d.summary : originalText;
  /* 四种口径：packaged=没连任何模型、原样打包；mock=模拟占位；
     inspiration=灵感类不重写；其余=真实 LLM 总结 */
  let note;
  if (d.packaged) {
    // 没连 LLM（总结模型）：总结即原文复制，并在面板里明确说明
    const jevConnected = d.mode && d.mode.jev === 'real';
    note = jevConnected
      ? '已连接分类模型，但未连接 LLM 总结模型 · 以下为原文复制（非 AI 总结）'
      : '未连接任何模型 · 已原样复制原文（非 AI 总结，连上 GLM 后会出摘要）';
    _handoffLead = '请帮我处理并总结下面这个 MD 文件：';
  } else if (d.mode && d.mode.llm === 'mock') {
    note = '（总结为模拟模式，未配置 LLM key）';
    _handoffLead = '请帮我处理下面这个内容：';
  } else if (d.summary && d.summary.trim()) {
    note = '（真实 LLM 总结）';
    _handoffLead = '请帮我继续处理下面这份总结：';
  } else {
    note = '原样保留（灵感类不重写）';
    _handoffLead = '请帮我处理下面这个内容：';
  }
  $('sumBody').textContent = _summaryText;
  $('sumMeta').textContent = (d.skill ? '类别：' + catName(d.skill) + ' · ' : '') + note;
  $('summaryBackdrop').classList.add('open');
}

function closeSummary() { $('summaryBackdrop').classList.remove('open'); }

/* 一键交给 Agent：把「指令 + 面板内容」复制走，用户粘进任意 Agent 对话即用 */
async function copySummary() {
  const payload = _handoffLead + '\n\n' + _summaryText;
  try { await navigator.clipboard.writeText(payload); } catch {
    const ta = document.createElement('textarea');
    ta.value = payload; ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0;';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); } finally { document.body.removeChild(ta); }
  }
  toast(tr('copiedHandoff'));
}

/* ---------- 5) 渲染层（组件化）：buildCard / renderWorkspace ---------- */
function chip(text, kind) {
  const s = document.createElement('span');
  s.className = 'chip' + (kind ? ' ' + kind : '');
  s.textContent = text;
  return s;
}

/* —— JEV 归类比例：展开卡片时展示各类别的概率分布（真实模型输出） —— */
function probsBox(t) {
  const box = document.createElement('div');
  box.className = 'tprobs';
  Object.entries(t.probs || {})
    .sort((a, b) => b[1] - a[1])                 // 概率高的排前面
    .forEach(([k, v]) => {
      const row = document.createElement('div'); row.className = 'tprob-row';
      const name = document.createElement('span'); name.className = 'tprob-name'; name.textContent = catName(k);
      const bar = document.createElement('span'); bar.className = 'tprob-bar';
      const fill = document.createElement('i'); fill.style.width = (v * 100).toFixed(1) + '%';
      bar.appendChild(fill);
      const pct = document.createElement('span'); pct.className = 'tprob-pct';
      pct.textContent = (v * 100).toFixed(1) + '%';
      row.append(name, bar, pct);
      box.appendChild(row);
    });
  return box;
}

/* —— 只认真实的 LLM 总结：MOCK 占位（含历史记录里已存的）一律不显示 —— */
function realSummary(t) {
  if (!t.summary) return '';
  if (t.llmMode === 'mock') return '';
  if (t.summary.indexOf('【MOCK 总结占位') === 0) return '';
  return t.summary;
}

/* —— 历史记录回填归类比例：老数据没存概率，展开时用原文补跑一次 JEV —— */
const probFilled = new Set();          // 已尝试过的 ts：失败也不反复请求

/* 服务端当前是真 key 还是 mock：比例口径变了要重算（mock 的 50/50 没意义） */
let serverMode = null;
async function ensureServerMode() {
  if (serverMode) return serverMode;
  try {
    const res = await fetch('/api/config');
    serverMode = await res.json();
  } catch { serverMode = { jev: 'mock', llm: 'none' }; }
  return serverMode;
}

function rawTextOf(t) {
  const md = t.raw_md || '';
  if (!md) return '';
  const m = md.match(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/);   // 剥掉 frontmatter
  return (m ? md.slice(m[0].length) : md).trim();
}

async function fillProbs(t) {
  if (probFilled.has(t.ts)) return;
  const text = rawTextOf(t);
  if (!text) return;
  const mode = serverMode || await ensureServerMode();
  if (t.probs && t.probsSource === mode.jev) return;   // 已经是同一口径的数据，不重复请求
  probFilled.add(t.ts);
  try {
    const d = await callClassify(text);
    const r = d.route || {};
    t.probs = r.skill_probabilities || null;
    t.conf = r.skill_confidence;
    t.probsSource = (d.mode && d.mode.jev) || mode.jev;
    saveTasks();
  } catch { /* 补算失败就当没有，不影响阅读 */ }
}

/* —— 卡片整体折叠 / 展开（默认只显标题，点一下展开看分类 + 文件格式），跨重渲染保留 —— */
const openCards = new Set();

function buildCard(task) {
  const card = document.createElement('div'); card.className = 'tcard'; card.dataset.ts = task.ts;
  const open = openCards.has(task.ts);

  const head = document.createElement('div'); head.className = 'tcard-head';
  const title = document.createElement('div'); title.className = 'tcard-title'; title.textContent = task.title;
  const time = document.createElement('div'); time.className = 'ttime'; time.textContent = task.time;
  const caret = document.createElement('span'); caret.className = 'tcaret'; caret.textContent = open ? '▾' : '▸';
  head.append(title, time, caret); card.appendChild(head);

  /* 默认只显标题（收起态）；点一下整卡才展开：分类 + 文件格式 + 摘要 / 报错 / 原文 md */
  if (open) {
    fillProbs(task);                      // 展开时补算/重算归类比例（内部判断口径）
    const meta = document.createElement('div'); meta.className = 'tcard-meta';
    const ok = (task.status === '已总结' || task.status === '已记录');
    const bad = (task.status === '处理失败');
    meta.appendChild(chip(statusLabel(task.status), ok ? 'ok' : bad ? 'bad' : ''));
    if (task.category && task.category !== 'raw') meta.appendChild(chip(tr('catLabel') + spaceName(task.category), 'cat'));
    meta.appendChild(chip(tr('filetypeChip')));           // 文件类型：MD文件
    if (task.project) meta.appendChild(chip(tr('projLabel') + task.project, ''));
    card.appendChild(meta);

    if (task.probs) card.appendChild(probsBox(task));      // JEV 归类比例（真实比例）
    const sum = realSummary(task);                         // MOCK 占位总结不显示
    if (sum) { const s = document.createElement('div'); s.className = 'tsummary'; s.textContent = sum; card.appendChild(s); }
    if (task.error) { const er = document.createElement('div'); er.className = 'terr'; er.textContent = '⚠ ' + task.error; card.appendChild(er); }
  }

  /* 点整卡切换折叠：但落在 <details> 折叠块 / 按钮 / 链接上时交给它们自己处理，不冒泡切换 */
  card.addEventListener('click', (e) => {
    if (e.target.closest('details, button, a, input')) return;
    if (openCards.has(task.ts)) openCards.delete(task.ts); else openCards.add(task.ts);
  });
  return card;
}

/* —— 书法体 → CSS font-family 名映射（供输入框、卡片等处引用） —— */
const CALLI_FONTS = { lishu: 'ZCOOL XiaoWei', kaishu: 'Ma Shan Zheng', caoshu: 'Liu Jian Mao Cao', xingshu: 'Zhi Mang Xing' };

let highlightTs = null;        // 需要高亮的记录（做成状态，重渲染时自动补上）

/* —— 侧栏归类（WorkBuddy 逻辑：任务 + 空间）——
   任务：所有记录按时间倒排成一条清单，一条记录 = 一个任务；
   空间：按 JEV 类别归成的文件夹，点文件夹展开/收起里面的任务。 */
function renderWorkspace() {
  const list = $('wsList');
  list.innerHTML = '';
  if (!tasks.length) {
    const e = document.createElement('div');
    e.className = 'ws-empty'; e.textContent = tr('empty');
    list.appendChild(e);
    return;
  }
  const ordered = [...tasks].reverse();          // 最新在上

  /* —— 任务（全部记录，一条 = 一个任务）—— */
  list.appendChild(wsSectionHead(tr('wsTasks') + ' (' + ordered.length + ')'));
  ordered.forEach(t => list.appendChild(wsItem(t, false)));

  /* —— 空间（按类别归档的文件夹 + 用户自建空间）—— */
  const spaces = {};
  ordered.forEach(t => {
    const key = spaceKey(t);
    (spaces[key] = spaces[key] || []).push(t);
  });
  const keys = [...new Set([...Object.keys(spaces), ...customSpaces.map(s => s.key)])].sort(spaceCmp);   // 有任务的 + 自建的（自建空空间也显示）
  list.appendChild(wsSectionHead(tr('wsSpaces') + ' (' + keys.length + ')'));
  keys.forEach(k => {
    list.appendChild(wsSpaceRow(k, spaces[k] || []));
    if (expandedSpaces.has(k)) (spaces[k] || []).forEach(t => list.appendChild(wsItem(t, true)));
  });
  list.appendChild(wsSpaceAddRow());         // 「+ 新建空间」
}

function wsSectionHead(text) {
  const h = document.createElement('div');
  h.className = 'ws-section'; h.textContent = text;
  return h;
}

/* 一条记录 = 一个任务行：状态圆点 + 标题 + 相对时间；nested=空间里展开的子项（多缩进） */
function wsItem(t, nested) {
  const it = document.createElement('div');
  it.className = 'ws-item' + (nested ? ' nested' : '');
  const label = document.createElement('span'); label.className = 'ws-label'; label.textContent = t.title;
  const time = document.createElement('span'); time.className = 'ws-item-time'; time.textContent = relTime(t.ts);
  it.append(label, time);

  /* 删除：先出 ✕，点一下整行换成「删除「标题」？ [删除] [取消]」，再点删除才真删。
     确认态里藏起标题/时间、把标题放进问句 —— 248px 窄栏里同行放不下，会全被截断 */
  if (pendingDeleteTs === t.ts) {
    it.classList.add('confirming');
    const ask = document.createElement('span'); ask.className = 'ws-del-ask';
    ask.textContent = tr('delAsk').replace('{t}', t.title);
    const yes = document.createElement('button'); yes.type = 'button'; yes.className = 'ws-del-yes';
    yes.textContent = tr('delYes');
    yes.onclick = (e) => { e.stopPropagation(); deleteTask(t.ts); };
    const no = document.createElement('button'); no.type = 'button'; no.className = 'ws-del-no';
    no.textContent = tr('cancel');
    no.onclick = (e) => { e.stopPropagation(); pendingDeleteTs = null; renderWorkspace(); };
    it.append(ask, yes, no);
  } else {
    const del = document.createElement('button'); del.type = 'button'; del.className = 'ws-del';
    del.textContent = '✕'; del.title = tr('del');
    del.onclick = (e) => { e.stopPropagation(); pendingDeleteTs = t.ts; renderWorkspace(); };
    it.append(del);
    it.onclick = () => { if ($('wsMoveMenu')) $('wsMoveMenu').remove(); focusTask(t.ts); unpinSidebar(); };
  }
  /* 右键：移动到空间 / 删除 */
  it.addEventListener('contextmenu', (e) => { e.preventDefault(); openTaskMenu(e, t); });
  /* 拖拽：直接拖到空间文件夹行上完成移动 */
  it.draggable = true;
  it.addEventListener('dragstart', (e) => {
    e.dataTransfer.setData('text/plain', String(t.ts));
    e.dataTransfer.effectAllowed = 'move';
    pinSidebar(true);                       // 拖拽期间侧栏钉住，不能自动收
  });
  it.addEventListener('dragend', () => {
    document.querySelectorAll('.ws-space.dropping').forEach(el => el.classList.remove('dropping'));
  });
  return it;
}

/* 空间文件夹行：▸/▾ + 文件夹图标 + 名称 + 记录数；点击展开/收起（状态存 localStorage） */
function wsSpaceRow(key, items) {
  const row = document.createElement('div');
  row.className = 'ws-space';
  const open = expandedSpaces.has(key);
  const caret = document.createElement('span'); caret.className = 'ws-space-caret'; caret.textContent = open ? '▾' : '▸';
  const icon = document.createElement('span'); icon.className = 'ws-space-icon';
  icon.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>';
  const name = document.createElement('span'); name.className = 'ws-space-name'; name.textContent = spaceName(key);
  const count = document.createElement('span'); count.className = 'ws-space-count'; count.textContent = String(items.length);
  row.append(caret, icon, name, count);
  row.onclick = () => {
    if (expandedSpaces.has(key)) expandedSpaces.delete(key); else expandedSpaces.add(key);
    saveSpaces();
    renderWorkspace();
  };
  /* 拖拽落点：把任务拖到文件夹上，即移入该空间 */
  row.addEventListener('dragover', (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; row.classList.add('dropping'); });
  row.addEventListener('dragleave', () => row.classList.remove('dropping'));
  row.addEventListener('drop', (e) => {
    e.preventDefault();
    row.classList.remove('dropping');
    const ts = Number(e.dataTransfer.getData('text/plain'));
    if (ts) moveTaskToSpace(ts, key);
  });
  return row;
}

/* 空间分区末尾：「+ 新建空间」→ 点开变成名称输入框（回车确认 / Esc 取消） */
function wsSpaceAddRow() {
  if (!addingSpace) {
    const add = document.createElement('div');
    add.className = 'ws-space-add';
    add.innerHTML = '<span class="plus">+</span><span>' + tr('newSpace') + '</span>';
    add.onclick = () => { addingSpace = true; renderWorkspace(); };
    return add;
  }
  const box = document.createElement('div');
  box.className = 'ws-space-input';
  const input = document.createElement('input');
  input.type = 'text';
  input.placeholder = tr('spaceNamePh');
  input.maxLength = 20;
  const ok = document.createElement('button');
  ok.type = 'button'; ok.className = 'ws-space-ok'; ok.textContent = '✓'; ok.title = tr('save');
  const cancel = document.createElement('button');
  cancel.type = 'button'; cancel.className = 'ws-space-cancel'; cancel.textContent = '✕'; cancel.title = tr('cancel');
  const done = (commit) => {
    addingSpace = false;
    if (commit) commitNewSpace(input.value);
    else renderWorkspace();
  };
  ok.onclick = (e) => { e.stopPropagation(); done(true); };
  cancel.onclick = (e) => { e.stopPropagation(); done(false); };
  input.addEventListener('keydown', (e) => {
    e.stopPropagation();                     // 别让全局 ESC 把侧栏一起关了
    if (e.key === 'Enter') done(true);
    if (e.key === 'Escape') done(false);
  });
  box.append(input, ok, cancel);
  setTimeout(() => input.focus(), 0);
  return box;
}

function commitNewSpace(raw) {
  const name = (raw || '').trim();
  if (!name) { renderWorkspace(); return; }
  customSpaces.push({ key: 'custom_' + Date.now(), name });
  saveCustomSpaces();
  renderWorkspace();
  toast(tr('spaceCreated') + ' ' + name);
}

/* —— 把任务移进空间：右键菜单「移动到空间」+ 直接拖到文件夹行 —— */
const FOLDER_SVG = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>';

function openTaskMenu(e, t) {
  e.preventDefault();
  if ($('wsMoveMenu')) $('wsMoveMenu').remove();
  pinSidebar(true);                        // 菜单开着时侧栏钉住，不许被 mouseleave 收掉
  const menu = document.createElement('div');
  menu.className = 'ws-menu'; menu.id = 'wsMoveMenu';
  const head = document.createElement('div');
  head.className = 'ws-menu-head'; head.textContent = tr('moveTo');
  menu.appendChild(head);
  /* 列出全部空间（标准 7 类 + 自建 + 数据里出现过的未知类），当前所在空间打 ✓ */
  const cur = spaceKey(t);
  allSpaceKeys().forEach(k => {
    const row = document.createElement('button');
    row.type = 'button';
    row.className = 'ws-menu-item' + (k === cur ? ' on' : '');
    row.innerHTML = '<span class="ws-menu-check">' + (k === cur ? '✓' : '') + '</span>' + FOLDER_SVG + '<span>' + spaceName(k) + '</span>';
    row.onclick = (ev) => { ev.stopPropagation(); moveTaskToSpace(t.ts, k); if ($('wsMoveMenu')) $('wsMoveMenu').remove(); };
    menu.appendChild(row);
  });
  const sep = document.createElement('div'); sep.className = 'ws-menu-sep'; menu.appendChild(sep);
  const del = document.createElement('button');
  del.type = 'button'; del.className = 'ws-menu-item danger'; del.textContent = tr('del');
  del.onclick = (ev) => {                   // 复用行内删除确认（任务清单/空间里都会出现确认态）
    ev.stopPropagation();
    if ($('wsMoveMenu')) $('wsMoveMenu').remove();
    pendingDeleteTs = t.ts;
    renderWorkspace();
  };
  menu.appendChild(del);
  document.body.appendChild(menu);
  const r = menu.getBoundingClientRect();   // 别溢出视口
  menu.style.left = Math.max(8, Math.min(e.clientX, window.innerWidth - r.width - 8)) + 'px';
  menu.style.top = Math.max(8, Math.min(e.clientY, window.innerHeight - r.height - 8)) + 'px';
}

function moveTaskToSpace(ts, key) {
  const t = tasks.find(x => x.ts === ts);
  if (!t || t.category === key) return;
  t.category = key;
  saveTasks();
  renderWorkspace();                        // 侧栏两边（任务清单 + 空间）都重排
}

let pendingDeleteTs = null;                    // 正在等待删除确认的记录 ts（一次只有一条）
function deleteTask(ts) {
  tasks = tasks.filter(t => t.ts !== ts);
  saveTasks();
  pendingDeleteTs = null;
  if (highlightTs === ts) highlightTs = null;
  renderWorkspace();                           // 左侧列表少一条
}

function focusTask(ts) {
  const t = tasks.find(x => x.ts === ts);
  if (t) {                                  // 点左侧记录：原文回填到书写框
    const text = rawTextOf(t);
    if (text) $('input').value = text;
  }
  // 只在对话区域显示，不拉起右侧任务栏
}

/* ---------- 6) 视图 / 输入 ---------- */

/* —— 语音输入（浏览器自带 Web Speech API，零配置零依赖，仅 Chrome/Edge 可用）——
   灵感来了张嘴就录：点麦克风开始，再点停止，识别结果直接追加进输入框。
   不支持时把按钮标灰并提示，绝不影响打字。 */
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let micRec = null, micOn = false;
function toggleMic() {
  if (!SR) {                       // 浏览器不支持 → 温和提示，不打断使用
    toast(tr('micUnsupported'));
    return;
  }
  if (micOn) { micRec && micRec.stop(); return; }   // 再点一次 = 停止

  const inp = $('input');
  micRec = new SR();
  micRec.lang = getSet('lang') === 'en' ? 'en-US' : 'zh-CN';
  micRec.continuous = true;        // 长句不断
  micRec.interimResults = true;    // 边说边出字

  // 把这次录音的基准位置记住：新识别的字插在它前面，不打乱已写内容
  const base = inp.value;
  let finalText = '';
  micRec.onresult = (e) => {
    let interim = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      if (r.isFinal) finalText += r[0].transcript;
      else interim += r[0].transcript;
    }
    inp.value = base + finalText + interim;
    inp.scrollTop = inp.scrollHeight;
    inp.focus();
  };
  micRec.onerror = (e) => {
    toast(e.error === 'not-allowed' ? tr('micDenied') : tr('micFailed'));
    stopMic();
  };
  micRec.onend = () => { if (micOn) stopMic(); };   // 静音自动结束也收尾

  try {
    micRec.start();
    micOn = true;
    micRec && ($('micBtn').classList.add('on'));    // 按钮进入录音态
    document.body.classList.add('mic-recording');  // 书写区留个可视提示
    inp.focus();
  } catch {
    toast(tr('micFailed'));
    stopMic();
  }
}
function stopMic() {
  micOn = false;
  try { micRec && micRec.stop(); } catch {}
  micRec = null;
  const b = $('micBtn');
  if (b) b.classList.remove('on');
  document.body.classList.remove('mic-recording');
}

/* 「+ 新任务」= 新建入口：开一页全新的空白输入。
   若当前页已有没存档的内容，先问一句「是否丢弃」，绝不静默清空。 */
let newPageFlash = null;                  // 新页面提示条的一次性定时器
function newCapture() {
  const inp = $('input');
  const hasDraft = inp.value.trim().length > 0;
  const go = () => {
    hidePermAsk();
    if ($('wsMoveMenu')) $('wsMoveMenu').remove();
    addingSpace = false;
    unpinSidebar();
    inp.value = '';
    document.body.classList.add('new-page');   // 新页面状态（新页视觉标记）
    inp.focus();
    // 输入一个字后就不再提示「新的一页」
    if (newPageFlash) clearTimeout(newPageFlash);
    newPageFlash = setTimeout(() => {
      document.body.classList.remove('new-page');
      newPageFlash = null;
    }, 2600);
  };
  if (hasDraft) {
    // 有草稿 → 确认再丢弃，不静默清空
    if (confirm(tr('discardDraft'))) go();
    return;
  }
  go();
}

/* ============================================================
   7) 设置（DSH 同款：左导航 + 右内容两栏）
      「通用设置」四行全部真生效：
        权限      —— 决定存档时是否调用 AI（见 resolveMode / archive）
        语言      —— 中/英文界面文案（applyI18n）
        外观      —— 浅色 / 深色 / 跟随系统（applyTheme）
        字号大小  —— 只改记录内容字号（--fs-content），改完重算列表高度
      「模型」里的 API 密钥同样真实写入 localStorage 并参与请求。
   ============================================================ */

/* —— 语言包：只放界面文案，不放被存档的数据 —— */
const I18N = {
  zh: {
    newTask: '+ 新的一页',
    mic: '语音输入（说想法）',
    micHint: '说想法',
    micUnsupported: '当前浏览器不支持语音识别，请用 Chrome 或 Edge',
    micDenied: '没拿到麦克风权限，请在浏览器地址栏允许后再试',
    micFailed: '语音识别没能启动，请再试一次',
    discardDraft: '当前这页还没存档，确定丢弃、直接开新的一页吗？',
    wsTasks: '任务',
    wsSpaces: '空间',
    moveTo: '移动到空间',
    newSpace: '新建空间',
    spaceNamePh: '空间名称（20 字以内）',
    spaceCreated: '已创建空间',
    empty: '暂无记录',
    settings: '设置',
    placeholder: '现在，写下你造的字吧',
    summarize: '总结',
    project: '项目（可选）',
    archive: '存档',
    taskbarHead: '任务栏 · 已存档 / 处理状态',
    snLabel: '简单随笔',

    settingsTitle: '设置',
    openConfig: '打开配置文件',
    navGeneral: '通用设置', navModel: '模型', navPlugin: '插件', navPreset: 'Agent 预设',

    perm: '权限',
    permDesc: '决定存档时是否调用 AI 处理',
    permFull: '完全权限',
    permAsk: '每次询问',
    permReadonly: '只读',
    lang: '语言',
    langZh: '中文', langEn: 'English',
    appear: '外观',
    light: '浅色', dark: '深色', system: '跟随系统',
    size: '字号大小',
    sizeDesc: '仅影响记录内容的字号（代码块不跟随）',
    calli: '字体', calliDesc: '书写与记录卡片的中文字体',
    calliLishu: '隶书', calliKaishu: '楷书', calliCaoshu: '草书', calliXingshu: '行书',
    calliSwitched: '已切换为', jevJudged: 'JEV 模型已判断',

    modelTitle: '模型',
    modelDesc: '默认走 OpenAI 官方接口，兼容所有 OpenAI 协议的服务（DeepSeek、本地模型等都可）。填入 API 密钥即可使用。',
    apiKey: 'API 密钥',
    apiKeyPlaceholder: '输入 API 密钥',
    adv: '自定义设置',
    threshold: '分类阈值（0–1）',
    llmBase: '接口地址',
    llmModel: '模型',
    cancel: '取消', save: '保存', saved: '已保存',
    addProvider: '+ 添加提供方',
    addCustomProvider: '+ 添加自定义提供方',
    pluginEmpty: '暂无插件。',
    presetEmpty: '暂无预设。',

    askTitle: '要调用 AI 处理这条记录吗？',
    askRaw: '只记录',
    askFull: 'AI 处理',

    /* 卡片 / 工作区里动态拼出来的文案 */
    catLabel: '分类：', projLabel: '项目：', filefmtLabel: '文件格式：',
    copy: '复制', copied: '已复制', copiedHandoff: '已复制，粘进 Agent 对话即可',
    filetypeChip: '文件类型：MD文件',
    relJust: '刚刚', relMin: '分钟前', relHour: '小时前',
    relYest: '昨天', relMonth: '月', relDay: '日', relYear: '年',
    del: '删除', delAsk: '删除「{t}」？', delYes: '删除',
    stRaw: '已记录', stDone: '已总结', stFail: '处理失败',
  },
  en: {
    newTask: '+ New page',
    mic: 'Voice input (speak your idea)',
    micHint: 'Speak',
    micUnsupported: 'This browser has no speech recognition. Please use Chrome or Edge.',
    micDenied: 'Microphone not allowed. Allow it from the address bar, then retry.',
    micFailed: 'Speech recognition could not start. Please try again.',
    discardDraft: "This page hasn't been archived yet. Discard it and start a new one?",
    wsTasks: 'Tasks',
    wsSpaces: 'Spaces',
    moveTo: 'Move to space',
    newSpace: 'New space',
    spaceNamePh: 'Space name',
    spaceCreated: 'Space created',
    empty: 'No records yet',
    settings: 'Settings',
    placeholder: 'Start a line to record your thoughts, or paste something in…\nThe top scrolls out of view as you write — nothing is lost.',
    summarize: 'Summarize',
    project: 'Project (optional)',
    archive: 'Archive',
    taskbarHead: 'Taskbar · archived / processing status',
    snLabel: 'simple note',

    settingsTitle: 'Settings',
    openConfig: 'Open config file',
    navGeneral: 'General', navModel: 'Models', navPlugin: 'Plugins', navPreset: 'Agent presets',

    perm: 'Permission',
    permDesc: 'Whether archiving calls the AI to process the note',
    permFull: 'Full access',
    permAsk: 'Ask each time',
    permReadonly: 'Read-only',
    lang: 'Language',
    langZh: '中文', langEn: 'English',
    appear: 'Appearance',
    light: 'Light', dark: 'Dark', system: 'System',
    size: 'Font size',
    sizeDesc: 'Affects record content only — code blocks keep their size',
    calli: 'Calligraphy', calliDesc: 'Chinese calligraphy font for writing & cards',
    calliLishu: 'LiShu 隶', calliKaishu: 'KaiShu 楷', calliCaoshu: 'CaoShu 草', calliXingshu: 'XingShu 行',
    calliSwitched: 'Switched to', jevJudged: 'JEV model judged',

    modelTitle: 'Models',
    modelDesc: 'Uses OpenAI by default and works with any OpenAI-compatible endpoint (DeepSeek, local models, etc). Enter an API key to enable it.',
    apiKey: 'API key',
    apiKeyPlaceholder: 'Enter API key',
    adv: 'Custom settings',
    threshold: 'Classification threshold (0–1)',
    llmBase: 'Endpoint',
    llmModel: 'Model',
    cancel: 'Cancel', save: 'Save', saved: 'Saved',
    addProvider: '+ Add provider',
    addCustomProvider: '+ Add custom provider',
    pluginEmpty: 'No plugins yet.',
    presetEmpty: 'No presets yet.',

    askTitle: 'Call the AI to process this note?',
    askRaw: 'Record only',
    askFull: 'Process with AI',

    catLabel: 'Category: ', projLabel: 'Project: ', filefmtLabel: 'Files: ',
    copy: 'Copy', copied: 'Copied', copiedHandoff: 'Copied — paste it into your Agent chat',
    filetypeChip: 'File type: MD',
    relJust: 'just now', relMin: 'm ago', relHour: 'h ago',
    relYest: 'yesterday', relMonth: '/', relDay: '', relYear: '/',
    del: 'Delete', delAsk: 'Delete "{t}"?', delYes: 'Delete',
    stRaw: 'Recorded', stDone: 'Summarized', stFail: 'Failed',
  },
};

/* 取界面文案；缺 key 时回退中文，再回退 key 本身 */
function tr(key) {
  const pack = I18N[curLang] || I18N.zh;
  return pack[key] != null ? pack[key] : (I18N.zh[key] != null ? I18N.zh[key] : key);
}

/* 存档状态是「数据」，用固定中文码存储；显示时翻译，保证换语言不污染数据 */
const ST_MAP = { '已记录': 'stRaw', '已总结': 'stDone', '处理失败': 'stFail' };
function statusLabel(code) { return ST_MAP[code] ? tr(ST_MAP[code]) : code; }

/* 分类标识 → 中文显示（中文界面用；英文界面保持英文标识） */
const CAT_CN = {
  todo: '待办类', existing_project: '项目类', inspiration: '灵感类',
  essay: '随笔类', life_talk: '人生探讨类', other: '其他类', raw: '原样记录',
};
function catName(c) { return curLang === 'zh' ? (CAT_CN[c] || c) : c; }

/* 空间（文件夹）用的类别名：比分类名更短，读起来像项目名 */
const SPACE_CN = {
  todo: '待办', existing_project: '项目', inspiration: '灵感',
  essay: '随笔', life_talk: '人生', other: '其他', raw: '随手记',
};
const SPACE_EN = {
  todo: 'To-dos', existing_project: 'Projects', inspiration: 'Inspiration',
  essay: 'Essays', life_talk: 'Life & talks', other: 'Other', raw: 'Quick notes',
};
const SPACE_ORDER = ['todo', 'existing_project', 'inspiration', 'essay', 'life_talk', 'other', 'raw'];
function spaceKey(t) { return t.category || 'other'; }              // 没分类过的老记录归到「其他」
function allSpaceKeys() {                                           // 全部空间：标准类 + 自建 + 数据里冒出来的未知类
  return [...new Set([...SPACE_ORDER, ...customSpaces.map(s => s.key), ...tasks.map(spaceKey)])].sort(spaceCmp);
}
function spaceName(k) {
  const custom = customSpaces.find(s => s.key === k);               // 自建空间名是用户数据，不随语言变
  if (custom) return custom.name;
  if (curLang === 'en') return SPACE_EN[k] || catName(k);
  return SPACE_CN[k] || catName(k);
}
function spaceRank(k) {                                             // 标准类固定序 → 自建按创建序 → 未知垫底
  const i = SPACE_ORDER.indexOf(k);
  if (i >= 0) return i;
  const c = customSpaces.findIndex(s => s.key === k);
  return c >= 0 ? 100 + c : 900;
}
function spaceCmp(a, b) {
  return spaceRank(a) - spaceRank(b) || a.localeCompare(b);
}

/* 相对时间：刚刚 / N分钟前 / N小时前 / 昨天 / M月D日 / YYYY年M月D日 */
function relTime(ts) {
  const now = new Date(), then = new Date(ts);
  const diff = Date.now() - ts;
  const MIN = 60000, HOUR = 3600000, DAY = 86400000;
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  if (diff < MIN) return tr('relJust');
  if (diff < HOUR) return Math.floor(diff / MIN) + tr('relMin');
  if (ts >= startToday) return Math.floor(diff / HOUR) + tr('relHour');
  if (ts >= startToday - DAY) return tr('relYest');
  const md = (then.getMonth() + 1) + tr('relMonth') + then.getDate() + tr('relDay');
  return then.getFullYear() === now.getFullYear() ? md : then.getFullYear() + tr('relYear') + md;
}

/* —— 语言：把文案刷到所有带 data-i18n* 标记的节点上 —— */
function applyI18n(lang) {
  curLang = lang;
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const v = tr(el.dataset.i18n); if (v != null) el.textContent = v;
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const v = tr(el.dataset.i18nPlaceholder); if (v != null) el.placeholder = v;
  });
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const v = tr(el.dataset.i18nTitle); if (v != null) { el.title = v; el.setAttribute('aria-label', v); }
  });
  document.documentElement.lang = lang === 'en' ? 'en' : 'zh-CN';
  renderWorkspace();                 // 分组名 / 状态标签也要跟着换
}
function pickLang(lang) {
  setSet('lang', lang);
  applyI18n(lang);
}

/* —— 字体（隶书/楷书/草书/行书）：切 data-calli，全局 --font-calli 生效 —— */
function pickCalli(v) {
  setSet('calli', v);
  applyCalli(v);
  toast(tr('calliSwitched') + ' ' + tr('calli' + v[0].toUpperCase() + v.slice(1)));
}

/* 轻提示：底部居中浮出一句话，1.4s 后消失 */
function toast(msg) {
  let t = $('toast');
  if (!t) { t = document.createElement('div'); t.id = 'toast'; document.body.appendChild(t); }
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(t.__timer);
  t.__timer = setTimeout(() => t.classList.remove('show'), 1400);
}
function applyCalli(v) {
  if (!CALLI_FONTS[v]) v = 'xingshu';
  document.documentElement.setAttribute('data-calli', v);
  const sel = $('set_calli'); if (sel) sel.value = v;
  const bar = $('calliQuick');
  if (bar) bar.querySelectorAll('.calli-btn').forEach(b => b.classList.toggle('on', b.dataset.calli === v));
  const inp = $('input');                       // 切换动效：重放一次淡入
  if (inp) { inp.classList.remove('calli-switch'); void inp.offsetWidth; inp.classList.add('calli-switch'); }
}



/* —— 外观：浅色 / 深色 / 跟随系统（真换主题） —— */
const mqDark = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
function applyTheme(mode) {
  const dark = mode === 'dark' || (mode === 'system' && !!(mqDark && mqDark.matches));
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
}
function syncAppearCards(mode) {
  document.querySelectorAll('.appear-card').forEach(c => c.classList.toggle('on', c.dataset.theme === mode));
}
function pickTheme(mode) {
  setSet('theme', mode);
  applyTheme(mode);
  syncAppearCards(mode);
}
if (mqDark && mqDark.addEventListener) {
  mqDark.addEventListener('change', () => { if (getSet('theme') === 'system') applyTheme('system'); });
}

/* —— 字号大小设置项已删除：--fs-content 固定走 SETTINGS.size.def（22px） —— */

/* —— 权限：只记状态，真正分流在 resolveMode / archive —— */
function pickPerm(mode) {
  setSet('perm', mode);
  if (mode !== 'ask') hidePermAsk();
}

/* —— 模型提供方（各卡独立保存 / 取消） —— */
const PROVIDER_FIELDS = {
  jev:   [['set_jev_key', 'jev_key'], ['set_threshold', 'threshold']],
  openai: [['set_openai_key', 'openai_key'], ['set_llm_base', 'llm_base'], ['set_llm_model', 'llm_model']],
};

function loadSettings() {                                  // 打开弹窗时把已存的值回填到控件
  /* 通用模型卡片默认指向 GLM（智谱）：用户主用 GLM，只填密钥即可，不必手改接口地址/模型。
     仅当本地还没存过时才落默认值，不覆盖用户自己改过的值 */
  if (!localStorage.getItem('llm_base')) localStorage.setItem('llm_base', 'https://open.bigmodel.cn/api/paas/v4');
  if (!localStorage.getItem('llm_model')) localStorage.setItem('llm_model', 'glm-4-flash');
  Object.values(PROVIDER_FIELDS).flat().forEach(([elId, key]) => {
    const el = $(elId); if (el) el.value = localStorage.getItem(key) || '';
  });
  $('set_perm').value = getSet('perm');
  $('set_lang').value = getSet('lang');
  syncAppearCards(getSet('theme'));
}
function openSettings() { loadSettings(); switchSetTab('general'); $('settingsBackdrop').classList.add('open'); }
function closeSettings() { $('settingsBackdrop').classList.remove('open'); }

function switchSetTab(name) {
  document.querySelectorAll('.set-nav-item').forEach(b => b.classList.toggle('on', b.dataset.tab === name));
  document.querySelectorAll('.set-pane').forEach(p => p.classList.toggle('on', p.dataset.pane === name));
}
function saveProvider(which, btn) {                        // 各提供方独立保存到 localStorage
  PROVIDER_FIELDS[which].forEach(([elId, key]) => localStorage.setItem(key, ($(elId).value || '').trim()));
  if (btn) { const old = btn.textContent; btn.textContent = tr('saved'); setTimeout(() => { btn.textContent = old; }, 1000); }
}
function revertProvider(which) {                           // 取消：回退到已保存的值
  PROVIDER_FIELDS[which].forEach(([elId, key]) => { $(elId).value = localStorage.getItem(key) || ''; });
}

/* 服务端本机配置（web/local_config.json）里的 key 同步进设置：
   浏览器本地没填过就直接落进来，这样「设置 → 模型」能看到、能改、能保存 */
async function syncServerKeys() {
  const cfg = await ensureServerMode();
  let changed = false;
  [['jev_key', cfg.jev_key], ['openai_key', cfg.openai_key]].forEach(([k, v]) => {
    if (v && !localStorage.getItem(k)) { localStorage.setItem(k, v); changed = true; }
  });
  if (changed) loadSettings();                             // 弹窗标题/输入框同步刷新
}

/* ---------- 8) 初始化 ---------- */
/* 先把设置套上：主题 / 字号 / 语言
   —— 字号必须在第一次量卡片高度之前生效，否则虚拟滚动的高度会算错 */
applyTheme(getSet('theme'));
syncAppearCards(getSet('theme'));
document.documentElement.style.setProperty('--fs-content', getSet('size') + 'px');
applyCalli(getSet('calli'));         // 恢复上次的书法体（隶/楷/草/行）
applyI18n(getSet('lang'));
syncServerKeys();                    // 本机配置的 key 同步进设置面板（异步，失败不影响启动）

/* 预加载四款书法体：菜单里每个选项要用自己的字体预览，而 @font-face 是
   font-display:block —— 字体没下载完时那几个字是「不画」的，不预载打开菜单就是一片空白 */
if (document.fonts && document.fonts.load) {
  Object.values(CALLI_FONTS).forEach(f => document.fonts.load('16px "' + f + '"'));
}

/* 手写体（行书 / Dancing Script）到齐后再做两件事：
   ① 把占位符重挂一遍 —— 浏览器可能在字体没下载完时先用系统字体画过 ::placeholder，
      字体随后加载完成却不再重绘那块，书写区里就混进系统字体。
   ② 作废卡片固定部件的高度探针并重算 —— font-display: block 期间量到的是回落字体的
      行高，字体到位后高度会变，不重算就会错位。 */
if (document.fonts && document.fonts.ready) {
  document.fonts.ready.then(() => {
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const v = tr(el.dataset.i18nPlaceholder);
      if (v != null) { el.placeholder = ''; el.placeholder = v; }
    });
  });
}

/* 左侧工具栏：鼠标挪到左边缘热区（或悬停其上）即展开，移开稍候即收起。
   右键菜单 / 拖拽期间会「钉住」不自动收，直到点别处 / 选了一条记录 / 按 ESC */
const sidebarEl = $('sidebar'), edgeEl = $('edge');
let sideHideTimer = null;
let sidePinned = false;
function openSidebar() { clearTimeout(sideHideTimer); sidebarEl.classList.add('open'); }
function closeSidebar() {
  if (sidePinned) return;
  sideHideTimer = setTimeout(() => { sidebarEl.classList.remove('open'); }, 130);
}
function pinSidebar(on) {
  sidePinned = on;
  if (on) { clearTimeout(sideHideTimer); sidebarEl.classList.add('open'); }
}
function unpinSidebar() { pinSidebar(false); sidebarEl.classList.remove('open'); }
/* 钉住的侧栏：点在侧栏 / 右键菜单之外 → 收起（浮层通用交互）。
   必须挂在捕获阶段：点空间文件夹 / 新建空间 / 删除确认时，处理函数会重渲列表、把当前点击的
   元素拆离文档，冒泡到这里时 closest 会失效、被误判成"点外面"把侧栏关掉。 */
document.addEventListener('click', (e) => {
  if (!e.target.closest || e.target.closest('#sidebar, #wsMoveMenu')) return;
  if ($('wsMoveMenu')) $('wsMoveMenu').remove();
  if (sidePinned) unpinSidebar();
}, true);
/* 菜单开着时滚动侧栏会脱锚，直接关掉 */
$('wsList').addEventListener('wheel', () => { if ($('wsMoveMenu')) $('wsMoveMenu').remove(); }, { passive: true });

/* —— 贴边唤起（左侧栏）：鼠标坐标判定，与层叠无关 ——
   原来的坑：面板滑出后会盖住贴边热区，鼠标停在边缘不动时收不到 mouseenter，
   导致面板刚开就被收起，必须挪出去再进来一次才留得住。
   坐标判定：鼠标在边缘带内就开，离开「面板宽度 + 宽容度」才收。 */
const EDGE_W = 20;        // 贴边敏感带（比原来的 14px 热区略宽，更好碰到）
const SIDEBAR_W = 248;    // 与 .sidebar width 一致
const KEEP_GRACE = 40;    // 越界宽容：刚移出面板边界不立刻收，避免来回抖
window.addEventListener('mousemove', (e) => {
  const x = e.clientX;
  if (x <= EDGE_W) { openSidebar(); }
  else if (sidebarEl.classList.contains('open') && x > SIDEBAR_W + KEEP_GRACE) { closeSidebar(); }
}, { passive: true });

$('input').addEventListener('input', e => { e.target.scrollTop = e.target.scrollHeight; });  // 写长上方滚出视野
const capInner = document.querySelector('.capture-inner');
$('input').addEventListener('focus', () => capInner.classList.add('hide-actions'));  // 开始输入 → 底部按钮消失
$('input').addEventListener('blur', () => capInner.classList.remove('hide-actions')); // 停笔 → 恢复可点
document.addEventListener('keydown', e => {        // DSH 同款：ESC 逐层关浮层（设置 → 右键菜单 → 侧栏 → 询问条）
  if (e.key !== 'Escape') return;
  if ($('settingsBackdrop').classList.contains('open')) { closeSettings(); return; }
  if ($('wsMoveMenu')) $('wsMoveMenu').remove();
  if (sidePinned) { unpinSidebar(); return; }
  hidePermAsk();
});
renderWorkspace();
$('input').focus();

/* 模块化（type="module"）后，HTML 内联 onclick 仍需要这些函数挂在 window 上 */
Object.assign(window, {
  newCapture, toggleCreate, archive, summarize, copyInput,
  toggleMic, stopMic,
  showSummaryPanel, closeSummary, copySummary,
  openSettings, closeSettings, switchSetTab,
  pickPerm, pickLang, pickTheme,
  // app.js 是 type="module"，函数声明不会自动挂到 window，
  // 内联 onclick 找不到就静默失效 —— 新加的按钮必须在这里导出
  pickCalli, toast,
  saveProvider, revertProvider,
});
