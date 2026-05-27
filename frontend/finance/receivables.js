(function () {
    window.FinanceViews = window.FinanceViews || {};
    window.FinanceViews.receivables = {
        init(root) {
            if (!root || root.dataset.initialized === "true") return;
            root.dataset.initialized = "true";
        },
    };
}());
