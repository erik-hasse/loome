const storageKey = 'loome:builder:' + BUILDER_KEY;
const firstComponent = document.querySelector('#loome-builder-component option')?.value ||
  document.querySelector('.component-view')?.dataset.component || '';
const scrollRoot = document.getElementById('loome-builder-main');
function loadState(){
  try{return JSON.parse(localStorage.getItem(storageKey)||'{"done":[]}');}
  catch(_e){return{done:[]};}
}
function saveState(state){localStorage.setItem(storageKey, JSON.stringify(state));}
function currentComponent(){
  return new URLSearchParams(window.location.search).get('component') || firstComponent;
}
function selectorOption(name){
  const selector = document.getElementById('loome-builder-component');
  if(!selector)return null;
  return [...selector.options].find(option => option.value === name) || null;
}
function setupStickyHeaders(){
  document.querySelectorAll('.component-view svg').forEach(svg => {
    if(svg.dataset.builderSticky === '1')return;
    svg.dataset.builderSticky = '1';
    const ns = 'http://www.w3.org/2000/svg';
    const overlay = document.createElementNS(ns, 'g');
    overlay.setAttribute('pointer-events', 'none');
    svg.appendChild(overlay);
    const mk = el => ({el, y: Number(el.id.split('-')[2]), parent: el.parentNode, next: el.nextSibling});
    const components = [...svg.querySelectorAll('[id^="sh-comp-"]')].map(mk).sort((a, b) => a.y - b.y);
    const connectors = [...svg.querySelectorAll('[id^="sh-conn-"]')].map(mk).sort((a, b) => a.y - b.y);
    const square = header => {
      header.el.querySelectorAll('rect').forEach(rect => {
        const rx = rect.getAttribute('rx');
        if(rx){
          rect.dataset.stickyRx = rx;
          rect.dataset.stickyRy = rect.getAttribute('ry') || '';
          rect.removeAttribute('rx');
          rect.removeAttribute('ry');
        }
      });
    };
    const unsquare = header => {
      header.el.querySelectorAll('rect').forEach(rect => {
        if(rect.dataset.stickyRx){
          rect.setAttribute('rx', rect.dataset.stickyRx);
          if(rect.dataset.stickyRy)rect.setAttribute('ry', rect.dataset.stickyRy);
          delete rect.dataset.stickyRx;
          delete rect.dataset.stickyRy;
        }
      });
    };
    const state = {
      svg, overlay, components, connectors,
      activeComponent: null, activeConnector: null,
      square, unsquare
    };
    svg._loomeStickyState = state;
  });
}
function findHeader(headers, threshold){
  let result = null;
  headers.forEach(header => {
    if(header.y <= threshold)result = header;
  });
  return result;
}
function svgScale(svg){
  const box = svg.getBoundingClientRect();
  const viewBox = svg.viewBox.baseVal;
  const height = viewBox && viewBox.height ? viewBox.height : Number(svg.getAttribute('height'));
  return height / box.height;
}
function svgViewTop(svg){
  const box = svg.getBoundingClientRect();
  const rootBox = scrollRoot.getBoundingClientRect();
  const viewBox = svg.viewBox.baseVal;
  const viewY = viewBox ? viewBox.y : 0;
  return viewY + (rootBox.top - box.top) * svgScale(svg);
}
function stickHeader(state, header, y){
  state.overlay.appendChild(header.el);
  header.el.setAttribute('transform', `translate(0,${y - header.y})`);
  state.square(header);
}
function unstickHeader(state, header){
  state.unsquare(header);
  if(header.next && header.next.parentNode === header.parent)header.parent.insertBefore(header.el, header.next);
  else header.parent.appendChild(header.el);
  header.el.removeAttribute('transform');
}
function updateStickyHeaders(){
  document.querySelectorAll('.component-view:not([hidden]) svg').forEach(svg => {
    const state = svg._loomeStickyState;
    if(!state)return;
    const CH = 28;
    const top = svgViewTop(svg);
    let component = findHeader(state.components, top);
    let connector = findHeader(state.connectors, top + CH);
    if(component && connector && connector.y <= component.y)connector = null;
    if(component !== state.activeComponent){
      if(state.activeComponent)unstickHeader(state, state.activeComponent);
      state.activeComponent = component;
    }
    if(connector !== state.activeConnector){
      if(state.activeConnector)unstickHeader(state, state.activeConnector);
      state.activeConnector = connector;
    }
    if(component){
      const nextComponent = state.components[state.components.indexOf(component) + 1];
      const y = nextComponent ? Math.min(top, nextComponent.y - CH) : top;
      stickHeader(state, component, y);
    }
    if(connector){
      const nextConnector = state.connectors[state.connectors.indexOf(connector) + 1];
      const nextComponent = component ? state.components[state.components.indexOf(component) + 1] : null;
      let nextY = Infinity;
      if(nextConnector)nextY = Math.min(nextY, nextConnector.y);
      if(nextComponent)nextY = Math.min(nextY, nextComponent.y);
      const y = Number.isFinite(nextY) ? Math.min(top + CH, nextY - CH) : top + CH;
      stickHeader(state, connector, y);
    }
  });
}
function scrollToTarget(targetId){
  const target = document.getElementById(targetId);
  if(!target)return;
  const rootBox = scrollRoot.getBoundingClientRect();
  const targetBox = target.getBoundingClientRect();
  const jumpOffset = Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue(
    '--builder-jump-offset'
  )) || 88;
  const top = scrollRoot.scrollTop + targetBox.top - rootBox.top - jumpOffset;
  scrollRoot.scrollTo({top: Math.max(0, top), behavior: 'auto'});
  updateStickyHeaders();
}
function showComponent(name, targetId, mode){
  const selected = name || firstComponent;
  const option = selectorOption(selected);
  const optionTarget = option?.dataset.target || '';
  const scrollTarget = targetId || (BUILDER_SINGLE_PAGE ? optionTarget : '');
  document.querySelectorAll('.component-view').forEach(view => {
    view.hidden = !BUILDER_SINGLE_PAGE && view.dataset.component !== selected;
  });
  const selector = document.getElementById('loome-builder-component');
  if(selector)selector.value = selected;
  const url = new URL(window.location.href);
  url.searchParams.set('component', selected);
  if(scrollTarget)url.hash = scrollTarget;else url.hash = '';
  if(mode === 'push')history.pushState(null, '', url);
  else if(mode === 'replace')history.replaceState(null, '', url);
  if(scrollTarget){
    requestAnimationFrame(() => scrollToTarget(scrollTarget));
  }else{
    scrollRoot.scrollTo({top: 0, behavior: 'auto'});
    updateStickyHeaders();
  }
}
function wireIds(){
  return BUILDER_ENTRIES.map(entry => entry.run_key);
}
function applyState(){
  const done = new Set(loadState().done || []);
  document.querySelectorAll('svg [data-seg-id]').forEach(el => {
    el.classList.toggle('wire--done', done.has(el.getAttribute('data-seg-id')));
    el.style.cursor = 'pointer';
  });
  const all = wireIds();
  const complete = all.filter(id => done.has(id)).length;
  document.getElementById('loome-builder-progress').textContent = `${complete} / ${all.length} wires run`;
  document.getElementById('loome-builder-progress-fill').style.width =
    all.length ? `${Math.round((complete / all.length) * 100)}%` : '0';
}
function attachHandlers(){
  setupStickyHeaders();
  showComponent(currentComponent(), window.location.hash ? window.location.hash.slice(1) : '', 'replace');
  scrollRoot.addEventListener('scroll', updateStickyHeaders, {passive: true});
  window.addEventListener('resize', updateStickyHeaders, {passive: true});
  document.getElementById('loome-builder-component')?.addEventListener('change', event => {
    showComponent(event.target.value, event.target.selectedOptions[0]?.dataset.target || '', 'push');
  });
  document.querySelectorAll('svg a.pin-link').forEach(link => {
    link.addEventListener('click', event => {
      const href = link.getAttribute('href') || link.getAttribute('xlink:href') || '';
      if(!href.startsWith('#'))return;
      const targetId = href.slice(1);
      const component = BUILDER_PIN_INDEX[targetId];
      if(!component)return;
      event.preventDefault();
      event.stopPropagation();
      showComponent(component, targetId, 'push');
    });
  });
  document.querySelectorAll('svg [data-seg-id]').forEach(el => {
    el.addEventListener('click', event => {
      if(event.target.closest('a.pin-link'))return;
      event.preventDefault();
      event.stopPropagation();
      const id = el.getAttribute('data-seg-id');
      const state = loadState();
      const done = new Set(state.done || []);
      if(done.has(id))done.delete(id);else done.add(id);
      state.done = [...done].sort();
      saveState(state);
      applyState();
    });
  });
  applyState();
}
window.addEventListener('popstate', () => {
  showComponent(currentComponent(), window.location.hash ? window.location.hash.slice(1) : '', 'none');
});
function yamlQuote(value){
  return JSON.stringify(String(value));
}
function doneEntries(){
  const done = new Set(loadState().done || []);
  const byFingerprint = new Map();
  BUILDER_ENTRIES.forEach(entry => {
    if(done.has(entry.run_key))byFingerprint.set(entry.fingerprint, entry);
  });
  return [...byFingerprint.values()].sort((a, b) => a.id.localeCompare(b.id));
}
function exportYaml(){
  const rows = ['version: 1', 'wires:'];
  doneEntries().forEach(entry => {
    rows.push(`- id: ${yamlQuote(entry.id)}`);
    rows.push(`  fingerprint: ${yamlQuote(entry.fingerprint)}`);
    rows.push(`  system: ${yamlQuote(entry.system)}`);
    rows.push(`  kind: ${yamlQuote(entry.kind)}`);
  });
  rows.push('orphans: []');
  const blob = new Blob([rows.join('\n') + '\n'], {type: 'application/yaml'});
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = BUILDER_SIDECAR_NAME;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}
window.addEventListener('storage', event => { if(event.key === storageKey) applyState(); });
document.getElementById('loome-builder-export-yaml').addEventListener('click', exportYaml);
attachHandlers();
