# Autostart on this Mac

id: autostart
short: The tracker starts by itself at login and restarts if it crashes, so data keeps flowing while you are away.

## What it is
A macOS "launch agent" (co.soclose.elninowatch) that runs the tracker in the
background at login and restarts it within about 15 seconds if it stops. It serves
http://127.0.0.1:8911 on this Mac only.

## How to read it
`./start.sh status` shows whether the agent is loaded and the server answers.
`./start.sh stop` really stops it (the agent is unloaded so it does not restart);
`./start.sh` starts it again; `./start.sh uninstall` removes autostart.

## Why it matters for Koh Samui
Alerts only help if the collectors keep running. A tracker that stopped silently
after a reboot would show old data.

## Limits
It runs only while the Mac is on and logged in. macOS privacy protection blocks
background programs from the Documents folder unless the program was allowed; the
agent therefore runs with Homebrew's Python, which has that permission here. If the
Mac is reinstalled, that permission may need to be granted again (System Settings >
Privacy & Security).

## Sources
- Apple, creating launchd jobs: https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html
- Apple, file and folder access on Mac: https://support.apple.com/guide/mac-help/control-access-to-files-and-folders-on-mac-mchld5a35146/mac
