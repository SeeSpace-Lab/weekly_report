import unittest

from weekly_intel.cli import build_parser


class CliParserTests(unittest.TestCase):
    def test_run_weekly_can_skip_wechat(self) -> None:
        args = build_parser().parse_args(["run-weekly", "--skip-wechat"])

        self.assertTrue(args.skip_wechat)


if __name__ == "__main__":
    unittest.main()
