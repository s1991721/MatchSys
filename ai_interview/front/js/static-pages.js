(() => {
  const route = document.body.dataset.page;
  const text = (zh, ja) => window.AIInterviewFrame.lang === 'zh-CN' ? zh : ja;
  const node = (tag, value, className = '') => { const el = document.createElement(tag); el.textContent = value; el.className = className; return el; };
  let quota = null, quotaError = null;
  async function loadQuota() {
    if (route !== 'plan' || !window.AIInterviewFrame.user) return;
    try { quota = (await window.AIInterview.requestSummary('/quota')).data; quotaError = null; }
    catch (error) { quota = null; quotaError = error; }
    render();
  }
  function render() {
    const title = window.AIInterviewCopy[window.AIInterviewFrame.lang][{help:'navHelp', settings:'navSettings', plan:'planLink'}[route]];
    document.title = `AOMERA — ${title}`;
    document.querySelector('#functionTitle').textContent = title;
    document.querySelector('#pageIntro').textContent = text({help:'从创建邀请到查看报告，了解当前工作空间的使用方式。',settings:'查看账号信息与面试默认配置，设置修改暂未开放。',plan:'查看剩余面试额度，具体套餐与服务详情请联系客服。'}[route], {help:'招待の作成からレポートの確認まで、ワークスペースの使い方をご案内します。',settings:'アカウント情報と面接の初期設定を確認できます。設定の変更は準備中です。',plan:'残りの面接枠を確認できます。プラン・サービスの詳細はサポートへお問い合わせください。'}[route]);
    const root = document.querySelector('#staticPage'); root.replaceChildren();
    const section = (heading, description) => { const el = node('section', '', 'panel static-panel'); el.append(node('h2', heading)); if (description) el.append(node('p', description, 'static-muted')); root.append(el); return el; };
    const rows = (el, items) => { const dl = document.createElement('dl'); dl.className = 'static-rows'; items.forEach(([label,value]) => { const row = document.createElement('div'); row.append(node('dt', label), node('dd', value)); dl.append(row); }); el.append(dl); };
    if (route === 'help') {
      const guide = section(text('快速入门','クイックガイド'));
      const steps = document.createElement('ol'); steps.className = 'guide-steps';
      [text('创建面试：填写岗位、技能、评价目标与候选人信息。','面接を作成：職種、スキル、評価目標、候補者情報を入力します。'),text('创建邀请：记录保存至服务器，每次成功创建扣减一次面试额度。','招待を作成：記録をサーバーに保存し、作成成功時に面接枠を1件消費します。'),text('查看状态与报告：面试管理与评估报告页面显示当前企业的数据。','状況とレポートを確認：面接管理・評価レポートに現在の企業のデータを表示します。')].forEach(value => steps.append(node('li',value))); guide.append(steps);
      const faq = section(text('常见问题','よくある質問'));
      [[text('如何开始面试？','面接はどう始めますか？'),text('从首页点击“创建面试”填写信息。可以创建并保存邀请，候选人在线面试流程尚未开放。','ホームの「面接を作成」から情報を入力してください。招待を作成・保存できます。候補者のオンライン面接は準備中です。')],[text('面试额度如何计算？','面接枠はどう計算されますか？'),text('成功创建一条邀请扣减一次额度；额度不足时不会创建邀请。侧栏和套餐页显示剩余次数。','招待の作成成功時に面接枠を1件消費します。枠が不足する場合は作成されません。残り件数はサイドバーとプラン画面で確認できます。')],[text('面试中断或失败怎么办？','面接が中断・失敗した場合は？'),text('在线面试流程尚未开放。已创建邀请消耗的额度不会因邀请过期或删除自动返还。','オンライン面接は準備中です。招待作成時に消費した枠は、期限切れや削除によって自動返還されません。')],[text('换浏览器后如何获取邀请链接？','別のブラウザで招待リンクを取得するには？'),text('面试记录保存在服务器。原始链接仅在当前标签页临时保留；重新生成链接后旧链接失效，请向候选人发送新链接。','面接の記録はサーバーに保存されます。元のリンクは現在のタブに一時保存されます。再発行すると以前のリンクは無効になるため、新しいリンクを候補者へ送付してください。')]].forEach(([q,a]) => { const detail = document.createElement('details'); detail.append(node('summary',q),node('p',a)); faq.append(detail); });
      section(text('问题反馈 · 暂未开放','お問い合わせ · 準備中'),text('反馈渠道开放后将在此公布。遇到问题时，可先记录操作步骤和错误信息。','お問い合わせ窓口は公開時にご案内します。問題が起きた際は操作手順とエラー内容を控えてください。'));
    } else if (route === 'settings') {
      const user = window.AIInterviewFrame.user;
      const account = section(text('账号信息','アカウント情報'),text('以下信息只读，显示名与密码可在账户设置中修改。','情報は閲覧専用です。表示名・パスワードはアカウント設定で変更できます。'));
      rows(account,[[text('姓名','表示名'),user?.display_name || user?.user_name || text('等待账号信息','アカウント情報を待機中')],[text('账号','アカウント'),user?.user_name || '—']]);
      const prefs = section(text('面试偏好','面接の初期設定'),text('以下为创建面试时的默认值；每场面试请在创建页面确认。','面接作成時の初期値です。各面接の設定は作成画面で確認してください。'));
      rows(prefs,[[text('面试语言','面接言語'),text('日语','日本語')],[text('面试时长','所要時間'),text('15分钟','15分')],[text('邀请有效期','招待の有効期間'),text('7天','7日')],[text('面试方式','面接形式'),text('技术问答（规划中）','技術問答（予定）')]]);
      const notifications = section(text('通知与账号安全','通知・セキュリティ'));
      rows(notifications,[[text('邮件通知','メール通知'),text('暂未开放','準備中')],[text('报告提醒','レポート通知'),text('侧栏显示未读报告数','サイドバーに未読件数を表示')],[text('密码与安全管理','パスワード・セキュリティ管理'),text('可在账户设置中修改密码','アカウント設定で変更可能')]]);
    } else {
      const current = section(text('当前套餐','現在のプラン'));
      rows(current, [[text('剩余面试次数','残りの面接枠'), quota ? String(quota.remaining_count) : '—']]);
      if (quotaError) { current.append(node('p', window.AIInterview.errorMessage(quotaError, window.AIInterviewFrame.lang), 'form-error')); const retry = node('button', text('重试','再試行'), 'outline-action'); retry.type = 'button'; retry.addEventListener('click', loadQuota); current.append(retry); }
      else if (quota && !quota.configured) current.append(node('p', text('尚未配置额度，请联系管理员。','面接枠が未設定です。管理者へお問い合わせください。')));
      current.append(node('p',text('具体套餐权益及使用期限，请联系客服了解。','プランの特典・利用期間についてはサポートへお問い合わせください。'),'static-muted'));
      const service = section(text('套餐咨询','プランのご相談'),text('如需增加面试额度、升级套餐或了解企业服务，请联系为您开通账号的客服人员。','面接枠の追加、プラン変更、法人向けサービスについては、アカウント開設を担当したサポート窓口へお問い合わせください。'));
      rows(service,[[text('套餐权益与价格','特典・料金'),text('联系客服','サポートへお問い合わせ')],[text('额度与使用期限','面接枠・利用期間'),text('以客服确认为准','サポートにてご確認ください')]]);
    }
  }
  window.addEventListener('aomera-language-change', render);
  window.addEventListener('aomera-user-ready', () => {render(); loadQuota();});
  document.addEventListener('visibilitychange', () => {if (!document.hidden) loadQuota();});
  window.addEventListener('storage', event => {if (event.key === 'aomera-data-updated') loadQuota();});
  render();
})();
