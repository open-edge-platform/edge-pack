<!--hide_directive ```{eval-rst}
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
  <a class="icon_documentation" href="https://github.com/open-edge-platform/edge-pack/blob/main/README.md">
     README
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

Edge Pack is a set of modular platform software packages that add key functionalities to
your operating system, including graphics, media, edge AI, networking, and manageability.
Prepared for different technical domains, Edge Pack offers the right setup for a particular
system or workload.

There are several ways of deploying Edge Pack. The [Get Started guide](./get-started.md) will
enable you to select the one that fits best and give you ready-made commands to proceed.

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

| Profile         | Name                    | Description                                   |
|-----------------|-------------------------|-----------------------------------------------|
| `base-standard` | Intel Edge Base Profile | Validated core Intel graphics/media packages, including the platform-enablement Dynamic Kernel Module Support driver, for Ubuntu LTS |

**Add-on Profiles**

| Profile | Name | Description |
|-----------------|---------------|---------------------------------------------------------|
| `ffmpeg`        | FFmpeg        | FFmpeg multimedia framework with Intel GPU support      |
| `gstreamer`     | GStreamer     | GStreamer multimedia framework with Intel GPU support   |
| `npu`           | NPU           | Enables Intel's Neural Processing Unit (NPU) technology on edge platforms |
| `manageability` | Manageability | Enables Intel® vPro® manageability on edge platforms    |



Currently, Edge Pack supports Ubuntu Desktop LTS 24.04.5 (Noble) and LTS 26.04.1 (Resolute),
deployed on Intel® Core™ Ultra Series 3 (formerly codenamed as Panther Lake) and
Intel® Core™ Series 3.
See [system requirements](./get-started/system-requirements.md) for more details.


<!--hide_directive
:::{toctree}
:hidden:

Get Started <./get-started.md>
Release Notes <./release-notes.md>
:::
hide_directive-->
