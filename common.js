(function () {
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

  window.formatDate = function (raw) {
    if (!raw) return "";
    const d = new Date(raw);
    if (Number.isNaN(d.getTime())) return raw;
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  };
})();
