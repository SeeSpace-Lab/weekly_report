from __future__ import annotations

import unittest
from datetime import datetime, timezone

from weekly_intel.calendar_window import previous_complete_week


class WeeklyCalendarWindowTest(unittest.TestCase):
    def test_monday_run_builds_previous_shanghai_monday_to_sunday(self) -> None:
        window = previous_complete_week(
            datetime(2026, 7, 27, 0, 0, tzinfo=timezone.utc)
        )

        self.assertEqual(window.iso_week, "2026-W30")
        self.assertEqual(
            window.start,
            datetime(2026, 7, 19, 16, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            window.end,
            datetime(
                2026,
                7,
                26,
                15,
                59,
                59,
                999999,
                tzinfo=timezone.utc,
            ),
        )

    def test_timezone_aware_datetime_is_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            previous_complete_week(datetime(2026, 7, 27, 8, 0))

    def test_next_monday_builds_w31(self) -> None:
        window = previous_complete_week(
            datetime(2026, 8, 3, 0, 0, tzinfo=timezone.utc)
        )

        self.assertEqual(window.iso_week, "2026-W31")
        self.assertEqual(
            window.start,
            datetime(2026, 7, 26, 16, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            window.end,
            datetime(
                2026,
                8,
                2,
                15,
                59,
                59,
                999999,
                tzinfo=timezone.utc,
            ),
        )


if __name__ == "__main__":
    unittest.main()
