#!/usr/bin/env bash
set -e

echo "Installing dependencies..."
sudo apt-get update
sudo apt-get install -y python3 python3-gi python3-matplotlib gir1.2-gtk-3.0

echo "Creating local .desktop file..."
mkdir -p ~/.local/share/applications


SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXEC_PATH="$SCRIPT_DIR/battery_monitor.py"
ICON_PATH="$SCRIPT_DIR/icon.png"

chmod +x "$EXEC_PATH"

# .desktop file creation
cat <<EOF > ~/.local/share/applications/battery_monitor.desktop
[Desktop Entry]
Name= Simple Battery Manager
Comment=Battery monitoring tool and power profile control center
Exec=python3 $EXEC_PATH
Icon=$ICON_PATH
Terminal=false
Type=Application
Categories=Utility;
EOF

echo "Updating desktop database..."
update-desktop-database ~/.local/share/applications || true

echo "Installation complete."
echo "You can now find 'Battery Monitor' in your application menu (may require re-login)."
