#!/usr/bin/env bash
# Mouse-friendly emergency ungrab — does NOT need a working Enter key.
# Double-click the .desktop launcher, or run this from a GUI "Run command".
exec pkexec /usr/bin/platform-bt-fn-row panic
