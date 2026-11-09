# Third-party materials

Character stroke medians in `assets/hanzi/` originate from Hanzi Writer Data / Make Me a Hanzi and Arphic fonts. Their Arphic Public License is included at `assets/hanzi/ARPHICPL.TXT`. Source: https://github.com/chanind/hanzi-writer-data . New characters are fetched from hanzi-writer-data 2.0.1 and cached in the lesson workspace.

The rendering and course scripts were developed from the notebook prototype in this conversation. No Frametell engine code is bundled. edulab and whiteboard-teacher-video were reviewed as workflow and integration references; their pinned versions and adoption decisions are recorded in `references/upstream-study.md`.

Pillow and edge-tts are external runtime packages installed separately under their respective licenses. FFmpeg and a user-selected Chinese font are required locally and are not bundled.
## Optional animation engines

Motion Canvas (MIT): https://github.com/motion-canvas/motion-canvas

Manim Community (MIT): https://github.com/ManimCommunity/manim

These engines are installed separately through their official npm/Python distributions, which retain their upstream license files. The course adapters and sample scene in this skill are project-specific integration code.
