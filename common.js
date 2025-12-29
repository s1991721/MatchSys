(function () {
  // 接口校验登录
  window.fetchWithAuth = async function (url, options = {}) {
    const mergedOptions = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      ...options,
    };
    const res = await fetch(url, mergedOptions);
    if (res.status === 401) {
      window.location.href = "/login.html";
      throw new Error("Unauthorized");
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res;
  };

  // 接口返回处理
  window.normalizeApiResponse = function (raw) {
    if (raw && typeof raw === "object" && "success" in raw) {
      return raw;
    }
    return {
      success: false,
      code: "ERR_INVALID_RESPONSE",
      message: "Invalid response",
      data: null,
      meta: {},
    };
  };

  // 日期格式化
  window.formatDate = function (raw) {
    if (!raw) return "";
    const d = new Date(raw);
    if (Number.isNaN(d.getTime())) return raw;
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  };

  // 根据生日计算年龄
  window.calcAge = function (birthday){
    if (!birthday) return null;
    const date = new Date(birthday);
    if (Number.isNaN(date.getTime())) return null;
    const today = new Date();
    let age = today.getFullYear() - date.getFullYear();
    const m = today.getMonth() - date.getMonth();
    if (m < 0 || (m === 0 && today.getDate() < date.getDate())) {
        age -= 1;
    }
    return age;
  };

    // 根据契约类型返回字符串
  window.contractTypeToLabel = function (value){
    const mapping = {
        1: '正社员',
        2: '契约社员',
        3: 'フリーランス'
    };
    return mapping[value] || '未定';
  };
})();
