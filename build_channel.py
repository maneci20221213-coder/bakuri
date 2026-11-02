"""Developer edition: separate settings, IPC and shortcut from installed releases."""
from version import VERSION
DEVELOPMENT=True
SETTINGS_APP='FileConverterDevelopment'
SERVER_NAME='BakuriDevelopment'
BUILD_LABEL=f'개발용 {VERSION}-dev.17'
DEFAULT_HOTKEY='F9' if DEVELOPMENT else '` (백틱)'
