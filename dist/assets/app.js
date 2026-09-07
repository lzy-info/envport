'use strict';
(() => {
  const reports = window.ENVPORT_DEMO_REPORTS || {};
  const content = document.getElementById('report-content');
  const download = document.getElementById('download-report');
  let selected = 'good';
  const checksOf = report => report.checks || report.results || [];
  function renderReport(kind) {
    selected = kind;
    document.getElementById('demo-name').textContent = kind;
    content.replaceChildren();
    const report = reports[kind];
    if (!report) {
      const p = document.createElement('p');
      p.textContent = '示例报告尚未生成。请在项目根目录运行 python scripts/build_release.py。';
      content.append(p); download.disabled = true; return;
    }
    const checks = checksOf(report);
    for (const check of checks) {
      const row = document.createElement('div'); row.className = 'report-row';
      const status = String(check.status || 'skip').toLowerCase();
      const badge = document.createElement('span');
      badge.className = 'report-result ' + (['pass','fail','skip'].includes(status) ? status : 'skip');
      badge.textContent = status.toUpperCase();
      const label = document.createElement('span'); label.className = 'report-label';
      label.textContent = check.name || check.id || 'check';
      if (check.detail) label.title = check.detail;
      row.append(badge,label); content.append(row);
    }
    const summary = document.createElement('p'); summary.className = 'report-summary';
    const counts = {pass:0, fail:0, skip:0};
    checks.forEach(check => { if (check.status in counts) counts[check.status]++; });
    summary.textContent = counts.pass + ' passed / ' + counts.fail + ' failed / ' + counts.skip + ' skipped';
    content.append(summary); download.disabled = false;
  }
  if (content) {
    document.querySelectorAll('input[name="demo"]').forEach(input => input.addEventListener('change', () => renderReport(input.value)));
    download.addEventListener('click', () => {
      const url = URL.createObjectURL(new Blob([JSON.stringify(reports[selected],null,2) + '\n'],{type:'application/json'}));
      const link = document.createElement('a'); link.href = url; link.download = 'envport-demo-' + selected + '.json';
      document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url),1000);
    });
    renderReport('good');
  }
  document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
    const code = document.getElementById(button.dataset.copy);
    const status = document.getElementById('copy-status');
    try {
      if (!navigator.clipboard) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(code.textContent);
      status.textContent = '已复制。请在解压后的项目根目录运行。';
    } catch (_) {
      const range = document.createRange(); range.selectNodeContents(code);
      const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
      status.textContent = '已选中命令，请按 Ctrl+C / ⌘C 复制。';
    }
  }));
})();
