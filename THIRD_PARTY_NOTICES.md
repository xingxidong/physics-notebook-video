# Third-party materials

Academic Humanizer 1.1 is bundled under `assets/academic-humanizer/` with its guide, examples, Chinese-language notes, lexicon, and revision checker. See `assets/academic-humanizer/LICENSE.txt` for the MIT license and original notices.

The local voice installer downloads the Apache-2.0 MLX conversion of Qwen3-TTS 0.6B Base 8-bit from https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit/tree/50f45ef0047cde7e84c2ef04326acb8ada2436a7 .

The authored starter-kit text, TikZ and templates have their notice in `assets/starter-kit/LICENSE.md`. Its new audio was synthesized from those texts with the public Kokoro-82M preset `zm_yunxi`, using locally cached Apache-2.0 model weights; no personal teacher reference was used. Model source: https://huggingface.co/hexgrad/Kokoro-82M . Exact model revision and audio hashes are in each example's `audio-provenance.json`. Neither Kokoro nor Qwen model weights are bundled.

Character stroke medians in `assets/hanzi/` originate from Hanzi Writer Data / Make Me a Hanzi and Arphic fonts. Their Arphic Public License is included at `assets/hanzi/ARPHICPL.TXT`. Source: https://github.com/chanind/hanzi-writer-data . New characters are fetched from hanzi-writer-data 2.0.1 and cached in the lesson workspace.

The rendering and course scripts were developed from the notebook prototype in this conversation. No Frametell or khan-explainer engine code is bundled. edulab, whiteboard-teacher-video, and khan-explainer were reviewed as workflow and integration references; their pinned versions and adoption decisions are recorded in `references/upstream-study.md`.

Pillow and edge-tts are external runtime packages installed separately under their respective licenses. FFmpeg and a user-selected Chinese font are required locally and are not bundled.
## Optional animation engines

Motion Canvas (MIT): https://github.com/motion-canvas/motion-canvas

Manim Community (MIT): https://github.com/ManimCommunity/manim

These engines are installed separately through their official npm/Python distributions, which retain their upstream license files. The course adapters and sample scene in this skill are project-specific integration code.
