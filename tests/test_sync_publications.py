from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sync_publications as importer


def work(code=1, title="A study", doi="10.1234/test", kind="journal-article"):
    return {"put-code": code, "title": {"title": {"value": title}}, "type": kind,
            "publication-date": {"year": {"value": "2026"}},
            "journal-title": {"value": "Example Journal"},
            "external-ids": {"external-id": [{"external-id-type": "doi",
                "external-id-value": doi, "external-id-relationship": "self"}]},
            "url": {"value": "https://example.org/paper"},
            "contributors": {"contributor": [{"credit-name": {"value": "Author, A."}}]}}


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / "_publications"
        self.directory.mkdir()

    def files(self):
        return {p.name: p.read_text() for p in self.directory.glob("*.md")}

    def sync(self, works, **kwargs):
        return importer.sync(works, self.root, **kwargs)

    def test_import_deduplicates_doi_and_is_idempotent(self):
        other = work(2, "Different punctuation!", "https://doi.org/10.1234/TEST")
        self.assertEqual(self.sync([work(), other])[0], 1)
        before = self.files()
        self.assertEqual(self.sync([work(), other])[0], 0)
        self.assertEqual(before, self.files())

    def test_title_matching_preserves_curated_category_and_citation(self):
        path = self.directory / "legacy.md"
        data = {"title": "A Study!", "category": "conferences", "conference_abstract": True,
                "citation": "Curated citation", "permalink": "/old/", "topics": ["Vaccines"]}
        path.write_text(importer.render(data, "\nKeep this paragraph.\n"))
        original = path.read_bytes()
        self.assertEqual(self.sync([work()])[0], 0)
        self.assertEqual(path.read_bytes(), original)

    def test_preprint_is_retained_and_linked_to_journal(self):
        self.assertEqual(self.sync([work(1, kind="preprint", doi="10.1234/preprint"), work(2)])[0], 2)
        records = [importer.read_record(p)[0] for p in self.directory.glob("*.md")]
        preprint = next(d for d in records if d["category"] == "preprints")
        journal = next(d for d in records if d["category"] == "manuscripts")
        self.assertEqual(preprint["published_version"], journal["permalink"])
        self.assertEqual(self.sync([work(1, kind="preprint", doi="10.1234/preprint"), work(2)])[0], 0)

    def test_metadata_refresh_preserves_editorial_fields_and_url(self):
        self.sync([work()])
        path = next(self.directory.glob("*.md"))
        data, body = importer.read_record(path)
        original_url = data["permalink"]
        data["title"] = "My edited title"
        data["topics"] = ["My topic"]
        path.write_text(importer.render(data, body + "My paragraph.\n"))
        revised = work(title="An updated title")
        revised["journal-title"]["value"] = "Updated Journal"
        revised["publication-date"]["month"] = {"value": "06"}
        self.sync([revised])
        result, body = importer.read_record(path)
        self.assertEqual(result["title"], "My edited title")
        self.assertEqual(result["venue"], "Updated Journal")
        self.assertEqual(result["date"], "2026-06-01")
        self.assertEqual(result["date_precision"], "month")
        self.assertEqual(result["permalink"], original_url)
        self.assertEqual(result["topics"], ["My topic"])
        self.assertIn("My paragraph.", body)
        self.assertEqual(self.sync([revised])[0], 0)

    def test_part_of_doi_is_not_a_paper_identifier(self):
        source = work()
        source["external-ids"]["external-id"][0]["external-id-relationship"] = "part-of"
        self.assertNotIn("doi", importer.metadata(source))
        source["external-ids"]["external-id"] = None
        source["contributors"]["contributor"] = None
        self.assertNotIn("doi", importer.metadata(source))

    def test_missing_or_ignored_upstream_work_never_deletes_local_records(self):
        self.sync([work()])
        before = self.files()
        self.assertEqual(self.sync([])[0], 0)
        self.assertEqual(self.sync([work(2, title="Ignored", doi="")], ignored=["2"])[0], 0)
        self.assertEqual(before, self.files())

    def test_missing_year_and_unsupported_type_are_reported(self):
        source = work()
        source["publication-date"] = None
        count, notes = self.sync([source, work(2, kind="dissertation-thesis")])
        self.assertEqual(count, 0)
        self.assertEqual(len(notes), 2)

    def test_html_liquid_and_unsafe_url_are_not_rendered(self):
        source = work(title='<script>alert(1)</script> {% include secrets %}')
        source["url"]["value"] = "javascript:alert(1)"
        data = importer.metadata(source)
        self.assertNotIn("<script>", data["title"])
        self.assertNotIn("{%", data["title"])
        self.assertNotIn("paperurl", data)

    def test_bad_remote_record_aborts_before_writes(self):
        bad = work(2)
        bad["publication-date"]["month"] = {"value": "13"}
        with self.assertRaises(ValueError):
            self.sync([work(), bad])
        self.assertEqual(self.files(), {})

    def test_incomplete_bulk_response_fails(self):
        summary = {"group": [{"work-summary": [{"put-code": 1, "display-index": "0"}]}]}
        with patch.object(importer, "get_json", side_effect=[summary, {"bulk": []}]):
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                importer.fetch_works()

    def test_preferred_source_selected_and_duplicate_codes_fetched_once(self):
        group = {"work-summary": [{"put-code": 1, "display-index": "0"},
                                  {"put-code": 2, "display-index": "1"}]}
        with patch.object(importer, "get_json", side_effect=[{"group": [group, group]},
                                {"bulk": [{"work": work(2)}]}]) as request:
            self.assertEqual(len(importer.fetch_works()), 1)
            self.assertTrue(request.call_args.args[0].endswith("/works/2"))


if __name__ == "__main__":
    unittest.main()
