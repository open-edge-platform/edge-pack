"use strict";

let lastHeight = 0;

function resizeInstallerFrame() {
  const frame = document.getElementById("installerFrame");
  if (!frame?.contentWindow) return;
  try {
    const frameDocument = frame.contentDocument || frame.contentWindow.document;
    const content = frameDocument.querySelector("main.app-wrap");
    if (!content) return;
    const height = Math.min(2400, content.offsetTop + content.scrollHeight);
    if (Math.abs(height - lastHeight) > 10) {
      frame.style.height = `${height + 20}px`;
      lastHeight = height;
    }
  } catch (error) {
    console.debug("Using fixed installer frame height", error);
    frame.style.height = "900px";
  }
}

function observeInstallerFrame() {
  const frame = document.getElementById("installerFrame");
  if (!frame) return;
  const observeContent = () => {
    resizeInstallerFrame();
    try {
      new ResizeObserver(resizeInstallerFrame).observe(frame.contentDocument.body);
      new MutationObserver(resizeInstallerFrame).observe(frame.contentDocument.body, {
        childList: true,
        subtree: true,
        attributes: true,
      });
    } catch (error) {
      console.debug("Installer frame observers unavailable", error);
    }
  };
  frame.addEventListener("load", observeContent);
  if (
    frame.contentDocument?.readyState === "complete"
    && frame.contentDocument.location.href !== "about:blank"
  ) {
    observeContent();
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", observeInstallerFrame, { once: true });
} else {
  observeInstallerFrame();
}

window.addEventListener("resize", resizeInstallerFrame);