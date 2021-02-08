import asyncio
import datetime
import docker
import dask.dataframe as dd
from fsspec.implementations.local import LocalFileSystem
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
import pytest

from adlfs import AzureBlobFileSystem, AzureBlobFile


URL = "http://127.0.0.1:10000"
ACCOUNT_NAME = "devstoreaccount1"
KEY = "Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw=="  # NOQA
CONN_STR = f"DefaultEndpointsProtocol=http;AccountName={ACCOUNT_NAME};AccountKey={KEY};BlobEndpoint={URL}/{ACCOUNT_NAME};"  # NOQA


def assert_almost_equal(x, y, threshold, prop_name=None):
    if x is None and y is None:
        return
    assert abs(x - y) <= threshold


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def spawn_azurite():
    print("Starting azurite docker container")
    client = docker.from_env()
    azurite = client.containers.run(
        "mcr.microsoft.com/azure-storage/azurite", ports={"10000": "10000"}, detach=True
    )
    yield azurite
    print("Teardown azurite docker container")
    azurite.stop()


def test_connect(storage):
    AzureBlobFileSystem(account_name=storage.account_name, connection_string=CONN_STR)


def assert_blob_equals(blob, expected_blob):
    time_based_props = [
        "last_modified",
        "creation_time",
        "deleted_time",
        "last_accessed_on",
    ]
    # creating a shallow copy since we are going to pop properties
    shallow_copy = {**blob}
    for time_based_prop in time_based_props:
        time_value = shallow_copy.pop(time_based_prop, None)
        expected_time_value = expected_blob.pop(time_based_prop, None)
        assert_almost_equal(
            time_value,
            expected_time_value,
            datetime.timedelta(minutes=1),
            prop_name=time_based_prop,
        )
    content_settings = dict(sorted(shallow_copy.pop("content_settings", {}).items()))
    expected_content_settings = dict(
        sorted(expected_blob.pop("content_settings", {}).items())
    )
    assert content_settings == expected_content_settings
    assert shallow_copy == expected_blob


def assert_blobs_equals(blobs, expected_blobs):
    assert len(blobs) == len(expected_blobs)
    for blob, expected_blob in zip(blobs, expected_blobs):
        assert_blob_equals(blob, expected_blob)


def test_ls(storage):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR
    )

    ## these are containers
    assert fs.ls("") == ["data/"]
    assert fs.ls("/") == ["data/"]
    assert fs.ls(".") == ["data/"]

    ## these are top-level directories and files
    assert fs.ls("data") == ["data/root/", "data/top_file.txt"]
    assert fs.ls("/data") == ["data/root/", "data/top_file.txt"]

    # root contains files and directories
    assert fs.ls("data/root") == [
        "data/root/a/",
        "data/root/a1/",
        "data/root/b/",
        "data/root/c/",
        "data/root/d/",
        "data/root/rfile.txt",
    ]
    assert fs.ls("data/root/") == [
        "data/root/a/",
        "data/root/a1/",
        "data/root/b/",
        "data/root/c/",
        "data/root/d/",
        "data/root/rfile.txt",
    ]

    ## slashes are not not needed, but accepted
    assert fs.ls("data/root/a") == ["data/root/a/file.txt"]
    assert fs.ls("data/root/a/") == ["data/root/a/file.txt"]
    assert fs.ls("/data/root/a") == ["data/root/a/file.txt"]
    assert fs.ls("/data/root/a/") == ["data/root/a/file.txt"]
    assert fs.ls("data/root/b") == ["data/root/b/file.txt"]
    assert fs.ls("data/root/b/") == ["data/root/b/file.txt"]
    assert fs.ls("data/root/a1") == ["data/root/a1/file1.txt"]
    assert fs.ls("data/root/a1/") == ["data/root/a1/file1.txt"]

    ## file details
    files = fs.ls("data/root/a/file.txt", detail=True)
    assert_blobs_equals(
        files,
        [
            {
                "name": "data/root/a/file.txt",
                "size": 10,
                "type": "file",
                "archive_status": None,
                "deleted": None,
                "creation_time": storage.insert_time,
                "last_modified": storage.insert_time,
                "deleted_time": None,
                "last_accessed_on": None,
                "remaining_retention_days": None,
                "tag_count": None,
                "tags": None,
                "metadata": {},
                "content_settings": {
                    "content_type": "application/octet-stream",
                    "content_encoding": None,
                    "content_language": None,
                    "content_md5": bytearray(
                        b"x\x1e^$]i\xb5f\x97\x9b\x86\xe2\x8d#\xf2\xc7"
                    ),
                    "content_disposition": None,
                    "cache_control": None,
                },
            }
        ],
    )

    # c has two files
    assert_blobs_equals(
        fs.ls("data/root/c", detail=True),
        [
            {
                "name": "data/root/c/file1.txt",
                "size": 10,
                "type": "file",
                "archive_status": None,
                "deleted": None,
                "creation_time": storage.insert_time,
                "last_modified": storage.insert_time,
                "deleted_time": None,
                "last_accessed_on": None,
                "remaining_retention_days": None,
                "tag_count": None,
                "tags": None,
                "metadata": {},
                "content_settings": {
                    "content_type": "application/octet-stream",
                    "content_encoding": None,
                    "content_language": None,
                    "content_md5": bytearray(
                        b"x\x1e^$]i\xb5f\x97\x9b\x86\xe2\x8d#\xf2\xc7"
                    ),
                    "content_disposition": None,
                    "cache_control": None,
                },
            },
            {
                "name": "data/root/c/file2.txt",
                "size": 10,
                "type": "file",
                "archive_status": None,
                "deleted": None,
                "creation_time": storage.insert_time,
                "last_modified": storage.insert_time,
                "deleted_time": None,
                "last_accessed_on": None,
                "remaining_retention_days": None,
                "tag_count": None,
                "tags": None,
                "metadata": {},
                "content_settings": {
                    "content_type": "application/octet-stream",
                    "content_encoding": None,
                    "content_language": None,
                    "content_md5": bytearray(
                        b"x\x1e^$]i\xb5f\x97\x9b\x86\xe2\x8d#\xf2\xc7"
                    ),
                    "content_disposition": None,
                    "cache_control": None,
                },
            },
        ],
    )

    # with metadata
    assert_blobs_equals(
        fs.ls("data/root/d", detail=True),
        [
            {
                "name": "data/root/d/file_with_metadata.txt",
                "size": 10,
                "type": "file",
                "archive_status": None,
                "deleted": None,
                "creation_time": storage.insert_time,
                "last_modified": storage.insert_time,
                "deleted_time": None,
                "last_accessed_on": None,
                "remaining_retention_days": None,
                "tag_count": None,
                "tags": None,
                "metadata": {"meta": "data"},
                "content_settings": {
                    "content_type": "application/octet-stream",
                    "content_encoding": None,
                    "content_language": None,
                    "content_md5": bytearray(
                        b"x\x1e^$]i\xb5f\x97\x9b\x86\xe2\x8d#\xf2\xc7"
                    ),
                    "content_disposition": None,
                    "cache_control": None,
                },
            }
        ],
    )

    ## if not direct match is found throws error
    with pytest.raises(FileNotFoundError):
        fs.ls("not-a-container")

    with pytest.raises(FileNotFoundError):
        fs.ls("data/not-a-directory/")

    with pytest.raises(FileNotFoundError):
        fs.ls("data/root/not-a-file.txt")


def test_info(storage):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR
    )

    container_info = fs.info("data")
    assert_blob_equals(
        container_info,
        {
            "name": "data/",
            "type": "directory",
            "size": 0,
            "deleted": None,
            "last_modified": storage.insert_time,
            "metadata": None,
        },
    )

    container2_info = fs.info("data/root")
    assert_blob_equals(
        container2_info, {"name": "data/root/", "type": "directory", "size": 0}
    )

    dir_info = fs.info("data/root/c")
    assert_blob_equals(
        dir_info, {"name": "data/root/c/", "type": "directory", "size": 0}
    )

    file_info = fs.info("data/root/a/file.txt")
    assert_blob_equals(
        file_info,
        {
            "name": "data/root/a/file.txt",
            "size": 10,
            "type": "file",
            "archive_status": None,
            "deleted": None,
            "creation_time": storage.insert_time,
            "last_modified": storage.insert_time,
            "deleted_time": None,
            "last_accessed_on": None,
            "remaining_retention_days": None,
            "tag_count": None,
            "tags": None,
            "metadata": {},
            "content_settings": {
                "content_type": "application/octet-stream",
                "content_encoding": None,
                "content_language": None,
                "content_md5": bytearray(
                    b"x\x1e^$]i\xb5f\x97\x9b\x86\xe2\x8d#\xf2\xc7"
                ),
                "content_disposition": None,
                "cache_control": None,
            },
        },
    )
    file_with_meta_info = fs.info("data/root/d/file_with_metadata.txt")
    assert_blob_equals(
        file_with_meta_info,
        {
            "name": "data/root/d/file_with_metadata.txt",
            "size": 10,
            "type": "file",
            "archive_status": None,
            "deleted": None,
            "creation_time": storage.insert_time,
            "last_modified": storage.insert_time,
            "deleted_time": None,
            "last_accessed_on": None,
            "remaining_retention_days": None,
            "tag_count": None,
            "tags": None,
            "metadata": {"meta": "data"},
            "content_settings": {
                "content_type": "application/octet-stream",
                "content_encoding": None,
                "content_language": None,
                "content_md5": bytearray(
                    b"x\x1e^$]i\xb5f\x97\x9b\x86\xe2\x8d#\xf2\xc7"
                ),
                "content_disposition": None,
                "cache_control": None,
            },
        },
    )


def test_find(storage):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR
    )

    ## just the directory name
    assert fs.find("data/root/a") == ["data/root/a/file.txt"]  # NOQA
    assert fs.find("data/root/a/") == ["data/root/a/file.txt"]  # NOQA

    assert fs.find("data/root/c") == [
        "data/root/c/file1.txt",
        "data/root/c/file2.txt",
    ]
    assert fs.find("data/root/c/") == [
        "data/root/c/file1.txt",
        "data/root/c/file2.txt",
    ]

    ## all files
    assert fs.find("data/root") == [
        "data/root/a/file.txt",
        "data/root/a1/file1.txt",
        "data/root/b/file.txt",
        "data/root/c/file1.txt",
        "data/root/c/file2.txt",
        "data/root/d/file_with_metadata.txt",
        "data/root/rfile.txt",
    ]
    assert fs.find("data/root", withdirs=False) == [
        "data/root/a/file.txt",
        "data/root/a1/file1.txt",
        "data/root/b/file.txt",
        "data/root/c/file1.txt",
        "data/root/c/file2.txt",
        "data/root/d/file_with_metadata.txt",
        "data/root/rfile.txt",
    ]

    # all files and directories
    assert fs.find("data/root", withdirs=True) == [
        "data/root/a",
        "data/root/a/file.txt",
        "data/root/a1",
        "data/root/a1/file1.txt",
        "data/root/b",
        "data/root/b/file.txt",
        "data/root/c",
        "data/root/c/file1.txt",
        "data/root/c/file2.txt",
        "data/root/d",
        "data/root/d/file_with_metadata.txt",
        "data/root/rfile.txt",
    ]
    assert fs.find("data/root/", withdirs=True) == [
        "data/root/a",
        "data/root/a/file.txt",
        "data/root/a1",
        "data/root/a1/file1.txt",
        "data/root/b",
        "data/root/b/file.txt",
        "data/root/c",
        "data/root/c/file1.txt",
        "data/root/c/file2.txt",
        "data/root/d",
        "data/root/d/file_with_metadata.txt",
        "data/root/rfile.txt",
    ]

    ## missing
    assert fs.find("data/missing") == []

    ## prefix search
    assert fs.find("data/root", prefix="a") == [
        "data/root/a/file.txt",
        "data/root/a1/file1.txt",
    ]

    assert fs.find("data/root", prefix="a", withdirs=True) == [
        "data/root/a",
        "data/root/a/file.txt",
        "data/root/a1",
        "data/root/a1/file1.txt",
    ]

    find_results = fs.find("data/root", prefix="a1", withdirs=True, detail=True)
    assert_blobs_equals(
        list(find_results.values()),
        [
            {"name": "data/root/a1", "size": 0, "type": "directory"},
            {
                "name": "data/root/a1/file1.txt",
                "size": 10,
                "type": "file",
                "archive_status": None,
                "deleted": None,
                "creation_time": storage.insert_time,
                "last_modified": storage.insert_time,
                "deleted_time": None,
                "last_accessed_on": None,
                "remaining_retention_days": None,
                "tag_count": None,
                "tags": None,
                "metadata": {},
                "content_settings": {
                    "content_type": "application/octet-stream",
                    "content_encoding": None,
                    "content_language": None,
                    "content_md5": bytearray(
                        b"x\x1e^$]i\xb5f\x97\x9b\x86\xe2\x8d#\xf2\xc7"
                    ),
                    "content_disposition": None,
                    "cache_control": None,
                },
            },
        ],
    )


# @pytest.mark.xfail
def test_find_missing(storage):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR
    )
    assert fs.find("data/roo") == []


def test_glob(storage):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR
    )

    ## just the directory name
    assert fs.glob("data/root") == ["data/root"]

    # top-level contents of a directory
    assert fs.glob("data/root/") == [
        "data/root/a",
        "data/root/a1",
        "data/root/b",
        "data/root/c",
        "data/root/d",
        "data/root/rfile.txt",
    ]
    assert fs.glob("data/root/*") == [
        "data/root/a",
        "data/root/a1",
        "data/root/b",
        "data/root/c",
        "data/root/d",
        "data/root/rfile.txt",
    ]

    assert fs.glob("data/root/b/*") == ["data/root/b/file.txt"]  # NOQA
    assert fs.glob("data/root/b/**") == ["data/root/b/file.txt"]  # NOQA

    ## across directories
    assert fs.glob("data/root/*/file.txt") == [
        "data/root/a/file.txt",
        "data/root/b/file.txt",
    ]

    ## regex match
    assert fs.glob("data/root/*/file[0-9].txt") == [
        "data/root/a1/file1.txt",
        "data/root/c/file1.txt",
        "data/root/c/file2.txt",
    ]

    ## text files
    assert fs.glob("data/root/*/file*.txt") == [
        "data/root/a/file.txt",
        "data/root/a1/file1.txt",
        "data/root/b/file.txt",
        "data/root/c/file1.txt",
        "data/root/c/file2.txt",
        "data/root/d/file_with_metadata.txt",
    ]

    ## all text files
    assert fs.glob("data/**/*.txt") == [
        "data/root/a/file.txt",
        "data/root/a1/file1.txt",
        "data/root/b/file.txt",
        "data/root/c/file1.txt",
        "data/root/c/file2.txt",
        "data/root/d/file_with_metadata.txt",
        "data/root/rfile.txt",
    ]

    ## all files
    assert fs.glob("data/root/**") == [
        "data/root/a",
        "data/root/a/file.txt",
        "data/root/a1",
        "data/root/a1/file1.txt",
        "data/root/b",
        "data/root/b/file.txt",
        "data/root/c",
        "data/root/c/file1.txt",
        "data/root/c/file2.txt",
        "data/root/d",
        "data/root/d/file_with_metadata.txt",
        "data/root/rfile.txt",
    ]
    assert fs.glob("data/roo**") == [
        "data/root",
        "data/root/a",
        "data/root/a/file.txt",
        "data/root/a1",
        "data/root/a1/file1.txt",
        "data/root/b",
        "data/root/b/file.txt",
        "data/root/c",
        "data/root/c/file1.txt",
        "data/root/c/file2.txt",
        "data/root/d",
        "data/root/d/file_with_metadata.txt",
        "data/root/rfile.txt",
    ]

    ## missing
    assert fs.glob("data/missing/*") == []


def test_open_file(storage, mocker):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR
    )
    f = fs.open("/data/root/a/file.txt")

    result = f.read()
    assert result == b"0123456789"

    close = mocker.patch.object(f.container_client, "close")
    f.close()

    close.assert_called_once()

def test_open_context_manager(storage, mocker):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR
    )
    with fs.open("/data/root/a/file.txt") as f:
        close = mocker.patch.object(f.container_client, "close")
        result = f.read()
        assert result == b"0123456789"

    close.assert_called_once()



def test_rm(storage):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR
    )

    fs.rm("/data/root/a/file.txt")

    with pytest.raises(FileNotFoundError):
        fs.ls("/data/root/a/file.txt", refresh=True)


def test_rm_recursive(storage):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR
    )

    assert "data/root/c/" in fs.ls("/data/root")

    assert fs.ls("data/root/c") == [
        "data/root/c/file1.txt",
        "data/root/c/file2.txt",
    ]
    fs.rm("data/root/c", recursive=True)
    assert "data/root/c/" not in fs.ls("/data/root")

    with pytest.raises(FileNotFoundError):
        fs.ls("data/root/c")


def test_mkdir(storage):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR,
    )

    # Verify mkdir will create a new container when create_parents is True
    fs.mkdir("new-container", create_parents=True)
    assert "new-container/" in fs.ls(".")
    fs.rm("new-container")

    # Verify a new container will not be created when create_parents
    # is False
    with pytest.raises(PermissionError):
        fs.mkdir("new-container", create_parents=False)

    # Test creating subdirectory when container does not exist
    fs.mkdir("new-container/dir", create_parents=True)
    assert "new-container/dir" in fs.ls("new-container")
    fs.rm("new-container", recursive=True)

    # Test raising error when container does not exist
    with pytest.raises(PermissionError):
        fs.mkdir("new-container/dir", create_parents=False)


def test_makedir(storage):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR,
    )

    # Verify makedir will create a new container when create_parents is True
    with pytest.raises(FileExistsError):
        fs.makedir("data", exist_ok=False)

    # The container and directory already exist.  Should pass
    fs.makedir("data", exist_ok=True)
    assert "data/" in fs.ls(".")

    # Test creating subdirectory when container does not exist
    fs.makedir("new-container/dir")
    assert "new-container/dir" in fs.ls("new-container")
    fs.rm("new-container", recursive=True)


def test_makedir_rmdir(storage, caplog):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR,
    )

    fs.makedir("new-container")
    assert "new-container/" in fs.ls("")
    assert fs.ls("new-container") == []

    with fs.open(path="new-container/file.txt", mode="wb") as f:
        f.write(b"0123456789")

    with fs.open("new-container/dir/file.txt", "wb") as f:
        f.write(b"0123456789")

    with fs.open("new-container/dir/file2.txt", "wb") as f:
        f.write(b"0123456789")

    # Verify that mkdir will raise an exception if the directory exists
    # and exist_ok is False
    with pytest.raises(FileExistsError):
        fs.makedir("new-container/dir/file.txt", exist_ok=False)

    # Verify that mkdir creates a directory if exist_ok is False and the
    # directory does not exist
    fs.makedir("new-container/file2.txt", exist_ok=False)
    assert "new-container/file2.txt" in fs.ls("new-container")

    # Verify that mkdir will silently ignore an existing directory if
    # the directory exists and exist_ok is True
    fs.makedir("new-container/dir", exist_ok=True)
    assert "new-container/dir/" in fs.ls("new-container")

    # Test to verify that the file contains expected contents
    with fs.open("new-container/file2.txt", "rb") as f:
        outfile = f.read()
    assert outfile == b""

    # Check that trying to overwrite an existing nested file in append mode works as expected
    # if exist_ok is True
    fs.makedir("new-container/dir/file2.txt", exist_ok=True)
    assert "new-container/dir/file2.txt" in fs.ls("new-container/dir")

    # Also verify you can make a nested directory structure
    fs.makedir("new-container/dir2/file.txt", exist_ok=False)
    with fs.open("new-container/dir2/file.txt", "wb") as f:
        f.write(b"0123456789")
    assert "new-container/dir2/file.txt" in fs.ls("new-container/dir2")
    fs.rm("new-container/dir2", recursive=True)

    fs.rm("new-container/dir", recursive=True)
    assert fs.ls("new-container") == [
        "new-container/file.txt",
        "new-container/file2.txt",
    ]

    fs.rm("new-container/file.txt")
    fs.rm("new-container/file2.txt")
    fs.rmdir("new-container")

    assert "new-container/" not in fs.ls("")


@pytest.mark.skip
def test_append_operation(storage):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR
    )
    fs.mkdir("append-container")

    # Check that appending to an existing file works as expected
    with fs.open("append-container/append_file.txt", "ab") as f:
        f.write(b"0123456789")
    with fs.open("append-container/append_file.txt", "ab") as f:
        f.write(b"0123456789")
    with fs.open("new-container/dir/file2.txt", "rb") as f:
        outfile = f.read()
    assert outfile == b"01234567890123456789"

    fs.rm("append-container", recursive=True)


def test_mkdir_rm_recursive(storage):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR
    )

    fs.mkdir("test_mkdir_rm_recursive")
    assert "test_mkdir_rm_recursive/" in fs.ls("")

    with fs.open("test_mkdir_rm_recursive/file.txt", "wb") as f:
        f.write(b"0123456789")

    with fs.open("test_mkdir_rm_recursive/dir/file.txt", "wb") as f:
        f.write(b"ABCD")

    with fs.open("test_mkdir_rm_recursive/dir/file2.txt", "wb") as f:
        f.write(b"abcdef")

    assert fs.find("test_mkdir_rm_recursive") == [
        "test_mkdir_rm_recursive/dir/file.txt",
        "test_mkdir_rm_recursive/dir/file2.txt",
        "test_mkdir_rm_recursive/file.txt",
    ]

    fs.rm("test_mkdir_rm_recursive", recursive=True)

    assert "test_mkdir_rm_recursive/" not in fs.ls("")
    assert fs.find("test_mkdir_rm_recursive") == []


def test_deep_paths(storage):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR
    )

    fs.mkdir("test_deep")
    assert "test_deep/" in fs.ls("")

    with fs.open("test_deep/a/b/c/file.txt", "wb") as f:
        f.write(b"0123456789")

    assert fs.ls("test_deep") == ["test_deep/a/"]
    assert fs.ls("test_deep/") == ["test_deep/a/"]
    assert fs.ls("test_deep/a") == ["test_deep/a/b/"]
    assert fs.ls("test_deep/a/") == ["test_deep/a/b/"]
    assert fs.find("test_deep") == ["test_deep/a/b/c/file.txt"]
    assert fs.find("test_deep/") == ["test_deep/a/b/c/file.txt"]
    assert fs.find("test_deep/a") == ["test_deep/a/b/c/file.txt"]
    assert fs.find("test_deep/a/") == ["test_deep/a/b/c/file.txt"]

    fs.rm("test_deep", recursive=True)

    assert "test_deep/" not in fs.ls("")
    assert fs.find("test_deep") == []


def test_large_blob(storage):
    import tempfile
    import hashlib
    import io
    import shutil
    from pathlib import Path

    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR
    )

    # create a 20MB byte array, ensure it's larger than blocksizes to force a
    # chuncked upload
    blob_size = 120_000_000
    # blob_size = 2_684_354_560
    assert blob_size > fs.blocksize
    assert blob_size > AzureBlobFile.DEFAULT_BLOCK_SIZE

    data = b"1" * blob_size
    _hash = hashlib.md5(data)
    expected = _hash.hexdigest()

    # create container
    fs.mkdir("chunk-container")

    # upload the data using fs.open
    path = "chunk-container/large-blob.bin"
    with fs.open(path, "ab") as dst:
        dst.write(data)

    assert fs.exists(path)
    assert fs.size(path) == blob_size

    del data

    # download with fs.open
    bio = io.BytesIO()
    with fs.open(path, "rb") as src:
        shutil.copyfileobj(src, bio)

    # read back the data and calculate md5
    bio.seek(0)
    data = bio.read()
    _hash = hashlib.md5(data)
    result = _hash.hexdigest()

    assert expected == result

    # do the same but using upload/download and a tempdir
    path = path = "chunk-container/large_blob2.bin"
    with tempfile.TemporaryDirectory() as td:
        local_blob: Path = Path(td) / "large_blob2.bin"
        with local_blob.open("wb") as fo:
            fo.write(data)
        assert local_blob.exists()
        assert local_blob.stat().st_size == blob_size

        fs.upload(str(local_blob), path)
        assert fs.exists(path)
        assert fs.size(path) == blob_size

        # download now
        local_blob.unlink()
        fs.download(path, str(local_blob))
        assert local_blob.exists()
        assert local_blob.stat().st_size == blob_size


def test_dask_parquet(storage):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR
    )
    fs.mkdir("test")
    STORAGE_OPTIONS = {
        "account_name": "devstoreaccount1",
        "connection_string": CONN_STR,
    }
    df = pd.DataFrame(
        {
            "col1": [1, 2, 3, 4],
            "col2": [2, 4, 6, 8],
            "index_key": [1, 1, 2, 2],
            "partition_key": [1, 1, 2, 2],
        }
    )

    dask_dataframe = dd.from_pandas(df, npartitions=1)
    for protocol in ["abfs", "az"]:
        dask_dataframe.to_parquet(
            "{}://test/test_group.parquet".format(protocol),
            storage_options=STORAGE_OPTIONS,
            engine="pyarrow",
        )

        fs = AzureBlobFileSystem(**STORAGE_OPTIONS)
        assert fs.ls("test/test_group.parquet") == [
            "test/test_group.parquet/_common_metadata",
            "test/test_group.parquet/_metadata",
            "test/test_group.parquet/part.0.parquet",
        ]
        fs.rm("test/test_group.parquet")

    df_test = dd.read_parquet(
        "abfs://test/test_group.parquet",
        storage_options=STORAGE_OPTIONS,
        engine="pyarrow",
    ).compute()
    assert_frame_equal(df, df_test)

    A = np.random.randint(0, 100, size=(10000, 4))
    df2 = pd.DataFrame(data=A, columns=list("ABCD"))
    ddf2 = dd.from_pandas(df2, npartitions=4)
    dd.to_parquet(
        ddf2,
        "abfs://test/test_group2.parquet",
        storage_options=STORAGE_OPTIONS,
        engine="pyarrow",
    )
    assert fs.ls("test/test_group2.parquet") == [
        "test/test_group2.parquet/_common_metadata",
        "test/test_group2.parquet/_metadata",
        "test/test_group2.parquet/part.0.parquet",
        "test/test_group2.parquet/part.1.parquet",
        "test/test_group2.parquet/part.2.parquet",
        "test/test_group2.parquet/part.3.parquet",
    ]
    df2_test = dd.read_parquet(
        "abfs://test/test_group2.parquet",
        storage_options=STORAGE_OPTIONS,
        engine="pyarrow",
    ).compute()
    assert_frame_equal(df2, df2_test)

    a = np.full(shape=(10000, 1), fill_value=1)
    b = np.full(shape=(10000, 1), fill_value=2)
    c = np.full(shape=(10000, 1), fill_value=3)
    d = np.full(shape=(10000, 1), fill_value=4)
    B = np.concatenate((a, b, c, d), axis=1)
    df3 = pd.DataFrame(data=B, columns=list("ABCD"))
    ddf3 = dd.from_pandas(df3, npartitions=4)
    dd.to_parquet(
        ddf3,
        "abfs://test/test_group3.parquet",
        partition_on=["A", "B"],
        storage_options=STORAGE_OPTIONS,
        engine="pyarrow",
    )
    assert fs.glob("test/test_group3.parquet/*") == [
        "test/test_group3.parquet/A=1",
        "test/test_group3.parquet/_common_metadata",
        "test/test_group3.parquet/_metadata",
    ]
    df3_test = dd.read_parquet(
        "abfs://test/test_group3.parquet",
        filters=[("A", "=", 1)],
        storage_options=STORAGE_OPTIONS,
        engine="pyarrow",
    ).compute()
    df3_test = df3_test[["A", "B", "C", "D"]]
    df3_test = df3_test[["A", "B", "C", "D"]].astype(int)
    assert_frame_equal(df3, df3_test)

    A = np.random.randint(0, 100, size=(10000, 4))
    df4 = pd.DataFrame(data=A, columns=list("ABCD"))
    ddf4 = dd.from_pandas(df4, npartitions=4)
    dd.to_parquet(
        ddf4,
        "abfs://test/test_group4.parquet",
        storage_options=STORAGE_OPTIONS,
        engine="pyarrow",
        flavor="spark",
        write_statistics=False,
    )
    fs.rmdir("test/test_group4.parquet/_common_metadata", recursive=True)
    fs.rmdir("test/test_group4.parquet/_metadata", recursive=True)
    fs.rm("test/test_group4.parquet/_common_metadata")
    fs.rm("test/test_group4.parquet/_metadata")
    assert fs.ls("test/test_group4.parquet") == [
        "test/test_group4.parquet/part.0.parquet",
        "test/test_group4.parquet/part.1.parquet",
        "test/test_group4.parquet/part.2.parquet",
        "test/test_group4.parquet/part.3.parquet",
    ]
    df4_test = dd.read_parquet(
        "abfs://test/test_group4.parquet",
        storage_options=STORAGE_OPTIONS,
        engine="pyarrow",
    ).compute()
    assert_frame_equal(df4, df4_test)

    A = np.random.randint(0, 100, size=(10000, 4))
    df5 = pd.DataFrame(data=A, columns=list("ABCD"))
    ddf5 = dd.from_pandas(df5, npartitions=4)
    dd.to_parquet(
        ddf5,
        "abfs://test/test group5.parquet",
        storage_options=STORAGE_OPTIONS,
        engine="pyarrow",
    )
    assert fs.ls("test/test group5.parquet") == [
        "test/test group5.parquet/_common_metadata",
        "test/test group5.parquet/_metadata",
        "test/test group5.parquet/part.0.parquet",
        "test/test group5.parquet/part.1.parquet",
        "test/test group5.parquet/part.2.parquet",
        "test/test group5.parquet/part.3.parquet",
    ]
    df5_test = dd.read_parquet(
        "abfs://test/test group5.parquet",
        storage_options=STORAGE_OPTIONS,
        engine="pyarrow",
    ).compute()
    assert_frame_equal(df5, df5_test)


def test_metadata_write(storage):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR
    )
    fs.mkdir("test_metadata_write")
    data = b"0123456789"
    metadata = {"meta": "data"}

    # standard blob type
    with fs.open("test_metadata_write/file.txt", "wb", metadata=metadata) as f:
        f.write(data)
    info = fs.info("test_metadata_write/file.txt")
    assert info["metadata"] == metadata
    metadata_changed_on_write = {"meta": "datum"}
    with fs.open(
        "test_metadata_write/file.txt", "wb", metadata=metadata_changed_on_write
    ) as f:
        f.write(data)
    info = fs.info("test_metadata_write/file.txt")
    assert info["metadata"] == metadata_changed_on_write

    # append blob type
    new_metadata = {"data": "meta"}
    with fs.open("test_metadata_write/append-file.txt", "ab", metadata=metadata) as f:
        f.write(data)

    # try change metadata on block appending
    with fs.open(
        "test_metadata_write/append-file.txt", "ab", metadata=new_metadata
    ) as f:
        f.write(data)
    info = fs.info("test_metadata_write/append-file.txt")

    # azure blob client doesn't seem to support metadata mutation when appending blocks
    # lets be sure this behavior doesn't change as this would imply
    # a potential breaking change
    assert info["metadata"] == metadata

    # getxattr / setxattr
    assert fs.getxattr("test_metadata_write/file.txt", "meta") == "datum"
    fs.setxattrs("test_metadata_write/file.txt", metadata="data2")
    assert fs.getxattr("test_metadata_write/file.txt", "metadata") == "data2"
    assert fs.info("test_metadata_write/file.txt")["metadata"] == {"metadata": "data2"}

    # empty file and nested directory
    with fs.open(
        "test_metadata_write/a/b/c/nested-file.txt", "wb", metadata=metadata
    ) as f:
        f.write(b"")
    assert fs.getxattr("test_metadata_write/a/b/c/nested-file.txt", "meta") == "data"
    fs.setxattrs("test_metadata_write/a/b/c/nested-file.txt", metadata="data2")
    assert fs.info("test_metadata_write/a/b/c/nested-file.txt")["metadata"] == {
        "metadata": "data2"
    }
    fs.rmdir("test_metadata_write")


def test_put_file(storage):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR
    )
    lfs = LocalFileSystem()

    fs.mkdir("putdir")

    # Check that put on an empty file works
    with open("sample.txt", "wb") as f:
        f.write(b"")
    fs.put("sample.txt", "putdir/sample.txt")
    fs.get("putdir/sample.txt", "sample2.txt")

    with open("sample.txt", "rb") as f:
        f1 = f.read()
    with open("sample2.txt", "rb") as f:
        f2 = f.read()
    assert f1 == f2

    lfs.rm("sample.txt")
    lfs.rm("sample2.txt")

    # Check that put on a file with data works
    with open("sample3.txt", "wb") as f:
        f.write(b"01234567890")
    fs.put("sample3.txt", "putdir/sample3.txt")
    fs.get("putdir/sample3.txt", "sample4.txt")
    with open("sample3.txt", "rb") as f:
        f3 = f.read()
    with open("sample4.txt", "rb") as f:
        f4 = f.read()
    assert f3 == f4
    fs.rm("putdir", recursive=True)


@pytest.mark.skip
def test_isdir(storage):
    pass


def test_cat(storage):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR
    )
    fs.mkdir("catdir")
    data = b"0123456789"
    with fs.open("catdir/catfile.txt", "wb") as f:
        f.write(data)
    assert fs.cat("catdir/catfile.txt") == data
    fs.rm("catdir/catfile.txt")


def test_cp_file(storage):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR
    )
    fs.mkdir("homedir")
    fs.mkdir("homedir/enddir")
    fs.touch("homedir/startdir/test_file.txt")
    fs.cp_file("homedir/startdir/test_file.txt", "homedir/enddir/test_file.txt")
    files = fs.ls("homedir/enddir")
    assert "homedir/enddir/test_file.txt" in files

    fs.rm("homedir", recursive=True)


def test_exists(storage):
    fs = AzureBlobFileSystem(
        account_name=storage.account_name, connection_string=CONN_STR
    )

    assert fs.exists("data/top_file.txt")
    assert fs.exists("data")
    assert fs.exists("data/")
    assert fs.exists("")
    assert not fs.exists("data/not-a-key")
