import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
from io import BytesIO
from fastapi import UploadFile

from app.storage.azure_blob_storage import AzureBlobStorageProvider
from app.storage.local_storage import get_storage_provider, LocalStorageProvider
from app.core.config import settings


def test_default_storage_provider_is_local():
    """Verify local storage provider remains default without breaking existing setup."""
    provider = get_storage_provider()
    assert isinstance(provider, LocalStorageProvider)


@patch("app.storage.azure_blob_storage.BlobServiceClient")
def test_azure_blob_provider_connection_string_init(mock_blob_service_client):
    provider = AzureBlobStorageProvider(
        connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=fake;EndpointSuffix=core.windows.net",
        container_name="test-container"
    )
    assert provider.container_name == "test-container"
    # Access client
    client = provider._get_client()
    mock_blob_service_client.from_connection_string.assert_called_once()


@patch("app.storage.azure_blob_storage.DefaultAzureCredential")
@patch("app.storage.azure_blob_storage.BlobServiceClient")
def test_azure_blob_provider_managed_identity_init(mock_blob_service_client, mock_credential):
    provider = AzureBlobStorageProvider(
        account_url="https://testautohr.blob.core.windows.net",
        container_name="autohr-data"
    )
    client = provider._get_client()
    mock_credential.assert_called_once()
    mock_blob_service_client.assert_called_once_with(
        account_url="https://testautohr.blob.core.windows.net",
        credential=mock_credential.return_value
    )


@patch("app.storage.azure_blob_storage.BlobServiceClient")
def test_azure_blob_provider_exists(mock_blob_service_client):
    mock_instance = MagicMock()
    mock_container = MagicMock()
    mock_blob = MagicMock()
    mock_blob.exists.return_value = True
    mock_container.get_blob_client.return_value = mock_blob
    mock_instance.get_container_client.return_value = mock_container
    mock_blob_service_client.from_connection_string.return_value = mock_instance

    provider = AzureBlobStorageProvider(connection_string="fake-conn-str", container_name="test")
    assert provider.exists("presentations/deck.pptx") is True
    mock_container.get_blob_client.assert_called_with("presentations/deck.pptx")
    assert provider.exists("") is False


@patch("app.storage.azure_blob_storage.BlobServiceClient")
def test_azure_blob_provider_delete(mock_blob_service_client):
    mock_instance = MagicMock()
    mock_container = MagicMock()
    mock_blob = MagicMock()
    mock_container.get_blob_client.return_value = mock_blob
    mock_instance.get_container_client.return_value = mock_container
    mock_blob_service_client.from_connection_string.return_value = mock_instance

    provider = AzureBlobStorageProvider(connection_string="fake-conn-str", container_name="test")
    res = provider.delete("presentations/deck.pptx")
    assert res is True
    mock_blob.delete_blob.assert_called_once()


@pytest.mark.asyncio
@patch("app.storage.azure_blob_storage.BlobServiceClient")
async def test_azure_blob_provider_save_file(mock_blob_service_client):
    mock_instance = MagicMock()
    mock_container = MagicMock()
    mock_blob = MagicMock()
    mock_container.get_blob_client.return_value = mock_blob
    mock_instance.get_container_client.return_value = mock_container
    mock_blob_service_client.from_connection_string.return_value = mock_instance

    provider = AzureBlobStorageProvider(connection_string="fake-conn-str", container_name="test")
    raw_data = b"Hello AutoHR Azure Blob Storage"
    file = UploadFile(filename="test_file.txt", file=BytesIO(raw_data))

    filename, storage_key, size, file_hash = await provider.save_file(file, "employee_lists")
    assert filename == "test_file.txt"
    assert storage_key == "employee_lists/test_file.txt"
    assert size == len(raw_data)
    mock_blob.upload_blob.assert_called_once_with(raw_data, overwrite=True)


def test_secure_storage_open_decrypted_file_local_unencrypted(tmp_path):
    """Test secure_storage open_decrypted_file with local unencrypted legacy file."""
    from app.core.security.secure_storage import secure_storage

    test_file = tmp_path / "legacy.pptx"
    test_file.write_bytes(b"legacy presentation content")

    mock_entity = MagicMock()
    mock_entity.storage_path = str(test_file)
    mock_entity.encryption_version = 0

    with secure_storage.open_decrypted_file(mock_entity) as path:
        assert Path(path).exists()
        assert Path(path).read_bytes() == b"legacy presentation content"


@patch("app.core.security.secure_storage.get_storage_provider")
def test_secure_storage_open_decrypted_file_uses_configured_provider(mock_get_provider, tmp_path):
    """Regression test: secure_storage.open_decrypted_file resolves path via configured provider."""
    from app.core.security.secure_storage import secure_storage

    dummy_file = tmp_path / "cached_download.pptx"
    dummy_file.write_bytes(b"downloaded azure content")

    mock_provider = MagicMock()
    mock_provider.get_path.return_value = dummy_file
    mock_get_provider.return_value = mock_provider

    mock_entity = MagicMock()
    mock_entity.storage_path = "presentations/cached_download.pptx"
    mock_entity.encryption_version = 0

    with secure_storage.open_decrypted_file(mock_entity) as path:
        assert Path(path).exists()
        assert Path(path).read_bytes() == b"downloaded azure content"

    mock_get_provider.assert_called_once()
    mock_provider.get_path.assert_called_once_with("presentations/cached_download.pptx")

