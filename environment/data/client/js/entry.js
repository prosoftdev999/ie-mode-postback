/*
 * entry.js - reads the keyed entry, normalises it and fills the hidden
 * fields that the gateway reads. Shared by import, export and amend screens.
 */
CV.entry = (function (u) {
    var e = {};
    var MAX_LINES = 6;
    var LB_TO_KG = 0.45359237;
    var DAY = 86400000;

    // ISO 6346 letter values (multiples of 11 are skipped)
    var LETTER = {
        A: 10, B: 12, C: 13, D: 14, E: 15, F: 16, G: 17, H: 18, I: 19, J: 20,
        K: 21, L: 23, M: 24, N: 25, O: 26, P: 27, Q: 28, R: 29, S: 30, T: 31,
        U: 32, V: 34, W: 35, X: 36, Y: 37, Z: 38
    };

    // ids of the keyed controls
    var KEYED = {
        ref: 'txtRef', party: 'txtParty', addr: 'txaAddr', inv_date: 'txtInvDate', arr_date: 'txtArrDate',
        currency: 'selCurrency', freight: 'txtFreight', weight: 'txtWeight', pkgs: 'txtPkgs',
        cntrs: 'txtCntrs', lines: 'txaLines'
    };

    function val(name) {
        return document.getElementById(KEYED[name]).value;
    }

    function put(form, name, v) {
        form.elements[name].value = (v === null || v === undefined) ? '' : String(v);
    }

    // Dates are keyed as printed on the paperwork. Dotted dates come from
    // the European desks and are day first; everything else goes to the browser.
    e.parseDate = function (s) {
        var m, y, d;
        s = u.trim(s);
        if (s === '') {
            return null;
        }
        m = /^(\d{1,2})\.(\d{1,2})\.(\d{2,4})$/.exec(s);
        if (m) {
            y = parseInt(m[3]);
            if (y < 100) {
                y += 2000;
            }
            return new Date(y, parseInt(m[2]) - 1, parseInt(m[1]));
        }
        d = new Date(s);
        if (isNaN(d.getTime())) {
            return null;
        }
        return d;
    };

    e.dutyRate = function (cell, hs) {
        var r = u.trim(cell).replace('%', '');
        var chapter;
        if (r === '' || isNaN(parseFloat(r))) {
            r = CV.tariff.standard;
        } else {
            r = parseFloat(r);
        }
        chapter = parseInt(hs.substr(0, 2));
        if (u.inList(CV.tariff.plantChapters, chapter)) {
            r += CV.tariff.plantLevy;
        }
        return r;
    };

    e.hsFormat = function (digits) {
        if (digits.length < 6) {
            return digits;
        }
        return digits.substr(0, 4) + '.' + digits.substr(4, 2) + (digits.length > 6 ? '.' + digits.substr(6) : '');
    };

    e.containerOk = function (c) {
        var sum = 0, i, ch, v;
        if (!/^[A-Z]{4}\d{7}$/.test(c)) {
            return false;
        }
        for (i = 0; i < 10; i++) {
            ch = c[i];
            v = i < 4 ? LETTER[ch] : parseInt(ch, 10);
            sum += v * Math.pow(2, i);
        }
        return (sum % 11) % 10 === parseInt(c[10], 10);
    };

    e.kilos = function (s) {
        var w = u.trim(s).toLowerCase();
        var n = parseFloat(w.replace(/,/g, ''));
        if (isNaN(n)) {
            return '';
        }
        if (/lb/.test(w)) {
            n = n * LB_TO_KG;
        }
        return n.toFixed(1);
    };

    e.submit = function (form, screen) {
        var ref, party, addr, inv, arr, rate, rows, i, cells, hs, qty, price, value, duty;
        var n = 0, goods = 0, dutyFc = 0, list, checks, freight, goodsUsd, freightUsd, kg, descs = [], block;

        ref = u.squash(val('ref')).toUpperCase();
        put(form, 'ref', ref);
        put(form, 'ref_seq', ref.substr(-6));

        party = u.squash(val('party')).toUpperCase();
        put(form, 'party', party);

        addr = val('addr').split(/\r\n|\n/);
        put(form, 'addr1', u.trim(addr[0]));
        put(form, 'addr2', u.trim(addr[1]));
        for (i = 3; i < addr.length; i++) {
            addr[2] = addr[2] + ', ' + addr[i];
        }
        put(form, 'addr3', u.trim(addr[2]));
        // the label printer takes the address as one block, a line per row
        block = [];
        for (i = 0; i < 3; i++) {
            if (u.trim(addr[i]) !== '') {
                block.push(u.trim(addr[i]));
            }
        }
        put(form, 'addr_block', block.join('\n'));

        inv = e.parseDate(val('inv_date'));
        arr = e.parseDate(val('arr_date'));
        put(form, 'inv_date', u.isoDate(inv));
        put(form, 'arr_date', u.isoDate(arr));
        put(form, 'transit_days', inv && arr ? Math.round((arr - inv) / DAY) : '');
        put(form, 'inv_year', inv ? inv.getYear() : '');
        put(form, 'arr_long', arr ? arr.toLocaleDateString() : '');

        rate = CV.fx(val('currency'), inv);
        put(form, 'fx_rate', rate);

        rows = val('lines').split(/\r\n|\n/);
        for (i = 0; i < rows.length; i++) {
            if (u.trim(rows[i]) === '') {
                continue;
            }
            cells = rows[i].split(/\t/);
            hs = String(cells[0]).replace(/\D/g, '');
            qty = parseInt(cells[2]);
            price = u.amount(cells[3]);
            value = u.money(qty * price);
            duty = u.money(parseFloat(value) * e.dutyRate(cells[4], hs) / 100);
            goods += parseFloat(value) || 0;
            dutyFc += parseFloat(duty) || 0;
            n++;
            descs.push(u.squash(cells[1]).toUpperCase());
            if (n <= MAX_LINES) {
                put(form, 'l' + n + '_hs', e.hsFormat(hs));
                put(form, 'l' + n + '_desc', u.squash(cells[1]).toUpperCase());
                put(form, 'l' + n + '_qty', isNaN(qty) ? '' : qty);
                put(form, 'l' + n + '_value', value);
                put(form, 'l' + n + '_duty', duty);
            }
        }
        put(form, 'line_count', n);
        put(form, 'lines_json', JSON.stringify(descs));
        put(form, 'goods_fc', u.money(goods));

        goodsUsd = u.money(goods * rate);
        freight = u.amount(val('freight'));
        freightUsd = u.money(freight * rate);
        put(form, 'goods_usd', goodsUsd);
        put(form, 'freight_usd', freightUsd);
        put(form, 'cif_usd', u.money((parseFloat(goodsUsd) || 0) + (parseFloat(freightUsd) || 0)));
        put(form, 'duty_usd', screen === 'EX' ? '0.00' : u.money(dutyFc * rate));

        kg = e.kilos(val('weight'));
        put(form, 'gross_kg', kg);
        put(form, 'kg_text', kg === '' ? '' : parseFloat(kg).toLocaleString() + ' kg');
        put(form, 'pkgs', parseInt(u.trim(val('pkgs'))));

        list = [];
        checks = '';
        rows = u.trim(val('cntrs')).toUpperCase().split(/[\s,;\/]+/);
        for (i = 0; i < rows.length; i++) {
            if (rows[i].length) {
                list.push(rows[i]);
                checks += e.containerOk(rows[i]) ? 'Y' : 'N';
            }
        }
        put(form, 'cntrs', JSON.stringify(list));
        put(form, 'cntr_check', checks);

        put(form, 'docket', screen + ' ' + ref + ' / ' + (inv ? inv.toDateString() : 'no invoice date') + ' / ' + n + ' line(s)');
        return true;
    };

    return e;
}(CV.util));
