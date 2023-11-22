const warn = console.warn;
console.warn = function (message, ...optionalParams) {
    if (message.startsWith("Feature flags")) {
        return;
    }
    const p = document.createElement("p");
    p.className = "warnings";
    p.appendChild(document.createTextNode(message));
    document.body.appendChild(p);
    warn(message, ...optionalParams);
}

const error = console.error;
console.error = function (message, ...optionalParams) {
    const p = document.createElement("p");
    p.className = "errors";
    p.appendChild(document.createTextNode(message));
    document.body.appendChild(p);
    error(message, ...optionalParams)
}

// https://webpack.js.org/concepts/module-federation/#uncaught-error-shared-module-is-not-available-for-eager-consumption
import('./main.js');
