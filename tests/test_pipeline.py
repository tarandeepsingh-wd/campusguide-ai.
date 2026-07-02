import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from campusguide.rag_pipeline import ask_question, index_directory
from campusguide.storage import RagStore


class RagPipelineTest(unittest.TestCase):
    def test_index_and_answer_with_citation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            docs.mkdir()
            (docs / "placement.txt").write_text(
                "Students must apply before the placement deadline. "
                "Late applications are not accepted unless an extension is announced.",
                encoding="utf-8",
            )
            store = RagStore(root / "rag.db")

            stats = index_directory(docs, store)
            answer = ask_question(store, "Can I apply after deadline?")

            self.assertEqual(stats["documents"], 1)
            self.assertGreaterEqual(stats["chunks"], 1)
            self.assertIn("deadline", answer.answer.lower())
            self.assertEqual(answer.citations[0].document_name, "placement.txt")

    def test_unknown_when_no_chunks_match(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs = root / "docs"
            docs.mkdir()
            (docs / "hostel.txt").write_text(
                "Hostel maintenance requests are handled by administration.",
                encoding="utf-8",
            )
            store = RagStore(root / "rag.db")
            index_directory(docs, store)

            answer = ask_question(store, "quantum cryptography syllabus")

            self.assertEqual(answer.answer, "I don't know from the indexed campus documents.")


if __name__ == "__main__":
    unittest.main()
