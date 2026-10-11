(() => {
  const route = document.body.dataset.page;
  const text = (zh, ja) => window.AIInterviewFrame.lang === 'zh-CN' ? zh : ja;
  const node = (tag, value, className = '') => { const el = document.createElement(tag); el.textContent = value; el.className = className; return el; };
  function render() {
    const title = window.AIInterviewCopy[window.AIInterviewFrame.lang][{help:'navHelp', settings:'navSettings', plan:'planLink'}[route]];
    document.title = `AOMERA — ${title}`;
    document.querySelector('#functionTitle').textContent = title;
    document.querySelector('#pageIntro').textContent = text({help:'从创建邀请到查看报告，了解当前工作空间的使用方式。',settings:'查看账号信息与面试默认配置，设置修改暂未开放。',plan:'当前为试用套餐，具体套餐与服务详情请联系客服。'}[route], {help:'招待の作成からレポートの確認まで、ワークスペースの使い方をご案内します。',settings:'アカウント情報と面接の初期設定を確認できます。設定の変更は準備中です。',plan:'現在はトライアルプランをご利用中です。プラン・サービスの詳細はサポートへお問い合わせください。'}[route]);
    const root = document.querySelector('#staticPage'); root.replaceChildren();
    const section = (heading, description) => { const el = node('section', '', 'panel static-panel'); el.append(node('h2', heading)); if (description) el.append(node('p', description, 'static-muted')); root.append(el); return el; };
    const rows = (el, items) => { const dl = document.createElement('dl'); dl.className = 'static-rows'; items.forEach(([label,value]) => { const row = document.createElement('div'); row.append(node('dt', label), node('dd', value)); dl.append(row); }); el.append(dl); };
    if (route === 'help') {
      const guide = section(text('快速入门','クイックガイド'));
      const steps = document.createElement('ol'); steps.className = 'guide-steps';
      [text('创建面试：填写岗位、技能、评价目标与候选人信息。','面接を作成：職種、スキル、評価目標、候補者情報を入力します。'),text('预览邀请：生成链接预览，记录保存在当前浏览器。邀请链接尚未启用。','招待をプレビュー：リンクのプレビューと記録は現在のブラウザに保存されます。招待リンクはまだ利用できません。'),text('查看状态与报告：面试管理和评估报告页面目前包含示例内容。','状況とレポートを確認：面接管理・評価レポートには現在サンプルが含まれます。')].forEach(value => steps.append(node('li',value))); guide.append(steps);
      const faq = section(text('常见问题','よくある質問'));
      [[text('如何开始面试？','面接はどう始めますか？'),text('从首页点击“创建面试”填写信息。目前只能生成邀请预览，候选人在线面试暂未开放。','ホームの「面接を作成」から情報を入力してください。現在は招待プレビューのみ作成でき、候補者のオンライン面接は準備中です。')],[text('面试额度如何计算？','面接枠はどう計算されますか？'),text('24 / 50 为示例：已使用24次，总额度50次，剩余26次。实际扣除条件、重置日期及结转规则将在正式开放时公布。','24 / 50はサンプルです。使用済み24件、上限50件、残り26件を示します。消費条件、リセット日、繰り越し規則は正式公開時にご案内します。')],[text('面试中断或失败怎么办？','面接が中断・失敗した場合は？'),text('正式面试暂未开放。恢复方式、重试与额度返还规则待公布；当前示例不代表实际扣费。','正式な面接機能は準備中です。再開、再試行、面接枠の返還規則は今後ご案内します。サンプルは実際の課金を示しません。')],[text('为什么换浏览器后看不到邀请预览？','別のブラウザで招待プレビューが見えないのは？'),text('预览记录保存在创建时使用的浏览器中。清除浏览器数据后记录也会被删除。','プレビューは作成時のブラウザに保存されます。ブラウザのデータを削除すると記録も削除されます。')]].forEach(([q,a]) => { const detail = document.createElement('details'); detail.append(node('summary',q),node('p',a)); faq.append(detail); });
      section(text('问题反馈 · 暂未开放','お問い合わせ · 準備中'),text('反馈渠道开放后将在此公布。遇到问题时，可先记录操作步骤和错误信息。','お問い合わせ窓口は公開時にご案内します。問題が起きた際は操作手順とエラー内容を控えてください。'));
    } else if (route === 'settings') {
      const user = window.AIInterviewFrame.user;
      const account = section(text('账号信息','アカウント情報'),text('以下信息只读，资料编辑与账号安全设置暂未开放。','情報は閲覧専用です。プロフィール編集とセキュリティ設定は準備中です。'));
      rows(account,[[text('姓名','表示名'),user?.display_name || user?.user_name || text('等待账号信息','アカウント情報を待機中')],[text('账号','アカウント'),user?.user_name || '—']]);
      const prefs = section(text('面试偏好','面接の初期設定'),text('以下为创建面试时的默认值；每场面试请在创建页面确认。','面接作成時の初期値です。各面接の設定は作成画面で確認してください。'));
      rows(prefs,[[text('面试语言','面接言語'),text('日语','日本語')],[text('面试时长','所要時間'),text('15分钟','15分')],[text('邀请有效期','招待の有効期間'),text('7天','7日')],[text('面试方式','面接形式'),text('技术问答（规划中）','技術問答（予定）')]]);
      const notifications = section(text('通知与账号安全','通知・セキュリティ'));
      rows(notifications,[[text('邮件通知','メール通知'),text('暂未开放','準備中')],[text('报告提醒','レポート通知'),text('暂未开放','準備中')],[text('密码与安全管理','パスワード・セキュリティ管理'),text('暂未开放','準備中')]]);
    } else {
      const current = section(text('当前套餐','現在のプラン'));
      current.append(node('span',text('试用套餐','トライアルプラン'),'static-badge'));
      current.append(node('p',text('您当前使用的是试用套餐。具体套餐权益、面试额度及使用期限，请联系客服了解。','現在はトライアルプランをご利用中です。プランの特典、面接枠、利用期間についてはサポートへお問い合わせください。'),'static-muted'));
      const service = section(text('套餐咨询','プランのご相談'),text('如需增加面试额度、升级套餐或了解企业服务，请联系为您开通账号的客服人员。','面接枠の追加、プラン変更、法人向けサービスについては、アカウント開設を担当したサポート窓口へお問い合わせください。'));
      rows(service,[[text('套餐权益与价格','特典・料金'),text('联系客服','サポートへお問い合わせ')],[text('额度与使用期限','面接枠・利用期間'),text('以客服确认为准','サポートにてご確認ください')]]);
    }
  }
  window.addEventListener('aomera-language-change', render);
  window.addEventListener('aomera-user-ready', render);
  render();
})();
