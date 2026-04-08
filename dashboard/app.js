// ─── i18n ───
document.getElementById('lang-select').value = currentLang;

function applyI18n() {
  document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
  document.getElementById('search-input').placeholder = t('searchPlaceholder');
  updateStats();
  renderLayers();
}

function switchLang(lang) {
  currentLang = lang;
  localStorage.setItem('steercode-lang', lang);
  applyI18n();
}

function updateStats() {
  document.getElementById('stat-files').textContent = nodes.filter(n=>n.type==='file').length.toLocaleString() + ' ' + t('files').toLowerCase();
  document.getElementById('stat-functions').textContent = nodes.filter(n=>n.type==='function').length.toLocaleString() + ' ' + t('functions').toLowerCase();
  document.getElementById('stat-classes').textContent = nodes.filter(n=>n.type==='class').length.toLocaleString() + ' ' + t('classes').toLowerCase();
  document.getElementById('stat-edges').textContent = edges.length.toLocaleString() + ' ' + t('connections');
  document.getElementById('stat-langs').textContent = langs.size + ' ' + t('languages');
}

const nodes = GRAPH_DATA.nodes;
const edges = GRAPH_DATA.edges;
const layers = GRAPH_DATA.layers;
const project = GRAPH_DATA.project;

const IS_LARGE = nodes.length > 1000;
const MAX_NODE_DEFAULT = IS_LARGE ? 500 : 0;
const langs = new Set(nodes.map(n=>n.language).filter(Boolean));

if (IS_LARGE) {
  document.getElementById('filter-function').checked = false;
  document.getElementById('filter-class').checked = false;
  document.getElementById('banner-area').innerHTML =
    '<div class="banner banner-warn">⚡ ' + t('largeGraph') + ' (' + nodes.length.toLocaleString() +
    ' ' + t('largeGraphMsg') + '</div>';
} else {
  document.getElementById('filter-function').checked = true;
  document.getElementById('filter-class').checked = true;
}

updateStats();
const TYPE_COLORS = {file:'#58a6ff',function:'#3fb950',class:'#bc8cff',module:'#d29922'};
const TYPE_SHAPES = {file:'dot',function:'diamond',class:'triangle',module:'square'};
const LAYER_COLORS = {api:'#58a6ff',ui:'#f778ba',service:'#3fb950',data:'#d29922',infra:'#bc8cff',test:'#39d2c0',docs:'#8b949e'};
const EDGE_COLORS = {contains:'#30363d',imports:'#58a6ff',calls:'#3fb950',inherits:'#bc8cff',implements:'#d29922'};

const nodeLayerMap = {};
layers.forEach(l => l.node_ids.forEach(id => { nodeLayerMap[id] = l.id; }));

// ─── Layer Sidebar ───
const layerListEl = document.getElementById('layer-list');
let activeLayer = null;

function renderLayers() {
  layerListEl.innerHTML = '<div class="layer-item' + (activeLayer===null?' active':'') + '" onclick="filterLayer(null)"><div class="layer-dot" style="background:var(--text)"></div>' + t('all') + '<span class="layer-count">' + nodes.length.toLocaleString() + '</span></div>';
  layers.forEach(l => {
    layerListEl.innerHTML += '<div class="layer-item' + (activeLayer===l.id?' active':'') + '" onclick="filterLayer(\'' + l.id + '\')"><div class="layer-dot layer-' + l.id + '"></div>' + l.name + '<span class="layer-count">' + l.node_ids.length.toLocaleString() + '</span></div>';
  });
}
renderLayers();

// ─── Complexity Filter ───
function getActiveComplexities() {
  const c = new Set();
  document.querySelectorAll('.complexity-cb').forEach(cb => { if (cb.checked) c.add(cb.dataset.complexity); });
  return c;
}
document.querySelectorAll('.complexity-cb').forEach(cb => cb.addEventListener('change', () => refreshGraph()));

// ─── Language Filter ───
const langCounts = new Map();
nodes.forEach(n => { if (n.language) langCounts.set(n.language, (langCounts.get(n.language)||0)+1); });
const activeLangs = new Set(langCounts.keys());

(function renderLangFilter() {
  const list = document.getElementById('lang-list');
  const sorted = [...langCounts.entries()].sort((a,b) => b[1]-a[1]);
  list.innerHTML = sorted.map(([lang, count]) =>
    '<label style="font-size:12px;color:var(--text2);display:flex;align-items:center;gap:6px;cursor:pointer;padding:3px 0">' +
    '<input type="checkbox" class="lang-cb" data-lang="' + lang + '" checked style="accent-color:var(--accent)"> ' +
    lang + ' <span style="margin-left:auto;font-size:10px;opacity:.6">' + count + '</span></label>'
  ).join('');
  list.querySelectorAll('.lang-cb').forEach(cb => cb.addEventListener('change', () => {
    if (cb.checked) activeLangs.add(cb.dataset.lang); else activeLangs.delete(cb.dataset.lang);
    refreshGraph();
  }));
})();

// ─── Vis Network ───
const nodeIdMap = {};
nodes.forEach(n => { nodeIdMap[n.id] = n; });

function getNodeColor(n) {
  const lid = nodeLayerMap[n.id];
  if (lid && LAYER_COLORS[lid]) return LAYER_COLORS[lid];
  return TYPE_COLORS[n.type] || '#8b949e';
}

function getActiveFilters() {
  const f = new Set();
  document.querySelectorAll('[data-filter]').forEach(cb => { if (cb.checked) f.add(cb.dataset.filter); });
  return f;
}

function getNodeLimit() {
  return parseInt(document.getElementById('node-limit').value) || 0;
}

// Pre-build set of nodes that have at least one edge
const connectedIds = new Set();
edges.forEach(e => { connectedIds.add(e.source); connectedIds.add(e.target); });

function buildVisNodes(filterTypes, filterLayerId, limit) {
  const activeComplexities = getActiveComplexities();
  let filtered = nodes.filter(n => {
    if (!connectedIds.has(n.id)) return false;
    if (!filterTypes.has(n.type)) return false;
    if (filterLayerId && !layers.find(l=>l.id===filterLayerId)?.node_ids.includes(n.id)) return false;
    if (n.complexity && !activeComplexities.has(n.complexity)) return false;
    if (n.language && !activeLangs.has(n.language)) return false;
    return true;
  });
  const total = filtered.length;
  if (limit > 0 && filtered.length > limit) {
    const typePrio = {class:3, function:2, file:1};
    const compPrio = {complex:3, moderate:2, simple:1};
    filtered.sort((a,b) => (compPrio[b.complexity]||0) - (compPrio[a.complexity]||0) || (typePrio[b.type]||0) - (typePrio[a.type]||0));
    filtered = filtered.slice(0, limit);
  }
  const info = document.getElementById('node-limit-info');
  if (limit > 0 && total > limit) {
    info.textContent = `${t('showing')} ${limit.toLocaleString()} ${t('of')} ${total.toLocaleString()} ${t('nodes')}`;
    info.style.display = 'block';
  } else {
    info.style.display = 'none';
  }
  return filtered.map(n => {
    const color = getNodeColor(n);
    const scale = filtered.length < 20 ? 2 : filtered.length < 100 ? 1.5 : 1;
    const size = (n.type === 'file' ? 12 : n.type === 'class' ? 16 : 10) * scale;
    const fontSize = Math.round(10 * scale);
    return {
      id: n.id, label: n.name, title: n.summary + '\n' + n.file_path,
      color: {background:color, border:color, highlight:{background:color,border:'#fff'}},
      shape: TYPE_SHAPES[n.type] || 'dot', size: size,
      font: {color:'#e6edf3', size:fontSize, face:'-apple-system,sans-serif'},
    };
  });
}

function buildVisEdges(visibleIds) {
  const idSet = new Set(visibleIds);
  return edges.filter(e => idSet.has(e.source) && idSet.has(e.target)).map((e,i) => ({
    id: e.source+'_'+e.target+'_'+e.type, from: e.source, to: e.target,
    color: {color: EDGE_COLORS[e.type]||'#444c56', opacity:0.7, highlight:EDGE_COLORS[e.type]||'#58a6ff'},
    arrows: e.type !== 'contains' ? {to:{enabled:true,scaleFactor:0.6}} : undefined,
    smooth: {type:'continuous'},
    width: e.type === 'contains' ? 0.8 : e.type === 'imports' ? 2 : 1.5,
  }));
}

const adjIndex = {};
edges.forEach(e => {
  if (!adjIndex[e.source]) adjIndex[e.source] = [];
  if (!adjIndex[e.target]) adjIndex[e.target] = [];
  adjIndex[e.source].push(e);
  adjIndex[e.target].push(e);
});

let visNodes, visEdges, network;
let expandedNodes = new Set();

function makeVisNode(n) {
  const color = getNodeColor(n);
  const size = n.type === 'file' ? 12 : n.type === 'class' ? 16 : 10;
  return {
    id: n.id, label: n.name, title: n.summary + '\n' + n.file_path,
    color: {background:color, border:color, highlight:{background:color,border:'#fff'}},
    shape: TYPE_SHAPES[n.type] || 'dot', size: size,
    font: {color:'#e6edf3', size:10, face:'-apple-system,sans-serif'},
  };
}

function expandNode(id) {
  if (expandedNodes.has(id)) return;
  expandedNodes.add(id);
  const neighborEdges = adjIndex[id] || [];
  const newNodes = [];
  const newEdges = [];
  neighborEdges.forEach(e => {
    const neighborId = e.source === id ? e.target : e.source;
    const neighborData = nodeIdMap[neighborId];
    if (!neighborData) return;
    if (!visNodes.get(neighborId)) {
      const vn = makeVisNode(neighborData);
      const pos = network.getPosition(id);
      if (pos) {
        vn.x = pos.x + (Math.random() - 0.5) * 200;
        vn.y = pos.y + (Math.random() - 0.5) * 200;
      }
      newNodes.push(vn);
    }
    const edgeId = e.source+'_'+e.target+'_'+e.type;
    if (!visEdges.get(edgeId)) {
      newEdges.push({
        id: edgeId, from: e.source, to: e.target,
        color: {color: EDGE_COLORS[e.type]||'#444c56', opacity:0.7, highlight:EDGE_COLORS[e.type]||'#58a6ff'},
        arrows: e.type !== 'contains' ? {to:{enabled:true,scaleFactor:0.6}} : undefined,
        smooth: {type:'continuous'},
        width: e.type === 'contains' ? 0.8 : e.type === 'imports' ? 2 : 1.5,
      });
    }
  });
  if (newNodes.length) visNodes.add(newNodes);
  if (newEdges.length) visEdges.add(newEdges);
  const info = document.getElementById('node-limit-info');
  info.textContent = `${visNodes.length} ${t('nodes')}, ${visEdges.length} ${t('connections')} (${t('clickExplore')})`;
  info.style.display = 'block';
}

function refreshGraph() {
  const filters = getActiveFilters();
  const limit = getNodeLimit();
  const vn = buildVisNodes(filters, activeLayer, limit);
  expandedNodes = new Set();
  const nodeCount = vn.length;
  const usePhysics = nodeCount <= 2000;
  const startClean = nodeCount > 1000;
  if (!usePhysics) {
    vn.forEach((n, i) => {
      const angle = i * 0.3;
      const r = 30 + i * 2;
      n.x = r * Math.cos(angle);
      n.y = r * Math.sin(angle);
    });
  }
  visNodes = new vis.DataSet(vn);
  const ids = vn.map(n=>n.id);
  visEdges = new vis.DataSet(startClean ? [] : buildVisEdges(ids));
  if (network) network.destroy();
  network = new vis.Network(document.getElementById('graph'), {nodes:visNodes,edges:visEdges}, {
    physics: usePhysics ? {
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {gravitationalConstant: nodeCount > 500 ? -20 : -40, centralGravity:0.005, springLength: nodeCount > 500 ? 80 : 120, springConstant:0.05, damping:0.4},
      stabilization: {iterations: nodeCount > 500 ? 80 : 150, fit:true},
    } : false,
    interaction: {hover:true, tooltipDelay:200, zoomView:true, dragView:true},
    layout: {improvedLayout: nodeCount < 300},
    edges: {smooth: {type:'continuous'}},
  });
  if (!usePhysics) setTimeout(() => network.fit(), 100);
  if (startClean) {
    const info = document.getElementById('node-limit-info');
    info.textContent = `${vn.length} ${t('clickAnyNode')}`;
    info.style.display = 'block';
  }
  network.on('click', function(p) {
    if (p.nodes.length > 0) { expandNode(p.nodes[0]); showDetail(p.nodes[0]); }
    else { closeDetail(); }
  });
  network.on('doubleClick', function(p) {
    if (p.nodes.length > 0) network.focus(p.nodes[0], {scale:1.5, animation:true});
  });
}
refreshGraph();

// ─── Filters ───
document.querySelectorAll('[data-filter]').forEach(cb => {
  cb.addEventListener('change', () => refreshGraph());
});
document.getElementById('node-limit').addEventListener('change', () => refreshGraph());

function filterLayer(lid) {
  activeLayer = lid;
  renderLayers();
  refreshGraph();
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('collapsed');
}

// ─── Search ───
const searchInput = document.getElementById('search-input');
const searchResults = document.getElementById('search-results');
let searchTimer = null;

const searchIndex = nodes.map(n => ({
  id: n.id, type: n.type, name: n.name,
  path: n.file_path || '',
  searchText: (n.name + ' ' + (n.file_path||'')).toLowerCase(),
}));

searchInput.addEventListener('input', () => {
  clearTimeout(searchTimer);
  const q = searchInput.value.toLowerCase().trim();
  if (!q) { searchResults.classList.remove('active'); return; }
  searchTimer = setTimeout(() => {
    const matches = searchIndex.filter(n => n.searchText.includes(q)).slice(0, 30);
    if (!matches.length) {
      searchResults.innerHTML = '<div class="sr-item" style="color:var(--text2)">' + t('noResults') + ' "' + q + '"</div>';
      searchResults.classList.add('active');
      return;
    }
    searchResults.innerHTML = matches.map(n =>
      '<div class="sr-item" onmousedown="focusNode(\'' + n.id + '\')"><span class="sr-type type-' + n.type + '">' + n.type + '</span>' + n.name + '<span style="margin-left:auto;font-size:11px;color:var(--text2)">' + n.path.split('/').pop() + '</span></div>'
    ).join('');
    searchResults.classList.add('active');
  }, IS_LARGE ? 150 : 0);
});

searchInput.addEventListener('blur', () => setTimeout(()=>searchResults.classList.remove('active'), 300));
document.addEventListener('keydown', e => {
  if ((e.ctrlKey||e.metaKey) && e.key === 'k') { e.preventDefault(); searchInput.focus(); searchInput.select(); }
  if (e.key === 'Escape') { searchInput.blur(); searchResults.classList.remove('active'); closeDetail(); }
});

function focusNode(id) {
  searchResults.classList.remove('active');
  searchInput.value = '';
  if (!visNodes.get(id)) {
    const n = nodeIdMap[id];
    if (n) visNodes.add(makeVisNode(n));
  }
  expandNode(id);
  network.selectNodes([id]);
  network.focus(id, {scale:1.2, animation:true});
  showDetail(id);
}

// ─── Detail Panel ───
function showDetail(id) {
  const n = nodeIdMap[id];
  if (!n) return;
  const panel = document.getElementById('detail-panel');
  const content = document.getElementById('detail-content');
  const incoming = edges.filter(e => e.target === id);
  const outgoing = edges.filter(e => e.source === id);
  const layer = layers.find(l => l.node_ids.includes(id));

  let html = '<span class="dp-type type-' + n.type + '">' + n.type + '</span>';
  if (layer) html += ' <span class="dp-type layer-' + layer.id + '" style="color:#fff">' + layer.name + '</span>';
  html += '<div class="dp-name">' + n.name + '</div>';
  if (n.file_path) html += '<div class="dp-path">📁 ' + n.file_path;
  if (n.line_range && n.line_range[0]) html += ':' + n.line_range[0] + '-' + n.line_range[1];
  html += '</div>';
  html += '<div class="dp-summary">' + n.summary + '</div>';
  html += '<span class="dp-complexity ' + n.complexity + '">' + n.complexity + '</span>';

  if (n.tags && n.tags.length) {
    html += '<div class="dp-section"><h3>' + t('tags') + '</h3>' + n.tags.map(t=>'<span class="dp-tag">' + t + '</span>').join('') + '</div>';
  }
  if (incoming.length) {
    html += '<div class="dp-section"><h3>' + t('incoming') + ' (' + incoming.length + ')</h3>';
    incoming.slice(0,30).forEach(e => {
      const src = nodeIdMap[e.source];
      if (src) html += '<div class="dp-edge" onclick="focusNode(\'' + e.source + '\')"><span class="dp-edge-type">' + e.type + '</span> ← ' + src.name + '</div>';
    });
    if (incoming.length > 30) html += '<div style="font-size:11px;color:var(--text2);padding:4px 0">...+' + (incoming.length-30) + ' ' + t('andMore') + '</div>';
    html += '</div>';
  }
  if (outgoing.length) {
    html += '<div class="dp-section"><h3>' + t('outgoing') + ' (' + outgoing.length + ')</h3>';
    outgoing.slice(0,30).forEach(e => {
      const tgt = nodeIdMap[e.target];
      if (tgt) html += '<div class="dp-edge" onclick="focusNode(\'' + e.target + '\')"><span class="dp-edge-type">' + e.type + '</span> → ' + tgt.name + '</div>';
    });
    if (outgoing.length > 30) html += '<div style="font-size:11px;color:var(--text2);padding:4px 0">...+' + (outgoing.length-30) + ' ' + t('andMore') + '</div>';
    html += '</div>';
  }
  content.innerHTML = html;
  panel.classList.add('active');
}

function closeDetail() {
  document.getElementById('detail-panel').classList.remove('active');
  if (network) network.unselectAll();
}

applyI18n();
