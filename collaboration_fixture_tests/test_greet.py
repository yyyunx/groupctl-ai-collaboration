import unittest
from collaboration_fixture.greet import greet
class GreetingTest(unittest.TestCase):
    def test_name(self):
        self.assertIn("Ada", greet("Ada"))
