import json
import os
import stat

import pytest

OUTPUT = "/app/output/postback.json"
EXPECTED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "expected.json")
MAX_BYTES = 64 * 1024 * 1024

GROUPS = {
    "reference": ["ref", "ref_seq", "docket"],
    "party": ["party", "addr1", "addr2", "addr3", "addr_block"],
    "dates": ["inv_date", "arr_date", "transit_days", "inv_year", "arr_long", "fx_rate"],
    "totals": ["goods_fc", "goods_usd", "freight_usd", "cif_usd", "duty_usd"],
    "cargo": ["gross_kg", "kg_text", "pkgs", "cntrs", "cntr_check"],
    "lines": ["line_count", "lines_json"] +["l%d_%s" % (i, f) for i in range(1, 7) for f in ("hs", "desc", "qty", "value", "duty")],
}


@pytest.fixture(scope="session")
def expected():
    with open(EXPECTED, encoding="utf-8") as f:
        return json.load(f)["entries"]


@pytest.fixture(scope="session")
def answer():
    st = os.lstat(OUTPUT)
    assert stat.S_ISREG(st.st_mode), "postback.json must be a regular file"
    assert st.st_size <= MAX_BYTES, "postback.json is larger than 64 MiB"
    with open(OUTPUT, "rb") as f:
        doc = json.loads(f.read().decode("utf-8-sig"))
    assert isinstance(doc, dict), "top level must be a JSON object"
    entries = doc.get("entries")
    assert isinstance(entries, dict), "entries must be a JSON object"
    return entries


def test_entry_ids(answer, expected):
    missing = sorted(set(expected) - set(answer))
    extra = sorted(set(answer) - set(expected))
    assert not missing and not extra, "missing %d entries (%s), extra %d (%s)" % (
        len(missing), missing[:5], len(extra), extra[:5])


def test_field_names(answer, expected):
    grouped = {name for names in GROUPS.values() for name in names}
    assert all(set(exp) == grouped for exp in expected.values()), "a recorded control is not compared by any test"
    bad = []
    for eid, exp in expected.items():
        got = answer.get(eid)
        if not isinstance(got, dict) or set(got) != set(exp):
            bad.append(eid)
    assert not bad, "%d entries do not have exactly the form's named controls, e.g. %s" % (len(bad), bad[:5])


@pytest.mark.parametrize("group", sorted(GROUPS))
def test_values(answer, expected, group):
    wrong = []
    for eid, exp in sorted(expected.items()):
        got = answer.get(eid)
        if not isinstance(got, dict):
            wrong.append((eid, None))
            continue
        for name in GROUPS[group]:
            v = got.get(name)
            if not isinstance(v, str) or v != exp[name]:
                wrong.append((eid, name))
    assert not wrong, "%d %s values differ, e.g. %s" % (len(wrong), group, wrong[:5])
