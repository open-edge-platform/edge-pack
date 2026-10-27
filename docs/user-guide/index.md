<!--hide_directive```{eval-rst}
.. meta::
   :description: Use Edge Packs from Open Edge Platform to enable the full potential of Intel hardware at the edge.
   :keywords: Linux, drivers, system enablement, Linux config for Intel hardware
``` hide_directive-->

# Edge Pack

<!--hide_directive
::::{container} component_header_row
<div class="component_card_widget">
  <a class="icon_github" href="https://github.com/open-edge-platform/edge-pack">
     GitHub project
  </a>
</div>
hide_directive-->
> [!NOTE]
> Edge Pack is currently available as a technical preview for evaluation purposes, we do not
> recommend this early version for use in production environments.
<!--hide_directive
::::
hide_directive-->

Enable the full potential of Intel hardware on Linux for edge use cases.

Edge Pack, installed via APT, constitutes a lean enablement layer that quickly and easily
extends Linux OS with Intel-validated software and drivers that unlock specific Intel platform
capabilities, such as:

- graphics and media acceleration
- GPU compute runtime support
- Neural Processing Unit support (NPU)
- platform manageability
- real-time kernel support
- camera (IPU) enablement



<!--hide_directive ::::{grid} 1 2 2 4 hide_directive-->
<!--hide_directive :::{grid-item-card} hide_directive--> Base profiles

The validated core package set for a given platform and OS, forming the required
foundation before any add-on can be installed.
<!--hide_directive ::: hide_directive-->
<!--hide_directive :::{grid-item-card} hide_directive--> Add-on profiles

Optional package groups layered on top of a base profile, each enabling a specific
Intel platform capability.
<!--hide_directive ::: hide_directive-->
<!--hide_directive :::{grid-item-card} hide_directive--> Platform and OS validation

Every profile and add-on is validated against specific hardware models, Ubuntu
versions, and kernels, so only tested combinations are offered.
<!--hide_directive ::: hide_directive-->
<!--hide_directive :::{grid-item-card} hide_directive--> Compatibility checks

Conflicting or unsupported combinations are flagged before anything is installed.
<!--hide_directive ::: hide_directive-->
<!--hide_directive :::: hide_directive-->



**Base Profiles**

| Profile | Name | Description |
|---|---|---|
| `base-standard` | Intel Edge Base Profile | Validated core Intel graphics/media packages, including the platform-enablement DKMS driver, for Ubuntu LTS |

**Add-on Profiles**

| Profile | Name | Description |
|-----------------|---------------|---------------------------------------------------------|
| `ffmpeg`        | FFmpeg        | FFmpeg multimedia framework with Intel GPU support      |
| `gstreamer`     | GStreamer     | GStreamer multimedia framework with Intel GPU support   |
| `npu`           | NPU           | Enables Intel's Neural Processing Unit (NPU) technology on Edge platforms |
| `manageability` | Manageability | Enables Intel's vPRO Manageability on Edge platforms    |



Currently, Edge Pack supports Ubuntu Desktop LTS 24.04.5 (Noble) and LTS 26.04.1 (Resolute),
deployed on Intel® Core™ Ultra Series 3 (formerly codenamed as Panther Lake) and
Intel® Core™ Series 3.
See (System Requirements)[./get-started/system-requirements.md] for more details.


<!--hide_directive
:::{toctree}
:hidden:

Get Started <./get-started.md>
Release Notes <./release-notes.md>
:::
hide_directive-->