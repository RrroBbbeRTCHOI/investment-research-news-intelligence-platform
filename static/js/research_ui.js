const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
document.querySelectorAll('[data-statement-target]').forEach(button => button.addEventListener('click', () => {
  const target = button.dataset.statementTarget;
  document.querySelectorAll('[data-statement-target]').forEach(item => item.setAttribute('aria-selected', String(item === button)));
  document.querySelectorAll('[data-statement-panel]').forEach(panel => { panel.hidden = panel.dataset.statementPanel !== target; });
}));
document.querySelectorAll('.meridian-financial-table [data-period]').forEach(cell => {
  const toggle = active => document.querySelectorAll(`[data-period="${cell.dataset.period}"]`).forEach(peer => peer.classList.toggle('is-period-linked', active));
  cell.addEventListener('mouseenter', () => toggle(true)); cell.addEventListener('mouseleave', () => toggle(false));
  cell.addEventListener('focusin', () => toggle(true)); cell.addEventListener('focusout', () => toggle(false));
});
if (!reducedMotion && 'IntersectionObserver' in window) {
  const observer = new IntersectionObserver(entries => entries.forEach(entry => { if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); } }), { threshold: 0.08 });
  document.querySelectorAll('[data-reveal]').forEach(element => observer.observe(element));
} else document.querySelectorAll('[data-reveal]').forEach(element => element.classList.add('is-visible'));

const trendCanvas = document.getElementById('fundamentalTrendChart');
if (trendCanvas && window.meridianHistoricalData && window.Chart) {
  const source = window.meridianHistoricalData;
  const years = [...new Set(['revenue_growth','eps_growth','operating_margin','fcf_margin'].flatMap(key => (source[key] || []).map(row => row.year)))].sort();
  const values = (key, field) => { const byYear = new Map((source[key] || []).map(row => [row.year, row[field]])); return years.map(year => byYear.get(year) == null ? null : byYear.get(year) * 100); };
  new Chart(trendCanvas, { type:'line', data:{ labels:years, datasets:[
    {label:'Revenue growth',data:values('revenue_growth','revenue_growth'),borderColor:'#3b82f6'},
    {label:'EPS growth',data:values('eps_growth','eps_growth'),borderColor:'#8b5cf6'},
    {label:'Operating margin',data:values('operating_margin','operating_margin'),borderColor:'#10b981'},
    {label:'FCF margin',data:values('fcf_margin','fcf_margin'),borderColor:'#f59e0b'}
  ].map(dataset => ({...dataset,borderWidth:2,pointRadius:2.5,pointHoverRadius:5,tension:.28,spanGaps:true})) }, options:{ responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{display:false},tooltip:{callbacks:{label:context=>`${context.dataset.label}: ${context.parsed.y.toFixed(1)}%`}}},scales:{x:{grid:{display:false}},y:{ticks:{callback:value=>`${value}%`},grid:{color:'rgba(128,140,160,.14)'}}},animation:reducedMotion?false:{duration:420}} });
}
