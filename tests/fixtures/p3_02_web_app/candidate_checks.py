import unittest

from server import greeting


class GreetingTest(unittest.TestCase):
    def test_exact_greeting(self) -> None:
        self.assertEqual(greeting(), "Hello, MiniTZ!")


if __name__ == "__main__":
    unittest.main()
