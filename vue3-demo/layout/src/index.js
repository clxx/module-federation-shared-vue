console.warn = function (message) {
    if (message.startsWith("Feature flags")) {
        return;
    }
    const p = document.createElement("p");
    p.className = "warnings";
    p.appendChild(document.createTextNode(message));
    document.body.appendChild(p)
}

console.error = function (message) {
    const p = document.createElement("p");
    p.className = "errors";
    p.appendChild(document.createTextNode(message));
    document.body.appendChild(p)
}

// https://webpack.js.org/concepts/module-federation/#uncaught-error-shared-module-is-not-available-for-eager-consumption
import('./main.js');
