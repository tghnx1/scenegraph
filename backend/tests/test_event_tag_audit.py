import json
from pathlib import Path

from scripts.audit_event_tag_jsonl import audit_records, compare_records, load_jsonl


def test_audit_jsonl_reports_metrics_and_invalid_lines(tmp_path: Path):
    path = tmp_path / "tags.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "eventId": 1,
                        "eventName": "Night",
                        "extractor": "llm_event_tags_v3:test",
                        "tags": [
                            {
                                "type": "style",
                                "value": "techno",
                                "evidence": "structured_genre: Techno",
                            }
                        ],
                    }
                ),
                "{invalid",
                json.dumps({"eventId": 2, "eventName": "Empty", "tags": []}),
            ]
        )
    )

    records, invalid = load_jsonl(path)
    audit = audit_records(records, invalid_lines=invalid)

    assert audit["validJsonLines"] == 2
    assert len(audit["invalidJsonLines"]) == 1
    assert audit["totalTagCount"] == 1
    assert audit["tagsPerType"] == {"style": 1}
    assert audit["maximumTagsPerEvent"] == 1
    assert audit["zeroTagEvents"] == [{"eventId": 2, "eventName": "Empty"}]
    assert audit["evidenceSourceCounts"] == {"structured_genre": 1}


def test_audit_comparison_reports_added_removed_and_empty_changes():
    before = [
        {"eventId": 1, "tags": [{"type": "style", "value": "techno"}]},
        {"eventId": 2, "tags": []},
    ]
    after = [
        {"eventId": 1, "tags": [{"type": "theme", "value": "queer"}]},
        {"eventId": 2, "tags": [{"type": "mood", "value": "energetic"}]},
    ]

    comparison = compare_records(before, after)

    assert comparison["eventsNoLongerEmpty"] == [2]
    assert comparison["newlyEmptyEvents"] == []
    assert comparison["aggregateDifferences"]["totalTagCount"] == 1
    assert comparison["eventsWithChanges"][0]["added"] == [("theme", "queer")]
    assert comparison["eventsWithChanges"][0]["removed"] == [("style", "techno")]
