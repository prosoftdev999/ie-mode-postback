/*
 * util.js - small helpers shared by the entry desk screens.
 * Keep this file ES3: the desk still has to work on the older screens.
 */
var CV = window.CV || {};

CV.util = (function () {
    var u = {};

    u.trim = function (s) {
        s = (s === null || s === undefined) ? '' : String(s);
        if (s.trim) {
            return s.trim();
        }
        return s.replace(/^\s+|\s+$/g, '');
    };

    // trim and fold every run of white space to a single blank
    u.squash = function (s) {
        return u.trim(s).replace(/\s+/g, ' ');
    };

    u.pad = function (n, width) {
        n = String(n);
        while (n.length < width) {
            n = '0' + n;
        }
        return n;
    };

    u.isoDate = function (d) {
        if (!d) {
            return '';
        }
        return d.getFullYear() + '-' + u.pad(d.getMonth() + 1, 2) + '-' + u.pad(d.getDate(), 2);
    };

    u.monthKey = function (d) {
        return d.getFullYear() + '-' + u.pad(d.getMonth() + 1, 2);
    };

    u.inList = function (list, x) {
        var i;
        if (list.indexOf) {
            return list.indexOf(x) >= 0;
        }
        for (i = 0; i < list.length; i++) {
            if (list[i] == x) {
                return true;
            }
        }
        return false;
    };

    // "12,345.60" -> 12345.6 ; blank -> 0 ; anything unreadable -> NaN
    u.amount = function (s) {
        s = u.trim(s).replace(/,/g, '');
        if (s === '') {
            return 0;
        }
        return parseFloat(s);
    };

    u.money = function (n) {
        if (isNaN(n)) {
            return '';
        }
        return n.toFixed(2);
    };

    return u;
}());
