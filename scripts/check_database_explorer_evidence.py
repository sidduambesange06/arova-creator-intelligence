"""Validate filled-database browser evidence from the Tears of Steel fixture."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit


def failed_checks(report):
    db = report["db_explorer_acceptance"]
    requests = db["rows_click_get_calls"]
    checks = {
        "single videos rows GET": len(requests) == 1
        and requests[0]["method"] == "GET"
        and requests[0]["status"] == 200
        and urlsplit(requests[0]["url"]).path == "/api/v1/admin/database/tables/videos/rows",
        "expected video visible": db["rows_shows_tears_of_steel"],
        "incoming relationship visible": db["er_diagram"]["inspector_shows_referenced_by"],
        "accessible relationship table visible": db["accessible_list_view_works"],
        "table filtering stays local": db["client_side_filter_api_calls"] == 0,
        "lock clears session and data": db["lock_clears_session_and_data"],
        "fixture rows preserved": db["db_records_immutable"],
        "source database preserved": report["live_db_immutable"],
        "backup count unchanged": report["spurious_backups_created"] == 0,
    }
    return [name for name, passed in checks.items() if passed is not True]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    failures = failed_checks(json.loads(parser.parse_args().report.read_text(encoding="utf-8")))
    if failures:
        raise SystemExit("Failed: " + ", ".join(failures))
    print("Database Explorer fixture checks passed.")

