(() => {
  const translations = {
    ja: {
      create: '面接を作成', back: '← ホームに戻る', intro: '職種要件と評価目標を入力して、専用の面接リンクを作成します。', positionInfo: '職種情報', positionName: '職種名 *', work: '業務内容 *', experience: '経験要件', positionPlaceholder: '例：バックエンドエンジニア', workPlaceholder: '担当業務や期待する役割を入力', experiencePlaceholder: '例：バックエンド開発経験3年以上', skills: '職種に必要なスキル', addSkill: '＋ スキルを追加', skillName: 'スキル名', level: '習熟度', basic: '基礎', proficient: '実務レベル', advanced: '熟練', targets: '評価目標', targetsHelp: 'AIの質問内容と評価レポートの採点項目を設定します。', addTarget: '＋ 評価目標を追加', targetName: '評価項目', targetDetail: '評価の重点', weight: '配点（%）', total: '配点合計', oralMode: '初期版は技術問答を想定しています。オンラインコーディングは今後対応予定です。', settings: '面接設定', interviewLanguage: '面接言語', japanese: '日本語', chinese: '中国語', english: '英語', duration: '所要時間（分）', validity: 'リンク有効期間（日） *', candidateName: '候補者氏名 *', candidateEmail: '候補者メール *', cancel: 'キャンセル', generate: '作成してリンクを生成 →', summary: '面接プレビュー', expires: '有効期限', anytime: '候補者の面接機能は準備中です', anytimeHelp: 'リンクごとに1名の候補者を招待します。作成すると面接枠を1件消費します。', success: '面接を作成しました', successHelp: '面接を保存しました。候補者のオンライン面接は準備中です。', copy: 'リンクをコピー', linkLabel: '招待リンク', waiting: '参加待ち', another: '別の面接を作成', untitled: '職種名を入力', unspecified: '未設定', minutes: '分', remove: '削除', required: '必須項目を入力してください。', invalid: '入力内容を確認してください。', weightError: '評価目標の配点合計を100%にしてください。', rowError: 'スキルと評価目標をそれぞれ1件以上入力してください。', emailError: '有効なメールアドレスを入力してください。', validityError: '有効期間は1〜30日の整数で入力してください。', copied: 'リンクをコピーしました。', copyError: 'コピーできませんでした。リンクを選択してコピーしてください。', saveError: 'ブラウザへの保存に失敗しました。空き容量やブラウザの設定を確認してください。', userError: 'ユーザー情報の読み込みを待ってから、もう一度お試しください。', languageTarget: '日本語能力', codingTarget: 'コーディング能力', databaseTarget: 'データベース最適化', languageDetail: '業務上の会話、技術説明、聴解', codingDetail: '実装、境界条件、問題分析', databaseDetail: 'スロークエリ、インデックス、実行計画', custom: 'カスタム', limit: '追加できる項目は最大20件です。'
    },
    'zh-CN': {
      create: '创建面试', back: '← 返回首页', intro: '填写岗位要求与评价目标，生成专属面试链接。', positionInfo: '岗位信息', positionName: '岗位名称 *', work: '工作内容 *', experience: '经验要求', positionPlaceholder: '例如：后端工程师', workPlaceholder: '填写主要工作内容和职责', experiencePlaceholder: '例如：3 年以上后端开发经验', skills: '岗位所需技能', addSkill: '＋ 添加技能', skillName: '技能名称', level: '要求程度', basic: '基础', proficient: '掌握', advanced: '熟练', targets: '评价目标', targetsHelp: '决定 AI 的提问重点及报告评分维度。', addTarget: '＋ 添加评价目标', targetName: '评价项目', targetDetail: '考察重点', weight: '权重（%）', total: '权重合计', oralMode: '第一版采用技术问答，在线编程将在后续支持。', settings: '面试设置', interviewLanguage: '面试语言', japanese: '日语', chinese: '中文', english: '英语', duration: '面试时长（分钟）', validity: '链接有效期（天） *', candidateName: '候选人姓名 *', candidateEmail: '候选人邮箱 *', cancel: '取消', generate: '创建并生成链接 →', summary: '面试预览', expires: '有效至', anytime: '候选人面试功能尚未开放', anytimeHelp: '每条链接对应一位候选人，成功创建后扣减一次面试额度。', success: '面试已创建', successHelp: '面试记录已保存至服务器。候选人在线面试功能尚未开放。', copy: '复制链接', linkLabel: '邀请链接', waiting: '待参加', another: '再创建一场', untitled: '请填写岗位名称', unspecified: '未设置', minutes: '分钟', remove: '删除', required: '请填写必填项。', invalid: '请检查输入内容。', weightError: '评价目标的权重合计必须为 100%。', rowError: '请至少填写一项岗位技能和一项评价目标。', emailError: '请输入有效的邮箱地址。', validityError: '有效期需为 1–30 天的整数。', copied: '链接已复制。', copyError: '复制失败，请选中链接手动复制。', saveError: '浏览器保存失败，请检查可用空间或浏览器设置。', userError: '请等待用户信息加载完成后重试。', languageTarget: '日语能力', codingTarget: '编码能力', databaseTarget: '数据库调优', languageDetail: '工作沟通、技术说明、听力理解', codingDetail: '代码实现、边界处理、问题分析', databaseDetail: '慢查询、索引设计、执行计划', custom: '自定义', limit: '最多可添加 20 项。'
    }
  };
  const $ = (selector) => document.querySelector(selector);
  const form = $('#interviewForm');
  let lang = translations[localStorage.getItem('aomera-language')] ? localStorage.getItem('aomera-language') : 'ja';
  let owner = null;
  let requestId = null;
  let submitting = false;
  let result = null;
  let dirty = false;
  let toastTimer;
  let lastError = null;
  const t = (key) => translations[lang][key] || key;
  const fields = () => form.elements;
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function localized(node, key) { node.dataset.ui = key; node.textContent = t(key); return node; }
  function inputLabel(key, input) {
    const label = element('label');
    label.append(localized(element('span'), key), input);
    return label;
  }
  function input(className, maxLength, value = '') {
    const node = element('input', className);
    node.type = 'text'; node.required = true; node.maxLength = maxLength; node.value = value;
    return node;
  }
  function removeButton(row) {
    const button = localized(element('button', 'remove-row'), 'remove');
    button.type = 'button';
    button.addEventListener('click', () => { row.remove(); dirty = true; updateSummary(); saveDraft(); });
    return button;
  }
  function addSkill() {
    if ($('#skillRows').children.length >= 20) return toast('limit');
    const row = element('div', 'skill-row');
    const name = input('skill-name', 100);
    const level = element('select', 'skill-level');
    ['basic', 'proficient', 'advanced'].forEach((key) => {
      const option = localized(element('option'), key); option.value = key; level.append(option);
    });
    level.value = 'proficient';
    row.append(inputLabel('skillName', name), inputLabel('level', level), removeButton(row));
    $('#skillRows').append(row); updateSummary(); return name;
  }
  function addTarget(preset = 'custom', weight = '') {
    if ($('#targetRows').children.length >= 20) return toast('limit');
    const row = element('div', 'target-row');
    const name = input('target-name', 100);
    name.dataset.placeholderUi = preset === 'custom' ? 'targetName' : preset;
    name.placeholder = t(name.dataset.placeholderUi);
    const nameLabel = inputLabel('targetName', name);
    const detail = input('target-detail', 1000);
    const presetDetail = {languageTarget: 'languageDetail', codingTarget: 'codingDetail', databaseTarget: 'databaseDetail'};
    const points = element('input', 'target-weight');
    Object.assign(points, { type: 'number', min: '1', max: '100', step: '1', required: true, value: String(weight) });
    detail.dataset.placeholderUi = presetDetail[preset] || 'targetDetail';
    detail.placeholder = t(detail.dataset.placeholderUi);
    row.append(nameLabel, inputLabel('targetDetail', detail), inputLabel('weight', points), removeButton(row));
    $('#targetRows').append(row); updateSummary(); return name;
  }
  function skills() {
    return Array.from($('#skillRows').children, (row) => ({ name: row.querySelector('.skill-name').value.trim(), level: row.querySelector('.skill-level').value }));
  }
  function targets() {
    return Array.from($('#targetRows').children, (row) => ({ name: row.querySelector('.target-name').value.trim(), detail: row.querySelector('.target-detail').value.trim(), weight: Number(row.querySelector('.target-weight').value) }));
  }
  function expiration(days, now = Date.now()) { return new Date(now + days * 86400000).toISOString(); }
  function date(value) {
    return new Intl.DateTimeFormat(lang, { timeZone: 'Asia/Tokyo', year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value));
  }
  function settings(record) { return `${t({ja:'japanese', 'zh-CN':'chinese', en:'english'}[record.language])} · ${record.duration} ${t('minutes')}`; }
  function updateSummary() {
    const skillList = skills(); const targetList = targets();
    const total = targetList.reduce((sum, item) => sum + item.weight, 0);
    $('#weightTotal').textContent = `${t('total')} ${total}%`;
    $('#weightTotal').classList.toggle('invalid-weight', total !== 100);
    $('#summaryPosition').textContent = fields().position.value.trim() || t('untitled');
    $('#summarySkills').textContent = skillList.filter((item) => item.name).map((item) => `${item.name} · ${t(item.level)}`).join(' / ') || t('unspecified');
    $('#summaryTargets').textContent = targetList.map((item) => `${item.name || t('custom')} ${item.weight}%`).join(' / ') || t('unspecified');
    $('#summarySettings').textContent = settings({ language: fields().interviewLanguage.value, duration: 15 });
    const days = Number(fields().validity.value);
    $('#summaryExpires').textContent = Number.isInteger(days) && days >= 1 && days <= 30 ? date(expiration(days)) : t('unspecified');
  }
  function applyLanguage(next) {
    lang = translations[next] ? next : 'ja';
    document.querySelectorAll('[data-ui]').forEach((node) => { node.textContent = t(node.dataset.ui); });
    document.querySelectorAll('[data-placeholder-ui]').forEach((node) => { node.placeholder = t(node.dataset.placeholderUi); });
    document.querySelectorAll('[data-aria-ui]').forEach((node) => { node.setAttribute('aria-label', t(node.dataset.ariaUi)); });
    if (!$('#formError').hidden) $('#formError').textContent = $('#formError').dataset.errorKey ? t($('#formError').dataset.errorKey) : window.AIInterview.errorMessage(lastError, lang);
    if (submitting) form.querySelector('[type=submit]').textContent = lang === 'ja' ? '作成中…' : '正在创建…';
    updateSummary(); if (result) renderResult();
  }
  function view(name) {
    ['create', 'success'].forEach((key) => { $(`#${key}View`).hidden = key !== name; });
    window.scrollTo({top: 0, behavior: 'instant'});
    $(`#${name}Title`).focus();
  }
  function clearForm() {
    requestId = null;
    form.reset(); $('#skillRows').replaceChildren(); $('#targetRows').replaceChildren();
    addSkill(); addTarget('languageTarget', 30); addTarget('codingTarget', 40); addTarget('databaseTarget', 30);
    $('#formError').hidden = true; dirty = false; updateSummary();
  }
  function startCreate() {
    if (owner) {try { sessionStorage.removeItem(draftKey()); } catch { toast('saveError'); }}
    result = null; clearForm(); view('create');
  }
  function backHome(event) {
    event?.preventDefault();
    saveDraft(); window.AIInterviewFrame.navigate('home');
  }
  function toast(key) {
    clearTimeout(toastTimer); $('#toast').textContent = t(key); $('#toast').classList.add('show');
    toastTimer = setTimeout(() => $('#toast').classList.remove('show'), 3000);
  }
  function error(key, control) {
    $('#formError').dataset.errorKey = key; $('#formError').textContent = t(key); $('#formError').hidden = false;
    if (control) { control.setAttribute('aria-invalid', 'true'); control.focus(); }
    else $('#formError').scrollIntoView({block:'center'});
  }
  function validate() {
    form.querySelectorAll('[aria-invalid]').forEach((control) => control.removeAttribute('aria-invalid'));
    for (const control of form.querySelectorAll('input, textarea, select')) {
      if (control.required && !String(control.value).trim()) { error('required', control); return false; }
      if (!control.checkValidity()) {
        error(control.name === 'candidateEmail' ? 'emailError' : control.name === 'validity' ? 'validityError' : 'invalid', control); return false;
      }
    }
    if (!skills().length || !targets().length) { error('rowError'); return false; }
    if (targets().reduce((sum, item) => sum + item.weight, 0) !== 100) { error('weightError', $('.target-weight')); return false; }
    return true;
  }
  async function copyLink(link, fallback) {
    try {
      if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(link); toast('copied');
    } catch {
      fallback.focus(); fallback.select();
      toast('copyError');
    }
  }
  function renderResult() {
    $('#invitationLink').value = result.link;
    $('#invitationCode').textContent = `${lang === 'zh-CN' ? '面试码' : '面接コード'}: ${result.code || ''}`;
    $('#successPosition').textContent = result.position;
    $('#successSettings').textContent = `${settings(result)} · ${t('expires')} ${date(result.expiresAt)}`;
  }
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submitting) return;
    $('#formError').hidden = true;
    if (!validate()) return;
    if (!owner) { error('userError'); return; }
    // 请求标识随草稿保留，网络失败后重试也不会重复扣减额度。
    requestId ||= Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('');
    dirty = true; saveDraft();
    const payload = {
      request_id: requestId, position_name: fields().position.value.trim(),
      work_description: fields().work.value.trim(), position_requirements: fields().experience.value.trim(),
      skills: skills(), assessment_targets: targets().map((target, index) => ({...target, id:`target-${index + 1}`})),
      duration_minutes: 15, candidate_name: fields().candidateName.value.trim(),
      candidate_email: fields().candidateEmail.value.trim(), validity_days: Number(fields().validity.value)
    };
    submitting = true;
    // 锁定表单，避免请求期间的编辑与提交快照不一致。
    const disabled = Array.from(form.elements, control => [control, control.disabled]);
    disabled.forEach(([control]) => { control.disabled = true; });
    form.setAttribute('aria-busy', 'true'); applyLanguage(lang);
    try {
      const response = await window.AIInterview.requestJson('/interviews', {method:'POST', body:JSON.stringify(payload)});
      const interview = response.data.interview;
      result = {position:interview.position_name, language:'ja', duration:interview.duration_minutes, expiresAt:interview.invite_expires_at, link:response.data.invitation_url, code:response.data.invitation_code};
      window.AIInterview.cacheInvitation(owner, interview.id, result.link);
      dirty = false; requestId = null;
      try { sessionStorage.removeItem(draftKey()); } catch {}
      window.AIInterviewFrame.recordsUpdated(); renderResult(); view('success');
    } catch (cause) {
      lastError = cause; delete $('#formError').dataset.errorKey;
      $('#formError').textContent = window.AIInterview.errorMessage(cause, lang);
      $('#formError').hidden = false;
    } finally {
      submitting = false; disabled.forEach(([control, state]) => { control.disabled = state; });
      form.removeAttribute('aria-busy'); applyLanguage(lang);
    }
  });
  form.addEventListener('input', updateForm);
  form.addEventListener('change', updateForm);
  $('#addSkill').addEventListener('click', () => { const control = addSkill(); dirty = true; control?.focus(); saveDraft(); });
  $('#addTarget').addEventListener('click', () => { const control = addTarget(); dirty = true; control?.focus(); saveDraft(); });
  $('#createAnother').addEventListener('click', startCreate);
  ['backHome', 'cancelCreate', 'successHome'].forEach((id) => $(`#${id}`).addEventListener('click', backHome));
  $('#copyInvitation').addEventListener('click', () => copyLink(result.link, $('#invitationLink')));
  window.addEventListener('aomera-language-change', (event) => applyLanguage(event.detail));
  window.addEventListener('aomera-user-ready', (event) => {
    owner = event.detail.id;
    restoreDraft();
  });

  function draftKey() { return `aomera-interview-draft:${owner}`; }
  function saveDraft() {
    if (!owner || !dirty) return;
    const values = Object.fromEntries(Array.from(form.elements).filter(control => control.name).map(control => [control.name, control.value]));
    const skillRows = Array.from($('#skillRows').children, row => ({name:row.querySelector('.skill-name').value, level:row.querySelector('.skill-level').value}));
    const targetRows = Array.from($('#targetRows').children, row => ({name:row.querySelector('.target-name').value, detail:row.querySelector('.target-detail').value, weight:row.querySelector('.target-weight').value}));
    try { sessionStorage.setItem(draftKey(), JSON.stringify({values, skills:skillRows, targets:targetRows, requestId})); }
    catch { toast('saveError'); }
  }
  function restoreDraft() {
    try {
      const draft = JSON.parse(sessionStorage.getItem(draftKey()) || 'null');
      if (!draft || !draft.values || !Array.isArray(draft.skills) || !Array.isArray(draft.targets)) return;
      requestId = typeof draft.requestId === 'string' ? draft.requestId : null;
      Object.entries(draft.values).forEach(([name,value]) => { if (fields().namedItem(name)) fields().namedItem(name).value = value; });
      $('#skillRows').replaceChildren(); $('#targetRows').replaceChildren();
      draft.skills.slice(0,20).forEach(item => { const control = addSkill(); control.value = item.name; control.closest('.skill-row').querySelector('.skill-level').value = item.level; });
      draft.targets.slice(0,20).forEach(item => { const control = addTarget('custom', item.weight); control.value = item.name; control.closest('.target-row').querySelector('.target-detail').value = item.detail; });
      fields().interviewLanguage.value = 'ja';
      dirty = true; updateSummary();
    } catch { toast('saveError'); }
  }
  function updateForm() { dirty = true; updateSummary(); saveDraft(); }
  window.addEventListener('pagehide', saveDraft);
  clearForm(); applyLanguage(lang);
})();
