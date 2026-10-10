(function (root) {
  'use strict';
  function filterRepos(repos, state = {}) {
    const query = (state.query || '').trim().toLocaleLowerCase();
    const result = repos.filter(repo => {
      const text = [repo.full_name, repo.description_original, repo.category,
        repo.language, ...(repo.topics || [])].filter(Boolean).join(' ').toLocaleLowerCase();
      return (!query || text.includes(query)) &&
        (!state.category || state.category === 'all' || repo.category === state.category) &&
        (!state.language || state.language === 'all' || (repo.language || '未标注') === state.language);
    });
    result.sort((a, b) => {
      if (state.sort === 'stars' || state.sort === 'today') {
        const key = state.sort === 'stars' ? 'stars_total' : 'stars_today';
        if (a[key] == null && b[key] != null) return 1;
        if (b[key] == null && a[key] != null) return -1;
        const difference = (b[key] ?? 0) - (a[key] ?? 0);
        if (difference) return difference;
      } else if (state.aiFirst) {
        const priority = Number(b.category === 'AI / Agent') - Number(a.category === 'AI / Agent');
        if (priority) return priority;
      }
      return a.trending_rank - b.trending_rank;
    });
    return result;
  }
  if (typeof module === 'object' && module.exports) module.exports = {filterRepos};
  else root.RadarFilters = {filterRepos};
})(typeof globalThis === 'object' ? globalThis : this);
