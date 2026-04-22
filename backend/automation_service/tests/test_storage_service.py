import pytest
from pathlib import Path
from backend.automation_service.storage_service import StorageService, _sha256


@pytest.fixture
def storage(tmp_path):
    return StorageService(base_dir=tmp_path)


class TestFolderCreation:
    def test_creates_all_category_dirs(self, tmp_path):
        StorageService(base_dir=tmp_path)
        for name in ("invoices", "important", "spam", "other"):
            assert (tmp_path / name).is_dir()

    def test_idempotent_on_existing_dirs(self, tmp_path):
        StorageService(base_dir=tmp_path)
        StorageService(base_dir=tmp_path)  # should not raise


class TestSaveAttachment:
    def test_saves_file_to_correct_folder(self, storage, tmp_path):
        result = storage.save_attachment(b"PDF_DATA", "invoice.pdf", "invoice")
        assert result is not None
        assert result.saved_path.parent == tmp_path / "invoices"
        assert result.saved_path.exists()

    def test_important_goes_to_important_dir(self, storage, tmp_path):
        result = storage.save_attachment(b"data", "doc.pdf", "important")
        assert "important" in str(result.saved_path)

    def test_spam_goes_to_spam_dir(self, storage, tmp_path):
        result = storage.save_attachment(b"data", "ad.jpg", "spam")
        assert "spam" in str(result.saved_path)

    def test_unknown_category_goes_to_other(self, storage, tmp_path):
        result = storage.save_attachment(b"data", "file.txt", "unknown_cat")
        assert "other" in str(result.saved_path)

    def test_file_content_preserved(self, storage):
        data = b"exact binary content 123"
        result = storage.save_attachment(data, "test.bin", "other")
        assert result.saved_path.read_bytes() == data

    def test_size_recorded(self, storage):
        data = b"x" * 512
        result = storage.save_attachment(data, "file.bin", "invoice")
        assert result.size == 512

    def test_checksum_recorded(self, storage):
        data = b"hello"
        result = storage.save_attachment(data, "file.txt", "other")
        assert result.checksum == _sha256(data)

    def test_empty_data_returns_none(self, storage):
        result = storage.save_attachment(b"", "empty.pdf", "invoice")
        assert result is None


class TestDuplicateHandling:
    def test_exact_duplicate_skipped(self, storage):
        data = b"same content"
        storage.save_attachment(data, "file.pdf", "invoice")
        result = storage.save_attachment(data, "file.pdf", "invoice")
        assert result is None  # skipped

    def test_same_name_different_content_gets_new_name(self, storage):
        storage.save_attachment(b"content A", "report.pdf", "invoice")
        result = storage.save_attachment(b"content B", "report.pdf", "invoice")
        assert result is not None
        assert result.saved_path.name == "report_1.pdf"

    def test_triple_collision_resolves_sequentially(self, storage):
        storage.save_attachment(b"v1", "doc.pdf", "other")
        storage.save_attachment(b"v2", "doc.pdf", "other")
        result = storage.save_attachment(b"v3", "doc.pdf", "other")
        assert result.saved_path.name == "doc_2.pdf"


class TestFilenamesSanitisation:
    def test_strips_dangerous_chars(self, storage):
        result = storage.save_attachment(b"data", 'bad/name:file*.txt', "other")
        assert "/" not in result.saved_path.name
        assert ":" not in result.saved_path.name
        assert "*" not in result.saved_path.name

    def test_whitespace_replaced(self, storage):
        result = storage.save_attachment(b"data", "my file name.pdf", "other")
        assert " " not in result.saved_path.name

    def test_empty_filename_becomes_unnamed(self, storage):
        result = storage.save_attachment(b"data", "", "other")
        assert result is not None
        assert result.saved_path.name.startswith("unnamed")


class TestBatchSave:
    def test_saves_multiple_attachments(self, storage):
        attachments = [("a.pdf", b"AAA"), ("b.pdf", b"BBB"), ("c.pdf", b"CCC")]
        result = storage.save_attachments(attachments, category="invoice")
        assert len(result.saved) == 3
        assert result.errors == []

    def test_skips_empty_files(self, storage):
        attachments = [("good.pdf", b"data"), ("empty.pdf", b"")]
        result = storage.save_attachments(attachments, category="spam")
        assert len(result.saved) == 1
        assert len(result.skipped) == 1

    def test_list_files_returns_saved(self, storage):
        storage.save_attachment(b"d1", "x.pdf", "invoice")
        storage.save_attachment(b"d2", "y.pdf", "invoice")
        files = storage.list_files("invoice")
        assert len(files) == 2
