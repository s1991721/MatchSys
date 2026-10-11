(() => {
  // Frontend-only fixtures. No report API or database access.
  const samples = [
    {id: 'demo-4', candidate_name: '山田 太郎', position: '后端工程师', completed_at: '2026-10-11T14:30:00+09:00', report_text: '能力表现\n候选人能够结合项目经历解释接口设计与数据存储方案，回答条理清晰。\n\n回答依据\n在介绍订单处理项目时，说明了请求校验、事务处理及重复提交的处理思路。对于慢查询，提到了索引与执行计划，但未提供优化前后的具体数据。\n\n证据不足之处\n本次回答不足以确认其在高并发生产环境中的独立排障经验。', recording_url: 'assets/media/report-demo.wav', video_url: 'assets/media/report-demo.mp4'},
    {id: 'demo-3', candidate_name: '李 明', position: '产品经理', completed_at: '2026-10-10T16:00:00+09:00', report_text: '项目经验\n候选人围绕用户反馈、需求优先级和上线验证介绍了一次产品改版。\n\n回答依据\n能够说明需求取舍的理由，并区分用户诉求与实际问题。效果描述以定性反馈为主，缺少量化指标。\n\n待核实事项\n跨团队推进的具体职责和项目效果仍需更多证据。', recording_url: 'assets/media/report-demo.wav'},
    {id: 'demo-2', candidate_name: '佐藤 美咲', position: 'UX 设计师', completed_at: '2026-10-09T11:00:00+09:00', report_text: '设计过程与证据\n候选人介绍了从用户访谈到原型验证的过程，能说明设计调整与反馈之间的关系。\n\n对可用性问题的描述较具体。对于设计效果，回答未覆盖长期使用数据，本次无法充分评价。', video_url: 'assets/media/report-demo.mp4'},
    {id: 'demo-1', candidate_name: '山田 太郎', position: '后端工程师', completed_at: '2026-10-08T10:00:00+09:00', initially_read: true, report_text: '本次面试记录\n候选人能够解释基础数据结构的选择，并描述异常处理思路。\n\n回答依据\n在缓存失效问题中提到了更新策略，但对并发条件下的一致性问题解释不够完整。\n\n本报告属于该候选人的另一次独立面试。'}
  ];
  const key = userId => `aomera-report-demo-read:${userId || 'preview'}`;
  function readIds(userId) {
    try {const value = JSON.parse(localStorage.getItem(key(userId)) || '[]'); return new Set(Array.isArray(value) ? value : []);} catch {return new Set();}
  }
  window.AIInterviewReportDemo = {
    list(userId) {
      const read = readIds(userId);
      return samples.map(item => ({...item, is_read: Boolean(item.initially_read || read.has(item.id))}));
    },
    markRead(userId, id) {
      const read = readIds(userId); read.add(id);
      try {localStorage.setItem(key(userId), JSON.stringify([...read]));} catch { /* Reading still works when storage is disabled. */ }
    },
    unreadCount(userId) {return this.list(userId).filter(item => !item.is_read).length;},
    storageKey: key
  };
})();
