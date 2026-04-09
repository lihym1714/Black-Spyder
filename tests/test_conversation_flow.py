from __future__ import annotations

import unittest

from tools.agent_runtime import run_conversational_analysis


class ConversationFlowTests(unittest.TestCase):
    def test_converse_extracts_url_from_goal(self) -> None:
        result = run_conversational_analysis("웹 페이지 진단해줘 https://loaflex.com/")

        self.assertEqual(result["analysis_mode"], "conversation")
        self.assertIn("conversation_extraction", result)
        self.assertEqual(result["conversation_extraction"]["url"], "https://loaflex.com/")

    def test_converse_asks_for_apk_target_when_missing(self) -> None:
        result = run_conversational_analysis("apk 분석해줘")

        self.assertTrue(result["needs_clarification"])
        self.assertIn("APK", result["clarification_question"].upper())

    def test_converse_extracts_path_for_mobile_review(self) -> None:
        result = run_conversational_analysis("~/apk 분석해줘 /Users/example/app.apk")

        self.assertEqual(result["analysis_mode"], "conversation")
        self.assertTrue(result["needs_clarification"])
        self.assertIn("target_path", result["suggested_input"])


if __name__ == "__main__":
    unittest.main()
