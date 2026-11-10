# OpenAL Soft source and license

openQ4 macOS packages include the dynamically linked [OpenAL Soft](https://openal-soft.org/) runtime, version 1.25.2. OpenAL Soft is distributed under the GNU Library General Public License, version 2 or (at your option) any later version; see `COPYING` in this directory. Notices for the incorporated PFFFT, fmt, and Microsoft GSL components are provided as `LICENSE-pffft`, `LICENSE-fmt`, and `LICENSE-gsl`.

The corresponding source archive is bundled with each macOS package as `openal-soft-1.25.2.tar.gz`. Its canonical upstream URL is:

`https://github.com/kcat/openal-soft/archive/refs/tags/1.25.2.tar.gz`

Expected SHA-256:

`fb27e5839aa11f0e5b9d33756965291fad5d6909ab928ea1f796f4a1a6877894`

The exact macOS build recipe is maintained in [`tools/build/prepare_macos_openal_soft.sh`](../../../tools/build/prepare_macos_openal_soft.sh).
