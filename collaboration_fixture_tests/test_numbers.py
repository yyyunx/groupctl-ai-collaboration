import unittest
from collaboration_fixture.numbers_lib import add
class AdditionTest(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(add(2, 3), 5)
    def test_negative(self):
        self.assertEqual(add(-2, 1), -1)
