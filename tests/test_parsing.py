"""
Unit tests for parsing utilities.
"""
import unittest
from indexer.parsing import EpisodeParser


class TestEpisodeParser(unittest.TestCase):
    """Test cases for EpisodeParser."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = EpisodeParser()

    def test_extract_season_pack(self):
        """Test extraction of season pack information."""
        test_cases = [
            ("Complete Season 1", {'season': 1, 'full_season_pack': True}),
            ("Full Season 02", {'season': 2, 'full_season_pack': True}),
            ("S03 Complete Pack", {'season': 3, 'full_season_pack': True}),
        ]

        for text, expected in test_cases:
            with self.subTest(text=text):
                result = self.parser.extract_episode_info(text)
                self.assertEqual(result, expected)

    def test_extract_single_episode(self):
        """Test extraction of single episode information."""
        test_cases = [
            ("S01E01", {'season': 1, 'episode': 1}),
            ("1x02", {'season': 1, 'episode': 2}),
            ("Stagione 2 Episodio 3", {'season': 2, 'episode': 3}),
        ]

        for text, expected in test_cases:
            with self.subTest(text=text):
                result = self.parser.extract_episode_info(text)
                self.assertEqual(result, expected)

    def test_categorize_title(self):
        """Test title categorization."""
        test_cases = [
            ("Show Name S01E01", "5000"),
            ("Movie Title 2023", "2000"),
            ("Anime Series", "5070"),
            ("Some Other Content", "8000"),
        ]

        for title, expected in test_cases:
            with self.subTest(title=title):
                result = self.parser.categorize_title(title)
                self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()