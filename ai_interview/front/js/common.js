(() => {
  const AIInterview = window.AIInterview || {};
  window.AIInterview = AIInterview;

  const localHosts = new Set(["localhost", "127.0.0.1"]);

  function normalizeBaseUrl(value) {
    return String(value || "").trim().replace(/\/+$/, "");
  }

  function resolveApiBase() {
    if (window.AI_INTERVIEW_API_BASE) {
      return normalizeBaseUrl(window.AI_INTERVIEW_API_BASE);
    }

    if (localHosts.has(window.location.hostname)) {
      const backendHost = window.location.hostname === "localhost"
        ? "localhost"
        : "127.0.0.1";
      return `http://${backendHost}:8001/api`;
    }

    return "/ai_interview/api";
  }

  const apiBase = resolveApiBase();

  AIInterview.getApiBase = function () {
    return apiBase;
  };

  AIInterview.buildApiUrl = function (path = "") {
    const normalizedPath = String(path).replace(/^\/+/, "");
    return normalizedPath ? `${apiBase}/${normalizedPath}` : apiBase;
  };

  AIInterview.requestJson = async function (path, options = {}) {
    const { headers = {}, ...requestOptions } = options;
    let response;

    try {
      response = await fetch(AIInterview.buildApiUrl(path), {
        credentials: "include",
        ...requestOptions,
        headers: {
          "Content-Type": "application/json",
          ...headers,
        },
      });
    } catch (cause) {
      const error = new Error("Network request failed", { cause });
      error.isNetworkError = true;
      throw error;
    }

    const payload = await response.json().catch(() => null);
    if (!response.ok || !payload?.success) {
      const error = new Error(
        payload?.error?.message || `HTTP ${response.status}`,
      );
      error.status = response.status;
      error.code = payload?.error?.code;
      error.payload = payload;
      throw error;
    }

    return payload;
  };
})();
