(() => {
  const route = document.body.dataset.page;
  const keys = {interviews:'navInterviews', reports:'navReports', help:'navHelp', settings:'navSettings', plan:'planLink', account:'accountSettings'};
  function render(lang) {
    const ja = lang !== 'zh-CN';
    const title = window.AIInterviewCopy[ja ? 'ja' : 'zh-CN'][keys[route]];
    document.title = title;
    document.querySelector('#functionTitle').textContent = title;
    document.querySelector('#functionNotice').textContent = ja ? 'この機能は準備中です。現在はホームで面接状況を確認し、面接の招待プレビューを作成できます。' : '此功能正在准备中。目前可在首页查看面试状态，或创建面试邀请预览。';
    document.querySelector('#functionAction').textContent = route === 'interviews' ? (ja ? '面接を作成' : '创建面试') : (ja ? 'ホームに戻る' : '返回首页');
  }
  document.querySelector('#functionAction').addEventListener('click', () => window.AIInterviewFrame.navigate(route === 'interviews' ? 'create' : 'home'));
  window.addEventListener('aomera-language-change', event => render(event.detail));
  render(window.AIInterviewFrame.lang);
})();
