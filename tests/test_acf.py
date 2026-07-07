from steam_dl.steam.acf import parse_acf

_DOWNLOADING = '''
"AppState"
{
    "appid"  "220"
    "installdir"  "Half-Life 2"
    "StateFlags"  "1026"
    "BytesDownloaded"  "500"
    "BytesToDownload"  "1000"
}
'''

_INSTALLED = '''
"AppState"
{
    "appid"  "220"
    "installdir"  "Half-Life 2"
    "StateFlags"  "4"
    "BytesDownloaded"  "1000"
    "BytesToDownload"  "1000"
}
'''

# StateFlags shows the installed bit but a commit is still in progress and
# bytes disagree -- must NOT be treated as done.
_INSTALLED_BUT_COMMITTING = '''
"AppState"
{
    "appid"  "220"
    "StateFlags"  "4100"
    "BytesDownloaded"  "900"
    "BytesToDownload"  "1000"
}
'''


def test_downloading_not_installed():
    st = parse_acf(_DOWNLOADING)
    assert not st.is_fully_installed
    assert 0.49 < st.progress < 0.51
    assert "downloading" in st.describe_flags()


def test_installed():
    st = parse_acf(_INSTALLED)
    assert st.is_fully_installed
    assert st.installdir == "Half-Life 2"
    assert st.progress == 1.0


def test_in_progress_bit_blocks_completion():
    st = parse_acf(_INSTALLED_BUT_COMMITTING)
    assert not st.is_fully_installed
