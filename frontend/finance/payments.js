(function () {
    window.FinanceViews = window.FinanceViews || {};
    window.FinanceViews.payments = {
        init(root) {
            if (!root || root.dataset.initialized === "true") return;
            root.dataset.initialized = "true";
        },
    };
}());
