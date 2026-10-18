# Third-Party Model Licenses

This folder contains 3D model files converted from third-party CAD projects.
The models are distributed under their original licenses as noted below.

## Positron 3D (CC BY-SA 4.0)

The following model is derived from Positron 3D CAD files, licensed under the
**Creative Commons Attribution-ShareAlike 4.0 International** license.
See [LICENSE-CC-BY-SA-4.0.txt](LICENSE-CC-BY-SA-4.0.txt).

- `Positron_v3.2.2.glb`

Copyright (c) Positron 3D
Source: https://github.com/Positron3D/Positron

## Millennium Machines Milo V2 (GPL-3.0)

The following model is derived from Millennium Machines Milo V2.0 CAD files,
licensed under the **GNU General Public License v3.0**.
See [LICENSE-GPL-3.0.txt](LICENSE-GPL-3.0.txt).

- `Milo_V2.RC3.glb`

Copyright (c) Millennium Machines
Source: https://github.com/MillenniumMachines/Milo-V2.0

## Doron Velta (GPL-3.0)

The following model is derived from Doron Velta CAD files, licensed under the
**GNU General Public License v3.0**.
See [LICENSE-GPL-3.0.txt](LICENSE-GPL-3.0.txt).

- `Doron_Velta_R2.glb`

Copyright (c) Rogerio Goncalves
Source: https://github.com/rogerlz/Doron-Velta

## Voron Design (GPL-3.0)

The following models are derived from Voron Design CAD files, licensed under
the **GNU General Public License v3.0**.
See [LICENSE-GPL-3.0.txt](LICENSE-GPL-3.0.txt).

- `Voron_2.4r2.glb` — Source: https://github.com/VoronDesign/Voron-2
- `Voron_0.2r1.glb` — Source: https://github.com/VoronDesign/Voron-0
- `Voron_Switchwire.glb` — Source: https://github.com/VoronDesign/Voron-Switchwire
- `Voron_Cascade_v20260504.glb` — Source: https://github.com/VoronDesign/Voron-Cascade

Copyright (c) Voron Design

`Voron_2.4r2.glb` also includes the ClickyClacky Door from tanaes's Voron
mods, licensed under the **GNU General Public License v3.0**.
Source: https://github.com/tanaes/whopping_Voron_mods/tree/main/clickyclacky_door

## Opulo LumenPnP (CERN-OHL-W v2)

The following models are derived from the Opulo LumenPnP hardware design
files, licensed under the **CERN Open Hardware Licence Version 2 - Weakly
Reciprocal**.
See [LICENSE-CERN-OHL-W-2.0.txt](LICENSE-CERN-OHL-W-2.0.txt).

- `LumenPnP_v4.1.0.glb`, from release v4.1.0 (`pnp/cad/assembly.FCStd`)
- `LumenPnP_v4.2.0.glb`, from release v4.2.0 (`src/assembly.FCStd` and the
  files it links under `src/`)

Copyright (c) Opulo
Source: https://github.com/opulo-inc/lumenpnp (releases v4.1.0 and v4.2.0)

Modified 2026-10-14 (v4.1.0) and 2026-10-17 (v4.2.0): converted from the
FreeCAD assembly to a Draco-compressed GLB for viewing. Parts are tessellated
to meshes, and part colors and default visibility come from the CADScope
model spec. Geometry and assembly structure are otherwise unchanged.

Opulo's license notice, reproduced as it requires:

```text
# Opulo LumenPnP License and Copyright Notices

LumenPnP is (c) by Opulo

This notice must be included in any distributions of this project or derivative works.

Because this project consists of many types of source, individual parts of the project are made available under different licenses.

1. The hardware designs located at `./pnp/cad` and `./pnp/pcb` are available under the CERN-OHL-W v2 license. Full text is available at https://cern.ch/cern-ohl.

2. The software located at `./.github/workflows` is available under Mozilla MPL v2.0. Full text is available at https://www.mozilla.org/en-US/MPL/2.0/.

3. The KiCAD libraries located at `./lib/kicad/` are available under Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0). Full text available at https://creativecommons.org/licenses/by-sa/4.0/

4. Opulo's logo, branding, and other media is used throughout this project. This is Copyright (c) Opulo and all rights are reserved. You may not distribute derivative works or products bearing the Opulo logo, icon, or other relevant mark. Derivative works should remove Opulo branding.

5. The name `Opulo` and `LumenPnP` are trademarked, and only to be used by Opulo. Any derivative works should remove both marks.
```

In the v4.2.0 release these hardware designs are under `src/`.
