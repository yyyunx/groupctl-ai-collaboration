import unittest
from collaboration_fixture.greet import greet
class GreetingTest(unittest.TestCase):
    def test_name(self):
        self.assertIn("Ada", greet("Ada"))
    def test_trim(self):
        self.assertEqual(greet("  Ada  ").split()[-1], "Ada")
        self.assertFalse(greet("  Ada  ").endswith(" "))
