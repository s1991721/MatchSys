(function () {
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
