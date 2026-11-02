"use strict";

let config;
const configUrl = new URL("config.json", document.currentScript.src);
const state = {
  os: "",
  method: "",
  baseProfile: "",
  addons: [],
};

const element = (id) => document.getElementById(id);

function valuesFor(key) {
  return [...new Set(config.installations.map((installation) => installation.selection[key]))];
}

function matchesCore(installation) {
  const selection = installation.selection;
  return selection.os === state.os
    && selection.baseProfile === state.baseProfile;
}

function currentInstallation() {
  const addons = [...state.addons].sort();
  return config.installations.find((installation) => {
    if (!matchesCore(installation)) return false;
    return [...installation.selection.addons].sort().join(",") === addons.join(",");
  });
}

function availableBaseProfiles() {
  return new Set(config.installations
    .filter((installation) => installation.selection.os === state.os)
    .map((installation) => installation.selection.baseProfile));
}

function availableAddons() {
  const available = new Set();
  config.installations.filter(matchesCore).forEach((installation) => {
    installation.selection.addons.forEach((addon) => available.add(addon));
  });
  return available;
}

function choice(option, group, type, checked, disabled = false) {
  const label = document.createElement("label");
  label.className = "choice spark-button spark-button-size-l spark-button-primary";
  const input = document.createElement("input");
  input.type = type;
  input.name = group;
  input.value = option.value;
  input.checked = checked;
  input.disabled = disabled;
  const text = document.createElement("span");
  const title = document.createElement("strong");
  title.textContent = option.label;
  text.appendChild(title);
  if (option.description) {
    const description = document.createElement("small");
    description.textContent = option.description;
    text.appendChild(description);
  }
  label.append(input, text);
  return label;
}

function renderSingle(hostId, options, key, disabledValues = new Set()) {
  const host = element(hostId);
  host.replaceChildren();
  options.forEach((option) => {
    const item = choice(option, key, "radio", state[key] === option.value, disabledValues.has(option.value));
    item.querySelector("input").addEventListener("change", () => {
      state[key] = option.value;
      if (key === "os") repairBaseProfile();
      if (key === "baseProfile" || key === "os") repairAddons();
      render({ name: key, value: option.value });
    });
    host.appendChild(item);
  });
}

function renderAddons() {
  const host = element("addon-options");
  const available = availableAddons();
  host.replaceChildren();
  config.addons.forEach((addon) => {
    const item = choice(addon, "addons", "checkbox", state.addons.includes(addon.value), !available.has(addon.value));
    item.querySelector("input").addEventListener("change", (event) => {
      if (event.target.checked) state.addons.push(addon.value);
      else state.addons = state.addons.filter((value) => value !== addon.value);
      render({ name: "addons", value: addon.value });
    });
    host.appendChild(item);
  });
}

function repairBaseProfile() {
  const available = availableBaseProfiles();
  if (!available.has(state.baseProfile)) state.baseProfile = [...available][0] || "";
}

function repairAddons() {
  const available = availableAddons();
  state.addons = state.addons.filter((addon) => available.has(addon));
}

function writeUrl() {
  const query = new URLSearchParams({
    os: state.os,
    method: state.method,
    profile: state.baseProfile,
  });
  if (state.addons.length) query.set("addons", [...state.addons].sort().join(","));
  history.replaceState({}, "", `${location.pathname}?${query}`);
}

function renderResult() {
  const installation = currentInstallation();
  element("result").hidden = !installation;
  if (!installation) return;
  const method = config.methods.find((entry) => entry.value === state.method);
  const os = config.operatingSystems.find((entry) => entry.value === state.os);
  element("result-title").textContent = method.label;
  element("command-output").textContent = installation.commands[state.method];
  element("package-output").textContent = installation.packages.join(", ");
  element("requirements").textContent = `${os.label} requires Ubuntu kernel ${os.minKernelVersion} or later.`;
}

function commandBox(command) {
  const box = document.createElement("div");
  box.className = "code-box st-code-snippet-multi-line";
  const copy = document.createElement("button");
  copy.className = "spark-button spark-button-size-s spark-button-primary code-copy";
  copy.type = "button";
  copy.textContent = "Copy";
  copy.addEventListener("click", () => copyText(command, copy));
  const output = document.createElement("pre");
  output.className = "st-code-snippet-content";
  output.textContent = command;
  box.append(copy, output);
  return box;
}

function renderHeadlessSupport() {
  const support = config.headlessSupport;
  element("headless-description").textContent = support.description;
  const steps = element("headless-steps");
  steps.replaceChildren();
  support.steps.forEach((step) => {
    const item = document.createElement("li");
    const title = document.createElement("strong");
    title.textContent = step.title;
    const description = document.createElement("p");
    description.className = "notice";
    description.textContent = step.description;
    item.append(title, description, commandBox(step.command));
    steps.appendChild(item);
  });

  const verification = support.verification;
  const verificationHost = element("headless-verification");
  const verificationTitle = document.createElement("strong");
  verificationTitle.textContent = verification.title;
  const verificationDescription = document.createElement("p");
  verificationDescription.className = "notice";
  verificationDescription.textContent = verification.description;
  verificationHost.replaceChildren(
    verificationTitle,
    verificationDescription,
    commandBox(verification.command),
  );
  element("headless-guide").href = new URL(support.guideUrl, window.parent.location.href);
}

function render(focusTarget) {
  const availableBases = availableBaseProfiles();
  renderSingle("os-options", config.operatingSystems, "os");
  renderSingle("method-options", config.methods, "method");
  renderSingle(
    "base-options",
    config.baseProfiles,
    "baseProfile",
    new Set(config.baseProfiles.map((profile) => profile.value).filter((value) => !availableBases.has(value))),
  );
  renderAddons();
  renderResult();
  writeUrl();
  if (focusTarget) {
    const replacement = [...document.querySelectorAll(`input[name="${focusTarget.name}"]`)]
      .find((input) => input.value === focusTarget.value);
    replacement?.focus();
  }
}

function initialiseState() {
  const query = new URLSearchParams(location.search);
  state.os = query.get("os") || valuesFor("os")[0];
  state.method = query.get("method") || config.defaultMethod;
  state.baseProfile = query.get("profile") || valuesFor("baseProfile")[0];
  state.addons = (query.get("addons") || "").split(",").filter(Boolean);
  if (!valuesFor("os").includes(state.os)) state.os = valuesFor("os")[0];
  if (!config.methods.some((method) => method.value === state.method)) state.method = config.defaultMethod;
  repairBaseProfile();
  repairAddons();
}

function copyFallback(text) {
  const textArea = document.createElement("textarea");
  textArea.value = text;
  textArea.style.position = "fixed";
  textArea.style.opacity = "0";
  document.body.appendChild(textArea);
  textArea.select();
  const copied = document.execCommand("copy");
  textArea.remove();
  if (!copied) throw new Error("Copy command was rejected");
}

async function copyText(text, button) {
  try {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
    else copyFallback(text);
    button.textContent = "Copied";
  } catch (error) {
    console.error("Copy failed", error);
    button.textContent = "Select text";
  }
  window.setTimeout(() => { button.textContent = "Copy"; }, 1200);
}

function copyCommand() {
  return copyText(element("command-output").textContent, element("copy-command"));
}

function toggleHeadlessSupport() {
  const button = element("toggle-headless");
  const panel = element("headless-panel");
  const expanded = button.getAttribute("aria-expanded") === "true";
  button.setAttribute("aria-expanded", String(!expanded));
  button.textContent = expanded ? "Headless Support" : "Hide Headless Support";
  panel.hidden = expanded;
}

async function init() {
  try {
    const response = await fetch(configUrl);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    config = await response.json();
    element("page-title").textContent = config.title;
    initialiseState();
    element("selector-form").hidden = false;
    element("copy-command").addEventListener("click", copyCommand);
    element("toggle-headless").addEventListener("click", toggleHeadlessSupport);
    renderHeadlessSupport();
    render();
  } catch (error) {
    element("error").hidden = false;
    element("error").textContent = `Unable to load installer configuration: ${error.message}`;
  }
}

document.addEventListener("DOMContentLoaded", init);