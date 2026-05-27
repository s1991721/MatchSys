(function () {
    window.FinanceViews = window.FinanceViews || {};
    window.FinanceViews.settings = {
        init(root) {
            if (!root || root.dataset.initialized === "true") return;
            root.dataset.initialized = "true";
        },
    };
}());
