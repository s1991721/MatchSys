(function () {
    window.FinanceViews = window.FinanceViews || {};
    window.FinanceViews.payables = {
        init(root) {
            if (!root || root.dataset.initialized === "true") return;
            root.dataset.initialized = "true";
        },
    };
}());
