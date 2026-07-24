export function replaceRegion(root, selector, replacement) {
  const current = root.querySelector(selector);
  if (current) {
    current.replaceWith(replacement);
  }
}

export function animateRegion(element) {
  if (!element) {
    return;
  }
  element.classList.remove("region-update");
  void element.offsetWidth;
  element.classList.add("region-update");
}

export function activateMotion(root) {
  root.querySelectorAll(".vital-fill").forEach((fill) => fill.classList.add("is-filled"));
}

export function node(tag, className = "", content = null) {
  const element = document.createElement(tag);
  if (className) {
    element.className = className;
  }
  if (Array.isArray(content)) {
    content.forEach((item) => item != null && element.append(item));
  } else if (content instanceof Node) {
    element.append(content);
  } else if (content != null) {
    element.textContent = String(content);
  }
  return element;
}

export function controlButton(label, action, value, active) {
  const button = node("button", "control-button", label);
  button.type = "button";
  button.dataset.action = action;
  button.dataset.value = value;
  button.setAttribute("aria-pressed", String(active));
  return button;
}

export function renderFacts(facts, className) {
  return node(
    "div",
    className,
    facts.map((fact) => node("span", "", `${fact.label}: ${displayValue(fact.value)}`)),
  );
}

export function detailLine(label, value) {
  return node("p", "", [node("strong", "", label), document.createTextNode(value)]);
}

export function rawBlock(value) {
  return node("pre", "raw-event", JSON.stringify(value, null, 2));
}

export function names(values) {
  return values.length ? values.map((item) => item.name).join("、") : "无";
}

export function namedValues(values) {
  return values.length
    ? values.map((item) => `${item.name} ${formatNumber(item.value)}`).join("、")
    : "无";
}

export function effectNames(values) {
  return values.length
    ? values
        .map((item) => `${item.name}${item.stacks > 1 ? ` ×${item.stacks}` : ""} (${item.duration})`)
        .join("、")
    : "无";
}

export function cooldownNames(values) {
  return values.length
    ? values.map((item) => `${item.name} ${item.turns} 回合`).join("、")
    : "无";
}

export function renderEffectChips(effects) {
  if (!effects.length) {
    return node("p", "effect-empty", "当前无持续状态");
  }
  return node(
    "div",
    "effect-chips",
    effects.slice(0, 6).map((effect) => {
      const stacks = effect.stacks > 1 ? ` ×${effect.stacks}` : "";
      return node(
        "span",
        `effect-chip ${effect.polarity || "neutral"}`,
        `${effect.name}${stacks}`,
      );
    }),
  );
}

export function fraction(value) {
  if (value?.current == null || value?.maximum == null) {
    return "无";
  }
  return `${formatNumber(value.current)}/${formatNumber(value.maximum)}`;
}

export function displayValue(value) {
  if (Array.isArray(value)) {
    return value.length ? value.map(displayValue).join("、") : "无";
  }
  if (value && typeof value === "object") {
    return Object.entries(value)
      .map(([key, item]) => `${key}=${displayValue(item)}`)
      .join("、");
  }
  if (typeof value === "number") {
    return formatNumber(value);
  }
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  return value == null || value === "" ? "无" : String(value);
}

export function percentage(current, maximum) {
  const max = Number(maximum || 0);
  if (max <= 0) {
    return 0;
  }
  return Math.max(0, Math.min(100, Number(current || 0) / max * 100));
}

export function formatNumber(value) {
  const number = Number(value || 0);
  return Number.isInteger(number)
    ? String(number)
    : number.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

export function formatTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

export function durationText(start, finish) {
  const milliseconds = new Date(finish).getTime() - new Date(start).getTime();
  if (!Number.isFinite(milliseconds) || milliseconds < 0) {
    return "时长未知";
  }
  if (milliseconds === 0) {
    return "";
  }
  const seconds = milliseconds / 1000;
  return seconds < 60
    ? `用时 ${formatNumber(seconds)} 秒`
    : `用时 ${formatNumber(seconds / 60)} 分钟`;
}

export function outcomeTone(value) {
  const text = String(value || "");
  if (/胜|完成|成功/.test(text)) {
    return "victory";
  }
  if (/败|失败|覆灭/.test(text)) {
    return "defeat";
  }
  return "neutral";
}
