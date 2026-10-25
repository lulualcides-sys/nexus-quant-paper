import json
import tempfile
import unittest
from pathlib import Path
from src.private_chat import load_chat, save_chat

class ChatSecretTests(unittest.TestCase):
    def test_encrypted_chat_not_plaintext(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"chat.enc.json"
            save_chat("test-secret-long-123","123456789",path)
            blob=path.read_text()
            self.assertNotIn("123456789",blob)
            self.assertEqual(load_chat("test-secret-long-123",path),"123456789")
            with self.assertRaises(RuntimeError):
                load_chat("different-token",path)
    def test_no_file(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(load_chat("token",Path(folder)/"missing.json"))
if __name__=="__main__":unittest.main()
