from unittest.mock import MagicMock, patch


def test_upload_pdf_uploads_to_correct_folder():
    from backend.drive import DriveClient

    mock_svc = MagicMock()
    # Three list() calls: root found, Payslips/ missing, 2026-04/ missing
    mock_svc.files.return_value.list.return_value.execute.side_effect = [
        {"files": [{"id": "root-id"}]},
        {"files": []},
        {"files": []},
    ]
    # Three create() calls: Payslips/ folder, 2026-04/ folder, file upload
    mock_svc.files.return_value.create.return_value.execute.side_effect = [
        {"id": "type-id"},
        {"id": "month-id"},
        {"id": "file-id"},
    ]

    with patch("backend.drive.build_drive_service", return_value=mock_svc):
        client = DriveClient()
        client.upload_pdf(b"pdf-data", "payslip.pdf", "Payslips", "2026-04")

    assert mock_svc.files.return_value.create.call_count == 3
    last_call = mock_svc.files.return_value.create.call_args_list[2]
    assert last_call.kwargs["body"]["name"] == "payslip.pdf"
    assert last_call.kwargs["body"]["parents"] == ["month-id"]


def test_upload_pdf_skips_when_root_not_found():
    from backend.drive import DriveClient

    mock_svc = MagicMock()
    mock_svc.files.return_value.list.return_value.execute.return_value = {"files": []}

    with patch("backend.drive.build_drive_service", return_value=mock_svc):
        client = DriveClient()
        client.upload_pdf(b"pdf-data", "payslip.pdf", "Payslips", "2026-04")

    mock_svc.files.return_value.create.assert_not_called()
