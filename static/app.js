'use strict';
function projectPoint([x, y, z], view = 'iso') {
  return view === 'front' ? [x, -z] : [0.866 * x + 0.5 * y, 0.28 * x - 0.48 * y - z];
}
if (typeof module !== 'undefined') module.exports = { projectPoint };

if (typeof document !== 'undefined') {
  const form = document.querySelector('#rack-form');
  const generate = document.querySelector('#generate');
  const error = document.querySelector('#form-error');
  const previewStatus = document.querySelector('#preview-status');
  const downloadStatus = document.querySelector('#download-status');
  const drawing = document.querySelector('#drawing');
  const svg = document.querySelector('#preview');
  const themeToggle = document.querySelector('#theme-toggle');
  const systemTheme = window.matchMedia('(prefers-color-scheme: light)');
  let savedTheme = null;
  try { savedTheme = localStorage.getItem('rackstream-theme'); } catch (_) { /* Storage can be denied in private contexts. */ }
  function applyTheme(light) {
    document.documentElement.classList.toggle('ds-theme--light', light);
    themeToggle.setAttribute('aria-pressed', String(light));
    themeToggle.textContent = light ? 'Dark theme' : 'Light theme';
    themeToggle.setAttribute('aria-label', light ? 'Switch to dark theme' : 'Switch to light theme');
  }
  applyTheme(savedTheme === 'light' || (savedTheme !== 'dark' && systemTheme.matches));
  themeToggle.addEventListener('click', () => {
    const light = !document.documentElement.classList.contains('ds-theme--light');
    savedTheme = light ? 'light' : 'dark';
    try { localStorage.setItem('rackstream-theme', savedTheme); } catch (_) { /* Theme still works without persistence. */ }
    applyTheme(light);
  });
  systemTheme.addEventListener('change', () => { if (!savedTheme) applyTheme(systemTheme.matches); });

  let view = 'iso';
  let layout = null;
  let revision = 0;
  let approvedRevision = -1;
  let timer;
  let controller;
  let generating = false;
  function readInputs() {
    const data = {};
    for (const name of ['width', 'depth', 'height', 'feet', 'radius', 'clearance', 'wall']) {
      data[name] = form.elements[name].valueAsNumber;
    }
    data.units = form.elements.units.value;
    data.height_includes_feet = form.elements.height_includes_feet.checked;
    return data;
  }
  function updateButton() {
    generate.disabled = generating || !form.checkValidity() || approvedRevision !== revision;
    generate.textContent = generating ? 'Generating STL…' : 'Generate STL ↓';
    generate.setAttribute('aria-busy', String(generating));
  }
  function showError(message) {
    error.textContent = message;
    error.hidden = !message;
  }
  async function responseError(response) {
    try { const body = await response.json(); return body.error || `Request failed (${response.status}).`; }
    catch (_) { return `Request failed (${response.status}). Please try again.`; }
  }
  const svgNamespace = 'http://www.w3.org/2000/svg';
  function element(tag, attributes, parent = svg) {
    const node = document.createElementNS(svgNamespace, tag);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
    parent.append(node);
    return node;
  }
  function render() {
    if (!layout) return;
    const l = layout;
    svg.replaceChildren();
    element('title', { id: 'svg-title' }).textContent = `${l.units}U rack mount, ${view === 'iso' ? 'isometric' : 'front'} view`;
    element('desc', { id: 'svg-description' }).textContent = 'Illustrative open-rear cradle and faceplate with translucent device. Not an exact STL rendering.';
    const projected = [];
    const point = p => { const result = projectPoint(p, view); projected.push(result); return result.join(','); };
    const polygon = (points, css) => element('polygon', { points: points.map(point).join(' '), class: css });
    function box(x0, x1, y0, y1, z0, z1, css) {
      polygon([[x0,y0,z1],[x0,y1,z1],[x1,y1,z1],[x1,y0,z1]], css);
      polygon([[x1,y0,z0],[x1,y1,z0],[x1,y1,z1],[x1,y0,z1]], css);
      polygon([[x0,y0,z0],[x1,y0,z0],[x1,y0,z1],[x0,y0,z1]], css);
    }
    const tw = l.tray_width / 2;
    // Draw rear geometry first; the faceplate is last so it masks the cradle correctly.
    box(-tw,tw,0,l.tray_depth,l.tray_bottom,l.tray_top,'mount-top');
    const railTop = l.body_bottom + Math.min(l.body_height / 2, 12);
    box(-tw,-tw+l.wall,l.wall,l.tray_depth,l.tray_top,railTop,'mount-face');
    box(-l.body_width/2,l.body_width/2,l.wall,l.wall+l.body_depth,l.body_bottom,l.body_bottom+l.body_height,'device');
    box(tw-l.wall,tw,l.wall,l.tray_depth,l.tray_top,railTop,'mount-face');
    // Front-face rounding is sampled before projection, so front and iso share geometry.
    function roundedLoop(x0, x1, z0, z1, radius) {
      const r = Math.max(0, Math.min(radius, (x1-x0)/2, (z1-z0)/2));
      const points = [];
      const centers = [[x1-r,z1-r,0],[x0+r,z1-r,90],[x0+r,z0+r,180],[x1-r,z0+r,270]];
      for (const [cx,cz,start] of centers) {
        for (let angle = start; angle <= start+90; angle += 15) {
          const a = angle * Math.PI/180;
          points.push([cx+r*Math.cos(a),0,cz+r*Math.sin(a)]);
        }
      }
      return points;
    }
    const loopPath = points => `M ${points.map(point).join(' L ')} Z`;
    const half = l.panel_width/2;
    const outline = [[-half,0,0],[half,0,0],[half,0,l.panel_height],[-half,0,l.panel_height]];
    // Face thickness is illustrative; all dimensions still come from server layout.
    polygon([[-half,0,l.panel_height],[half,0,l.panel_height],[half,l.wall,l.panel_height],[-half,l.wall,l.panel_height]],'mount-top');
    const opening = roundedLoop(-l.opening_width/2,l.opening_width/2,l.opening_bottom,l.opening_bottom+l.opening_height,l.opening_radius);
    let path = loopPath(outline) + ' ' + loopPath(opening);
    for (const x of [-l.hole_spacing/2,l.hole_spacing/2]) {
      for (const z of l.hole_z) path += ' ' + loopPath(roundedLoop(x-3,x+3,z-3,z+3,3));
    }
    element('path', { d: path, 'fill-rule': 'evenodd', class: 'mount-face' });
    const xs = projected.map(p => p[0]);
    const ys = projected.map(p => p[1]);
    const x0 = Math.min(...xs), y0 = Math.min(...ys);
    svg.setAttribute('viewBox', `${x0-15} ${y0-18} ${Math.max(...xs)-x0+30} ${Math.max(...ys)-y0+42}`);
    const mm = n => Number(n).toLocaleString(undefined, { maximumFractionDigits: 2 });
    document.querySelector('#mount-dimensions').textContent = l.print_dimensions.map(mm).join(' × ') + ' mm';
    document.querySelector('#rack-height').textContent = `${l.units}U / ${mm(l.panel_height)} mm`;
    document.querySelector('#tray-offset').textContent = `${mm(l.tray_top)} mm from panel bottom`;
    const warnings = document.querySelector('#warnings');
    warnings.replaceChildren();
    for (const message of l.warnings || []) {
      const li = document.createElement('li'); li.textContent = message; warnings.append(li);
    }
  }
  document.querySelectorAll('[data-view]').forEach(button => {
    button.addEventListener('click', () => {
      view = button.dataset.view;
      document.querySelectorAll('[data-view]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
      render();
    });
  });
  async function requestPreview(requestRevision) {
    const currentController = new AbortController();
    controller = currentController;
    try {
      const response = await fetch('/api/preview', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(readInputs()), signal: currentController.signal,
      });
      if (!response.ok) throw new Error(await responseError(response));
      const result = await response.json();
      if (requestRevision !== revision) return;
      layout = result;
      render();
      approvedRevision = requestRevision;
      showError('');
      previewStatus.textContent = 'Layout checked · server-calculated dimensions';
      if (!generating) downloadStatus.textContent = 'One STL. Ready for your slicer.';
    } catch (failure) {
      if (requestRevision !== revision || failure.name === 'AbortError') return;
      showError(failure.message || 'Could not calculate preview. Please try again.');
      previewStatus.textContent = 'Preview unavailable · layout not approved';
      if (!generating) downloadStatus.textContent = 'Adjust a dimension to retry.';
    } finally {
      if (requestRevision === revision) { drawing.setAttribute('aria-busy', 'false'); updateButton(); }
    }
  }
  function schedulePreview() {
    revision += 1;
    clearTimeout(timer);
    if (controller) controller.abort();
    updateButton();
    showError('');
    const valid = form.checkValidity();
    for (const input of form.querySelectorAll('input[type=number]')) input.setAttribute('aria-invalid', String(!input.validity.valid));
    drawing.setAttribute('aria-busy', String(valid));
    previewStatus.textContent = layout ? 'Previous layout · awaiting current dimensions' : 'Calculating layout…';
    if (!valid) {
      showError('Enter valid measurements: width, depth, height and wall must be positive; feet, radius and clearance cannot be negative.');
      previewStatus.textContent = 'Invalid dimensions · preview not current';
      if (!generating) downloadStatus.textContent = 'Correct the highlighted measurements.';
      return;
    }
    if (!generating) downloadStatus.textContent = 'Checking your dimensions…';
    const requestRevision = revision;
    timer = setTimeout(() => requestPreview(requestRevision), 280);
  }
  form.addEventListener('input', schedulePreview);
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (generating || !form.checkValidity() || approvedRevision !== revision) return;
    // The request owns an immutable snapshot even if the form changes while it runs.
    const snapshot = JSON.stringify(readInputs());
    generating = true;
    showError('');
    downloadStatus.textContent = 'Building your STL. This may take a moment…';
    updateButton();
    try {
      const response = await fetch('/api/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: snapshot });
      if (!response.ok) throw new Error(await responseError(response));
      const blob = await response.blob();
      if (!blob.size) throw new Error('The server returned an empty STL. Please try again.');
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'rackstream-mount.stl';
      document.body.append(link); link.click(); link.remove();
      // Do not revoke synchronously: browsers may not have started consuming the URL yet.
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      downloadStatus.textContent = 'STL download started · generated from your submitted dimensions.';
    } catch (failure) {
      showError(failure.message || 'STL generation failed. Please try again.');
      downloadStatus.textContent = 'No file downloaded. You can retry.';
    } finally { generating = false; updateButton(); }
  });
  schedulePreview();
}
