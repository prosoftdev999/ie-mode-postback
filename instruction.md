A customs brokerage's retired Windows desk client lodged import, export and amendment entries, and the gateway's copy of what it posted is lost.

The client showed the screens in `/app/data/client` in an embedded Internet Explorer control. When a clerk clicked Lodge entry, the screen's scripts filled the hidden fields of its form from what had been keyed, and the form was posted to the gateway. `/app/data/journal.jsonl` holds, for every entry, the screen it was keyed on and the value of each keyed control at that moment. `/app/data/README.md` describes the client, the workstations and the journal.

Write `/app/output/postback.json` like this (the values are made up):

```json
{"entries": {"E10001": {"ref": "AM-14-000001", "ref_seq": "000001", "party": "ACME LTD", "addr1": "1 MAIN ST", "docket": "AM AM-14-000001 / Mon Jan 13 2014 / 1 line(s)"}}}
```

`entries` must have exactly the entry ids of the journal as keys. Each entry maps the name of every input, select or textarea in the screen's form that has a `name` attribute, and nothing else, to that element's `value` as a string at the moment the form was submitted, after the scripts had run. An element that was left empty has the empty string. The example shows only a few of the names.

Every value of every entry has to match that `value` exactly, character for character; line breaks count as they are in `value`, not as a form submission would encode them. Other top-level keys are ignored and key order does not matter. The file must be a regular UTF-8 JSON file of at most 64 MiB.

You have 9000 seconds to complete this task. Do not cheat by using online solutions or hints specific to this task.
