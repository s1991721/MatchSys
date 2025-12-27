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
})();
