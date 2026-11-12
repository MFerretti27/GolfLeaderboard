import unittest
from unittest.mock import patch

from golf import get_preferred_events, select_display_event


def event(name, state="in", event_id="1"):
    return {
        "id": event_id,
        "name": name,
        "status": {"type": {"state": state}},
    }


class EventSelectionTests(unittest.TestCase):
    def test_empty_events(self):
        self.assertIsNone(select_display_event([]))

    def test_single_event_without_players(self):
        scheduled = event("Upcoming Tournament", "pre")
        self.assertIs(select_display_event([scheduled]), scheduled)

    def test_overlapping_major_and_signature_events(self):
        for preferred_name, alternate_name in (
            ("Arnold Palmer Invitational pres. by Mastercard", "Puerto Rico Open"),
            ("Truist Championship", "ONEflight Myrtle Beach Classic"),
            ("The Open", "Corales Puntacana Championship"),
            ("U.S. Open", "Alternate Tournament"),
            ("the Memorial Tournament presented by Workday", "Alternate Tournament"),
        ):
            with self.subTest(preferred_name=preferred_name):
                preferred = event(preferred_name)
                alternate = event(alternate_name, event_id="2")
                for events in ([alternate, preferred], [preferred, alternate]):
                    self.assertIs(select_display_event(events), preferred)

    def test_only_live_event_wins_over_scheduled_or_finished_major(self):
        live = event("Puerto Rico Open", event_id="2")
        for state in ("pre", "post"):
            with self.subTest(state=state):
                major = event("The Open", state)
                self.assertIs(select_display_event([major, live]), live)

    def test_major_wins_over_signature(self):
        major = event("Masters Tournament")
        signature = event("RBC Heritage", event_id="2")
        self.assertIs(select_display_event([signature, major]), major)

    def test_no_live_events_use_same_priority(self):
        signature = event("Truist Championship", "pre")
        alternate = event("ONEflight Myrtle Beach Classic", "pre", "2")
        self.assertIs(select_display_event([alternate, signature]), signature)

    def test_unknown_events_remain_stable_when_api_order_changes(self):
        first = event("A Tournament")
        second = event("B Tournament", event_id="2")
        self.assertIs(select_display_event([second, first]), first)
        self.assertIs(select_display_event([first, second]), first)

    def test_duplicate_names_use_id_for_stable_tie(self):
        first = event("Tournament", event_id="100")
        second = event("Tournament", event_id="200")
        self.assertIs(select_display_event([second, first]), first)

    def test_short_name_classification(self):
        major = event("Sponsored Event")
        major["shortName"] = "The Open"
        alternate = event("Alternate Event", event_id="2")
        self.assertIs(select_display_event([alternate, major]), major)

    def test_pipeline_switches_only_when_live_status_changes(self):
        signature = event("Truist Championship")
        alternate = event("ONEflight Myrtle Beach Classic", event_id="2")
        with patch("golf.fetch_scoreboard") as fetch:
            for events in ([alternate, signature], [signature, alternate]):
                fetch.return_value = {"events": events}
                self.assertIs(select_display_event(get_preferred_events()), signature)
            signature["status"]["type"]["state"] = "post"
            self.assertIs(select_display_event(get_preferred_events()), alternate)


if __name__ == "__main__":
    unittest.main()
