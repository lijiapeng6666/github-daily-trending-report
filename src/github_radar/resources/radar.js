(function () {
  'use strict';
  const data = JSON.parse(document.getElementById('report-data').textContent);
  const rows = new Map(Array.from(document.querySelectorAll('[data-repo]')).map(row => [row.dataset.repo, row]));
  const controls = Object.fromEntries(['search', 'category', 'language', 'sort', 'mode-ai',
    'mode-ranking', 'repos', 'empty', 'result-count', 'date'].map(id => [id, document.getElementById(id)]));
  let aiFirst = data.aiFirst;
  function render() {
    const matches = RadarFilters.filterRepos(data.repos, {
      query: controls.search.value, category: controls.category.value,
      language: controls.language.value, sort: controls.sort.value, aiFirst,
    });
    const visible = new Set(matches.map(repo => repo.full_name));
    for (const [name, row] of rows) row.hidden = !visible.has(name);
    for (const repo of matches) controls.repos.append(rows.get(repo.full_name));
    controls.empty.hidden = matches.length > 0;
    controls['result-count'].textContent = `${matches.length} / ${data.repos.length} 个项目`;
    controls['mode-ai'].setAttribute('aria-pressed', String(aiFirst));
    controls['mode-ranking'].setAttribute('aria-pressed', String(!aiFirst));
  }
  for (const key of ['search', 'category', 'language', 'sort']) {
    controls[key].addEventListener(key === 'search' ? 'input' : 'change', render);
  }
  for (const [key, priority] of [['mode-ai', true], ['mode-ranking', false]]) {
    controls[key].addEventListener('click', () => { aiFirst = priority; controls.sort.value = 'rank'; render(); });
  }
  document.getElementById('reset').addEventListener('click', () => {
    controls.search.value = '';
    controls.category.value = 'all';
    controls.language.value = 'all';
    controls.sort.value = 'rank';
    render();
    controls.search.focus();
  });
  controls.date.addEventListener('change', () => { window.location.href = controls.date.value; });
  for (const image of document.querySelectorAll('.avatar')) {
    image.addEventListener('error', () => { image.hidden = true; }, {once: true});
    if (image.complete && !image.naturalWidth) image.hidden = true;
  }
  document.getElementById('controls').hidden = false;
  controls.date.hidden = false;
  render();
})();
