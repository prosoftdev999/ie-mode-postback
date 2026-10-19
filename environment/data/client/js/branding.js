/* branding.js - environment banner for the desk screens (LIVE / TRAINING). */
var CV = window.CV || {};
CV.env = 'LIVE';
CV.banner = function () {
    var b = document.getElementById('banner');
    if (b) {
        b.innerHTML = 'Entry desk &middot; ' + CV.env;
    }
};
