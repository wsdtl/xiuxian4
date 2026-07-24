import {
  FILTER_OPTIONS,
  renderCompactTimeline,
  renderDetailedTimeline,
  renderDetailedTimelineEntries,
  renderRawDataAccess,
} from "./timeline.js?v=16";
import {
  activateMotion,
  animateRegion,
  controlButton,
  cooldownNames,
  detailLine,
  durationText,
  effectNames,
  formatNumber,
  formatTime,
  namedValues,
  names,
  node,
  outcomeTone,
  percentage,
  rawBlock,
  renderEffectChips,
  replaceRegion,
} from "./ui.js?v=16";

const root = document.querySelector("#reportRoot");

const MODE_OPTIONS = [
  { id: "compact", label: "战斗记录" },
  { id: "detail", label: "全部事件" },
];

const state = {
  report: null,
  segmentIndex: 0,
  mode: "compact",
  filter: "all",
  snapshot: "after",
  participantExpanded: !window.matchMedia("(max-width: 640px)").matches,
};

root.addEventListener("click", handleControlClick);
root.addEventListener("change", handleControlChange);

main().catch((error) => {
  renderError(error instanceof Error ? error.message : String(error));
});

async function main() {
  const report = await loadReport();
  if (report.schema !== "game.battle_report.presentation" || report.version !== 1) {
    renderUnsupportedReport(report);
    return;
  }
  state.report = report;
  document.title = `${report.game_name || "万象行纪"} · ${report.summary.title}`;
  renderReport();
}

async function loadReport() {
  const embedded = document.querySelector("#battleReportPreviewData");
  if (embedded) {
    return JSON.parse(embedded.textContent || "null");
  }
  const shareId = reportShareId();
  if (!shareId) {
    throw new Error("战报分享地址无效。");
  }
  const path = window.location.pathname.replace(/\/$/, "");
  const response = await fetch(`${path}/data`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail || "战报读取失败。");
  }
  return response.json();
}

function reportShareId() {
  const match = window.location.pathname.match(/^\/battle\/([^/]+)\/?$/);
  return match ? decodeURIComponent(match[1]) : "";
}

function handleControlClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button || !root.contains(button) || !state.report) {
    return;
  }
  const action = button.dataset.action;
  const value = button.dataset.value;
  if (action === "mode" && MODE_OPTIONS.some((item) => item.id === value)) {
    if (state.mode !== value) {
      state.mode = value;
      updateModeView();
    }
    return;
  }
  if (action === "segment") {
    selectSegment(Number(value));
    return;
  }
  if (action === "segment-step") {
    selectSegment(state.segmentIndex + Number(value));
    return;
  }
  if (action === "snapshot" && ["before", "after"].includes(value)) {
    if (state.snapshot !== value) {
      state.snapshot = value;
      updateSnapshotView();
    }
    return;
  }
  if (action === "participant-disclosure") {
    state.participantExpanded = !state.participantExpanded;
    updateParticipantDisclosure();
    return;
  }
  if (action === "filter" && FILTER_OPTIONS.some((item) => item.id === value)) {
    if (state.filter !== value) {
      state.filter = value;
      updateFilterView();
    }
  }
}

function handleControlChange(event) {
  const select = event.target.closest('select[data-action="segment-select"]');
  if (!select || !root.contains(select) || !state.report) {
    return;
  }
  selectSegment(Number(select.value));
}

function selectSegment(index) {
  const segments = state.report.detail.segments;
  if (!Number.isInteger(index) || !segments[index] || state.segmentIndex === index) {
    return;
  }
  state.segmentIndex = index;
  state.filter = "all";
  updateSegmentView();
}

function updateModeView() {
  document.body.dataset.mode = state.mode;
  root.querySelectorAll('[data-action="mode"]').forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.value === state.mode));
  });
  animateRegion(root.querySelector(state.mode === "compact" ? ".compact-panel" : ".detail-panel"));
}

function updateSegmentView() {
  const segment = currentSegment();
  replaceRegion(root, ".segment-tabs", renderSegmentNavigation(state.report.detail.segments));
  replaceRegion(root, ".segment-overview", renderMatchup(segment));
  replaceRegion(root, ".report-body", renderReportBody(segment));
  replaceRegion(root, ".raw-report-details", renderRawDataAccess(segment));
  animateRegion(root.querySelector(".segment-overview"));
  animateRegion(root.querySelector(".report-body"));
  requestAnimationFrame(() => activateMotion(root));
}

function updateSnapshotView() {
  const segment = currentSegment();
  const before = segment.initial_participants;
  const after = segment.final_participants.length ? segment.final_participants : before;
  const participants = state.snapshot === "before" ? before : after;
  const disclosure = root.querySelector(".participant-disclosure");
  if (!disclosure) {
    return;
  }
  const label = disclosure.querySelector(".participant-disclosure-title span");
  if (label) {
    label.textContent = state.snapshot === "before" ? "战前" : "战后";
  }
  const snapshotSwitch = disclosure.querySelector(".snapshot-switch");
  if (snapshotSwitch) {
    snapshotSwitch.dataset.snapshot = state.snapshot;
    snapshotSwitch.querySelectorAll('[data-action="snapshot"]').forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.value === state.snapshot));
    });
  }
  const participantStack = node(
    "div",
    "participant-stack region-update",
    participants.map((participant, index) => renderParticipantSummary(participant, index)),
  );
  replaceRegion(root, ".participant-stack", participantStack);
  requestAnimationFrame(() => activateMotion(root));
}

function updateParticipantDisclosure() {
  const disclosure = root.querySelector(".participant-disclosure");
  const button = disclosure?.querySelector(".participant-disclosure-title");
  const content = disclosure?.querySelector(".participant-disclosure-content");
  if (!disclosure || !button || !content) {
    return;
  }
  disclosure.dataset.expanded = String(state.participantExpanded);
  button.setAttribute("aria-expanded", String(state.participantExpanded));
  content.setAttribute("aria-hidden", String(!state.participantExpanded));
  content.toggleAttribute("inert", !state.participantExpanded);
  if (state.participantExpanded) {
    animateRegion(content);
  }
}

function updateFilterView() {
  root.querySelectorAll('[data-action="filter"]').forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.value === state.filter));
  });
  replaceRegion(
    root,
    ".detailed-timeline",
    renderDetailedTimelineEntries(currentSegment(), state.filter),
  );
}

function currentSegment() {
  return state.report.detail.segments[state.segmentIndex];
}

function renderReport() {
  const report = state.report;
  document.body.dataset.mode = state.mode;
  root.replaceChildren();
  root.className = "report-shell report-ready";

  if (!report.detail.available) {
    root.append(renderSummaryHeader(report));
    root.append(
      node("section", "notice", [
        node("p", "section-kicker", "公开档案"),
        node("h2", "", "完整战报已归档"),
        node("p", "", report.detail.retention_notice),
      ]),
    );
    return;
  }

  const segments = report.detail.segments;
  state.segmentIndex = Math.min(state.segmentIndex, Math.max(segments.length - 1, 0));
  const segment = segments[state.segmentIndex];
  root.append(renderSummaryHeader(report));
  if (segments.length > 1) {
    root.append(renderSegmentNavigation(segments));
  }
  root.append(renderMatchup(segment));
  root.append(renderViewToolbar());
  root.append(renderReportBody(segment));
  root.append(renderRawDataAccess(segment));
  requestAnimationFrame(() => activateMotion(root));
}

function renderSummaryHeader(report) {
  const header = node("header", "report-header");
  header.append(
    node("div", "brand-line", [
      node("span", "brand-name", report.game_name || "万象行纪"),
      node("span", "brand-divider", "公开战报"),
    ]),
  );
  header.append(
    node("div", "title-row", [
      node("div", "title-copy", [
        node("h1", "", report.summary.title),
        node(
          "p",
          "report-time",
          `${formatTime(report.started_at)} 至 ${formatTime(report.finished_at)}`,
        ),
      ]),
      node("div", `result-stamp ${outcomeTone(report.summary.outcome)}`, [
        node("span", "", "结算"),
        node("strong", "", report.summary.outcome),
      ]),
    ]),
  );
  const settlementLines = meaningfulLines(report.summary.lines);
  if (!settlementLines.length) {
    return header;
  }
  header.append(
    node(
      "ul",
      "summary-lines",
      settlementLines.slice(0, 2).map((line) => node("li", "", line)),
    ),
  );
  if (settlementLines.length > 2) {
    const more = node("details", "summary-lines-more");
    more.append(node("summary", "", "更多结算"));
    more.append(
      node(
        "ul",
        "summary-more-list",
        settlementLines.slice(2).map((line) => node("li", "", line)),
      ),
    );
    header.append(more);
  }
  return header;
}

function renderMatchup(segment) {
  const participants = segment.final_participants.length
    ? segment.final_participants
    : segment.initial_participants;
  const teams = groupByTeam(participants);
  if (!teams.length) {
    return node("div", "matchup segment-overview empty", "本片段没有参与者快照。");
  }
  const first = renderTeamSummary(teams[0], "我方");
  if (teams.length === 1) {
    return node("section", "matchup segment-overview single", first);
  }
  const last = renderTeamSummary(teams[teams.length - 1], "对方", true);
  const middleTeams = Math.max(0, teams.length - 2);
  const duration = durationText(segment.started_at, segment.finished_at);
  return node("section", "matchup segment-overview", [
    first,
    node("div", "versus", [
      node("strong", "", segment.outcome),
      duration ? node("span", "", duration) : null,
      middleTeams ? node("small", "", `另有 ${middleTeams} 方`) : null,
    ]),
    last,
  ]);
}

function renderTeamSummary(team, fallback, reverse = false) {
  const participantNames = team.participants.map((item) => item.label).join("、");
  return node("div", `combat-side${reverse ? " enemy" : ""}`, [
    node("div", "side-name", [
      node("span", "", teamDisplayLabel(team.id, fallback)),
      node("strong", "", participantNames || fallback),
    ]),
  ]);
}

function renderVitalBar(label, vital, type, reverse = false) {
  const ratio = percentage(vital.current, vital.maximum);
  const values = node(
    "span",
    "bar-value",
    `${formatNumber(vital.current)} / ${formatNumber(vital.maximum)}`,
  );
  const title = node("span", "bar-label", label);
  const bar = node("div", `vital-bar ${type}`);
  const fill = node("span", "vital-fill");
  fill.style.setProperty("--fill", `${ratio}%`);
  bar.append(fill);
  return node(
    "div",
    `bar-row${reverse ? " reverse" : ""}`,
    reverse ? [values, bar, title] : [title, bar, values],
  );
}

function renderSegmentNavigation(segments) {
  const many = segments.length > 6;
  const select = node(
    "select",
    "segment-select",
    segments.map((segment, index) => {
      const title = segment.title || `片段 ${index + 1}`;
      const option = node(
        "option",
        "",
        `${String(index + 1).padStart(2, "0")}/${segments.length} · ${title}`,
      );
      option.value = String(index);
      option.selected = index === state.segmentIndex;
      return option;
    }),
  );
  select.dataset.action = "segment-select";
  select.setAttribute("aria-label", "选择战斗片段");
  return node("nav", `segment-tabs${many ? " many-segments" : ""}`, [
    node("span", "segment-label", [
      document.createTextNode("战斗片段"),
      node("small", "segment-count", `${state.segmentIndex + 1} / ${segments.length}`),
    ]),
    node("div", "segment-navigation", [
      segmentStepButton("上一片段", -1, state.segmentIndex === 0),
      node("label", "segment-picker", [select]),
      node(
        "div",
        "segment-scroll",
        segments.map((segment, index) =>
          controlButton(
            segment.title || `片段 ${index + 1}`,
            "segment",
            String(index),
            index === state.segmentIndex,
          ),
        ),
      ),
      segmentStepButton("下一片段", 1, state.segmentIndex === segments.length - 1),
    ]),
  ]);
}

function segmentStepButton(label, direction, disabled) {
  const button = node("button", "segment-step", direction < 0 ? "‹" : "›");
  button.type = "button";
  button.dataset.action = "segment-step";
  button.dataset.value = String(direction);
  button.disabled = disabled;
  button.setAttribute("aria-label", label);
  button.title = label;
  return button;
}

function renderViewToolbar() {
  return node("section", "view-toolbar", [
    node(
      "div",
      "mode-switch",
      MODE_OPTIONS.map((option) =>
        controlButton(option.label, "mode", option.id, state.mode === option.id),
      ),
    ),
  ]);
}

function renderReportBody(segment) {
  return node("section", "report-body view-panel", [
    renderSummaryPanel(segment),
    node("section", "timeline-panel", [
      renderCompactTimeline(segment),
      renderDetailedTimeline(segment, state.filter),
    ]),
  ]);
}

function renderSummaryPanel(segment) {
  const before = segment.initial_participants;
  const after = segment.final_participants.length ? segment.final_participants : before;
  const participants = state.snapshot === "before" ? before : after;
  const snapshotSwitch = node("div", "snapshot-switch", [
    controlButton("战前", "snapshot", "before", state.snapshot === "before"),
    controlButton("战后", "snapshot", "after", state.snapshot === "after"),
  ]);
  snapshotSwitch.dataset.snapshot = state.snapshot;
  const disclosureButton = node("button", "participant-disclosure-title", [
    node("strong", "", "参与者状态"),
    node("span", "", state.snapshot === "before" ? "战前" : "战后"),
  ]);
  disclosureButton.type = "button";
  disclosureButton.dataset.action = "participant-disclosure";
  disclosureButton.setAttribute("aria-controls", "participantDetails");
  disclosureButton.setAttribute("aria-expanded", String(state.participantExpanded));
  const disclosureContent = node("div", "participant-disclosure-content", [
    node("div", "participant-disclosure-inner", [
      node("div", "panel-heading", [snapshotSwitch]),
      node(
        "div",
        "participant-stack",
        participants.map((participant, index) => renderParticipantSummary(participant, index)),
      ),
    ]),
  ]);
  disclosureContent.id = "participantDetails";
  disclosureContent.setAttribute("aria-hidden", String(!state.participantExpanded));
  disclosureContent.toggleAttribute("inert", !state.participantExpanded);
  const disclosure = node("section", "participant-disclosure", [
    disclosureButton,
    disclosureContent,
  ]);
  disclosure.dataset.expanded = String(state.participantExpanded);
  return node("aside", "summary-panel", disclosure);
}

function renderParticipantSummary(participant, index) {
  const temporaryEffects = participant.effects.filter((effect) => effect.duration !== "永久");
  const permanentEffects = participant.effects.filter((effect) => effect.duration === "永久");
  return node("article", "participant-summary", [
    node("div", "participant-heading", [
      node("span", "participant-index", String(index + 1).padStart(2, "0")),
      node("div", "", [node("strong", "", participant.label)]),
    ]),
    renderVitalBar("血气", participant.health, "health"),
    renderVitalBar("灵力", participant.spirit, "spirit"),
    renderEffectGroup("当前状态", temporaryEffects),
    renderParticipantRecord(participant, permanentEffects),
  ]);
}

function renderEffectGroup(label, effects) {
  return node("section", "participant-effect-group", [
    node("h3", "participant-group-label", label),
    renderEffectChips(effects),
  ]);
}

function renderParticipantRecord(participant, permanentEffects) {
  const details = node("details", "participant-record");
  details.append(node("summary", "", "完整状态"));
  details.append(
    node("div", "detail-grid", [
      detailLine("属性", namedValues(participant.attributes)),
      detailLine("资源", namedValues(participant.resources)),
      detailLine("招式", names(participant.abilities)),
      detailLine("常驻", effectNames(permanentEffects)),
      detailLine("冷却", cooldownNames(participant.cooldowns)),
      detailLine("触发", names(participant.mechanisms.triggers)),
      detailLine("拦截", names(participant.mechanisms.interceptors)),
      detailLine("限制", names(participant.mechanisms.target_constraints)),
    ]),
  );
  return details;
}

function groupByTeam(participants) {
  const teams = new Map();
  participants.forEach((participant) => {
    const key = participant.team_id || "未分队";
    if (!teams.has(key)) {
      teams.set(key, []);
    }
    teams.get(key).push(participant);
  });
  return [...teams.entries()].map(([id, values]) => ({ id, participants: values }));
}

function teamDisplayLabel(value, fallback) {
  return { player: "我方", enemy: "对方" }[value] || fallback;
}

function meaningfulLines(lines) {
  return lines.filter((line) => {
    const values = String(line).match(/[+-]?\d+(?:\.\d+)?/g);
    return !values || values.some((value) => Number(value) !== 0);
  });
}

function renderUnsupportedReport(report) {
  root.replaceChildren(
    node("section", "error-state", [
      node("p", "section-kicker", "协议边界"),
      node("h1", "", "战报协议暂不支持"),
      node("p", "", `收到协议版本 ${String(report?.version ?? "未知")}。`),
      rawBlock(report),
    ]),
  );
}

function renderError(message) {
  root.replaceChildren(
    node("section", "error-state", [
      node("p", "section-kicker", "读取失败"),
      node("h1", "", "战报暂时无法打开"),
      node("p", "", message),
    ]),
  );
}
