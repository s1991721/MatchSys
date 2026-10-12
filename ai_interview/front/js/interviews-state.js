/* Completion and recorded failures take precedence over invitation expiry. */
(() => {
  const validTime = value => typeof value === 'string' && Number.isFinite(Date.parse(value));
  window.AIInterviewList = {
    status(record, now = Date.now()) {
      if (validTime(record.completedAt)) return 'completed';
      if (validTime(record.errorAt) || record.errorReason || ['failed', 'interrupted', 'abnormal'].includes(record.status)) return 'abnormal';
      return Date.parse(record.expiresAt) <= now ? 'expired' : 'waiting';
    },
    dateKey(value) {
      if (!validTime(value)) return '';
      return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(value));
    },
    filter(records, { status = 'all', query = '', from = '', to = '' }, now = Date.now()) {
      const needle = query.trim().toLocaleLowerCase();
      return records.filter(record => {
        const date = this.dateKey(record.createdAt);
        return (status === 'all' || this.status(record, now) === status)
          && (!needle || `${record.candidateName || ''} ${record.candidateEmail || ''}`.toLocaleLowerCase().includes(needle))
          && (!from || date && date >= from) && (!to || date && date <= to);
      }).sort((a, b) => (Date.parse(b.createdAt) || 0) - (Date.parse(a.createdAt) || 0));
    }
  };
})();
